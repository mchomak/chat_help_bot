"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def _env_int(key: str, default: int = 0) -> int:
    return int(os.getenv(key, str(default)))


def _env_float(key: str, default: float = 0.0) -> float:
    return float(os.getenv(key, str(default)))


def _env_list(key: str, sep: str = ",") -> list[str]:
    raw = os.getenv(key, "")
    return [s.strip() for s in raw.split(sep) if s.strip()] if raw else []


@dataclass(frozen=True)
class BotConfig:
    token: str = field(default_factory=lambda: _env("BOT_TOKEN"))
    webhook_host: str = field(default_factory=lambda: _env("WEBHOOK_HOST"))
    webhook_path: str = field(default_factory=lambda: _env("WEBHOOK_PATH", "/webhook"))
    webhook_port: int = field(default_factory=lambda: _env_int("WEBHOOK_PORT", 8443))
    webhook_secret: str = field(default_factory=lambda: _env("WEBHOOK_SECRET", ""))

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_host}{self.webhook_path}"


@dataclass(frozen=True)
class DatabaseConfig:
    url: str = field(default_factory=lambda: _env("DATABASE_URL"))
    pool_size: int = field(default_factory=lambda: _env_int("DB_POOL_SIZE", 20))
    max_overflow: int = field(default_factory=lambda: _env_int("DB_MAX_OVERFLOW", 10))
    pool_recycle: int = field(default_factory=lambda: _env_int("DB_POOL_RECYCLE", 1800))


@dataclass(frozen=True)
class AIConfig:
    api_key: str = field(default_factory=lambda: _env("AI_API_KEY"))
    api_base_url: str = field(default_factory=lambda: _env("AI_API_BASE_URL", "https://api.openai.com/v1"))
    default_model: str = field(default_factory=lambda: _env("AI_DEFAULT_MODEL", "gpt-4o"))
    vision_model: str = field(default_factory=lambda: _env("AI_VISION_MODEL", "gpt-4o"))
    max_tokens: int = field(default_factory=lambda: _env_int("AI_MAX_TOKENS", 2048))
    temperature: float = field(default_factory=lambda: _env_float("AI_TEMPERATURE", 0.8))
    request_timeout: float = field(default_factory=lambda: _env_float("AI_REQUEST_TIMEOUT", 60.0))
    # Language for AI prompts: "en" (English) or "ru" (Russian).
    # Does NOT affect user-facing messages — only the language of internal prompts sent to the model.
    prompt_language: str = field(default_factory=lambda: _env("AI_PROMPT_LANGUAGE", "en").lower())


@dataclass(frozen=True)
class ProxyConfig:
    proxies: list[str] = field(default_factory=lambda: _env_list("PROXY_LIST"))
    connect_timeout: float = field(default_factory=lambda: _env_float("PROXY_CONNECT_TIMEOUT", 10.0))
    read_timeout: float = field(default_factory=lambda: _env_float("PROXY_READ_TIMEOUT", 30.0))
    max_retries: int = field(default_factory=lambda: _env_int("PROXY_MAX_RETRIES", 3))
    cooldown_seconds: int = field(default_factory=lambda: _env_int("PROXY_COOLDOWN_SECONDS", 120))
    slow_threshold: float = field(default_factory=lambda: _env_float("PROXY_SLOW_THRESHOLD", 20.0))


@dataclass(frozen=True)
class TrialConfig:
    duration_hours: int = field(default_factory=lambda: _env_int("TRIAL_DURATION_HOURS", 2))


@dataclass(frozen=True)
class AppConfig:
    bot: BotConfig = field(default_factory=BotConfig)
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    trial: TrialConfig = field(default_factory=TrialConfig)
    debug: bool = field(default_factory=lambda: _env("DEBUG", "false").lower() == "true")
    log_level: str = field(default_factory=lambda: _env("LOG_LEVEL", "INFO"))
    temp_dir: Path = field(default_factory=lambda: Path(_env("TEMP_DIR", "/tmp/chat_help_bot")))
    monthly_image_limit: int = field(default_factory=lambda: _env_int("MONTHLY_IMAGE_LIMIT", 300))


settings = AppConfig()
