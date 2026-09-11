"""매일 아침 구글 캘린더 일정을 읽어 카카오톡으로 보내는 진입점."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta

import requests

from .config import Config, ConfigError, load_config
from .events import Event
from .formatter import build_message, calendar_day_url, split_for_kakao
from .kakao import KakaoError, refresh_access_token, send_messages
from .secrets_sync import SecretUpdateError, update_repo_secret

logger = logging.getLogger("daily_brief")

SECRET_NAME = "KAKAO_REFRESH_TOKEN"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="구글 캘린더의 하루 일정을 카카오톡으로 보냅니다."
    )
    parser.add_argument(
        "--date",
        help="브리핑할 날짜 (YYYY-MM-DD). 기본값은 설정된 시간대의 오늘.",
    )
    parser.add_argument(
        "--tomorrow",
        action="store_true",
        help="내일 일정을 보냅니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="카카오톡으로 보내지 않고 메시지만 출력합니다.",
    )
    return parser.parse_args(argv)


def resolve_day(config: Config, args: argparse.Namespace) -> date:
    if args.date:
        return datetime.strptime(args.date, "%Y-%m-%d").date()
    today = datetime.now(config.timezone).date()
    return today + timedelta(days=1) if args.tomorrow else today


def collect_events(config: Config, day: date, session: requests.Session) -> list[Event]:
    if config.calendar_source == "google":
        from . import calendar_google

        return calendar_google.collect_events(
            config.google_calendar_ids,
            day,
            config.timezone,
            client_id=config.google_client_id,
            client_secret=config.google_client_secret,
            refresh_token=config.google_refresh_token,
            session=session,
            skip_declined=config.skip_declined,
        )

    from . import calendar_ics

    return calendar_ics.collect_events(config.ics_urls, day, config.timezone, session=session)


def persist_rotated_token(config: Config, new_refresh_token: str, session: requests.Session) -> None:
    """카카오가 새 refresh token 을 줬을 때 저장을 시도한다."""
    if not (config.github_repository and config.github_token):
        logger.warning(
            "카카오가 새 refresh token 을 발급했지만 자동 저장이 꺼져 있습니다. "
            "GitHub 시크릿 %s 값을 직접 바꿔 주세요: %s",
            SECRET_NAME,
            new_refresh_token,
        )
        return
    try:
        update_repo_secret(
            config.github_repository,
            config.github_token,
            SECRET_NAME,
            new_refresh_token,
            session=session,
        )
    except SecretUpdateError as exc:
        logger.error(
            "새 refresh token 자동 저장 실패: %s. 시크릿 %s 를 직접 갱신해 주세요.",
            exc,
            SECRET_NAME,
        )


def run(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        config = load_config()
    except ConfigError as exc:
        logger.error("%s", exc)
        return 2

    day = resolve_day(config, args)
    dry_run = config.dry_run or args.dry_run
    session = requests.Session()

    try:
        events = collect_events(config, day, session)
    except Exception as exc:  # noqa: BLE001 - 실패 원인을 사람이 읽게 남긴다
        logger.error("캘린더를 읽지 못했습니다: %s", exc)
        return 1

    logger.info("%s 일정 %d건", day.isoformat(), len(events))
    message = build_message(events, day, config.timezone)
    chunks = split_for_kakao(message)

    if dry_run:
        print(f"--- DRY RUN ({len(chunks)}통) ---")
        for index, chunk in enumerate(chunks, start=1):
            print(f"[{index}/{len(chunks)}] {len(chunk)}자")
            print(chunk)
            print("-" * 32)
        return 0

    try:
        bundle = refresh_access_token(
            config.kakao.rest_api_key,
            config.kakao.refresh_token,
            client_secret=config.kakao.client_secret,
            session=session,
        )
        send_messages(
            bundle.access_token,
            chunks,
            calendar_day_url(day),
            session=session,
        )
    except KakaoError as exc:
        logger.error("%s", exc)
        return 1

    if bundle.rotated and bundle.refresh_token:
        persist_rotated_token(config, bundle.refresh_token, session)

    logger.info("카카오톡 전송 완료 (%d통)", len(chunks))
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
