from idle_spider.utils import autostart


def test_autostart_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert not autostart.is_autostart_enabled()
    assert autostart.set_autostart(True)
    text = autostart.autostart_path().read_text()
    assert "[Desktop Entry]" in text and "Exec=" in text and "idle_spider" in text or "idle-spider" in text
    assert autostart.is_autostart_enabled()
    assert autostart.set_autostart(False)
    assert not autostart.is_autostart_enabled()
