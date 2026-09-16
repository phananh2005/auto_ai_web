def login(email, password, log=print):
    from playwright.sync_api import sync_playwright
    log("Đang khởi động trình duyệt...")
    with sync_playwright() as p:
        import os
        # Dùng một thư mục profile riêng trong code để lưu tài khoản mà không bị đụng Chrome máy
        user_data_dir = os.path.join(os.getcwd(), "chrome_profile")
        
        try:
            browser = p.chromium.launch_persistent_context(
                user_data_dir, 
                channel="chrome", 
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
        except Exception as e:
            if "pass --user-data-dir" in str(e) or "locked" in str(e).lower():
                raise Exception("Lỗi: Bạn phải TẮT HOÀN TOÀN trình duyệt Chrome trước khi chạy (đóng mọi cửa sổ Chrome).")
            else:
                raise e
            
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        import random
        def wait_human():
            page.wait_for_timeout(random.randint(1000, 3000))
            
        log("Đang mở trang đăng nhập...")
        page.goto("https://accounts.x.ai/sign-in")
        wait_human()
        
        log("Đang điền thông tin...")
        page.get_by_test_id("continue-with-email").click()
        wait_human()
        
        page.locator("#email").fill(email)
        wait_human()
        
        log("Đang bấm Next...")
        page.get_by_test_id("sign-in-submit").click()
        wait_human()
        
        page.locator('input[type="password"]').fill(password)
        wait_human()
        
        log("Chờ xử lý xác minh (có thể có Cloudflare)...")
        page.wait_for_timeout(random.randint(5000, 8000))
        
        try:
            cb = page.locator('input[aria-label="Xác minh bạn là con người"]')
            if cb.is_visible():
                log("Đang ấn xác minh con người...")
                cb.click()
                page.wait_for_timeout(random.randint(3000, 5000))
            else:
                for frame in page.frames:
                    fcb = frame.locator('input[type="checkbox"]')
                    if fcb.count() > 0 and fcb.first.is_visible():
                        log("Đang ấn xác minh con người (iframe)...")
                        fcb.first.click()
                        page.wait_for_timeout(random.randint(3000, 5000))
                        break
        except Exception:
            pass
        
        log("Đang bấm nút Sign in...")
        page.get_by_test_id("sign-in-submit").click()
        
        log("Xong bước điền. Đang giữ trình duyệt...")
        page.wait_for_timeout(30000)
        log("Đã kết thúc.")
