import queue
from unittest.mock import MagicMock, patch

import pytest

from src.bot import (
    _normalize_account_info,
    change_account_password,
    check_supergrok,
    execute_account_task,
    login,
    login_xai,
    mask_pwd,
    sign_out_all_devices,
)


EXPECTED_DATACONTRACT_KEYS = {
    "account",
    "status",
    "step",
    "supergrok",
    "signout",
    "pwd_changed",
    "final_password",
    "message",
    "error_code",
    "screenshot_path",
}


def test_bot_functions_exist():
    """Kiểm tra tất cả các hàm cốt lõi đã được định nghĩa và có thể gọi."""
    assert callable(login)
    assert callable(login_xai)
    assert callable(check_supergrok)
    assert callable(sign_out_all_devices)
    assert callable(change_account_password)
    assert callable(execute_account_task)


def test_mask_pwd():
    """Kiểm tra mật khẩu được che giấu đúng chuẩn, không bao giờ lộ plaintext."""
    assert mask_pwd("") == ""
    assert mask_pwd("secret123") == "***"


def test_normalize_account_info():
    """Kiểm tra hàm chuẩn hóa dữ liệu tài khoản với nhiều định dạng."""
    # Định dạng dict với account_new_pwd
    email, pwd, new_pwd, item_id, stop_if_no_sg = _normalize_account_info({
        "email": "test@example.com",
        "password": "pwd",
        "account_new_pwd": "new_from_acc",
        "item_id": "item1",
    })
    assert email == "test@example.com"
    assert pwd == "pwd"
    assert new_pwd == "new_from_acc"
    assert item_id == "item1"
    assert stop_if_no_sg is True

    # Định dạng tuple 2 phần tử (email, pwd)
    e, p, np, iid, stop = _normalize_account_info(("test2@example.com", "pwd2"))
    assert e == "test2@example.com"
    assert p == "pwd2"
    assert np == ""

    # Định dạng tuple 6 phần tử từ hàng đợi GUI cũ
    e, p, np, iid, stop = _normalize_account_info(("item_row_1", 1, "test3@example.com", "pwd3", "True", "npwd3"))
    assert e == "test3@example.com"
    assert p == "pwd3"
    assert np == "npwd3"
    assert iid == "item_row_1"


def test_datacontract_invalid_input():
    """Kiểm tra DataContract schema khi dữ liệu đầu vào không hợp lệ."""
    dummy_browser = MagicMock()
    q = queue.Queue()

    res = execute_account_task(dummy_browser, {"email": "", "password": ""}, queue=q)
    assert isinstance(res, dict)
    assert set(res.keys()) == EXPECTED_DATACONTRACT_KEYS
    assert res["status"] == "FAILED"
    assert res["error_code"] == "INVALID_DATA"


def test_queue_message_protocol_on_invalid():
    """Kiểm tra Queue Message Protocol nhận được message đúng chuẩn khi validate thất bại."""
    dummy_browser = MagicMock()
    q = queue.Queue()

    execute_account_task(dummy_browser, {"email": "", "password": ""}, queue=q)

    messages = []
    while not q.empty():
        messages.append(q.get())

    msg_types = [m.get("type") for m in messages]
    assert "RESULT" in msg_types
    assert "DONE" in msg_types


@patch("src.bot.login_xai")
@patch("src.bot.check_supergrok")
def test_execute_account_task_check_sg_only(mock_check_sg, mock_login):
    """Kiểm tra chỉ bật check_supergrok, các bước khác SKIPPED."""
    mock_login.return_value = True
    mock_check_sg.return_value = "YES"

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    q = queue.Queue()
    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "old_password", "item_id": "row_1"},
        queue=q,
        enable_check_sg=True,
        enable_change_pwd=False,
        enable_sign_out=False,
    )

    mock_browser.new_context.assert_called_once_with(
        locale="vi-VN",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720}
    )
    mock_context.close.assert_called_once()

    assert set(res.keys()) == EXPECTED_DATACONTRACT_KEYS
    assert res["status"] == "SUCCESS"
    assert res["supergrok"] == "YES"
    assert res["pwd_changed"] == "SKIPPED"
    assert res["signout"] == "SKIPPED"
    assert res["account"] == "user@xai.test"

    msg_types = []
    while not q.empty():
        msg_types.append(q.get().get("type"))

    assert "ROW_RUNNING" in msg_types
    assert "LOG" in msg_types
    assert "RESULT" in msg_types
    assert "DONE" in msg_types


@patch("src.bot.login_xai")
@patch("src.bot.change_account_password")
def test_execute_account_task_change_password_with_global_pwd(mock_cp, mock_login):
    """Kiểm tra đổi mật khẩu dùng global_new_pwd khi tài khoản không có account_new_pwd."""
    mock_login.return_value = True
    mock_cp.return_value = True

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "pwd"},
        enable_check_sg=False,
        enable_change_pwd=True,
        enable_sign_out=False,
        global_new_pwd="global_secret_pwd",
    )

    assert res["status"] == "SUCCESS"
    assert res["pwd_changed"] == "SUCCESS"
    assert res["final_password"] == "global_secret_pwd"
    assert res["supergrok"] == "SKIPPED"
    assert res["signout"] == "SKIPPED"
    assert mock_cp.call_args[0][3] == "global_secret_pwd"


