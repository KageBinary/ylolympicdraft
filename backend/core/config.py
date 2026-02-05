import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()  # loads backend/.env (local). On Render, env vars are already set.

def _parse_frontend_origins(value: str) -> list[str]:
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    return origins or ["http://localhost:3000"]

@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    frontend_origins: list[str] = field(
        default_factory=lambda: _parse_frontend_origins(
            os.getenv("FRONTEND_ORIGINS", os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"))
        )
    )
    results_admin_username: str = os.getenv("RESULTS_ADMIN_USERNAME", "").strip()
    results_admin_password: str = os.getenv("RESULTS_ADMIN_PASSWORD", "")

settings = Settings()

if not settings.database_url:
    raise RuntimeError("DATABASE_URL is missing. Set it in Render environment variables.")
