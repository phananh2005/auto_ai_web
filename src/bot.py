def login(email, password):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, channel="msedge")
        page = browser.new_page()
        page.goto("https://accounts.x.ai/sign-in")
        
        page.get_by_role("button", name="Log in with your email").click()
        page.get_by_label("Email address").fill(email)
        page.get_by_label("Password").fill(password)
        page.get_by_role("button", name="Sign in").click()
        
        page.wait_for_timeout(30000)
