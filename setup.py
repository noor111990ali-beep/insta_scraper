import os
import shutil

from channels import CHANNELS_FILE, load_channels
from config import (
    BASE_DIR,
    CONFIG_PATH,
    has_instagram_credentials,
    insta_username,
    scrape_start_date,
)
from database import DB_PATH, init_db, list_channels, status_summary, upsert_channel


EXAMPLE_CONFIG = os.path.join(BASE_DIR, "dhs622_config.cfg.example")
LOCAL_CONFIG = os.path.join(BASE_DIR, "dhs622_config.cfg")
EXAMPLE_CHANNELS = os.path.join(BASE_DIR, "channels.txt.example")


def ensure_starter_files() -> None:
    if not os.path.isfile(LOCAL_CONFIG) and os.path.isfile(EXAMPLE_CONFIG):
        shutil.copyfile(EXAMPLE_CONFIG, LOCAL_CONFIG)
    if not os.path.isfile(CHANNELS_FILE) and os.path.isfile(EXAMPLE_CHANNELS):
        shutil.copyfile(EXAMPLE_CHANNELS, CHANNELS_FILE)


def sync_channels_file_to_db(start_date: str | None = None, db_path: str | None = None) -> list[str]:
    handles = load_channels()
    for handle in handles:
        upsert_channel(handle, start_date=start_date, db_path=db_path)
    return handles


def checklist(db_path: str | None = None) -> dict:
    ensure_starter_files()
    init_db(db_path)
    handles = sync_channels_file_to_db(start_date=scrape_start_date, db_path=db_path)
    if not handles:
        handles = list_channels(db_path)
    ready = has_instagram_credentials() and bool(handles)
    return {
        "ready": ready,
        "database": db_path or DB_PATH,
        "config_file": CONFIG_PATH or LOCAL_CONFIG,
        "has_instagram_login": has_instagram_credentials(),
        "instagram_username": insta_username if has_instagram_credentials() else None,
        "channels_file": CHANNELS_FILE,
        "channels": handles,
    }


def print_checklist(info: dict) -> None:
    print("Instagram scraper setup")
    print("=======================")
    print(f"Database file: {info['database']}")
    print("  This is created for you. You do not need to install MySQL or anything else.")
    print()
    if info["has_instagram_login"]:
        print(f"Instagram login: ready (@{info['instagram_username']})")
    else:
        print("Instagram login: missing")
        print("  Open dhs622_config.cfg and replace the example username and password")
        print("  with the Instagram account YOU will log in with.")
        print("  Do not put your password in GitHub.")
    print()
    if info["channels"]:
        print("Channels to scrape:")
        for handle in info["channels"]:
            print(f"  - @{handle}")
    else:
        print("Channels to scrape: missing")
        print("  Open channels.txt and put one Instagram username per line, for example:")
        print("    nasa")
        print("    natgeo")
        print("  You can also paste profile URLs. Lines starting with # are ignored.")
    print()
    if info["ready"]:
        print("You are ready. Run:  python run.py")
        summary = status_summary(info["database"])
        print(
            f"Currently stored: {summary['channels']} channels, "
            f"{summary['posts']} posts, {summary['downloaded']}/{summary['media']} files downloaded"
        )
    else:
        print("Not ready yet. Add the missing login and/or channel list, then run python setup.py again.")


if __name__ == "__main__":
    info = checklist()
    print_checklist(info)
    raise SystemExit(0 if info["ready"] else 1)
