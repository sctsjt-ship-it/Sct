from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from daily_brief.events import Event
from daily_brief.formatter import (
    KAKAO_TEXT_LIMIT,
    build_message,
    calendar_day_url,
    format_day_header,
    format_time_range,
    split_for_kakao,
)
from daily_brief.events import day_bounds

KST = ZoneInfo("Asia/Seoul")
DAY = date(2026, 9, 11)  # 금요일


def event(summary, start_hour, end_hour, **kwargs):
    return Event(
        summary=summary,
        start=datetime(2026, 9, 11, start_hour, 0, tzinfo=KST),
        end=datetime(2026, 9, 11, end_hour, 0, tzinfo=KST),
        **kwargs,
    )


def test_header_uses_korean_weekday():
    assert format_day_header(DAY) == "9월 11일 (금)"


def test_empty_day_message():
    message = build_message([], DAY, KST)
    assert "등록된 일정이 없습니다" in message
    assert "9월 11일 (금)" in message


def test_message_lists_events_in_time_order():
    events = [event("고객 미팅", 13, 14), event("팀 스탠드업", 9, 10)]
    message = build_message(events, DAY, KST)
    assert message.index("팀 스탠드업") < message.index("고객 미팅")
    assert "일정 2건" in message
    assert "09:00-10:00" in message


def test_all_day_event_comes_first_and_is_labelled():
    all_day = Event(
        summary="워크숍",
        start=datetime(2026, 9, 11, 0, 0, tzinfo=KST),
        end=datetime(2026, 9, 12, 0, 0, tzinfo=KST),
        all_day=True,
    )
    message = build_message([event("스탠드업", 9, 10), all_day], DAY, KST)
    lines = [line for line in message.splitlines() if line.startswith("·")]
    assert lines[0] == "· [종일] 워크숍"


def test_location_is_appended_and_truncated():
    line = build_message([event("미팅", 9, 10, location="서울시 강남구 테헤란로 아주 긴 주소")], DAY, KST)
    assert "@서울시 강남구 테헤란로 아주" in line
    assert "…" in line


def test_time_range_marks_events_crossing_midnight():
    day_start, day_end = day_bounds(DAY, KST)
    overnight = Event(
        summary="야간 배포",
        start=datetime(2026, 9, 10, 22, 0, tzinfo=KST),
        end=datetime(2026, 9, 11, 2, 0, tzinfo=KST),
    )
    assert format_time_range(overnight, day_start, day_end) == "전날부터-02:00"

    late = Event(
        summary="심야 작업",
        start=datetime(2026, 9, 11, 23, 0, tzinfo=KST),
        end=datetime(2026, 9, 12, 3, 0, tzinfo=KST),
    )
    assert format_time_range(late, day_start, day_end) == "23:00-익일"


def test_short_message_is_not_split():
    assert split_for_kakao("짧은 메시지") == ["짧은 메시지"]


def test_long_message_is_split_within_kakao_limit():
    events = [event(f"아주 긴 이름의 회의 번호 {index}", 9, 10) for index in range(20)]
    chunks = split_for_kakao(build_message(events, DAY, KST))
    assert len(chunks) > 1
    assert all(len(chunk) <= KAKAO_TEXT_LIMIT for chunk in chunks)
    assert chunks[0].endswith(f"(1/{len(chunks)})")


def test_split_keeps_every_event_line():
    events = [event(f"회의 {index}", 9, 10) for index in range(25)]
    chunks = split_for_kakao(build_message(events, DAY, KST))
    joined = "\n".join(chunks)
    for index in range(25):
        assert f"회의 {index}" in joined


def test_single_line_longer_than_limit_is_hard_split():
    chunks = split_for_kakao("가" * 500)
    assert len(chunks) >= 3
    assert all(len(chunk) <= KAKAO_TEXT_LIMIT for chunk in chunks)


def test_calendar_day_url_points_to_the_day():
    assert calendar_day_url(DAY) == "https://calendar.google.com/calendar/r/day/2026/9/11"
