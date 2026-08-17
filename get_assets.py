import argparse
import json
import os
from urllib.parse import urlparse, unquote

from bs4 import BeautifulSoup
import requests

from config import IMAGE_DIR, VIDEO_DIR, HEADERS

IMAGE_EXTENSIONS = (".jpeg", ".jpg", ".png", ".heic", ".webp")


def get_video_name(post_id: str, video_url: str) -> str:
    path = unquote(urlparse(video_url).path)
    video_name = os.path.basename(path) or "video.mp4"
    if ".mp4" in video_name:
        video_name = video_name[: video_name.lower().find(".mp4") + 4]
    elif not video_name.lower().endswith(".mp4"):
        video_name = f"{video_name}.mp4"
    return f"{post_id}_{video_name}"


def get_image_name(post_id: str, image_url: str) -> str:
    path = unquote(urlparse(image_url).path)
    image_name = os.path.basename(path)
    found_extension = None
    lower_name = image_name.lower()
    for extension in IMAGE_EXTENSIONS:
        if extension in lower_name:
            found_extension = extension
            image_name = image_name[: lower_name.find(extension)]
            break

    if not found_extension:
        raise ValueError(f"Could not find an image extension in {image_url}")
    return f"{post_id}_{image_name}.png"


def load_data(file_path):
    """loads list of dictionaries into memory"""
    data = []
    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def parse_video_urls(video_xml: str) -> list:
    if video_xml is None:
        return []
    soup = BeautifulSoup(video_xml, "xml")
    video_urls = [video_url_tag.contents[0] for video_url_tag in soup.find_all("BaseURL")]
    video_urls = list(set(video_urls))
    return video_urls


def extract_image_url(image_versions2):
    image_urls = image_versions2["candidates"]

    if not isinstance(image_urls, list):
        raise ValueError("image_versions2.candidates is not a list")

    if len(image_urls) == 0:
        raise ValueError("image_versions2.candidates is empty")

    image_url = image_urls[0]["url"]
    return image_url


def extract_images_from_post(post: dict) -> list[dict]:
    post_id = post["id"]
    image_urls = []

    if post.get("image_versions2") is not None:
        image_url = extract_image_url(post["image_versions2"])
        image_urls.append(image_url)
    if post.get("carousel_media") is not None:
        for each_item in post["carousel_media"]:
            if each_item.get("image_versions2") is not None:
                image_url = extract_image_url(each_item["image_versions2"])
                image_urls.append(image_url)

    this_post_image_metadata = [
        {"post_id": post_id, "image_url": image_url} for image_url in image_urls
    ]
    return this_post_image_metadata


def extract_videos_from_post(post: dict) -> list[dict]:
    post_id = post["id"]
    video_urls = []

    if post.get("video_dash_manifest") is not None:
        video_urls += parse_video_urls(post["video_dash_manifest"])

    if post.get("carousel_media") is not None:
        for each_item in post["carousel_media"]:
            video_urls += parse_video_urls(each_item.get("video_dash_manifest"))

    this_post_video_metadata = [
        {"post_id": post_id, "video_url": video_url} for video_url in video_urls
    ]
    return this_post_video_metadata


def fetch_images(images: list[dict], image_dir: str = IMAGE_DIR, record_in_db: bool = False) -> None:
    os.makedirs(image_dir, exist_ok=True)
    for image in images:
        image_name = get_image_name(post_id=image["post_id"], image_url=image["image_url"])
        image_full_path = os.path.join(image_dir, image_name)
        if record_in_db:
            from database import mark_media_downloaded, upsert_media

            upsert_media(image["post_id"], "image", image["image_url"])

        if os.path.exists(image_full_path):
            print("skipping (already downloaded)")
            if record_in_db:
                from database import mark_media_downloaded

                mark_media_downloaded(image["image_url"], image_full_path)
            continue

        print(f"downloading image {image['image_url']}...")
        resp = requests.get(image["image_url"], headers=HEADERS, timeout=60)
        resp.raise_for_status()

        with open(image_full_path, "wb") as binary_file:
            binary_file.write(resp.content)
        if record_in_db:
            from database import mark_media_downloaded

            mark_media_downloaded(image["image_url"], image_full_path)


def fetch_videos(videos: list[dict], video_dir: str = VIDEO_DIR, record_in_db: bool = False) -> None:
    os.makedirs(video_dir, exist_ok=True)
    for video in videos:
        video_name = get_video_name(post_id=video["post_id"], video_url=video["video_url"])
        video_full_path = os.path.join(video_dir, video_name)
        if record_in_db:
            from database import upsert_media

            upsert_media(video["post_id"], "video", video["video_url"])

        if os.path.exists(video_full_path):
            print("skipping (already downloaded)")
            if record_in_db:
                from database import mark_media_downloaded

                mark_media_downloaded(video["video_url"], video_full_path)
            continue

        print(f"downloading video {video['video_url']}...")
        resp = requests.get(video["video_url"], headers=HEADERS, timeout=120)
        resp.raise_for_status()

        with open(video_full_path, "wb") as binary_file:
            binary_file.write(resp.content)
        if record_in_db:
            from database import mark_media_downloaded

            mark_media_downloaded(video["video_url"], video_full_path)


def download_records(data: list[dict], image_dir: str, video_dir: str, record_in_db: bool = False) -> None:
    for record in data:
        try:
            images = extract_images_from_post(record)
        except Exception as exc:
            print(f"skipping images for post {record.get('id')}: {exc}")
            images = []
        try:
            videos = extract_videos_from_post(record)
        except Exception as exc:
            print(f"skipping videos for post {record.get('id')}: {exc}")
            videos = []
        fetch_images(images, image_dir, record_in_db=record_in_db)
        fetch_videos(videos, video_dir, record_in_db=record_in_db)


def download_from_db(image_dir: str = IMAGE_DIR, video_dir: str = VIDEO_DIR) -> None:
    from database import init_db, list_posts

    init_db()
    rows = list_posts()
    data = [json.loads(row["raw_json"]) for row in rows]
    print(f"downloading media for {len(data)} posts from the database")
    download_records(data, image_dir, video_dir, record_in_db=True)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download images and videos from the database or a content metadata JSONL file."
    )
    parser.add_argument(
        "--input",
        "-i",
        help="Path to the *_content_metadata.jsonl file produced by insta_scraper_poc.py",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Download media for every post stored in scraper.db",
    )
    parser.add_argument("--image-dir", default=IMAGE_DIR)
    parser.add_argument("--video-dir", default=VIDEO_DIR)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.from_db or not args.input:
        download_from_db(args.image_dir, args.video_dir)
    else:
        data = load_data(args.input)
        download_records(data, args.image_dir, args.video_dir)
