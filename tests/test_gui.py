"""Unit tests cho Tkinter GUI, Toggle Buttons và Queue Consumer logic."""

import os
import queue
import sys
import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest

# Thiết lập TCL_LIBRARY cho môi trường Windows khi chạy pytest
if "TCL_LIBRARY" not in os.environ:
    tcl_path = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
    if os.path.isdir(tcl_path):
        os.environ["TCL_LIBRARY"] = tcl_path

from src.gui import App, _worker_task


@pytest.fixture
def app_instance():
    """Khởi tạo App trong chế độ ẩn cửa sổ (withdrawn) để test UI headless."""
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    yield app
    try:
        root.destroy()
    except Exception:
        pass


def test_app_initial_state(app_instance):
    """Kiểm tra trạng thái ban đầu của ứng dụng và các Toggle Button."""
    app = app_instance
    assert app.is_running is False
    assert app.stop_requested.is_set() is False
    assert len(app.queue_table.get_children()) == 0
    assert len(app.completed_table.get_children()) == 0

    # Trạng thái ban đầu của nút bấm
    assert app.btn_start["state"] == tk.NORMAL
    assert app.btn_stop["state"] == tk.DISABLED

    # 3 Toggle Buttons mặc định là Bật (True)
    assert app.enable_check_sg is True
    assert app.enable_change_pwd is True
    assert app.enable_sign_out is True
    assert "[Bật]" in app.btn_toggle_sg["text"]
    assert "[Bật]" in app.btn_toggle_pwd["text"]
    assert "[Bật]" in app.btn_toggle_signout["text"]
    assert app.btn_toggle_sg["state"] == tk.NORMAL
    assert app.btn_toggle_pwd["state"] == tk.NORMAL
    assert app.btn_toggle_signout["state"] == tk.NORMAL


def test_toggle_buttons(app_instance):
    """Kiểm tra Toggle Button khi click đổi text, màu và lưu biến class."""
    app = app_instance

    # Toggle Check SG
    app.btn_toggle_sg.invoke()
    assert app.enable_check_sg is False
    assert "[Tắt]" in app.btn_toggle_sg["text"]
    assert app.btn_toggle_sg["bg"] == "#6b7280"

    app.btn_toggle_sg.invoke()
    assert app.enable_check_sg is True
    assert "[Bật]" in app.btn_toggle_sg["text"]
    assert app.btn_toggle_sg["bg"] == "#059669"

    # Toggle Đổi MK
    app.btn_toggle_pwd.invoke()
    assert app.enable_change_pwd is False
    assert "[Tắt]" in app.btn_toggle_pwd["text"]
    assert app.btn_toggle_pwd["bg"] == "#6b7280"

    # Toggle Đăng xuất
    app.btn_toggle_signout.invoke()
    assert app.enable_sign_out is False
    assert "[Tắt]" in app.btn_toggle_signout["text"]
    assert app.btn_toggle_signout["bg"] == "#6b7280"


def test_ui_state_locking(app_instance):
    """Kiểm tra khóa và mở 3 toggle button cùng ô nhập new_password_entry khi chạy/dừng."""
    app = app_instance

    # Khi đang chạy: khóa 3 toggle buttons, new_password_entry, btn_start; mở btn_stop
    app._set_ui_state(running=True)
    assert str(app.btn_toggle_sg["state"]) == str(tk.DISABLED)
    assert str(app.btn_toggle_pwd["state"]) == str(tk.DISABLED)
    assert str(app.btn_toggle_signout["state"]) == str(tk.DISABLED)
    assert str(app.new_password_entry["state"]) == str(tk.DISABLED)
    assert str(app.btn_start["state"]) == str(tk.DISABLED)
    assert str(app.btn_stop["state"]) == str(tk.NORMAL)

    # Khi dừng: mở lại toàn bộ
    app._set_ui_state(running=False)
    assert str(app.btn_toggle_sg["state"]) == str(tk.NORMAL)
    assert str(app.btn_toggle_pwd["state"]) == str(tk.NORMAL)
    assert str(app.btn_toggle_signout["state"]) == str(tk.NORMAL)
    assert str(app.new_password_entry["state"]) == str(tk.NORMAL)
    assert str(app.btn_start["state"]) == str(tk.NORMAL)
    assert str(app.btn_stop["state"]) == str(tk.DISABLED)


def test_start_tasks_configuration_dict(app_instance):
    """Kiểm tra khi bấm Bắt đầu chạy, task dict chứa đủ các flag cấu hình và global_new_pwd."""
    app = app_instance

    # Thêm 1 tài khoản vào bảng
    app.email_entry.insert(0, "user@test.com")
    app.password_entry.insert(0, "old123")
    app.add_account()

    # Nhập mật khẩu mới chung
    app.new_password_entry.insert(0, "global_new_secret")

    # Tắt toggle Sign Out để test flag
    app.btn_toggle_signout.invoke()
    assert app.enable_sign_out is False

    submitted_tasks = []

    def mock_submit(fn, task_dict, action, q, stop_evt):
        submitted_tasks.append(task_dict)

    with patch("src.gui.ThreadPoolExecutor") as mock_executor_cls:
        mock_exec = MagicMock()
        mock_exec.submit.side_effect = mock_submit
        mock_executor_cls.return_value = mock_exec

        app.start_tasks()

    assert len(submitted_tasks) == 1
    task = submitted_tasks[0]
    assert task["email"] == "user@test.com"
    assert task["password"] == "old123"
    assert task["new_pwd"] == "global_new_secret"
    assert task["global_new_pwd"] == "global_new_secret"
    assert task["enable_check_sg"] is True
    assert task["enable_change_pwd"] is True
    assert task["enable_sign_out"] is False

    app.stop_tasks()


