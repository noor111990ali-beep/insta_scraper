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
from database import (
    describe_database,
    init_db,
    list_channels,
    status_summary,
    upsert_channel,
)

EXAMPLE_CONFIG = os.path.join(BASE_DIR, "dhs622_config.cfg.example")
LOCAL_CONFIG = os.path.join(BASE_DIR, "dhs622_config.cfg")
EXAMPLE_CHANNELS = os.path.join(BASE_DIR, "channels.txt.example")

DATABASE_SECTION = """
[database]
# Uses the PostgreSQL you already installed. setup.py will create this database.
type = postgres
host = localhost
port = 5432
name = insta_scraper
user = postgres
password = your_postgres_password
"""


def ensure_starter_files() -> None:
    if not os.path.isfile(LOCAL_CONFIG) and os.path.isfile(EXAMPLE_CONFIG):
        shutil.copyfile(EXAMPLE_CONFIG, LOCAL_CONFIG)
    elif os.path.isfile(LOCAL_CONFIG):
        _ensure_database_section(LOCAL_CONFIG)
    if not os.path.isfile(CHANNELS_FILE) and os.path.isfile(EXAMPLE_CHANNELS):
        shutil.copyfile(EXAMPLE_CHANNELS, CHANNELS_FILE)


def _ensure_database_section(path: str) -> None:
    import configparser

    parser = configparser.ConfigParser()
    parser.read(path)
    if parser.has_section("database"):
        return
    with open(path, "a", encoding="utf-8") as config_file:
        config_file.write("\n" + DATABASE_SECTION)


def sync_channels_file_to_db(start_date: str | None = None, db_path: str | None = None) -> list[str]:
    handles = load_channels()
    for handle in handles:
        upsert_channel(handle, start_date=start_date, db_path=db_path)
    return handles


def checklist(db_path: str | None = None) -> dict:
    ensure_starter_files()
    db_error = None
    try:
        init_db(db_path)
        handles = sync_channels_file_to_db(start_date=scrape_start_date, db_path=db_path)
        if not handles:
            handles = list_channels(db_path)
    except Exception as exc:
        db_error = str(exc)
        handles = load_channels()

    ready = has_instagram_credentials() and bool(handles) and not db_error
    return {
        "ready": ready,
        "database": describe_database(db_path),
        "sqlite_path": db_path,
        "db_error": db_error,
        "config_file": CONFIG_PATH or LOCAL_CONFIG,
        "has_instagram_login": has_instagram_credentials(),
        "instagram_username": insta_username if has_instagram_credentials() else None,
        "channels_file": CHANNELS_FILE,
        "channels": handles,
    }


def print_checklist(info: dict) -> None:
    print("Instagram scraper setup")
    print("=======================")
    print(f"Database: {info['database']}")
    if info.get("db_error"):
        print("  Could not create or open the dedicated Postgres database yet.")
        print(f"  {info['db_error']}")
        print("  In dhs622_config.cfg, under [database], set user and password to the")
        print("  same ones you use in pgAdmin / psql. Then run python setup.py again.")
        print("  setup.py will create a database named insta_scraper for this project.")
    elif info.get("sqlite_path"):
        print("  Using a local SQLite file (this is for tests or a fallback).")
    else:
        print("  A dedicated database named insta_scraper is created for this project.")
        print("  You do not need to create it by hand in pgAdmin.")
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
        summary = status_summary(info.get("sqlite_path"))
        print(
            f"Currently stored: {summary['channels']} channels, "
            f"{summary['posts']} posts, {summary['downloaded']}/{summary['media']} files downloaded"
        )
    else:
        print("Not ready yet. Fix the items above, then run python setup.py again.")


if __name__ == "__main__":
    info = checklist()
    print_checklist(info)
    raise SystemExit(0 if info["ready"] else 1)
