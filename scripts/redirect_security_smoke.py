"""Real-browser redirect protection test; localhost trap must receive zero hits."""
import asyncio
import json
from pathlib import Path
from urllib.parse import quote
from backend.agent import make_browser, harden_downloads
from backend.security import PublicProxy


async def main():
    hits=[]
    async def trap(reader,writer):
        hits.append(True)
        writer.write(b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\nFAIL')
        await writer.drain();writer.close()
    server=await asyncio.start_server(trap,'127.0.0.1',0)
    local=f'http://127.0.0.1:{server.sockets[0].getsockname()[1]}/'
    try:
        async with PublicProxy() as proxy:
            browser=make_browser(proxy)
            try:
                await browser.start();await harden_downloads(browser)
                # Do not call app check_url: test the browser's redirected network path.
                start=proxy.denied_count
                try:await browser.navigate_to('https://httpbin.org/redirect-to?url='+quote(local,safe=''))
                except Exception:pass
                blocked=proxy.denied_count>start
                report={'redirect_host':'httpbin.org','target':'loopback trap','proxy_blocked':blocked,'loopback_hits':len(hits),'pass':blocked and not hits}
            finally:await browser.kill()
    finally:server.close();await server.wait_closed()
    Path('docs/redirect-security-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    assert report['pass'], 'Redirect security could not be verified'


if __name__=='__main__':asyncio.run(main())