@patch("src.bot.login_xai")
@patch("src.bot.change_account_password")
def test_execute_account_task_account_new_pwd_priority(mock_cp, mock_login):
    """Kiểm tra ưu tiên account_new_pwd hơn global_new_pwd."""
    mock_login.return_value = True
    mock_cp.return_value = True

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "pwd", "account_new_pwd": "account_priority_pwd"},
        enable_change_pwd=True,
        global_new_pwd="global_secret_pwd",
    )

    assert res["status"] == "SUCCESS"
    assert res["final_password"] == "account_priority_pwd"
    assert mock_cp.call_args[0][3] == "account_priority_pwd"


@patch("src.bot.login_xai")
@patch("src.bot.change_account_password")
def test_execute_account_task_no_new_pwd_error(mock_cp, mock_login):
    """Kiểm tra bật enable_change_pwd nhưng không có mật khẩu mới thì đánh dấu lỗi NO_NEW_PWD và bỏ qua."""
    mock_login.return_value = True

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "pwd"},
        enable_change_pwd=True,
        global_new_pwd="",
    )

    assert res["status"] == "FAILED"
    assert res["error_code"] == "NO_NEW_PWD"
    assert res["pwd_changed"] == "FAILED"
    mock_cp.assert_not_called()


@patch("src.bot.login_xai")
@patch("src.bot.sign_out_all_devices")
def test_execute_account_task_sign_out_only(mock_signout, mock_login):
    """Kiểm tra chỉ bật enable_sign_out, các bước khác SKIPPED."""
    mock_login.return_value = True
    mock_signout.return_value = True

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "pwd"},
        enable_sign_out=True,
    )

    assert res["status"] == "SUCCESS"
    assert res["signout"] == "SUCCESS"
    assert res["supergrok"] == "SKIPPED"
    assert res["pwd_changed"] == "SKIPPED"
    mock_signout.assert_called_once()


@patch("src.bot.login_xai")
@patch("src.bot.check_supergrok")
@patch("src.bot.change_account_password")
@patch("src.bot.sign_out_all_devices")
def test_execute_account_task_all_flags_flow(mock_signout, mock_cp, mock_check_sg, mock_login):
    """Kiểm tra thứ tự luồng đầy đủ: login -> check_supergrok -> change_password -> sign_out."""
    mock_login.return_value = True
    mock_check_sg.return_value = "YES"
    mock_cp.return_value = True
    mock_signout.return_value = True

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "old_pwd", "account_new_pwd": "new_pwd"},
        enable_check_sg=True,
        enable_change_pwd=True,
        enable_sign_out=True,
    )

    assert res["status"] == "SUCCESS"
    assert res["supergrok"] == "YES"
    assert res["pwd_changed"] == "SUCCESS"
    assert res["signout"] == "SUCCESS"
    assert res["final_password"] == "new_pwd"

    # Đảm bảo tất cả các hàm bước đều được gọi
    mock_login.assert_called_once()
    mock_check_sg.assert_called_once()
    mock_cp.assert_called_once()
    mock_signout.assert_called_once()


@patch("src.bot.login_xai")
@patch("src.bot.check_supergrok")
@patch("src.bot.change_account_password")
@patch("src.bot.sign_out_all_devices")
def test_execute_account_task_all_disabled_skips_all(mock_signout, mock_cp, mock_check_sg, mock_login):
    """Kiểm tra khi tắt tất cả tính năng, chỉ login và tất cả bước đều SKIPPED."""
    mock_login.return_value = True

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "pwd"},
        enable_check_sg=False,
        enable_change_pwd=False,
        enable_sign_out=False,
    )

    assert res["status"] == "SUCCESS"
    assert res["supergrok"] == "SKIPPED"
    assert res["pwd_changed"] == "SKIPPED"
    assert res["signout"] == "SKIPPED"
    mock_login.assert_called_once()
    mock_check_sg.assert_not_called()
    mock_cp.assert_not_called()
    mock_signout.assert_not_called()


@patch("src.bot.login_xai")
def test_execute_account_task_login_failure(mock_login):
    """Kiểm tra khi login thất bại thì context vẫn được đóng và trả về đúng schema."""
    mock_login.return_value = False

    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_browser.new_context.return_value = mock_context

    res = execute_account_task(
        mock_browser,
        {"email": "user@xai.test", "password": "pwd"},
        enable_check_sg=True,
        enable_change_pwd=True,
        enable_sign_out=True,
    )

    mock_context.close.assert_called_once()
    assert res["status"] == "FAILED"
    assert res["step"] == "LOGIN"
    assert res["error_code"] in ("TIMEOUT", "WRONG_PASSWORD", "CAPTCHA")
