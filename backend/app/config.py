"""Central configuration. All values overridable via environment / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root (roadanalyz/)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "RoadPulse"
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'roadpulse.db').as_posix()}"
    MEDIA_DIR: str = str(BASE_DIR / "media" / "uploads")

    # Gemini Vision
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    # When True (or no API key set) the AI service returns a deterministic
    # mock verdict so the hackathon demo never blocks on network/quota.
    MOCK_AI: bool = True

    # Telegram bot token for WebApp initData verification.
    # Empty = lenient demo mode (any client accepted).
    TELEGRAM_BOT_TOKEN: str = ""

    # Comma-separated Telegram IDs that are always admins (bootstrap).
    # Example: ADMIN_IDS=123456789,987654321
    ADMIN_IDS: str = ""

    # Public URL of the Mini App client (used for the bot's Open button).
    # Must be HTTPS for Telegram — e.g. your tunnel or deployed domain.
    MINI_APP_URL: str = "http://localhost:8001/client/"

    # Upload guardrails
    MAX_UPLOAD_MB: int = 10
    ALLOWED_MIME: str = "image/jpeg,image/png,image/webp"

    # Game / AI thresholds
    CONFIDENCE_THRESHOLD: float = 0.65
    POINTS_PER_REPORT: int = 10

    # Rate limiting: max reports per user per rolling window
    RATE_LIMIT_REPORTS: int = 20
    RATE_LIMIT_WINDOW_SEC: int = 60

    @property
    def allowed_mime_set(self) -> set[str]:
        return {m.strip() for m in self.ALLOWED_MIME.split(",") if m.strip()}

    @property
    def admin_id_set(self) -> set[int]:
        ids: set[int] = set()
        for part in self.ADMIN_IDS.split(","):
            part = part.strip()
            if part.isdigit():
                ids.add(int(part))
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
