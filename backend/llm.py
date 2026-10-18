from browser_use.llm.deepseek.chat import ChatDeepSeek
from browser_use.llm.deepseek.serializer import DeepSeekMessageSerializer
from browser_use.llm.exceptions import ModelProviderError
from browser_use.llm.schema import SchemaOptimizer
from browser_use.llm.views import ChatInvokeCompletion
from pydantic import ValidationError
import json


class DeepSeekChat(ChatDeepSeek):
    """Support the current official Flash alias in Browser Use 0.13.11.

    DeepSeek defaults to thinking mode, which rejects forced tool selection.
    The upstream adapter only sends the flag for names containing deepseek-v4.
    """

    def _supports_thinking(self) -> bool:
        return self.model.lower() == 'deepseek-flash' or super()._supports_thinking()

    async def ainvoke(self, messages, output_format=None, tools=None, stop=None, **kwargs):
        if output_format is None:
            return await super().ainvoke(messages, output_format=output_format, tools=tools, stop=stop, **kwargs)
        # The live Flash endpoint returned tool arguments with missing closing
        # braces even with finish_reason=tool_calls (not token truncation).
        # Use the provider's documented JSON Output and validate the full schema.
        # Never repair output by guessing or dropping fields.
        serialized = DeepSeekMessageSerializer.serialize_messages(messages)
        schema = SchemaOptimizer.create_optimized_json_schema(output_format)
        serialized.append({'role': 'user', 'content': 'Return one valid JSON object matching this JSON Schema. Use only the allowed action names. Keep strings short, copy evidence verbatim, and close every object and array. No markdown. JSON Schema: ' + json.dumps(schema, ensure_ascii=False)})
        try:
            async with self._client() as client:
                response = await client.chat.completions.create(
                    model=self.model, messages=serialized,
                    response_format={'type': 'json_object'}, **self._request_kwargs())
            choice = response.choices[0]
            if choice.finish_reason == 'length':
                raise ValueError('Structured response exceeded token budget')
            completion = output_format.model_validate_json(choice.message.content or '')
            return ChatInvokeCompletion(completion=completion, usage=None)
        except ValidationError as error:
            fields = [{'field': '.'.join(str(part) for part in item['loc']), 'type': item['type']} for item in error.errors(include_input=False, include_url=False)[:6]]
            raise ModelProviderError('JSON schema validation failed; correct these fields: ' + json.dumps(fields), model=self.name) from error
        except Exception as error:
            # Keep raw provider responses and page content out of task/log errors.
            raise ModelProviderError(f'DeepSeek structured response failed ({type(error).__name__})', model=self.name) from error
