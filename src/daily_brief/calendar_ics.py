"""구글 캘린더 '비공개 iCal 주소'(.ics)에서 하루 일정을 읽는다.

OAuth 없이 주소 하나만 있으면 되는 방식이다. 반복 일정(RRULE)과 개별 변경/삭제는
recurring-ical-events 가 펼쳐 준다.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
import requests

from .events import Event, day_bounds

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30


def fetch_ics(url: str, *, session: requests.Session | None = None) -> bytes:
    http = session or requests.Session()
    response = http.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.content


def _as_aware(value: datetime | date, tz: ZoneInfo, *, end_of_day: bool = False) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=tz)
        return value.astimezone(tz)
    # date 만 있는 경우(종일 일정)
    moment = time.min
    return datetime.combine(value, moment, tzinfo=tz)


def _calendar_name(calendar: icalendar.Calendar) -> str:
    for key in ("X-WR-CALNAME", "NAME"):
        value = calendar.get(key)
        if value:
            return str(value)
    return ""


def events_from_ics(
    ics_bytes: bytes,
    day: date,
    tz: ZoneInfo,
    *,
    calendar_label: str = "",
) -> list[Event]:
    """ICS 본문에서 해당 날짜와 겹치는 일정을 뽑아낸다."""
    calendar = icalendar.Calendar.from_ical(ics_bytes)
    label = calendar_label or _calendar_name(calendar)
    day_start, day_end = day_bounds(day, tz)

    # 자정을 넘나드는 일정도 잡히도록 하루씩 넉넉히 조회한 뒤 걸러 낸다.
    occurrences = recurring_ical_events.of(calendar).between(
        day_start - timedelta(days=1), day_end + timedelta(days=1)
    )

    events: list[Event] = []
    for item in occurrences:
        raw_start = item.get("DTSTART")
        raw_end = item.get("DTEND") or item.get("DTSTART")
        if raw_start is None:
            continue
        start_value = raw_start.dt
        end_value = raw_end.dt
        all_day = not isinstance(start_value, datetime)

        start = _as_aware(start_value, tz)
        end = _as_aware(end_value, tz)
        if all_day and end <= start:
            end = start + timedelta(days=1)
        if end <= start:
            end = start

        if not (start < day_end and end > day_start):
            continue

        status = str(item.get("STATUS", "")).upper()
        if status == "CANCELLED":
            continue

        events.append(
            Event(
                summary=str(item.get("SUMMARY", "")).strip() or "(제목 없음)",
                start=start,
                end=end,
                all_day=all_day,
                location=str(item.get("LOCATION", "")).strip(),
                calendar=label,
            )
        )
    return events


def collect_events(
    urls: list[str],
    day: date,
    tz: ZoneInfo,
    *,
    session: requests.Session | None = None,
) -> list[Event]:
    """여러 개의 비공개 iCal 주소에서 하루 일정을 모은다."""
    http = session or requests.Session()
    collected: list[Event] = []
    for url in urls:
        logger.info("iCal 주소에서 일정을 읽는 중: %s", _mask(url))
        collected.extend(events_from_ics(fetch_ics(url, session=http), day, tz))
    return collected


def _mask(url: str) -> str:
    """비공개 주소가 로그에 그대로 남지 않게 가린다."""
    if len(url) <= 40:
        return url[:12] + "…"
    return url[:32] + "…" + url[-12:]
