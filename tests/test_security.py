import asyncio
import pytest
from backend.security import check_url, PublicProxy, resolve_public, UnsafeURL
from backend.main import csv_safe


@pytest.mark.parametrize('url', ['file:///etc/passwd','http://localhost','http://127.0.0.1','http://127.1','http://[::1]','http://169.254.169.254','http://10.0.0.1','http://192.168.1.1','http://user:pass@example.com','ftp://example.com','http://example.com:8000','http://[::ffff:127.0.0.1]'])
async def test_private_urls(url):
    with pytest.raises((UnsafeURL, OSError)):
        p=check_url(url)
        await resolve_public(p.hostname,p.port or 80)


async def test_dns_rebinding_mixed_answers_denied(monkeypatch):
    async def answers(*args,**kwargs):
        return [(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('127.0.0.1',443))]
    monkeypatch.setattr(asyncio.get_running_loop(),'getaddrinfo',answers)
    with pytest.raises(UnsafeURL):
        await resolve_public('public.example',443)


async def test_proxy_denies_local_connect_without_touching_target():
    calls=[]
    async def trap(reader,writer):
        calls.append(True);writer.close()
    server=await asyncio.start_server(trap,'127.0.0.1',0)
    try:
        async with PublicProxy() as proxy:
            port=int(proxy.url.rsplit(':',1)[1])
            reader,writer=await asyncio.open_connection('127.0.0.1',port)
            writer.write(b'CONNECT 127.0.0.1:80 HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n');await writer.drain()
            assert (await reader.read(100)).startswith(b'HTTP/1.1 403')
            writer.close();await writer.wait_closed()
        assert not calls
    finally:
        server.close();await server.wait_closed()


@pytest.mark.parametrize('value',['=SUM(A1)',' +cmd','-1','@IMPORT','\t=foo','\rhello'])
def test_csv_formulas(value):
    assert csv_safe(value).startswith("'")
