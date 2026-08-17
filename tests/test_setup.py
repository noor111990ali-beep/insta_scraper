import json

from channels import load_channels, normalize_handle, write_channels
from database import (
    init_db,
    list_channels,
    list_posts,
    save_posts,
    save_user,
    set_scrape_context,
    start_run,
    status_summary,
    upsert_channel,
    upsert_media,
)


def test_normalize_handle_accepts_urls_and_at_signs():
    assert normalize_handle("@NASA") == "NASA"
    assert normalize_handle("https://www.instagram.com/natgeo/") == "natgeo"
    assert normalize_handle("# comment") == ""
    assert normalize_handle("https://www.instagram.com/bbcnews/?hl=en") == "bbcnews"


def test_load_and_write_channels(tmp_path):
    path = tmp_path / "channels.txt"
    write_channels(["@nasa", "https://www.instagram.com/natgeo/"], path=str(path))
    assert load_channels(str(path)) == ["nasa", "natgeo"]


def test_database_stores_channels_users_and_posts(tmp_path):
    db_path = str(tmp_path / "scraper.db")
    init_db(db_path)
    upsert_channel("nasa", start_date="2023-10-07", db_path=db_path)
    run_id = start_run(db_path)
    set_scrape_context(run_id, "nasa", db_path=db_path)
    save_user({"id": "u1", "username": "nasa"}, db_path=db_path)
    saved = save_posts(
        [
            {
                "id": "p1",
                "taken_at": 1700000000,
                "caption": {"text": "hello"},
                "image_versions2": {"candidates": [{"url": "https://cdn.example.com/a.jpg"}]},
            }
        ],
        db_path=db_path,
    )
    assert saved == 1
    assert list_channels(db_path) == ["nasa"]
    posts = list_posts(handle="nasa", db_path=db_path)
    assert posts[0]["caption"] == "hello"
    assert json.loads(posts[0]["raw_json"])["id"] == "p1"
    upsert_media("p1", "image", "https://cdn.example.com/a.jpg", db_path=db_path)
    summary = status_summary(db_path)
    assert summary["channels"] == 1
    assert summary["posts"] == 1
    assert summary["media"] == 1
    set_scrape_context(None, None, None)


def test_setup_checklist_needs_login_and_channels(tmp_path, monkeypatch):
    import channels as channels_mod
    import setup as setup_mod

    channels_path = tmp_path / "channels.txt"
    channels_path.write_text("nasa\n", encoding="utf-8")
    monkeypatch.setattr(channels_mod, "CHANNELS_FILE", str(channels_path))
    monkeypatch.setattr(setup_mod, "CHANNELS_FILE", str(channels_path))
    monkeypatch.setattr(setup_mod, "LOCAL_CONFIG", str(tmp_path / "dhs622_config.cfg"))
    info = setup_mod.checklist(db_path=str(tmp_path / "scraper.db"))
    assert info["channels"] == ["nasa"]
    assert info["has_instagram_login"] is False
    assert info["ready"] is False
