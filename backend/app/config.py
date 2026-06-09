"""Application settings loaded from the environment.

The SEC requires a descriptive ``User-Agent`` with contact info on every
request and enforces a hard limit of 10 requests/second. Both are configured
here so the whole app shares one policy.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    # SEC requires real contact info here. Keep the default obviously-fake so
    # nobody ships it by accident.
    sechub_user_agent: str = "SecHub/0.1 (you@example.com)"

    database_url: str = "postgresql+psycopg://sechub:sechub@db:5432/sechub"

    # Real-time feed poll interval (seconds) and the UTC hour (0-23) at which
    # the worker runs its once-a-day daily-index catch-up backfill.
    sechub_poll_interval: int = 120
    sechub_backfill_hour: int = 5

    # Hard cap on requests/sec to EDGAR. SEC limit is 10; default lower for safety.
    sechub_max_rps: float = 8.0

    # Form types the real-time worker watches.
    sechub_watch_forms: str = "13F-HR,4,SC 13D,SC 13G,NPORT-P"

    # Earliest year the historical backfill (``python -m app.backfill``) walks.
    # EDGAR's full-index reaches back to 1993; the default is a recent-history
    # window to keep an unattended run bounded. Lower it to go deeper.
    sechub_backfill_since_year: int = 2014

    @property
    def watch_forms(self) -> list[str]:
        return [f.strip() for f in self.sechub_watch_forms.split(",") if f.strip()]


settings = Settings()
