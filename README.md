# Instagram scraper (DHS622 / Social Media Exposed, Chapter 7)

Python proof-of-concept that logs into Instagram with Playwright, intercepts GraphQL/API responses while scrolling a profile, and then downloads images and videos from the saved metadata.

Use an Instagram account you control, and only scrape accounts you are allowed to collect for the course. Instagram may challenge logins from new browsers or datacenter IPs; if that happens, run once with `--headed` on your own machine and reuse the saved cookies.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Copy the example config and put in the Instagram username/password for the account you will log in with:

```bash
cp dhs622_config.cfg.example dhs622_config.cfg
```

You can also keep the file at `~/dhs622_config.cfg` (the original course location) or set `INSTAGRAM_USERNAME` and `INSTAGRAM_PASSWORD`.

## Scrape a profile

```bash
python insta_scraper_poc.py --handle eye.on.palestine --start-date 2023-10-07 --max-scrolls 20
```

- `--headed` shows the browser (needed if Instagram asks for extra verification).
- `--headless` hides it (default when no display is attached).
- Posts are appended to `HANDLE_content_metadata.jsonl` and `HANDLE_user_metadata.jsonl`.
- Login cookies are saved as `login_cookies_USERNAME.json` so later runs can skip the login form.

The loop stops after `--max-scrolls`, after three scrolls with no new posts, or once it sees content older than `--start-date`.

## Download media

```bash
python get_assets.py --input eye.on.palestine_content_metadata.jsonl
```

Files go to `downloads/images` and `downloads/videos` by default.

## Tests

```bash
python -m pytest -q
```