def test_add_account_and_clear_queue(app_instance):
    """Kiểm tra thêm tài khoản vào hàng đợi và xoá hàng đợi."""
    app = app_instance

    # Nhập dữ liệu và thêm
    app.email_entry.insert(0, "test1@example.com")
    app.password_entry.insert(0, "pass123")
    app.new_password_entry.insert(0, "newpass456")
    app.add_account()

    items = app.queue_table.get_children()
    assert len(items) == 1
    vals = app.queue_table.item(items[0], "values")
    assert vals[1] == "test1@example.com"
    assert vals[2] == "pass123"
    assert vals[3] == "newpass456"
    assert "Chờ chạy" in vals[4]

    # Kiểm tra ô nhập email và pass cũ đã được xoá, nhưng ô mật khẩu mới được giữ nguyên
    assert app.email_entry.get() == ""
    assert app.password_entry.get() == ""
    assert app.new_password_entry.get() == "newpass456"

    # Xóa hàng đợi
    app.clear_queue()
    assert len(app.queue_table.get_children()) == 0


def test_poll_queue_consumption_and_skipped(app_instance):
    """Kiểm tra Queue Consumer pattern và hiển thị '-' cho giá trị SKIPPED."""
    app = app_instance

    # 1. Thêm một mục vào hàng đợi
    app.email_entry.insert(0, "user@example.com")
    app.password_entry.insert(0, "secret")
    app.add_account()
    item_id = app.queue_table.get_children()[0]

    app.active_tasks_count = 1
    app.is_running = True

    # 2. Đưa các thông điệp vào queue
    app.result_queue.put({"type": "LOG", "account": "user@example.com", "text": "Đang xử lý...", "level": "INFO"})
    app.result_queue.put({"type": "ROW_RUNNING", "item_id": item_id})
    app.poll_queue()

    # Xác nhận dòng chuyển sang Đang chạy
    vals = app.queue_table.item(item_id, "values")
    assert "Đang chạy" in vals[4]

    # 3. Đưa thông điệp RESULT có chứa SKIPPED
    mock_data = {
        "account": "user@example.com",
        "status": "SUCCESS",
        "step": "RUN",
        "supergrok": "SKIPPED",
        "signout": "SKIPPED",
        "pwd_changed": "SKIPPED",
        "final_password": "secret",
        "message": "Các bước đã được bỏ qua theo cấu hình",
        "error_code": None,
        "screenshot_path": None,
    }
    app.result_queue.put({"type": "RESULT", "item_id": item_id, "data": mock_data})
    app.result_queue.put({"type": "DONE", "account": "user@example.com"})
    app.poll_queue()

    # Hàng đợi trống, bảng kết quả có 1 dòng
    assert len(app.queue_table.get_children()) == 0
    c_items = app.completed_table.get_children()
    assert len(c_items) == 1

    c_vals = app.completed_table.item(c_items[0], "values")
    assert c_vals[1] == "user@example.com"
    assert c_vals[2] == "secret"
    # Các giá trị SKIPPED hiển thị dưới dạng "-"
    assert c_vals[3] == "-"
    assert c_vals[4] == "-"
    assert c_vals[5] == "-"
    assert "SUCCESS" in c_vals[6]

    # Kiểm tra ứng dụng quay lại trạng thái idle
    assert app.is_running is False
    assert app.active_tasks_count == 0


def test_formatters():
    """Kiểm tra các hàm định dạng hiển thị bảng bao gồm SKIPPED."""
    # SuperGrok
    assert "CÓ" in App._format_supergrok("YES")
    assert "KHÔNG" in App._format_supergrok("NO")
    assert "K.RÕ" in App._format_supergrok("UNKNOWN")
    assert App._format_supergrok("SKIPPED") == "-"
    assert App._format_supergrok("N/A") == "—"

    # Status sub
    assert "Đã đổi" in App._format_status_sub("SUCCESS", is_pwd=True)
    assert "Xong" in App._format_status_sub("SUCCESS", is_pwd=False)
    assert "Lỗi" in App._format_status_sub("FAILED")
    assert App._format_status_sub("SKIPPED") == "-"
    assert App._format_status_sub("N/A") == "—"

    # Main status
    assert "SUCCESS" in App._format_main_status("SUCCESS")
    assert "BLOCKED" in App._format_main_status("BLOCKED")
    assert "STOPPED" in App._format_main_status("STOPPED")
    assert App._format_main_status("SKIPPED") == "-"
    assert "FAILED" in App._format_main_status("FAILED")


def test_stop_tasks(app_instance):
    """Kiểm tra logic dừng khẩn cấp các tác vụ."""
    app = app_instance
    app.is_running = True
    app.executor = MagicMock()

    app.stop_tasks()

    assert app.is_running is False
    assert app.stop_requested.is_set() is True
    app.executor.shutdown.assert_called_once_with(wait=False)
    assert app.btn_stop["state"] == tk.DISABLED
