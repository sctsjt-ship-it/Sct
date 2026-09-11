"""일정 목록을 카카오톡으로 보낼 한국어 문구로 만든다."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .events import Event, day_bounds, sort_events

WEEKDAYS = ("월", "화", "수", "목", "금", "토", "일")

# 카카오톡 기본 텍스트 템플릿의 text 한도(200자). 넘치면 여러 통으로 나눠 보낸다.
KAKAO_TEXT_LIMIT = 200
COUNTER_WIDTH = 8  # " (1/3)" 같은 꼬리표 자리
MAX_LOCATION = 18


def format_day_header(day: date) -> str:
    return f"{day.month}월 {day.day}일 ({WEEKDAYS[day.weekday()]})"


def _clock(moment: datetime) -> str:
    return moment.strftime("%H:%M")


def format_time_range(event: Event, day_start: datetime, day_end: datetime) -> str:
    if event.all_day:
        return "[종일]"
    starts_earlier = event.start < day_start
    ends_later = event.end > day_end
    start_text = "전날부터" if starts_earlier else _clock(event.start)
    end_text = "익일" if ends_later else _clock(event.end)
    if start_text == end_text:
        return start_text
    return f"{start_text}-{end_text}"


def format_event_line(event: Event, day_start: datetime, day_end: datetime) -> str:
    line = f"· {format_time_range(event, day_start, day_end)} {event.summary}".rstrip()
    if event.location:
        location = event.location.splitlines()[0].strip()
        if len(location) > MAX_LOCATION:
            location = location[: MAX_LOCATION - 1] + "…"
        line += f" @{location}"
    return line


def build_message(events: list[Event], day: date, tz: ZoneInfo) -> str:
    """하루 일정 브리핑 본문을 만든다."""
    day_start, day_end = day_bounds(day, tz)
    header = format_day_header(day)

    if not events:
        return f"☀️ {header} 오늘의 일정\n\n등록된 일정이 없습니다. 좋은 하루 보내세요!"

    ordered = sort_events(events)
    lines = [f"☀️ {header} 오늘의 일정 {len(ordered)}건", ""]
    lines.extend(format_event_line(event, day_start, day_end) for event in ordered)
    return "\n".join(lines)


def split_for_kakao(text: str, limit: int = KAKAO_TEXT_LIMIT) -> list[str]:
    """카카오톡 글자 수 한도에 맞춰 줄 단위로 쪼갠다."""
    if len(text) <= limit:
        return [text]

    budget = limit - COUNTER_WIDTH
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            chunks.append("\n".join(current))
            current = []
            current_len = 0

    for line in text.split("\n"):
        for piece in _hard_split(line, budget):
            extra = len(piece) + (1 if current else 0)
            if current and current_len + extra > budget:
                flush()
                extra = len(piece)
            current.append(piece)
            current_len += extra
    flush()

    total = len(chunks)
    if total == 1:
        return chunks
    return [f"{chunk}\n({index}/{total})" for index, chunk in enumerate(chunks, start=1)]


def _hard_split(line: str, budget: int) -> list[str]:
    """한 줄이 통째로 한도를 넘으면 강제로 자른다."""
    if len(line) <= budget:
        return [line]
    return [line[start : start + budget] for start in range(0, len(line), budget)]


def calendar_day_url(day: date) -> str:
    """카카오톡 버튼이 열어 줄 구글 캘린더 해당 날짜 화면."""
    return f"https://calendar.google.com/calendar/r/day/{day.year}/{day.month}/{day.day}"
