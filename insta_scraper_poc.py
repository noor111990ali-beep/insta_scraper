from playwright.sync_api import Playwright, sync_playwright, expect
from config import insta_username, insta_password, require_instagram_credentials
import argparse
import functools
import time
import os
import json
from datetime import datetime, timezone
from typing import Optional

user_data_list = []
post_data_list = []
user_jsonl_path = ""
content_jsonl_path = ""

API_ENDPOINTS = (
    "https://www.instagram.com/api/graphql",
    "https://www.instagram.com/api/v1",
    "https://www.instagram.com/graphql",
)

LOGIN_USERNAME_LABELS = (
    "Phone number, username, or email",
    "Mobile phone, username or email",
    "Mobile number, username or email",
)

POPUP_BUTTON_NAMES = (
    "Allow all cookies",
    "Decline optional cookies",
    "Allow essential cookies",
    "Not Now",
    "Not now",
    "Save Info",
)


def save_user_metadata(user_record: dict):
    with open(user_jsonl_path, "a") as my_file:
        my_file.write(json.dumps(user_record) + "\n")


def save_content_metadata(content_records: list[dict]):
    with open(content_jsonl_path, "a") as my_file:
        for content_record in content_records:
            my_file.write(json.dumps(content_record) + "\n")


def extract_from_api_payload(data: dict) -> tuple[Optional[dict], list[dict]]:
    """Pull user + timeline posts out of an Instagram GraphQL/API JSON body."""
    if not isinstance(data, dict):
        return None, []

    payload = data.get("data")
    if not isinstance(payload, dict):
        return None, []

    user_data = payload.get("user") if isinstance(payload.get("user"), dict) else None
    posts: list[dict] = []

    timeline = payload.get("xdt_api__v1__feed__user_timeline_graphql_connection")
    if isinstance(timeline, dict) and isinstance(timeline.get("edges"), list):
        posts.extend(
            edge["node"]
            for edge in timeline["edges"]
            if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
        )

    if user_data:
        older_timeline = user_data.get("edge_owner_to_timeline_media")
        if isinstance(older_timeline, dict) and isinstance(older_timeline.get("edges"), list):
            posts.extend(
                edge["node"]
                for edge in older_timeline["edges"]
                if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
            )

    return user_data, posts


def intercept_response(response):
    try:
        url = response.url
        if not any(url.startswith(endpoint) for endpoint in API_ENDPOINTS):
            return None
        if response.request.resource_type not in ("xhr", "fetch"):
            return None

        data = response.json()
        user_data, content_records = extract_from_api_payload(data)

        if user_data is not None:
            print(user_data)
            save_user_metadata(user_data)
            user_data_list.append(user_data)
            print("=============================")

        if content_records:
            save_content_metadata(content_records)
            post_data_list.extend(content_records)
            for content_record in content_records:
                print(content_record)
                print("=============================")
    except Exception as exc:
        print(f"skipping response ({response.url}): {exc}")
    return None


def pause_scraper(seconds_before: int, seconds_after: int):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if seconds_before > 0:
                print(f"sleeping {seconds_before} seconds before")
                time.sleep(seconds_before)

            result = func(*args, **kwargs)

            if seconds_after > 0:
                print(f"sleeping {seconds_after} seconds after")
                time.sleep(seconds_after)

            return result

        return wrapper

    return decorator


def cookies_expired(auth_json_path: str) -> bool:
    if not os.path.exists(auth_json_path):
        return True

    with open(auth_json_path, "r") as f:
        auth_dict = json.load(f)

    cookies = {cookie["name"]: cookie for cookie in auth_dict.get("cookies", [])}
    session = cookies.get("sessionid")
    if session is None or not session.get("value"):
        return True

    expires = session.get("expires", -1)
    try:
        expires_value = float(expires)
    except (TypeError, ValueError):
        return False
    if expires_value <= 0:
        return False
    return datetime.fromtimestamp(expires_value) < datetime.now()


def dismiss_popups(page) -> None:
    for name in POPUP_BUTTON_NAMES:
        try:
            button = page.get_by_role("button", name=name)
            if button.count() and button.first.is_visible():
                button.first.click(timeout=2000)
                time.sleep(1)
        except Exception:
            continue


