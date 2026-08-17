from playwright.sync_api import sync_playwright

from insta_scraper_poc import password_locator, username_locator


def test_instagram_login_form_is_fillable():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            )
        )
        page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
        username_locator(page).first.wait_for(state="visible", timeout=20000)
        password_locator(page).first.wait_for(state="visible", timeout=20000)
        username_locator(page).first.fill("course_bot_placeholder")
        password_locator(page).first.fill("not-a-real-password")
        assert username_locator(page).first.input_value() == "course_bot_placeholder"
        browser.close()
