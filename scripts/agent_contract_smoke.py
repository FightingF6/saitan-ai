"""TEST ONLY: scripted model outputs + real Browser Use browser and tool registry.

Does not call a provider, claim model compatibility, or write production results.
"""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch
from backend.config import settings
from backend.agent import execute
from backend.verification import verify

URL = 'https://jsjds.blcu.edu.cn/info/1042/2294.htm'


class ScriptedModel:
    model = 'contract-test-only'
    provider = 'openai'
    name = 'contract-test-only'
    _verified_api_keys = True

    def __init__(self):
        self.calls = 0

    async def ainvoke(self, messages, output_format=None, **kwargs):
        from browser_use.llm.views import ChatInvokeCompletion
        actions = [
            {'open_public_page': {'url': URL}},
            {'record_competition': {'candidate': {'name': '中国大学生计算机设计大赛', 'source_urls': [URL], 'evidence': [{'field': 'name', 'quote': '中国大学生计算机设计大赛', 'source_url': URL}]}}},
            {'done': {'text': 'TEST ONLY: real page and tool contract checked.', 'success': True}},
        ]
        action = actions[min(self.calls, len(actions)-1)]
        self.calls += 1
        result = output_format.model_validate({'evaluation_previous_goal':'contract test', 'memory':'test only', 'next_goal':'verify tool contract', 'action':[action]})
        return ChatInvokeCompletion(completion=result, usage=None)


async def main():
    events=[]
    records=[]
    async def emit(kind,message,payload):
        events.append({'type':kind,'message':message,'payload':payload})
    async def accept(candidate,pages):
        result=verify(candidate,pages,{'grade':'大一'})
        events.append({'type':'test_evidence_diagnostic','candidate':candidate.name,'pages':[{'url':url,'text_length':len(p['text']),'name_present':candidate.name in p['text'],'text_excerpt':p['text'][:100]} for url,p in pages.items()]})
        if result:records.append(result)
        return bool(result)
    config=settings.model_copy(update={'max_steps':5,'max_pages':5})
    with patch('backend.agent.create_llm',return_value=ScriptedModel()):
        async with asyncio.timeout(120):
            await execute('contract-test','验证 Browser Use 工具契约',{'category':'人工智能'},config,emit,accept)
    report={'test_only':True,'real_llm':False,'events':events,'results':records}
    Path('docs/agent-contract-smoke.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    assert records and records[0]['source_urls']==[URL], 'No browser-grounded record'
    print('PASS: scripted model + real Browser Use navigation/extraction/screenshot; NOT a live LLM test')


if __name__=='__main__':asyncio.run(main())
