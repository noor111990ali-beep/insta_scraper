import argparse
import os
import sys

from config import (
    download_media,
    insta_username,
    require_instagram_credentials,
    scrape_max_scrolls,
    scrape_start_date,
)
from database import finish_run, init_db, set_scrape_context, start_run, upsert_channel
from get_assets import download_from_db
from setup import checklist, print_checklist


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check setup, scrape every channel in channels.txt, and save results to the database."
    )
    parser.add_argument("--status", action="store_true", help="Only show whether login and channels are ready")
    parser.add_argument("--skip-download", action="store_true", help="Scrape metadata only; do not download files")
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    parser.add_argument("--headless", action="store_true", help="Hide the browser window")
    parser.add_argument("--max-scrolls", type=int, default=None)
    parser.add_argument("--start-date", default=None)
    args = parser.parse_args()
    if args.headed and args.headless:
        parser.error("use either --headed or --headless, not both")
    default_headless = not os.environ.get("DISPLAY")
    args.headless_mode = (
        default_headless
        if not args.headed and not args.headless
        else args.headless or not args.headed
    )
    return args


def main():
    args = parse_args()
    info = checklist()
    print_checklist(info)
    if args.status:
        raise SystemExit(0 if info["ready"] else 1)
    if not info["ready"]:
        raise SystemExit(1)

    require_instagram_credentials()
    init_db()

    from insta_scraper_poc import create_browser, scrape_handle, set_output_paths
    from playwright.sync_api import sync_playwright

    start_date = args.start_date or scrape_start_date
    max_scrolls = args.max_scrolls or scrape_max_scrolls
    auth_json_path = os.path.join(
        os.path.dirname(__file__), f"login_cookies_{insta_username}.json"
    )
    run_id = start_run()
    try:
        with sync_playwright() as playwright:
            browser, context, page = create_browser(
                playwright, auth_json_path, args.headless_mode
            )
            try:
                for handle in info["channels"]:
                    print(f"\n=== scraping @{handle} ===")
                    set_output_paths(handle)
                    set_scrape_context(run_id, handle)
                    upsert_channel(handle, start_date=start_date)
                    scrape_handle(
                        page,
                        {"handle": handle, "start_date": start_date},
                        max_scrolls,
                    )
            finally:
                context.storage_state(path=auth_json_path)
                context.close()
                browser.close()

        if download_media and not args.skip_download:
            print("\nDownloading images and videos into downloads/ ...")
            download_from_db()

        finish_run(run_id, "ok")
        print("\nFinished. Run python setup.py to see how many posts are stored.")
    except Exception as exc:
        finish_run(run_id, "error", str(exc))
        print(f"\nThe scrape stopped because: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
