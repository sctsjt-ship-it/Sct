from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from daily_brief import main as main_module
from daily_brief.events import Event
from daily_brief.kakao import TokenBundle

KST = ZoneInfo("Asia/Seoul")

ENV = {
    "KAKAO_REST_API_KEY": "KEY",
    "KAKAO_REFRESH_TOKEN": "RT",
    "GOOGLE_CALENDAR_ICS_URLS": "https://example.com/basic.ics",
    "TIMEZONE": "Asia/Seoul",
}

SAMPLE = [
    Event(
        summary="팀 스탠드업",
        start=datetime(2026, 9, 11, 9, 0, tzinfo=KST),
        end=datetime(2026, 9, 11, 10, 0, tzinfo=KST),
    )
]


@pytest.fixture
def env(monkeypatch):
    for key in list(ENV) + ["DRY_RUN", "CALENDAR_SOURCE", "SECRETS_UPDATE_TOKEN"]:
        monkeypatch.delenv(key, raising=False)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def sent(monkeypatch):
    """카카오 호출을 가로채 전송 내용을 기록한다."""
    record: dict = {}

    def fake_refresh(*args, **kwargs):
        return TokenBundle(access_token="AT", refresh_token=record.get("rotate_to"))

    def fake_send(access_token, messages, link_url, **kwargs):
        record["access_token"] = access_token
        record["messages"] = messages
        record["link_url"] = link_url
        return len(messages)

    monkeypatch.setattr(main_module, "refresh_access_token", fake_refresh)
    monkeypatch.setattr(main_module, "send_messages", fake_send)
    return record


def use_events(monkeypatch, events):
    monkeypatch.setattr(main_module, "collect_events", lambda config, day, session: events)


def test_sends_the_day_brief(env, sent, monkeypatch):
    use_events(monkeypatch, SAMPLE)
    assert main_module.run(["--date", "2026-09-11"]) == 0
    assert sent["access_token"] == "AT"
    assert "팀 스탠드업" in "\n".join(sent["messages"])
    assert sent["link_url"].endswith("/2026/9/11")


def test_empty_day_still_sends_a_message(env, sent, monkeypatch):
    use_events(monkeypatch, [])
    assert main_module.run(["--date", "2026-09-11"]) == 0
    assert "등록된 일정이 없습니다" in "\n".join(sent["messages"])


def test_dry_run_does_not_send(env, sent, monkeypatch, capsys):
    use_events(monkeypatch, SAMPLE)
    assert main_module.run(["--date", "2026-09-11", "--dry-run"]) == 0
    assert "messages" not in sent
    assert "팀 스탠드업" in capsys.readouterr().out


def test_calendar_failure_exits_nonzero(env, sent, monkeypatch):
    def boom(config, day, session):
        raise RuntimeError("네트워크 오류")

    monkeypatch.setattr(main_module, "collect_events", boom)
    assert main_module.run(["--date", "2026-09-11"]) == 1


def test_missing_configuration_exits_with_two(monkeypatch):
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)
    monkeypatch.delenv("KAKAO_REFRESH_TOKEN", raising=False)
    assert main_module.run([]) == 2


def test_rotated_refresh_token_is_persisted(env, sent, monkeypatch):
    use_events(monkeypatch, SAMPLE)
    sent["rotate_to"] = "NEW-RT"
    monkeypatch.setenv("SECRETS_UPDATE_TOKEN", "gh-pat")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")

    updates: dict = {}

    def fake_update(repository, token, name, value, **kwargs):
        updates.update(repository=repository, token=token, name=name, value=value)

    monkeypatch.setattr(main_module, "update_repo_secret", fake_update)
    assert main_module.run(["--date", "2026-09-11"]) == 0
    assert updates == {
        "repository": "owner/repo",
        "token": "gh-pat",
        "name": "KAKAO_REFRESH_TOKEN",
        "value": "NEW-RT",
    }


def test_resolve_day_defaults_to_today_and_supports_tomorrow(env):
    config = main_module.load_config()
    today = datetime.now(KST).date()
    assert main_module.resolve_day(config, main_module.parse_args([])) == today
    tomorrow = main_module.resolve_day(config, main_module.parse_args(["--tomorrow"]))
    assert tomorrow == today + timedelta(days=1)
