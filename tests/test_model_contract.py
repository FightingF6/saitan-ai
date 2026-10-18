import httpx
import pytest
from pydantic import BaseModel, SecretStr
from backend.agent import create_llm, make_browser
from backend.config import settings


async def test_deepseek_adapter_uses_native_json_output():
    """Protocol test only; does NOT assert live DeepSeek compatibility."""
    requests=[]
    def handler(request):
        import json
        body=json.loads(request.content)
        requests.append(body)
        return httpx.Response(200,json={'id':'test','object':'chat.completion','created':0,'model':'deepseek-flash','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':'{"ok":true}'}}]})
    class Probe(BaseModel):ok:bool
    from browser_use.llm.messages import UserMessage
    config=settings.model_copy(update={'api_key':SecretStr('test-only')})
    llm=create_llm(config)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        llm.client_params={'http_client':client,'max_retries':0}
        result=await llm.ainvoke([UserMessage(content='Return JSON ok true')],output_format=Probe)
    assert result.completion.ok
    assert requests[0]['model']=='deepseek-flash'
    assert requests[0]['max_tokens']==6000
    assert requests[0]['thinking']=={'type':'disabled'}
    assert requests[0]['response_format']=={'type':'json_object'}
    assert 'JSON Schema' in requests[0]['messages'][-1]['content']
    assert 'max_completion_tokens' not in requests[0]


def test_browser_config_disables_high_risk_features():
    class Proxy:url='http://127.0.0.1:9999'
    browser=make_browser(Proxy())
    config=browser.browser_profile
    assert not config.accept_downloads and not config.auto_download_pdfs
    assert not config.captcha_solver and not config.enable_default_extensions
    assert config.proxy.bypass=='<-loopback>'
    assert config.chromium_sandbox


@pytest.mark.parametrize(('content', 'finish'), [('{"ok":true', 'stop'), ('{}', 'stop'), ('{"ok":true}', 'length')])
async def test_deepseek_rejects_malformed_missing_or_truncated_output(content, finish):
    from browser_use.llm.exceptions import ModelProviderError
    from browser_use.llm.messages import UserMessage
    class Probe(BaseModel):
        ok: bool
    def handler(request):
        return httpx.Response(200, json={'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'deepseek-flash', 'choices': [{'index': 0, 'finish_reason': finish, 'message': {'role': 'assistant', 'content': content}}]})
    llm = create_llm(settings.model_copy(update={'api_key': SecretStr('test-only')}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        llm.client_params = {'http_client': client, 'max_retries': 0}
        with pytest.raises(ModelProviderError):
            await llm.ainvoke([UserMessage(content='Return JSON')], output_format=Probe)
