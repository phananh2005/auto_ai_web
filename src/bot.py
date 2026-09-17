def login(email, password, log=print):
    from playwright.sync_api import sync_playwright
    log("🚀 Khởi động trình duyệt...")
    with sync_playwright() as p:
        try:
            # Khởi chạy trình duyệt (luôn ẩn danh / không lưu lịch sử)
            browser = p.chromium.launch(
                channel="chrome", 
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context() # new_context() mặc định là ẩn danh
            page = context.new_page()
        except Exception as e:
            raise Exception(f"Lỗi khởi động trình duyệt: {str(e)}")
        
        import random
        def wait_human():
            page.wait_for_timeout(random.randint(1000, 3000))
            
        log("🌐 Đang mở trang đăng nhập X...")
        page.goto("https://accounts.x.ai/sign-in")
        wait_human()
        
        log("✍️ Đang nhập email...")
        page.get_by_test_id("continue-with-email").click()
        wait_human()
        
        page.locator("#email").fill(email)
        wait_human()
        
        log("🔑 Đang nhập mật khẩu...")
        page.get_by_test_id("sign-in-submit").click()
        wait_human()
        
        page.locator('input[type="password"]').fill(password)
        wait_human()
        
        log("⏳ Chờ xử lý xác minh bảo mật (Cloudflare/Captcha)...")
        page.wait_for_timeout(random.randint(5000, 8000))
        
        try:
            cb = page.locator('input[aria-label="Xác minh bạn là con người"]')
            if cb.is_visible():
                log("🤖 Đang click xác minh con người...")
                cb.click()
                page.wait_for_timeout(random.randint(3000, 5000))
            else:
                for frame in page.frames:
                    fcb = frame.locator('input[type="checkbox"]')
                    if fcb.count() > 0 and fcb.first.is_visible():
                        log("🤖 Đang click xác minh con người (iframe)...")
                        fcb.first.click()
                        page.wait_for_timeout(random.randint(3000, 5000))
                        break
        except Exception:
            pass
        
        log("➡️ Đang gửi yêu cầu đăng nhập...")
        page.get_by_test_id("sign-in-submit").click()
        
        log("⏳ Đang chờ chuyển hướng vào tài khoản...")
        try:
            # Đợi trình duyệt nhảy sang link có chữ "account" (tối đa 15s)
            page.wait_for_url("**/account**", timeout=15000)
            log(f"✅ Đăng nhập thành công! (URL: {page.url})")
        except Exception:
            log(f"⚠️ Chờ hơi lâu, URL hiện tại: {page.url}")
            
        if "account" not in page.url:
            log("❌ Đăng nhập thất bại (sai pass hoặc kẹt captcha). Dừng lại.")
            return None, False

        
        log("🌐 Chuyển sang trang grok.com...")
        grok_page = context.new_page()
        grok_page.goto("https://grok.com/")
        
        log("🔍 Đang tải trang Grok và kiểm tra cài đặt...")
        try:
            # Chọn div chứa tên bằng tổ hợp class (không dùng nội dung text hay avatar)
            grok_page.locator('div.min-w-0.flex-1.overflow-hidden:has(span.text-fg-primary)').click(timeout=30000)
            log("🖱️ Đã mở menu tài khoản.")
            
            grok_page.wait_for_timeout(1000) # Đợi menu mở ra
            grok_page.locator('div[role="menuitem"]:has(path[d^="m13.456"])').click(timeout=10000)
            log("⚙️ Đã mở bảng Cài đặt.")
            
            grok_page.wait_for_timeout(3000) # Đợi bảng cài đặt hiện ra
            if grok_page.locator('text="Nhận SuperGrok"').count() > 0:
                log(f"⚪ THƯỜNG: {email} | {password} (Chưa có SuperGrok)")
                has_sg = False
            elif grok_page.locator('text="SuperGrok"').count() > 0:
                log(f"🌟 SUPERGROK: {email} | {password} (ĐÃ CÓ SuperGrok)")
                has_sg = True
            else:
                log(f"⚠️ KHÔNG RÕ TRẠNG THÁI: {email} | {password} (Không tìm thấy label SuperGrok)")
                has_sg = False
                
        except Exception as e:
            log(f"⛔ Lỗi khi kiểm tra trạng thái Grok: {e}")
            has_sg = None
        
        log("✅ Hoàn tất. Đang quay về tab tài khoản...")
        grok_page.close()
        page.bring_to_front()
        page.wait_for_timeout(2000)
        
        signed_out = False
        try:
            log("🔌 Đang click nút 'Sign out of all devices'...")
            # Nút có text "Sign out of all devices"
            page.locator('button:has-text("Sign out of all devices")').click(timeout=10000)
            page.wait_for_timeout(2000)
            log("✅ Đã Sign out thành công.")
            signed_out = True
        except Exception as e:
            log(f"⚠️ Không thể click nút Sign out: {e}")

        log("🛑 Kết thúc tiến trình.")
        return has_sg, signed_out
