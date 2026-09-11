import pytest

from daily_brief.config import ConfigError, load_config

BASE = {
    "KAKAO_REST_API_KEY": "KEY",
    "KAKAO_REFRESH_TOKEN": "RT",
    "GOOGLE_CALENDAR_ICS_URLS": "https://example.com/basic.ics",
}


def test_defaults_to_seoul_and_ics_source():
    config = load_config(dict(BASE))
    assert config.timezone_name == "Asia/Seoul"
    assert config.calendar_source == "ics"
    assert config.ics_urls == ["https://example.com/basic.ics"]
    assert config.dry_run is False
    assert config.skip_declined is True


def test_multiple_ics_urls_are_split():
    config = load_config({**BASE, "GOOGLE_CALENDAR_ICS_URLS": "https://a.ics, https://b.ics"})
    assert config.ics_urls == ["https://a.ics", "https://b.ics"]


def test_google_oauth_credentials_switch_the_source():
    config = load_config(
        {
            "KAKAO_REST_API_KEY": "KEY",
            "KAKAO_REFRESH_TOKEN": "RT",
            "GOOGLE_CLIENT_ID": "cid",
            "GOOGLE_CLIENT_SECRET": "csecret",
            "GOOGLE_REFRESH_TOKEN": "grt",
        }
    )
    assert config.calendar_source == "google"
    assert config.google_calendar_ids == ["primary"]


def test_missing_kakao_settings_are_reported():
    with pytest.raises(ConfigError) as excinfo:
        load_config({"GOOGLE_CALENDAR_ICS_URLS": "https://example.com/basic.ics"})
    assert "KAKAO_REST_API_KEY" in str(excinfo.value)
    assert "KAKAO_REFRESH_TOKEN" in str(excinfo.value)


def test_missing_calendar_settings_are_reported():
    with pytest.raises(ConfigError) as excinfo:
        load_config({"KAKAO_REST_API_KEY": "KEY", "KAKAO_REFRESH_TOKEN": "RT"})
    assert "GOOGLE_CALENDAR_ICS_URLS" in str(excinfo.value)


def test_google_source_without_credentials_is_rejected():
    with pytest.raises(ConfigError):
        load_config({**BASE, "CALENDAR_SOURCE": "google"})


def test_invalid_timezone_is_rejected():
    with pytest.raises(ConfigError):
        load_config({**BASE, "TIMEZONE": "Mars/Olympus"})


def test_flags_are_parsed():
    config = load_config({**BASE, "DRY_RUN": "true", "SKIP_DECLINED": "false"})
    assert config.dry_run is True
    assert config.skip_declined is False