def username_locator(page):
    return page.locator('input[name="username"], input[name="email"]')


def password_locator(page):
    return page.locator('input[name="password"], input[name="pass"]')


def visible_login_username_label(page) -> Optional[str]:
    for label in LOGIN_USERNAME_LABELS:
        try:
            locator = page.get_by_label(label)
            if locator.count() and locator.first.is_visible():
                return label
        except Exception:
            continue
    return None


def need_to_log_in(page) -> bool:
    if "accounts/login" in page.url:
        return True

    try:
        username_box = username_locator(page)
        password_box = password_locator(page)
        if username_box.count() and password_box.count():
            if username_box.first.is_visible() and password_box.first.is_visible():
                return True
    except Exception:
        pass

    if visible_login_username_label(page) and page.get_by_label("Password").is_visible():
        if page.get_by_text("Log in", exact=True).is_visible():
            return True

    return False


@pause_scraper(0, 5)
def visit_target_home_page(page, handle: str):
    print(f"visiting home page of @{handle}...")
    seed_home_page_url = f"https://www.instagram.com/{handle}/"
    page.goto(seed_home_page_url, wait_until="domcontentloaded")
    dismiss_popups(page)
    time.sleep(5)

    current = page.url.split("?")[0].rstrip("/") + "/"
    expected = seed_home_page_url.rstrip("/") + "/"
    if expected not in current and not current.startswith(expected):
        raise Exception(f"Failed to load target home page (ended up at {page.url})")


@pause_scraper(5, 10)
def log_in_if_necessary(page, context, auth_json_path: str):
    dismiss_popups(page)
    if not need_to_log_in(page):
        print("No need to log in! Skipping...")
        return

    print(f"attempting login with account @{insta_username}...")
    username_locator(page).first.wait_for(state="visible", timeout=15000)
    username_input = username_locator(page)
    password_input = password_locator(page)

    if username_input.count() and username_input.first.is_visible():
        username_input.first.fill(insta_username)
    else:
        label = visible_login_username_label(page)
        if not label:
            raise Exception("Unexpected login layout")
        page.get_by_label(label).fill(insta_username)

    if password_input.count() and password_input.first.is_visible():
        password_input.first.fill(insta_password)
    else:
        page.get_by_label("Password").fill(insta_password)

    submit = page.locator('button[type="submit"], input[type="submit"]')
    if submit.count():
        submit.first.click()
    else:
        page.get_by_role("button", name="Log in").click()

    page.wait_for_timeout(5000)
    dismiss_popups(page)

    if any(token in page.url for token in ("challenge", "two_factor", "accounts/login")):
        if need_to_log_in(page) or "challenge" in page.url or "two_factor" in page.url:
            raise Exception(
                "Instagram requires extra verification (checkpoint/2FA). "
                "Log in once in a headed browser (`--headed`) and reuse the saved cookies."
            )

    context.storage_state(path=auth_json_path)


def is_content(relative_url: Optional[str], handle: str) -> bool:
    if not relative_url:
        return False
    if relative_url.startswith(f"/{handle}/p/") or relative_url.startswith(
        f"/{handle}/reel/"
    ):
        return True
    if relative_url.startswith("/p/") or relative_url.startswith("/reel/"):
        return True
    return False


def find_lowest_content(page, handle: str):
    a_tags = page.locator("a")
    count = a_tags.count()
    for i in range(count):
        j = count - 1 - i
        elt = a_tags.nth(j)
        href = elt.get_attribute("href")
        if is_content(href, handle):
            return elt
    return None


@pause_scraper(0, 5)
def scroll_down(page):
    print("scrolling down...")
    page.keyboard.down("PageDown")


@pause_scraper(0, 5)
def scroll_down_smart(lowest_content):
    print("scrolling down...")
    lowest_content.scroll_into_view_if_needed()
    return lowest_content


