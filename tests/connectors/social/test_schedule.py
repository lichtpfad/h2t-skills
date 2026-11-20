"""Task Scheduler registration. Never runs the real schtasks: every call uses a fake runner."""
from __future__ import annotations

import pytest

from h2t_ops.connectors.social import schedule
from h2t_ops.core.errors import ConfigError, ProviderError, UsageError


class FakeRunner:
    def __init__(self, returncode=0, stderr=""):
        self.calls = []
        self.kwargs = []
        self.returncode = returncode
        self.stderr = stderr

    def __call__(self, argv, **kwargs):
        self.calls.append(list(argv))
        self.kwargs.append(kwargs)

        class Result:
            pass

        r = Result()
        r.returncode = self.returncode
        r.stderr = self.stderr
        r.stdout = ""
        return r


@pytest.fixture(autouse=True)
def _which(monkeypatch):
    monkeypatch.setattr(schedule.shutil, "which", lambda name: "C:/bin/h2t-ops.exe")


def test_add_registers_store_command():
    fake = FakeRunner()
    out = schedule.add("insights", "07:00", runner=fake, platform="win32")
    argv = fake.calls[0]
    assert argv[:4] == ["schtasks", "/Create", "/TN", "h2t-social-insights"]
    assert argv[4] == "/TR"
    assert argv[6:] == ["/SC", "DAILY", "/ST", "07:00", "/F"]
    assert argv[5].endswith("social run insights --trigger schedule --store")
    assert fake.kwargs[0].get("capture_output") is True
    assert fake.kwargs[0].get("text") is True
    assert out["task"] == "h2t-social-insights"
    assert out["daily"] == "07:00"
    assert out["command"] == argv[5]


def test_add_quotes_exe_with_space(monkeypatch):
    monkeypatch.setattr(schedule.shutil, "which", lambda name: "C:/Program Files/x/h2t-ops.exe")
    fake = FakeRunner()
    schedule.add("insights", "07:00", runner=fake, platform="win32")
    assert fake.calls[0][5].startswith('"C:/Program Files/x/h2t-ops.exe"')


@pytest.mark.parametrize("bad", ["7am", "25:00", "07:60", "7:00", ""])
def test_bad_time_is_usage_error(bad):
    fake = FakeRunner()
    with pytest.raises(UsageError):
        schedule.add("insights", bad, runner=fake, platform="win32")
    assert fake.calls == []


def test_bad_process_is_usage_error():
    fake = FakeRunner()
    with pytest.raises(UsageError, match="insights"):
        schedule.add("ads", "07:00", runner=fake, platform="win32")
    with pytest.raises(UsageError, match="insights"):
        schedule.remove("ads", runner=fake, platform="win32")
    assert fake.calls == []


def test_not_windows_is_usage_error():
    fake = FakeRunner()
    with pytest.raises(UsageError, match="VPS"):
        schedule.add("insights", "07:00", runner=fake, platform="linux")
    with pytest.raises(UsageError, match="VPS"):
        schedule.remove("insights", runner=fake, platform="linux")
    assert fake.calls == []


def test_schtasks_failure_is_provider_error():
    fake = FakeRunner(returncode=1, stderr="Access is denied.")
    with pytest.raises(ProviderError, match="Access is denied."):
        schedule.add("insights", "07:00", runner=fake, platform="win32")
    with pytest.raises(ProviderError, match="Access is denied."):
        schedule.remove("insights", runner=fake, platform="win32")


def test_missing_exe_is_config_error(monkeypatch):
    monkeypatch.setattr(schedule.shutil, "which", lambda name: None)
    fake = FakeRunner()
    with pytest.raises(ConfigError):
        schedule.add("insights", "07:00", runner=fake, platform="win32")
    assert fake.calls == []


def test_remove():
    fake = FakeRunner()
    out = schedule.remove("insights", runner=fake, platform="win32")
    assert fake.calls == [["schtasks", "/Delete", "/TN", "h2t-social-insights", "/F"]]
    assert out["task"] == "h2t-social-insights"


def test_schtasks_output_is_decoded_with_the_oem_code_page():
    fake = FakeRunner()
    schedule.add("insights", "07:00", runner=fake, platform="win32")
    schedule.remove("insights", runner=fake, platform="win32")
    for kwargs in fake.kwargs:
        assert kwargs["encoding"] == "oem" and kwargs["errors"] == "replace"
        assert kwargs["capture_output"] is True and kwargs["text"] is True
