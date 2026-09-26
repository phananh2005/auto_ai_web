"""Cấu hình hằng số, URLs, timeouts và selectors cho Playwright bot."""

# URLs
XAI_SIGNIN_URL = "https://accounts.x.ai/sign-in"
XAI_ACCOUNT_URL = "https://accounts.x.ai/account"
GROK_URL = "https://grok.com/"

# Timeouts (ms)
TIMEOUT_PAGE_LOAD = 30000   # 30s cho page load nặng
TIMEOUT_NAV = 15000         # 15s cho chuyển hướng / navigation
TIMEOUT_ACTION = 10000      # 10s cho click / fill
TIMEOUT_MODAL = 5000        # 5s cho modal / popup

# Captcha / Cloudflare Selectors
CF_TURNSTILE_WRAPPER = 'div:has(> input[name="cf-turnstile-response"])'
CF_TURNSTILE_WRAPPER_FALLBACK = 'div:has(input[name="cf-turnstile-response"])'

CAPTCHA_SELECTORS = [
    'text="Verify you are human"',
    'text="Xác minh bạn là con người"',
    'text="Verify"',
    'input[type="checkbox"]',
    '#challenge-stage',
    '.cb-c',
]

# Selectors (Ưu tiên: data-testid > aria-label > CSS class > text)
# Mỗi hành động có danh sách fallback selector (Tiếng Anh, Tiếng Việt)
SELECTORS = {
    # Đăng nhập X.ai
    "continue_email": [
        '[data-testid="continue-with-email"]',
        'button:has-text("Continue with email")',
        'button:has-text("Tiếp tục với email")',
        'button:has-text("Login with email")',
        'button:has-text("Đăng nhập với email")',
        'button[type="button"]:has-text("email")',
    ],
    "email_input": [
        "#email",
        'input[name="email"]',
        'input[type="email"]',
        '[data-testid="email-input"]',
    ],
    "signin_submit": [
        '[data-testid="sign-in-submit"]',
        'button[type="submit"]',
        'button:has-text("Tiếp tục")',
        'button:has-text("Continue")',
        'button:has-text("Sign in")',
        'button:has-text("Đăng nhập")',
    ],
    "password_input": [
        'input[type="password"]',
        'input[name="password"]',
        "#password",
        '[data-testid="password-input"]',
    ],

    # Kiểm tra Grok
    "grok_profile_btn": [
        'div.min-w-0.flex-1.overflow-hidden:has(span.text-fg-primary)',
        'button[aria-label*="account" i]',
        'button[aria-label*="profile" i]',
        'button[aria-label*="user" i]',
        'button[aria-label*="tài khoản" i]',
        'div[role="button"]:has(span.text-fg-primary)',
        'button:has(span.text-fg-primary)',
        '[data-testid="user-menu"]',
    ],
    "grok_settings_btn": [
        'div[role="menuitem"]:has(path[d^="m13.456"])',
        'div[role="menuitem"]:has-text("Cài đặt")',
        'div[role="menuitem"]:has-text("Settings")',
        'button:has-text("Settings")',
        'button:has-text("Cài đặt")',
        'a[href*="/settings"]',
    ],

    # Đăng xuất tất cả thiết bị
    "signout_all_btn": [
        'button:has-text("Sign out of all devices")',
        'button:has-text("Đăng xuất khỏi tất cả các thiết bị")',
        'button:has-text("Đăng xuất tất cả thiết bị")',
        'button:has-text("Sign out all devices")',
        '[data-testid="sign-out-all-devices"]',
        '[data-testid="sign-out-all"]',
    ],
    "signout_confirm_btn": [
        'div[role="dialog"] button:has-text("Sign out")',
        'div[role="dialog"] button:has-text("Đăng xuất")',
        'div[role="dialog"] button:has-text("Confirm")',
        'div[role="dialog"] button:has-text("Xác nhận")',
    ],

    # Đổi mật khẩu
    "change_pwd_btn": [
        '#security button:has-text("Change")',
        '#security button:has-text("Đổi")',
        'button:has-text("Change password")',
        'button:has-text("Đổi mật khẩu")',
        'button:has-text("Change")',
        '[data-testid="change-password-button"]',
    ],
    "old_pwd_input": [
        'input[name="oldPassword"]',
        'input[name="currentPassword"]',
        'input[autocomplete="current-password"]',
        'input[type="password"]',
    ],
    "new_pwd_input": [
        'input[name="password"]',
        'input[name="newPassword"]',
        'input[autocomplete="new-password"]',
    ],
    "confirm_pwd_input": [
        'input[name="confirmPassword"]',
        'input[name="newPasswordConfirmation"]',
    ],
    "save_pwd_btn": [
        'button:has-text("Save password")',
        'button:has-text("Lưu mật khẩu")',
        'button:has-text("Save")',
        'button:has-text("Lưu")',
        'button[type="submit"]',
    ],
}
