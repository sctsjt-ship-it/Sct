"""환경변수에서 설정을 읽어들인다."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Seoul"


class ConfigError(RuntimeError):
    """설정이 비어 있거나 서로 맞지 않을 때."""


def _split(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _flag(env: dict[str, str], name: str, default: bool = False) -> bool:
    raw = env.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class KakaoConfig:
    rest_api_key: str
    refresh_token: str
    client_secret: str | None = None


@dataclass(frozen=True)
class Config:
    kakao: KakaoConfig
    timezone: ZoneInfo
    calendar_source: str  # "ics" 또는 "google"
    ics_urls: list[str] = field(default_factory=list)
    google_client_id: str = ""
    google_client_secret: str = ""
    google_refresh_token: str = ""
    google_calendar_ids: list[str] = field(default_factory=list)
    skip_declined: bool = True
    dry_run: bool = False
    github_repository: str = ""
    github_token: str = ""

    @property
    def timezone_name(self) -> str:
        return str(self.timezone.key)


def load_config(env: dict[str, str] | None = None) -> Config:
    """환경변수를 읽어 Config 를 만든다. 빠뜨린 값이 있으면 ConfigError."""
    env = dict(os.environ if env is None else env)

    tz_name = env.get("TIMEZONE", "").strip() or DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(tz_name)
    except Exception as exc:  # noqa: BLE001 - 잘못된 IANA 이름
        raise ConfigError(f"TIMEZONE 값이 올바른 IANA 시간대가 아닙니다: {tz_name!r}") from exc

    rest_api_key = env.get("KAKAO_REST_API_KEY", "").strip()
    refresh_token = env.get("KAKAO_REFRESH_TOKEN", "").strip()
    missing = [
        name
        for name, value in (
            ("KAKAO_REST_API_KEY", rest_api_key),
            ("KAKAO_REFRESH_TOKEN", refresh_token),
        )
        if not value
    ]
    if missing:
        raise ConfigError(
            "카카오 설정이 없습니다: " + ", ".join(missing) + " (README 의 준비물 참고)"
        )

    ics_urls = _split(env.get("GOOGLE_CALENDAR_ICS_URLS"))
    google_client_id = env.get("GOOGLE_CLIENT_ID", "").strip()
    google_client_secret = env.get("GOOGLE_CLIENT_SECRET", "").strip()
    google_refresh_token = env.get("GOOGLE_REFRESH_TOKEN", "").strip()
    has_google_oauth = all((google_client_id, google_client_secret, google_refresh_token))

    source = env.get("CALENDAR_SOURCE", "").strip().lower()
    if not source:
        source = "google" if has_google_oauth else "ics"
    if source not in {"ics", "google"}:
        raise ConfigError(f"CALENDAR_SOURCE 는 'ics' 또는 'google' 이어야 합니다: {source!r}")

    if source == "ics" and not ics_urls:
        raise ConfigError(
            "캘린더 설정이 없습니다: GOOGLE_CALENDAR_ICS_URLS(비공개 iCal 주소) 를 넣거나, "
            "GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/GOOGLE_REFRESH_TOKEN 을 넣어 주세요."
        )
    if source == "google" and not has_google_oauth:
        raise ConfigError(
            "CALENDAR_SOURCE=google 인데 GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / "
            "GOOGLE_REFRESH_TOKEN 중 빠진 값이 있습니다."
        )

    return Config(
        kakao=KakaoConfig(
            rest_api_key=rest_api_key,
            refresh_token=refresh_token,
            client_secret=env.get("KAKAO_CLIENT_SECRET", "").strip() or None,
        ),
        timezone=tz,
        calendar_source=source,
        ics_urls=ics_urls,
        google_client_id=google_client_id,
        google_client_secret=google_client_secret,
        google_refresh_token=google_refresh_token,
        google_calendar_ids=_split(env.get("GOOGLE_CALENDAR_IDS")) or ["primary"],
        skip_declined=_flag(env, "SKIP_DECLINED", True),
        dry_run=_flag(env, "DRY_RUN", False),
        github_repository=env.get("GITHUB_REPOSITORY", "").strip(),
        github_token=env.get("SECRETS_UPDATE_TOKEN", "").strip(),
    )
