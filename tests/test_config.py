import json

from idle_spider.config import Config, ConfigStore


def test_defaults():
    c = Config()
    assert c.idle_timeout == 60 and c.spider_color == "#000000"
    assert c.start_corner == "top_left" and c.monitor_mode == "current"


def test_normalize_clamps_and_repairs():
    c = Config(idle_timeout=-5, spider_size=999, web_opacity=7, animation_speed="x",
               spider_color="red", start_corner="middle", monitor_mode="x",
               web_density=0).normalize()
    assert c.idle_timeout == 5 and c.spider_size == 48 and c.web_opacity == 1.0
    assert c.animation_speed == 1.0 and c.spider_color == "#000000"
    assert c.start_corner == "top_left" and c.monitor_mode == "current"
    assert c.web_density == 1


def test_roundtrip(tmp_path):
    store = ConfigStore(tmp_path / "sub" / "config.json")
    cfg = Config(idle_timeout=120, web_color="#112233", max_webs=2)
    assert store.save(cfg)
    assert ConfigStore(store.path).config == cfg.normalize()


def test_unknown_keys_ignored(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"idle_timeout": 33, "bogus": 1}))
    assert ConfigStore(path).config.idle_timeout == 33


def test_corrupt_file_falls_back_and_is_backed_up(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("{not json")
    assert ConfigStore(path).config == Config()
    assert (tmp_path / "c.json.bak").exists()
