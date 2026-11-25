"""
✅ ADVANCED — Centralized Config Management (12-Factor: Config in Env)

Tất cả config đọc từ environment variables.
- Không có giá trị nhạy cảm trong code
- Dễ thay đổi giữa dev/staging/production
- Validation rõ ràng — fail fast nếu thiếu config quan trọng
"""
import os
import logging
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Nạp .env nếu có (ưu tiên biến môi trường hệ thống nếu đã được set)
load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


@dataclass
class Settings:
    # Server
    host: str = field(default_factory=lambda: os.getenv("HOST") or "0.0.0.0")
    port: int = field(default_factory=lambda: int(os.getenv("PORT") or "8000"))
    debug: bool = field(default_factory=lambda: os.getenv("DEBUG", "false").lower() == "true")

    # App
    app_name: str = field(default_factory=lambda: os.getenv("APP_NAME", "AI Agent"))
    app_version: str = field(default_factory=lambda: os.getenv("APP_VERSION", "1.0.0"))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))

    # LLM (optional — chỉ warn nếu thiếu, không crash)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MAX_TOKENS", "500")))

    # Security
    api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    allowed_origins: list = field(
        default_factory=lambda: os.getenv("ALLOWED_ORIGINS", "*").split(",")
    )

    def validate(self):
        """Fail fast nếu thiếu config bắt buộc."""
        warnings = []
        if not self.openai_api_key:
            warnings.append("OPENAI_API_KEY not set — using mock LLM")
        if not self.api_key and self.environment == "production":
            raise ValueError("AGENT_API_KEY must be set in production!")
        for w in warnings:
            logging.warning(w)
        return self


# Singleton — import từ bất kỳ file nào đều dùng chung
settings = Settings().validate()
