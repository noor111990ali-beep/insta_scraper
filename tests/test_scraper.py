import json
from datetime import datetime, timedelta

from get_assets import (
    extract_images_from_post,
    extract_videos_from_post,
    get_image_name,
    get_video_name,
    load_data,
    parse_video_urls,
)
from insta_scraper_poc import (
    cookies_expired,
    extract_from_api_payload,
    is_content,
    post_timestamp,
)


DASH_MANIFEST = """<?xml version="1.0"?>
<MPD>
  <Period>
    <AdaptationSet>
      <Representation>
        <BaseURL>https://cdn.example.com/v/clip.mp4?a=1</BaseURL>
      </Representation>
    </AdaptationSet>
  </Period>
</MPD>
"""


def test_get_image_name_strips_query_and_forces_png():
    name = get_image_name("123", "https://cdn.example.com/p/photo.jpg?oh=abc&oe=def")
    assert name == "123_photo.png"
    jpeg_name = get_image_name("123", "https://cdn.example.com/p/photo.jpeg")
    assert jpeg_name == "123_photo.png"


def test_get_video_name_keeps_mp4():
    name = get_video_name("123", "https://cdn.example.com/v/clip.mp4?_nc_ht=1")
    assert name == "123_clip.mp4"


def test_parse_video_urls_from_dash_manifest():
    urls = parse_video_urls(DASH_MANIFEST)
    assert urls == ["https://cdn.example.com/v/clip.mp4?a=1"]


def test_extract_images_and_videos_from_single_and_carousel_posts():
    single = {
        "id": "111",
        "image_versions2": {
            "candidates": [
                {"url": "https://cdn.example.com/a.jpg", "width": 1080},
                {"url": "https://cdn.example.com/small.jpg", "width": 320},
            ]
        },
        "carousel_media": None,
        "video_dash_manifest": None,
    }
    carousel = {
        "id": "222",
        "image_versions2": None,
        "carousel_media": [
            {
                "image_versions2": {"candidates": [{"url": "https://cdn.example.com/c1.jpg"}]},
                "video_dash_manifest": None,
            },
            {
                "image_versions2": {"candidates": [{"url": "https://cdn.example.com/c2.webp"}]},
                "video_dash_manifest": DASH_MANIFEST,
            },
        ],
        "video_dash_manifest": DASH_MANIFEST,
    }

    images = extract_images_from_post(single)
    assert images == [{"post_id": "111", "image_url": "https://cdn.example.com/a.jpg"}]
    assert extract_videos_from_post(single) == []

    carousel_images = extract_images_from_post(carousel)
    assert [item["image_url"] for item in carousel_images] == [
        "https://cdn.example.com/c1.jpg",
        "https://cdn.example.com/c2.webp",
    ]
    carousel_videos = extract_videos_from_post(carousel)
    assert any("clip.mp4" in item["video_url"] for item in carousel_videos)


def test_load_data_skips_blank_lines(tmp_path):
    path = tmp_path / "posts.jsonl"
    path.write_text('{"id": "1"}\n\n{"id": "2"}\n', encoding="utf-8")
    assert load_data(path) == [{"id": "1"}, {"id": "2"}]


def test_extract_from_api_payload_timeline_and_user():
    payload = {
        "data": {
            "user": {"username": "demo", "id": "1"},
            "xdt_api__v1__feed__user_timeline_graphql_connection": {
                "edges": [
                    {"node": {"id": "p1", "taken_at": 1700000000}},
                    {"node": None},
                ]
            },
        }
    }
    user, posts = extract_from_api_payload(payload)
    assert user["username"] == "demo"
    assert posts == [{"id": "p1", "taken_at": 1700000000}]


def test_extract_from_api_payload_ignores_non_dict():
    assert extract_from_api_payload(None) == (None, [])
    assert extract_from_api_payload({"status": "ok"}) == (None, [])


def test_is_content_accepts_profile_and_short_urls():
    assert is_content("/eye.on.palestine/p/abc/", "eye.on.palestine")
    assert is_content("/eye.on.palestine/reel/xyz/", "eye.on.palestine")
    assert is_content("/p/abc/", "eye.on.palestine")
    assert is_content("/reel/xyz/", "eye.on.palestine")
    assert not is_content("/eye.on.palestine/", "eye.on.palestine")
    assert not is_content(None, "eye.on.palestine")


def test_cookies_expired_checks_sessionid(tmp_path):
    missing = tmp_path / "missing.json"
    assert cookies_expired(str(missing)) is True

    fresh = tmp_path / "fresh.json"
    fresh.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "sessionid",
                        "value": "abc",
                        "expires": (datetime.now() + timedelta(days=30)).timestamp(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert cookies_expired(str(fresh)) is False

    session_cookie = tmp_path / "session.json"
    session_cookie.write_text(
        json.dumps({"cookies": [{"name": "sessionid", "value": "abc", "expires": -1}]}),
        encoding="utf-8",
    )
    assert cookies_expired(str(session_cookie)) is False

    stale = tmp_path / "stale.json"
    stale.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "sessionid",
                        "value": "abc",
                        "expires": (datetime.now() - timedelta(days=1)).timestamp(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert cookies_expired(str(stale)) is True


def test_reached_start_date_uses_oldest_captured_post(monkeypatch):
    import insta_scraper_poc as scraper

    monkeypatch.setattr(
        scraper,
        "post_data_list",
        [{"id": "new", "taken_at": 2000000000}, {"id": "old", "taken_at": 1000000000}],
    )
    assert scraper.reached_start_date("2023-10-07") is True
    monkeypatch.setattr(scraper, "post_data_list", [{"id": "new", "taken_at": 2000000000}])
    assert scraper.reached_start_date("2023-10-07") is False
    assert post_timestamp({"taken_at_timestamp": 123}) == 123