def post_timestamp(post: dict) -> Optional[int]:
    for key in ("taken_at", "taken_at_timestamp", "created_at"):
        value = post.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def reached_start_date(start_date: Optional[str]) -> bool:
    if not start_date or not post_data_list:
        return False
    cutoff = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    cutoff_ts = int(cutoff.timestamp())
    timestamps = [post_timestamp(post) for post in post_data_list]
    timestamps = [ts for ts in timestamps if ts is not None]
    if not timestamps:
        return False
    return min(timestamps) <= cutoff_ts


def run(
    playwright: Playwright,
    seed: dict,
    auth_json_path: str,
    headless: bool,
    max_scrolls: int,
) -> None:
    browser = playwright.chromium.launch(headless=headless)
    storage_state = (
        auth_json_path
        if os.path.exists(auth_json_path) and not cookies_expired(auth_json_path)
        else None
    )
    context = browser.new_context(
        viewport={"width": 800, "height": 600},
        storage_state=storage_state,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/128.0.0.0 Safari/537.36"
        ),
        locale="en-US",
    )
    page = context.new_page()
    page.on("response", intercept_response)

    page.goto("https://www.instagram.com", wait_until="domcontentloaded")
    log_in_if_necessary(page, context, auth_json_path)
    dismiss_popups(page)

    home = page.get_by_label("Home")
    try:
        expect(home.first).to_be_visible(timeout=30000)
    except Exception:
        if "accounts/login" in page.url or need_to_log_in(page):
            raise
        print("Home icon not found; continuing after login anyway")
    context.storage_state(path=auth_json_path)

    visit_target_home_page(page, seed["handle"])
    expect(page.get_by_text(seed["handle"])).to_be_visible()

    seen = 0
    stale_rounds = 0
    for scroll_index in range(max_scrolls):
        lowest_content = find_lowest_content(page, seed["handle"])
        if lowest_content is None:
            if scroll_index == 0:
                raise Exception("No posts found in content gallery")
            print("no more posts found; stopping")
            break

        scroll_down_smart(lowest_content)

        if reached_start_date(seed.get("start_date")):
            print(f"reached start_date {seed['start_date']}; stopping")
            break

        if len(post_data_list) == seen:
            stale_rounds += 1
            if stale_rounds >= 3:
                print("no new posts after several scrolls; stopping")
                break
        else:
            stale_rounds = 0
            seen = len(post_data_list)
            print(f"captured {seen} posts so far (scroll {scroll_index + 1}/{max_scrolls})")

    print(f"done. saved {len(post_data_list)} posts to {content_jsonl_path}")
    context.storage_state(path=auth_json_path)
    context.close()
    browser.close()


def parse_args():
    default_headless = not os.environ.get("DISPLAY")
    parser = argparse.ArgumentParser(
        description="Log into Instagram and scrape a profile's posts via intercepted API responses."
    )
    parser.add_argument("--handle", default="eye.on.palestine", help="Instagram username to scrape")
    parser.add_argument("--start-date", default="2023-10-07", help="Stop after reaching this YYYY-MM-DD")
    parser.add_argument("--max-scrolls", type=int, default=20, help="Maximum gallery scroll steps")
    parser.add_argument("--headed", action="store_true", help="Show the browser window")
    parser.add_argument("--headless", action="store_true", help="Run without a browser window")
    args = parser.parse_args()
    if args.headed and args.headless:
        parser.error("use either --headed or --headless, not both")
    args.headless_mode = default_headless if not args.headed and not args.headless else args.headless or not args.headed
    return args


if __name__ == "__main__":
    args = parse_args()
    require_instagram_credentials()

    auth_json_path = os.path.join(
        os.path.dirname(__file__), f"login_cookies_{insta_username}.json"
    )
    seed = {"handle": args.handle.lstrip("@"), "start_date": args.start_date}

    user_jsonl_path = os.path.join(
        os.path.dirname(__file__), f"{seed['handle']}_user_metadata.jsonl"
    )
    content_jsonl_path = os.path.join(
        os.path.dirname(__file__), f"{seed['handle']}_content_metadata.jsonl"
    )

    with sync_playwright() as playwright:
        run(playwright, seed, auth_json_path, args.headless_mode, args.max_scrolls)
