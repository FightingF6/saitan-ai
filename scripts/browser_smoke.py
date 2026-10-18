"""Real browser transport smoke test. No LLM, no production competition fixtures."""
import asyncio
import json
from pathlib import Path
from backend.agent import make_browser, capture_page, harden_downloads
from backend.security import PublicProxy


async def main():
    report=[]
    async with PublicProxy() as proxy:
        browser=make_browser(proxy)
        try:
            await browser.start()
            await harden_downloads(browser)
            for url in ['https://www.bing.com/search?q=大学生+人工智能+竞赛+报名', 'https://jsjds.blcu.edu.cn/']:
                try:
                    await browser.navigate_to(url)
                    await asyncio.sleep(2)
                    page=await capture_page(browser)
                    report.append({'requested_url':url,'url':page['url'],'title':page['title'],'text_length':len(page['text']),'excerpt':page['text'][:150],'captured_at':page['captured_at']})
                except Exception as e:
                    report.append({'requested_url':url,'error_type':type(e).__name__})
            image=await browser.take_screenshot(format='jpeg',quality=70)
            Path('docs/screenshots').mkdir(parents=True,exist_ok=True)
            Path('docs/screenshots/browser-smoke.jpg').write_bytes(image)
        finally:
            await browser.kill()
    Path('docs/browser-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True,indent=2))


if __name__=='__main__':asyncio.run(main())
