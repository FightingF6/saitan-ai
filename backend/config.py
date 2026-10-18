import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

os.environ.setdefault('ANONYMIZED_TELEMETRY', 'false')
os.environ.setdefault('BROWSER_USE_LOGGING_LEVEL', 'error')


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='SAITAN_', env_file='.env', extra='ignore')
    llm_provider: Literal['deepseek', 'openai-compatible'] = 'deepseek'
    model: str = 'deepseek-flash'
    api_base_url: str = 'https://api.deepseek.com/v1'
    api_key: SecretStr = SecretStr('')
    max_steps: int = Field(25, ge=3, le=80)
    timeout_seconds: int = Field(300, ge=30, le=900)
    max_pages: int = Field(15, ge=2, le=40)
    default_count: int = Field(8, ge=1, le=20)
    headless: bool = True
    data_dir: Path = Path('data')


class SettingsUpdate(BaseModel):
    llm_provider: Literal['deepseek', 'openai-compatible'] = 'deepseek'
    model: str = Field('deepseek-flash', min_length=1, max_length=120, pattern=r'^[\w.\-/]+$')
    api_base_url: str = 'https://api.deepseek.com/v1'
    api_key: SecretStr | None = None
    clear_api_key: bool = False
    max_steps: int = Field(25, ge=3, le=80)
    timeout_seconds: int = Field(300, ge=30, le=900)
    max_pages: int = Field(15, ge=2, le=40)
    default_count: int = Field(8, ge=1, le=20)
    headless: bool = True

    @field_validator('api_base_url')
    @classmethod
    def validate_url(cls, value):
        p = urlsplit(value)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment:
            raise ValueError('API Base URL 必须是不含凭据的 HTTPS 地址')
        return value.rstrip('/')


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)


def load_settings():
    path = settings.data_dir / 'settings.json'
    if path.exists():
        values = json.loads(path.read_text('utf-8'))
        encrypted = values.pop('encrypted_key', None)
        for name, value in SettingsUpdate(**values).model_dump(exclude={'api_key', 'clear_api_key'}).items():
            setattr(settings, name, value)
        if encrypted:
            settings.api_key = SecretStr(_unprotect(encrypted))


def _protect(secret: str) -> str:
    # Windows DPAPI binds ciphertext to the current OS user. Other platforms use env only.
    if os.name != 'nt':
        raise ValueError('此平台请通过后端 .env 配置密钥')
    import base64
    import win32crypt
    return base64.b64encode(win32crypt.CryptProtectData(secret.encode(), 'SaiTan', None, None, None, 0)).decode()


def _unprotect(cipher: str) -> str:
    import base64
    import win32crypt
    return win32crypt.CryptUnprotectData(base64.b64decode(cipher), None, None, None, 0)[1].decode()


def save_settings(update: SettingsUpdate):
    values = update.model_dump(exclude={'api_key', 'clear_api_key'})
    key = '' if update.clear_api_key else (update.api_key.get_secret_value() if update.api_key else settings.api_key.get_secret_value())
    if key:
        values['encrypted_key'] = _protect(key)
    path = settings.data_dir / 'settings.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(values, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)
    for name, value in update.model_dump(exclude={'api_key', 'clear_api_key'}).items():
        setattr(settings, name, value)
    settings.api_key = SecretStr(key)


def public_settings():
    result = settings.model_dump(exclude={'api_key', 'data_dir'})
    result['api_key_configured'] = bool(settings.api_key.get_secret_value())
    result['browser_mode'] = '本地 Chromium · 独立会话'
    return result
