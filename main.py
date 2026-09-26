import sys
import os

# Cấu hình Playwright browsers path khi chạy dưới dạng executable đóng gói (PyInstaller)
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(sys.executable)
    portable_pw = os.path.join(exe_dir, "ms-playwright")
    internal_pw = os.path.join(getattr(sys, "_MEIPASS", exe_dir), "ms-playwright")
    if os.path.isdir(portable_pw):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = portable_pw
    elif os.path.isdir(internal_pw):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = internal_pw

# Thêm đường dẫn hiện tại vào sys.path để import src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.gui import run_gui

if __name__ == "__main__":
    run_gui()
