def login(browser, email, password, log=print, auto_change=False, new_pwd=""):
    # Dummy block to preserve indentation
    if True:
        try:
            # Không khởi tạo browser ở đây nữa, dùng chung browser được truyền vào
            context = browser.new_context() # new_context() mặc định là ẩn danh
            page = context.new_page()
            
            def handle_cap(loc):
                log("🤖 Tự động click Captcha ngầm...")
                loc.click()
                page.wait_for_timeout(3000)
            page.add_locator_handler(page.locator('input[aria-label="Xác minh bạn là con người"]'), handle_cap)
            for i in range(5):
                page.add_locator_handler(page.frame_locator('iframe').nth(i).locator('input[type="checkbox"]'), handle_cap)
        except Exception as e:
            raise Exception(f"Lỗi tạo context: {str(e)}")
        
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
            has_sg = False
        
        grok_page.close()
        
        if not has_sg:
            log("🛑 Tài khoản KHÔNG CÓ SuperGrok. Dừng xử lý các bước tiếp theo.")
            if 'context' in locals(): context.close()
            return False, False, False
            
        log("✅ Hoàn tất check Grok. Đang quay về tab tài khoản...")
        page.bring_to_front()
        page.wait_for_timeout(2000)
        
        signed_out = False
        pwd_changed = False
        try:
            log("🔌 Đang click nút 'Sign out of all devices'...")
            # Nút có text "Sign out of all devices"
            page.locator('button:has-text("Sign out of all devices")').click(timeout=10000)
            page.wait_for_timeout(2000)
            log("✅ Đã Sign out thành công.")
            signed_out = True
            
            if auto_change and new_pwd:
                if not signed_out:
                    log("🛑 Lỗi Sign Out. Hủy thao tác đổi mật khẩu.")
                    if 'context' in locals(): context.close()
                    return has_sg, False, False
                    
                log("🔄 Đang click nút Change mật khẩu...")
                try:
                    page.locator('#security button:has-text("Change")').click(timeout=10000)
                    page.wait_for_timeout(2000)
                    
                    # Điền form đổi mật khẩu
                    page.locator('input[name="oldPassword"]').fill(password)
                    page.wait_for_timeout(500)
                    page.locator('input[name="password"]').fill(new_pwd)
                    page.wait_for_timeout(500)
                    page.locator('button:has-text("Save password")').click(timeout=10000)
                    page.wait_for_timeout(2000)
                    log("✅ Đã gửi yêu cầu lưu mật khẩu mới.")
                    pwd_changed = True
                except Exception as e:
                    log(f"⚠️ Lỗi khi đổi mật khẩu: {e}")
                    
        except Exception as e:
            log(f"⚠️ Không thể click nút Sign out: {e}")

        log("🛑 Kết thúc tiến trình.")
        if 'context' in locals():
            context.close()
        return has_sg, signed_out, pwd_changed
