import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # loads backend/.env

def _parse_frontend_origins(value: str) -> list[str]:
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    return origins or ["http://localhost:3000"]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    frontend_origins: list[str] = _parse_frontend_origins(
        os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")
    )

settings = Settings()

if not settings.database_url:
    raise RuntimeError(
        "DATABASE_URL is missing. Add it to backend/.env and restart the server."
    )
