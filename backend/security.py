"""Resolve once, validate every answer and connect to the pinned public IP.

The browser uses this HTTP CONNECT proxy for HTTPS, redirects and subresources.
It is deliberately loopback-only and never follows a redirect itself.
"""
import asyncio
import ipaddress
import socket
import httpx
from contextlib import suppress
from urllib.parse import urlsplit


class UnsafeURL(ValueError):
    pass


def check_url(url: str):
    try:
        p = urlsplit(url)
        if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
            raise UnsafeURL('只允许不含凭据的 HTTP(S) 公网页面')
        if p.port not in (None, 80, 443) or len(url) > 2048:
            raise UnsafeURL('目标端口或链接不受支持')
        hostname = p.hostname.rstrip('.').lower()
        if hostname == 'localhost' or hostname.endswith(('.localhost', '.local', '.internal', '.home', '.lan')):
            raise UnsafeURL('禁止访问本机或内网地址')
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None
        if ip is not None and not public_ip(str(ip)):
            raise UnsafeURL('禁止访问非公网 IP')
        return p
    except ValueError as e:
        raise UnsafeURL('目标地址不安全或格式错误') from e


def public_ip(value: str):
    ip = ipaddress.ip_address(value)
    return ip.is_global and not ip.is_multicast and not getattr(ip, 'ipv4_mapped', None) and not getattr(ip, 'sixtofour', None) and not getattr(ip, 'teredo', None)


async def resolve_public(host: str, port: int):
    check_url(f'https://[{host}]:{port}' if ':' in host else f'https://{host}:{port}')
    infos = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(info[4][0] for info in infos))
    # Some desktop VPNs synthesize RFC 2544 fake-IP DNS answers. Never permit
    # those addresses; independently resolve via a fixed public HTTPS resolver.
    # Mixed private/public answers still fail closed, without a fallback.
    if addresses and all(ipaddress.ip_address(addr) in ipaddress.ip_network('198.18.0.0/15') for addr in addresses):
        async with httpx.AsyncClient(trust_env=False, timeout=10) as client:
            response = await client.get('https://1.1.1.1/dns-query', params={'name': host, 'type': 'A'}, headers={'Accept': 'application/dns-json'})
            response.raise_for_status()
            addresses = [answer['data'] for answer in response.json().get('Answer', []) if answer.get('type') == 1]
    if not addresses or any(not public_ip(addr) for addr in addresses):
        raise UnsafeURL('DNS 指向受保护的网络地址')
    return addresses[0]


class PublicProxy:
    def __init__(self):
        self.connections = set()
        self.jobs = set()
        self.denied_count = 0

    async def __aenter__(self):
        self.server = await asyncio.start_server(self.handle, '127.0.0.1', 0, limit=65536)
        self.url = f'http://127.0.0.1:{self.server.sockets[0].getsockname()[1]}'
        return self

    async def __aexit__(self, *_):
        self.server.close()
        await self.server.wait_closed()
        for writer in tuple(self.connections):
            writer.close()
        for job in tuple(self.jobs):
            job.cancel()
        await asyncio.gather(*tuple(self.jobs), return_exceptions=True)

    async def pipe(self, reader, writer):
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()

    async def handle(self, reader, writer):
        job = asyncio.current_task()
        self.jobs.add(job)
        self.connections.add(writer)
        upstream = None
        try:
            head = await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'), 10)
            first, *headers = head.decode('latin1').split('\r\n')
            method, target, _ = first.split(' ', 2)
            if method == 'CONNECT':
                p = check_url('https://' + target)
            elif method in ('GET', 'HEAD'):
                p = check_url(target)
            else:
                raise UnsafeURL('Method blocked')
            port = p.port or (443 if p.scheme == 'https' else 80)
            address = await resolve_public(p.hostname, port)
            remote_reader, upstream = await asyncio.wait_for(asyncio.open_connection(address, port), 15)
            self.connections.add(upstream)
            if method == 'CONNECT':
                writer.write(b'HTTP/1.1 200 Connection Established\r\n\r\n')
                await writer.drain()
            else:
                path = (p.path or '/') + ('?' + p.query if p.query else '')
                safe_headers = [h for h in headers if h and h.split(':', 1)[0].lower() not in ('connection', 'proxy-connection', 'host', 'proxy-authorization')]
                upstream.write((f'{method} {path} HTTP/1.1\r\nHost: {p.netloc}\r\n' + '\r\n'.join(safe_headers) + '\r\nConnection: close\r\n\r\n').encode('latin1'))
                await upstream.drain()
            tasks = [asyncio.create_task(self.pipe(reader, upstream)), asyncio.create_task(self.pipe(remote_reader, writer))]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=90)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except (Exception, asyncio.CancelledError) as error:
            if isinstance(error, UnsafeURL):
                self.denied_count += 1
            with suppress(Exception):
                writer.write(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
                await writer.drain()
        finally:
            for stream in (writer, upstream):
                if stream:
                    stream.close()
                    self.connections.discard(stream)
            self.jobs.discard(job)
