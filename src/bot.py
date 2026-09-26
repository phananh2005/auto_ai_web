"""Module tự động hóa cho X.ai và Grok sử dụng Playwright sync_api.

Cung cấp các hàm đơn nhiệm:
- login_xai: Đăng nhập X.ai
- check_supergrok: Kiểm tra gói SuperGrok trên Grok.com
- sign_out_all_devices: Đăng xuất tất cả thiết bị trên X.ai
- change_account_password: Đổi mật khẩu tài khoản X.ai
- execute_account_task: Điều phối tác vụ theo yêu cầu và trả về DataContract dict
- login: Hàm wrapper tương thích ngược
"""

import os
import random
import time
from datetime import datetime

from src.config import (
    CAPTCHA_SELECTORS,
    GROK_URL,
    SELECTORS,
    TIMEOUT_ACTION,
    TIMEOUT_MODAL,
    TIMEOUT_NAV,
    TIMEOUT_PAGE_LOAD,
    XAI_ACCOUNT_URL,
    XAI_SIGNIN_URL,
)


def mask_pwd(pwd: str) -> str:
    """Mask mật khẩu để không bao giờ ghi plaintext vào log."""
    return "***" if pwd else ""


def wait_human(page, min_ms: int = 2000, max_ms: int = 4000):
    """Mô phỏng độ trễ tự nhiên của người dùng."""
    try:
        page.wait_for_timeout(random.randint(min_ms, max_ms))
    except Exception:
        pass


def send_queue_msg(queue, msg_type: str, **kwargs):
    """Gửi message theo Queue Message Protocol nếu có queue."""
    if queue is None:
        return
    if hasattr(queue, "put"):
        try:
            queue.put({"type": msg_type, **kwargs})
        except Exception:
            pass
    elif callable(queue):
        # Tương thích với callback log dạng hàm log(msg)
        if msg_type == "LOG":
            try:
                queue(kwargs.get("text", ""))
            except Exception:
                pass


def queue_log(queue, account: str, text: str, level: str = "INFO"):
    """Ghi log qua queue an toàn."""
    send_queue_msg(queue, "LOG", account=account, text=text, level=level)


