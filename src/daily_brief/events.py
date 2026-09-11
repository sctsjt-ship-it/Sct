"""캘린더 소스가 공통으로 돌려주는 일정 모델."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Event:
    summary: str
    start: datetime
    end: datetime
    all_day: bool = False
    location: str = ""
    calendar: str = ""

    def sort_key(self) -> tuple[int, datetime, str]:
        # 종일 일정을 먼저, 그 다음 시작 시각 순.
        return (0 if self.all_day else 1, self.start, self.summary)


def day_bounds(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """해당 날짜의 00:00 ~ 다음날 00:00 (tz 기준)."""
    start = datetime.combine(day, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


def overlaps_day(event: Event, day_start: datetime, day_end: datetime) -> bool:
    """일정이 그날 구간과 조금이라도 겹치면 True (자정을 넘는 일정 포함)."""
    return event.start < day_end and event.end > day_start


def sort_events(events: list[Event]) -> list[Event]:
    return sorted(events, key=lambda item: item.sort_key())