def capture_screenshot(page, account: str) -> str | None:
    """Chụp ảnh màn hình khi có lỗi và trả về đường dẫn tuyệt đối."""
    try:
        os.makedirs("screenshots", exist_ok=True)
        safe_account = account.replace("@", "_at_").replace(".", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.abspath(f"screenshots/error_{safe_account}_{timestamp}.png")
        page.screenshot(path=path)
        return path
    except Exception:
        return None


def solve_cloudflare(page, queue=None, email: str = "") -> bool:
    """Xử lý triệt để Cloudflare / Turnstile bằng thẻ bọc Turnstile Shadow DOM, đa selector và tọa độ mù."""
    try:
        clicked = False

        # Ưu tiên SỐ 1: Dùng Radar Javascript đo tọa độ thực tế của Shadow Host
        try:
            rect = page.evaluate("""() => {
                const input = document.querySelector('input[name="cf-turnstile-response"]');
                if (!input) return null;
                let host = input.previousElementSibling;
                if (!host || host.tagName !== 'DIV') host = input.parentElement;
                if (!host) return null;
                const r = host.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height};
            }""")

            if rect and rect["w"] > 10 and rect["h"] > 10:
                queue_log(queue, email, "🎯 Đã khóa mục tiêu Captcha bằng Radar. Đang khai hỏa...", level="WARN")
                cx = rect["x"] + rect["w"] / 2
                cy = rect["y"] + rect["h"] / 2
                try: page.mouse.move(cx, cy, steps=5)
                except Exception: pass
                for _ in range(3):
                    try: page.mouse.click(cx, cy, delay=100)
                    except Exception: pass
                    page.wait_for_timeout(500)
                clicked = True
        except Exception:
            pass

        if clicked:
            return True

        # Ưu tiên 2: Quét qua page và tất cả frames tìm CAPTCHA_SELECTORS thông thường
        if not clicked:
            frames_to_check = [page]
            try:
                raw_frames = page.frames() if callable(getattr(page, "frames", None)) else getattr(page, "frames", [])
                if hasattr(raw_frames, "__iter__"):
                    frames_to_check.extend([f for f in raw_frames if f is not None])
            except Exception:
                pass

            for f in frames_to_check:
                for sel in CAPTCHA_SELECTORS:
                    try:
                        loc = f.locator(sel).first
                        if loc.is_visible():
                            queue_log(queue, email, "🛡️ Đã phát hiện Captcha. Đang xử lý...", level="WARN")
                            for _ in range(3):
                                try:
                                    loc.click(force=True, timeout=1000)
                                except Exception:
                                    pass
                            clicked = True
                            break
                    except Exception:
                        pass
                if clicked:
                    break

        # Ưu tiên 3 (Dự phòng): TỌA ĐỘ MÙ quét all_iframes tìm từ khóa challenge/turnstile/arkose/cloudflare
        if not clicked:
            try:
                all_iframes = page.locator("iframe").all()
                target_kws = ("challenge", "turnstile", "arkose", "cloudflare")
                for iframe in all_iframes:
                    try:
                        src = (iframe.get_attribute("src", timeout=300) or "").lower()
                        title = (iframe.get_attribute("title", timeout=300) or "").lower()
                        if any(kw in src or kw in title for kw in target_kws):
                            box = iframe.bounding_box(timeout=500)
                            if box:
                                w = box.get("width", 0) if isinstance(box, dict) else getattr(box, "width", 0)
                                h = box.get("height", 0) if isinstance(box, dict) else getattr(box, "height", 0)
                                if w > 10 and h > 10:
                                    queue_log(queue, email, "🛡️ Đã phát hiện Captcha. Đang xử lý...", level="WARN")
                                    x = box.get("x", 0) if isinstance(box, dict) else getattr(box, "x", 0)
                                    y = box.get("y", 0) if isinstance(box, dict) else getattr(box, "y", 0)
                                    cx = x + w / 2
                                    cy = y + h / 2
                                    page.mouse.click(cx, cy)
                                    clicked = True
                                    break
                    except Exception:
                        pass
            except Exception:
                pass

        if clicked:
            try:
                page.wait_for_timeout(500)
            except Exception:
                pass

        return clicked
    except Exception:
        return False


def click_fallback(page, selectors: list[str], timeout: int = TIMEOUT_ACTION) -> bool:
    """Thử click bằng vòng lặp polling quét liên tục danh sách selectors trên page và tất cả iframes."""
    if not selectors:
        return False
    start_time = time.time()
    while (time.time() - start_time) < (timeout / 1000.0):
        solve_cloudflare(page)
        try:
            raw_frames = page.frames() if callable(getattr(page, "frames", None)) else getattr(page, "frames", [])
            frames_to_check = [page] + list(raw_frames)
        except Exception:
            frames_to_check = [page]

        for target in frames_to_check:
            for sel in selectors:
                try:
                    elements = target.locator(sel).all()
                    for el in elements:
                        if el.is_visible():
                            try:
                                page.wait_for_timeout(500)
                            except Exception:
                                pass
                            try:
                                el.click(timeout=2000, delay=100)
                                return True
                            except Exception:
                                try:  # Nếu bị chặn bởi overlay (popup), force click luôn
                                    el.click(timeout=2000, force=True)
                                    return True
                                except Exception:
                                    pass
                except Exception:
                    pass
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
    return False


def fill_fallback(page, selectors: list[str], value: str, timeout: int = TIMEOUT_ACTION) -> bool:
    """Thử điền văn bản bằng vòng lặp polling quét liên tục danh sách selectors trên page và tất cả iframes."""
    if not selectors:
        return False
    start_time = time.time()
    while (time.time() - start_time) < (timeout / 1000.0):
        solve_cloudflare(page)
        try:
            raw_frames = page.frames() if callable(getattr(page, "frames", None)) else getattr(page, "frames", [])
            frames_to_check = [page] + list(raw_frames)
        except Exception:
            frames_to_check = [page]

        for target in frames_to_check:
            for sel in selectors:
                try:
                    elements = target.locator(sel).all()
                    for el in elements:
                        if el.is_visible():
                            try:
                                page.wait_for_timeout(500)
                            except Exception:
                                pass
                            try:
                                el.fill(value, timeout=2000)
                                return True
                            except Exception:
                                try:  # Nếu bị chặn bởi overlay (popup), force fill luôn
                                    el.fill(value, timeout=2000, force=True)
                                    return True
                                except Exception:
                                    pass
                except Exception:
                    pass
        try:
            page.wait_for_timeout(500)
        except Exception:
            pass
    return False


def setup_captcha_handlers(page, queue=None, email: str = ""):
    """Đăng ký handler tự động xử lý Captcha Turnstile/Cloudflare xuyên suốt quá trình chạy."""
    def handle_cf_checkbox(loc):
        queue_log(queue, email, "🤖 Đang tự động xử lý Cloudflare ngầm...", level="WARN")
        try:
            if loc and loc.is_visible():
                for _ in range(3):
                    try:
                        loc.click(force=True, timeout=1000)
                    except Exception:
                        pass
        except Exception:
            pass
        solve_cloudflare(page, queue=queue, email=email)

    # Đăng ký handler tự động
    try:
        cf_text_loc = page.locator('text="Verify you are human", text="Xác minh bạn là con người"').first
        page.add_locator_handler(cf_text_loc, handle_cf_checkbox)
    except Exception:
        pass

    try:
        cf_inner_loc = page.frame_locator('iframe').locator(
            'text="Verify you are human", text="Xác minh bạn là con người"'
        ).first
        page.add_locator_handler(cf_inner_loc, handle_cf_checkbox)
    except Exception:
        pass


def login_xai(page, email: str, password: str, queue=None) -> bool:
    """Đăng nhập X.ai đến khi xuất hiện URL chứa 'account'.

    Trả về:
        bool: True nếu đăng nhập thành công, False nếu thất bại.
    """
    try:
        setup_captcha_handlers(page, queue=queue, email=email)
        queue_log(queue, email, "🌐 Đang mở trang đăng nhập X.ai...")
        page.goto(XAI_SIGNIN_URL, timeout=TIMEOUT_PAGE_LOAD)

        # Xử lý Cloudflare chủ động ngay khi load trang
        solve_cloudflare(page, queue=queue, email=email)
        wait_human(page)

        # Nếu đã ở trang account từ trước
        if "account" in page.url and "sign-in" not in page.url.lower():
            queue_log(queue, email, f"✅ Đã ở trang tài khoản! (URL: {page.url})")
            return True

        queue_log(queue, email, "✍️ Đang nhập email...")
        if not click_fallback(page, SELECTORS["continue_email"], timeout=TIMEOUT_ACTION):
            queue_log(queue, email, "⚠️ Nút 'Continue with email' không tìm thấy, thử tìm ô email trực tiếp...", level="WARN")
            solve_cloudflare(page, queue=queue, email=email)

        wait_human(page)
        if not fill_fallback(page, SELECTORS["email_input"], email, timeout=TIMEOUT_ACTION):
            queue_log(queue, email, "❌ Không thể điền email vào form", level="ERROR")
            return False

        wait_human(page)
        solve_cloudflare(page, queue=queue, email=email)
        if not click_fallback(page, SELECTORS["signin_submit"], timeout=TIMEOUT_ACTION):
            queue_log(queue, email, "❌ Không tìm thấy nút Tiếp tục (Submit email)", level="ERROR")
            return False
        wait_human(page)

        queue_log(queue, email, f"🔑 Đang nhập mật khẩu ({mask_pwd(password)})...")
        if not fill_fallback(page, SELECTORS["password_input"], password, timeout=TIMEOUT_ACTION):
            queue_log(queue, email, "❌ Không thể điền mật khẩu vào form", level="ERROR")
            return False

        wait_human(page)
        queue_log(queue, email, "➡️ Đang gửi yêu cầu đăng nhập...")
        solve_cloudflare(page, queue=queue, email=email)

        # Ấn Enter trực tiếp từ bàn phím để submit form đáng tin cậy hơn
        try:
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
        except Exception:
            pass

        # Dự phòng nếu Enter chưa kích hoạt chuyển trang: tìm và click nút Đăng nhập
        if not (("account" in page.url and "sign-in" not in page.url.lower()) or "grok.com" in page.url):
            if not click_fallback(page, SELECTORS["signin_submit"], timeout=TIMEOUT_ACTION):
                if not (("account" in page.url and "sign-in" not in page.url.lower()) or "grok.com" in page.url):
                    queue_log(queue, email, "❌ Không tìm thấy nút Đăng nhập (Submit password)", level="ERROR")
                    return False

        queue_log(queue, email, "⏳ Đang chờ chuyển hướng vào tài khoản...")
        start_wait = time.time()
        nav_success = False
        while time.time() - start_wait < 15:
            if ("account" in page.url and "sign-in" not in page.url.lower()) or "grok.com" in page.url:
                nav_success = True
                break
            solve_cloudflare(page, queue=queue, email=email)
            page.wait_for_timeout(500)

        if nav_success:
            queue_log(queue, email, f"✅ Đăng nhập thành công! (URL: {page.url})")
            return True

        queue_log(queue, email, f"❌ Đăng nhập thất bại (URL hiện tại: {page.url})", level="WARN")
        return False

    except Exception as e:
        queue_log(queue, email, f"⛔ Lỗi đăng nhập: {str(e)}", level="ERROR")
        return False


def check_supergrok(context, email: str, queue=None) -> str:
    """Mở tab grok.com, kiểm tra trạng thái SuperGrok và đóng tab.

    Trả về:
        str: "YES" | "NO" | "UNKNOWN"
    """
    queue_log(queue, email, "🌐 Mở trang grok.com để kiểm tra gói SuperGrok...")
    grok_page = context.new_page()
    try:
        grok_page.goto(GROK_URL, timeout=TIMEOUT_PAGE_LOAD)
        queue_log(queue, email, "🔍 Đang mở menu cài đặt tài khoản Grok...")

        opened = click_fallback(grok_page, SELECTORS["grok_profile_btn"], timeout=TIMEOUT_PAGE_LOAD)
        if not opened:
            queue_log(queue, email, "⚠️ Không thể mở menu tài khoản Grok", level="WARN")
            return "UNKNOWN"

        wait_human(grok_page)
        settings_opened = click_fallback(grok_page, SELECTORS["grok_settings_btn"], timeout=TIMEOUT_ACTION)
        if not settings_opened:
            queue_log(queue, email, "⚠️ Không thể mở bảng Cài đặt Grok", level="WARN")
            return "UNKNOWN"

        wait_human(grok_page)

        # Các nhãn biểu thị KHÔNG có SuperGrok
        no_sg_selectors = [
            'text="Nhận SuperGrok"',
            'text="Get SuperGrok"',
            'text="Nâng cấp lên SuperGrok"',
            'text="Upgrade to SuperGrok"',
        ]
        has_no_sg = any(grok_page.locator(sel).count() > 0 for sel in no_sg_selectors)

        # Các nhãn biểu thị ĐÃ CÓ SuperGrok
        active_sg_selectors = [
            'text="Quản lý gói đăng ký"',
            'text="Manage subscription"',
            'text="Quản lý gói cước"',
        ]
        has_active_sg = any(grok_page.locator(sel).count() > 0 for sel in active_sg_selectors)
        has_supergrok_label = grok_page.locator('text="SuperGrok"').count() > 0

        if has_no_sg:
            queue_log(queue, email, f"⚪ THƯỜNG: {email} (Chưa có SuperGrok)")
            return "NO"
        elif has_active_sg or has_supergrok_label:
            queue_log(queue, email, f"🌟 SUPERGROK: {email} (ĐÃ CÓ SuperGrok)")
            return "YES"
        else:
            queue_log(queue, email, f"⚠️ KHÔNG RÕ TRẠNG THÁI: {email}", level="WARN")
            return "UNKNOWN"

    except Exception as e:
        queue_log(queue, email, f"⛔ Lỗi khi kiểm tra SuperGrok: {str(e)}", level="ERROR")
        return "UNKNOWN"
    finally:
        try:
            grok_page.close()
        except Exception:
            pass


def sign_out_all_devices(page, email: str, queue=None) -> bool:
    """Đăng xuất tất cả thiết bị trên trang tài khoản X.ai.

    Trả về:
        bool: True nếu thành công, False nếu thất bại.
    """
    queue_log(queue, email, "🔌 Đang thực hiện đăng xuất tất cả thiết bị...")
    try:
        if "account" not in page.url:
            queue_log(queue, email, "🌐 Điều hướng về trang tài khoản...")
            page.goto(XAI_ACCOUNT_URL, timeout=TIMEOUT_NAV)
            wait_human(page)

        page.bring_to_front()
        wait_human(page)

        clicked = click_fallback(page, SELECTORS["signout_all_btn"], timeout=TIMEOUT_ACTION)
        if not clicked:
            queue_log(queue, email, "⚠️ Không tìm thấy nút 'Sign out of all devices'", level="WARN")
            return False

        wait_human(page)

        # Click modal xác nhận nếu có xuất hiện
        if not click_fallback(page, SELECTORS["signout_confirm_btn"], timeout=TIMEOUT_MODAL):
            queue_log(queue, email, "⚠️ Không tìm thấy nút Xác nhận đăng xuất", level="WARN")
            return False
        wait_human(page)

        queue_log(queue, email, "✅ Đã đăng xuất tất cả thiết bị thành công.")
        return True

    except Exception as e:
        queue_log(queue, email, f"⚠️ Lỗi khi đăng xuất thiết bị: {str(e)}", level="ERROR")
        return False


def change_account_password(page, email: str, old_pwd: str, new_pwd: str, queue=None) -> bool:
    """Đổi mật khẩu tài khoản X.ai.

    Trả về:
        bool: True nếu đổi thành công, False nếu thất bại.
    """
    if not new_pwd:
        queue_log(queue, email, "❌ Mật khẩu mới trống, không thể đổi.", level="ERROR")
        return False

    queue_log(queue, email, "🔄 Đang mở form đổi mật khẩu...")
    try:
        if "account" not in page.url:
            queue_log(queue, email, "🌐 Điều hướng về trang tài khoản...")
            page.goto(XAI_ACCOUNT_URL, timeout=TIMEOUT_NAV)
            wait_human(page)

        page.bring_to_front()
        wait_human(page)

        clicked = click_fallback(page, SELECTORS["change_pwd_btn"], timeout=TIMEOUT_ACTION)
        if not clicked:
            queue_log(queue, email, "⚠️ Không tìm thấy nút đổi mật khẩu", level="WARN")
            return False

        wait_human(page)

        queue_log(queue, email, "🔑 Đang điền mật khẩu cũ và mới...")
        if not fill_fallback(page, SELECTORS["old_pwd_input"], old_pwd, timeout=TIMEOUT_ACTION):
            queue_log(queue, email, "⚠️ Không tìm thấy ô nhập mật khẩu cũ", level="WARN")
            return False

        wait_human(page)
        if not fill_fallback(page, SELECTORS["new_pwd_input"], new_pwd, timeout=TIMEOUT_ACTION):
            queue_log(queue, email, "⚠️ Không tìm thấy ô nhập mật khẩu mới", level="WARN")
            return False

        wait_human(page)
        # Điền ô xác nhận mật khẩu mới nếu giao diện yêu cầu
        for conf_sel in SELECTORS["confirm_pwd_input"]:
            try:
                conf_loc = page.locator(conf_sel).first
                if conf_loc.is_visible(timeout=1000):
                    conf_loc.fill(new_pwd, timeout=2000)
                    wait_human(page)
                    break
            except Exception:
                pass

        queue_log(queue, email, "💾 Đang lưu mật khẩu mới...")
        saved = click_fallback(page, SELECTORS["save_pwd_btn"], timeout=TIMEOUT_ACTION)
        if not saved:
            queue_log(queue, email, "⚠️ Không tìm thấy nút lưu mật khẩu", level="WARN")
            return False

        wait_human(page)

        # Kiểm tra thông báo lỗi nếu có
        err_loc = page.locator('text="Incorrect password", text="Sai mật khẩu", text="Current password is wrong"')
        if err_loc.count() > 0 and err_loc.first.is_visible():
            queue_log(queue, email, "❌ Đổi mật khẩu thất bại: Mật khẩu cũ không chính xác", level="ERROR")
            return False

        queue_log(queue, email, "✅ Đã đổi mật khẩu thành công.")
        return True

    except Exception as e:
        queue_log(queue, email, f"⚠️ Lỗi khi đổi mật khẩu: {str(e)}", level="ERROR")
        return False


def _normalize_account_info(account_info) -> tuple[str, str, str, str, bool]:
    """Chuẩn hóa dữ liệu đầu vào account_info thành tuple (email, pwd, new_pwd, item_id, stop_if_no_sg)."""
    if isinstance(account_info, dict):
        email = str(account_info.get("email", "")).strip()
        pwd = str(account_info.get("password") or account_info.get("pwd", "")).strip()
        new_pwd = str(
            account_info.get("account_new_pwd")
            or account_info.get("new_pwd")
            or account_info.get("new_password", "")
        ).strip()
        item_id = str(account_info.get("item_id") or account_info.get("id", ""))
        stop_if_no_sg = bool(account_info.get("stop_if_no_sg", True))
        return email, pwd, new_pwd, item_id, stop_if_no_sg

    if isinstance(account_info, (list, tuple)):
        if len(account_info) == 2:
            return str(account_info[0]).strip(), str(account_info[1]).strip(), "", "", True
        if len(account_info) == 3:
            return str(account_info[0]).strip(), str(account_info[1]).strip(), str(account_info[2]).strip(), "", True
        if len(account_info) >= 6:
            # Dạng (item_id, item_stt, email, pwd, auto_change, new_pwd)
            item_id = str(account_info[0])
            email = str(account_info[2]).strip()
            pwd = str(account_info[3]).strip()
            new_pwd = str(account_info[5]).strip()
            return email, pwd, new_pwd, item_id, True
        if len(account_info) > 0:
            email = str(account_info[0]).strip()
            pwd = str(account_info[1]).strip() if len(account_info) > 1 else ""
            return email, pwd, "", "", True

    return "", "", "", "", True


def execute_account_task(
    browser,
    account_info,
    action: str = "EXECUTE",
    queue=None,
    enable_check_sg: bool | None = None,
    enable_change_pwd: bool | None = None,
    enable_sign_out: bool | None = None,
    global_new_pwd: str = "",
) -> dict:
    """Điều phối và thực thi tác vụ cho 1 tài khoản, tuân thủ DataContract.

    Thực hiện thứ tự luồng chính duy nhất:
    1. login_xai(page, email, pwd, queue=queue)
    2. Nếu enable_check_sg: chạy check_supergrok(context, email, queue=queue). Nếu không: trả về "SKIPPED".
    3. Nếu enable_change_pwd: kiểm tra có new_pwd (ưu tiên account_new_pwd từ tài khoản, nếu không thì dùng global_new_pwd),
       nếu có thì chạy change_account_password(page, email, pwd, new_pwd, queue=queue).
       Nếu không có new_pwd mà chức năng bật thì đánh dấu lỗi NO_NEW_PWD và bỏ qua. Nếu chức năng tắt: trả về "SKIPPED".
    4. Nếu enable_sign_out: chạy sign_out_all_devices(page, email, queue=queue). Nếu không: trả về "SKIPPED".
    """
    if hasattr(action, "put") or callable(action):
        queue = action
        action = "EXECUTE"
    elif not isinstance(action, str) or not action:
        action = "EXECUTE"
    else:
        action = str(action).upper().strip()

    if enable_check_sg is None and enable_change_pwd is None and enable_sign_out is None:
        if action == "CHECK_SUPERGROK":
            enable_check_sg, enable_change_pwd, enable_sign_out = True, False, False
        elif action == "SIGN_OUT":
            enable_check_sg, enable_change_pwd, enable_sign_out = False, False, True
        elif action == "CHANGE_PASSWORD":
            enable_check_sg, enable_change_pwd, enable_sign_out = False, True, False
        elif action == "FULL_FLOW":
            enable_check_sg, enable_change_pwd, enable_sign_out = True, True, True
        else:
            enable_check_sg, enable_change_pwd, enable_sign_out = False, False, False
    else:
        enable_check_sg = bool(enable_check_sg)
        enable_change_pwd = bool(enable_change_pwd)
        enable_sign_out = bool(enable_sign_out)

    email, pwd, account_new_pwd, item_id, stop_if_no_sg = _normalize_account_info(account_info)

    result = {
        "account": email,
        "status": "FAILED",
        "step": action,
        "supergrok": "N/A" if enable_check_sg else "SKIPPED",
        "signout": "N/A" if enable_sign_out else "SKIPPED",
        "pwd_changed": "N/A" if enable_change_pwd else "SKIPPED",
        "final_password": pwd,
        "message": "",
        "error_code": None,
        "screenshot_path": None,
    }

    if not email or not pwd:
        result["message"] = "Thiếu email hoặc mật khẩu"
        result["error_code"] = "INVALID_DATA"
        send_queue_msg(queue, "RESULT", item_id=item_id, data=result)
        send_queue_msg(queue, "DONE", account=email)
        return result

    if item_id:
        send_queue_msg(queue, "ROW_RUNNING", item_id=item_id)
    queue_log(queue, email, f"🚀 Bắt đầu thực thi tác vụ: {action}")

        # Stealth context for Cloudflare bypass
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    context = browser.new_context(
        locale="vi-VN",
        user_agent=USER_AGENT,
        viewport={"width": 1280, "height": 720}
    )
    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    page = None
    try:
        page = context.new_page()

        # 1. Đăng nhập X.ai
        result["step"] = "LOGIN"
        login_ok = login_xai(page, email, pwd, queue=queue)

        if not login_ok:
            result["status"] = "FAILED"
            try:
                has_cf = page.locator('iframe[title*="Cloudflare"], iframe[title*="Turnstile"]').count() > 0
                has_turnstile_txt = False
                try:
                    raw_frames = page.frames() if callable(getattr(page, "frames", None)) else getattr(page, "frames", [])
                    frames_to_check = [page] + (list(raw_frames) if hasattr(raw_frames, "__iter__") else [])
                    for f in frames_to_check:
                        if f.locator('text="Verify you are human", text="Xác minh bạn là con người"').count() > 0:
                            has_turnstile_txt = True
                            break
                except Exception:
                    has_turnstile_txt = page.locator('text="Verify you are human", text="Xác minh bạn là con người"').count() > 0
                has_wrong_pwd = page.locator('text="Invalid email or password", text="Sai mật khẩu", text="Incorrect password"').count() > 0

                if has_cf or has_turnstile_txt:
                    result["status"] = "BLOCKED"
                    result["error_code"] = "CAPTCHA"
                    result["message"] = "Kẹt Captcha Cloudflare / Turnstile"
                elif has_wrong_pwd:
                    result["error_code"] = "WRONG_PASSWORD"
                    result["message"] = "Sai tài khoản hoặc mật khẩu"
                else:
                    result["error_code"] = "TIMEOUT"
                    result["message"] = "Đăng nhập thất bại hoặc hết thời gian chờ"
            except Exception:
                result["error_code"] = "TIMEOUT"
                result["message"] = "Đăng nhập thất bại"

            result["screenshot_path"] = capture_screenshot(page, email)
            send_queue_msg(queue, "RESULT", item_id=item_id, data=result)
            send_queue_msg(queue, "DONE", account=email)
            return result

        result["step"] = action

        # 2. Nếu enable_check_sg: chạy check_supergrok(context, email, queue=queue). Nếu không: trả về "SKIPPED".
        if enable_check_sg:
            sg = check_supergrok(context, email, queue=queue)
            result["supergrok"] = sg
            if sg == "UNKNOWN":
                result["error_code"] = result["error_code"] or "CHECK_SG_FAILED"

            if stop_if_no_sg and sg != "YES":
                queue_log(queue, email, "🛑 Không có SuperGrok, bỏ qua Đổi mật khẩu và Đăng xuất.", level="WARN")
                enable_change_pwd = False
                enable_sign_out = False
                result["pwd_changed"] = "SKIPPED"
                result["signout"] = "SKIPPED"
        else:
            result["supergrok"] = "SKIPPED"

        # 3. Nếu enable_change_pwd: kiểm tra có new_pwd (ưu tiên account_new_pwd, nếu không thì dùng global_new_pwd)
        target_new_pwd = account_new_pwd or str(global_new_pwd or "").strip()
        if enable_change_pwd:
            if target_new_pwd:
                cp = change_account_password(page, email, pwd, target_new_pwd, queue=queue)
                result["pwd_changed"] = "SUCCESS" if cp else "FAILED"
                if cp:
                    result["final_password"] = target_new_pwd
                else:
                    result["error_code"] = result["error_code"] or "CHANGE_PWD_FAILED"
            else:
                result["error_code"] = "NO_NEW_PWD"
                result["pwd_changed"] = "FAILED"
                result["message"] = "Thiếu mật khẩu mới"
                queue_log(queue, email, "⚠️ Bật đổi mật khẩu nhưng không có mật khẩu mới", level="WARN")
        else:
            result["pwd_changed"] = "SKIPPED"

        # 4. Nếu enable_sign_out: chạy sign_out_all_devices(page, email, queue=queue). Nếu không: trả về "SKIPPED".
        if enable_sign_out:
            so = sign_out_all_devices(page, email, queue=queue)
            result["signout"] = "SUCCESS" if so else "FAILED"
            if not so:
                result["error_code"] = result["error_code"] or "SIGNOUT_FAILED"
        else:
            result["signout"] = "SKIPPED"

        has_error = (
            result.get("error_code") is not None
            or (enable_check_sg and result["supergrok"] == "UNKNOWN")
            or (enable_change_pwd and result["pwd_changed"] != "SUCCESS")
            or (enable_sign_out and result["signout"] != "SUCCESS")
        )

        if has_error:
            result["status"] = "FAILED"
            if not result["message"]:
                result["message"] = f"Hoàn tất với lỗi: {result.get('error_code') or 'FAILED'}"
            result["screenshot_path"] = capture_screenshot(page, email)
        else:
            result["status"] = "SUCCESS"
            if not result["message"]:
                result["message"] = "Hoàn tất thành công"

    except Exception as e:
        result["status"] = "FAILED"
        result["error_code"] = "EXCEPTION"
        result["message"] = f"Lỗi ngoại lệ: {str(e)}"
        queue_log(queue, email, f"⛔ Ngoại lệ trong tiến trình: {str(e)}", level="ERROR")
        if page:
            try:
                result["screenshot_path"] = capture_screenshot(page, email)
            except Exception:
                pass
    finally:
        try:
            context.close()
        except Exception:
            pass

    send_queue_msg(queue, "RESULT", item_id=item_id, data=result)
    send_queue_msg(queue, "DONE", account=email)
    return result


def login(browser, email: str, password: str, queue=None, auto_change: bool = False, new_pwd: str = "") -> dict:
    """Wrapper tương thích ngược cho hàm login cũ.

    Trả về DataContract dict thay vì tuple.
    """
    return execute_account_task(
        browser=browser,
        account_info={
            "email": email,
            "password": password,
            "new_pwd": new_pwd if auto_change else "",
        },
        action="FULL_FLOW",
        queue=queue,
        enable_check_sg=True,
        enable_change_pwd=bool(auto_change and new_pwd),
        enable_sign_out=True,
        global_new_pwd=new_pwd if auto_change else "",
    )
