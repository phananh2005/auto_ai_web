"""Giao diện đồ họa Tkinter quản lý tài khoản X.ai và Grok tự động.

Tuân thủ nguyên tắc đa luồng an toàn:
- Không gọi Playwright trên main thread.
- Worker threads giao tiếp với GUI thông qua queue.Queue.
- GUI polling queue định kỳ bằng root.after(100, poll_queue).
- Quản lý thread pool thông qua concurrent.futures.ThreadPoolExecutor.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from src.bot import execute_account_task, send_queue_msg


def _worker_task(account_data: dict, action: str, msg_queue: queue.Queue, stop_event: threading.Event):
    """Hàm worker chạy trên luồng phụ của ThreadPoolExecutor.

    Tự khởi tạo và giải phóng phiên Playwright độc lập cho từng luồng.
    """
    email = account_data.get("email", "")
    item_id = account_data.get("item_id", "")

    if stop_event.is_set():
        data = {
            "account": email,
            "status": "STOPPED",
            "step": action,
            "supergrok": "N/A",
            "signout": "N/A",
            "pwd_changed": "N/A",
            "final_password": account_data.get("password", ""),
            "message": "Bị dừng trước khi chạy",
            "error_code": "STOPPED",
            "screenshot_path": None,
        }
        send_queue_msg(msg_queue, "RESULT", item_id=item_id, data=data)
        send_queue_msg(msg_queue, "DONE", account=email)
        return

    from playwright.sync_api import sync_playwright

    browser = None
    try:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    channel="chrome",
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            except Exception:
                browser = p.chromium.launch(
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"],
                )

            execute_account_task(
                browser,
                account_data,
                action,
                queue=msg_queue,
                enable_check_sg=account_data.get("enable_check_sg"),
                enable_change_pwd=account_data.get("enable_change_pwd"),
                enable_sign_out=account_data.get("enable_sign_out"),
                global_new_pwd=account_data.get("global_new_pwd"),
            )
    except Exception as ex:
        send_queue_msg(
            msg_queue,
            "LOG",
            account=email,
            text=f"Lỗi khởi động trình duyệt Playwright: {str(ex)}",
            level="ERROR",
        )
        data = {
            "account": email,
            "status": "FAILED",
            "step": action,
            "supergrok": "N/A",
            "signout": "N/A",
            "pwd_changed": "N/A",
            "final_password": account_data.get("password", ""),
            "message": f"Lỗi khởi động trình duyệt: {str(ex)}",
            "error_code": "BROWSER_ERROR",
            "screenshot_path": None,
        }
        send_queue_msg(msg_queue, "RESULT", item_id=item_id, data=data)
        send_queue_msg(msg_queue, "DONE", account=email)
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


class App:
    """Lớp giao diện chính ứng dụng quản lý tài khoản."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("X.ai / Grok Account Manager - Trình quản lý tài khoản tự động")
        self.root.geometry("1180x720")
        self.root.minsize(980, 600)

        # Cấu hình theme clam để màu nền tag Treeview hoạt động đồng nhất
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        # Quản lý luồng và queue an toàn
        self.result_queue = queue.Queue()
        self.executor: ThreadPoolExecutor | None = None
        self.is_running = False
        self.stop_requested = threading.Event()
        self.active_tasks_count = 0
        self.total_tasks_count = 0

        # Thống kê nhanh
        self.stat_success = 0
        self.stat_failed = 0
        self.stat_blocked = 0
        self.stat_supergrok = 0

        # Trạng thái các toggle tác vụ (mặc định Bật)
        self.enable_check_sg = True
        self.enable_change_pwd = True
        self.enable_sign_out = True

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _build_ui(self):
        """Khởi tạo toàn bộ các thành phần giao diện."""
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Cột trái: Nhập liệu, Điều khiển và Bảng dữ liệu
        left_frame = ttk.Frame(main_paned)
        # Cột phải: Log panel
        right_frame = ttk.Frame(main_paned)

        main_paned.add(left_frame, weight=3)
        main_paned.add(right_frame, weight=2)

        # ---------------- 1. KHU VỰC NHẬP LIỆU & CẤU HÌNH ----------------
        input_group = ttk.LabelFrame(left_frame, text="Nhập liệu & Cấu hình tác vụ", padding=8)
        input_group.pack(fill=tk.X, pady=(0, 6))

        input_grid = ttk.Frame(input_group)
        input_grid.pack(fill=tk.X)
        input_grid.columnconfigure(1, weight=1)
        input_grid.columnconfigure(3, weight=1)

        ttk.Label(input_grid, text="Email:").grid(row=0, column=0, sticky="w", padx=4, pady=3)
        self.email_entry = ttk.Entry(input_grid, width=28)
        self.email_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=3)

        ttk.Label(input_grid, text="Mật khẩu hiện tại:").grid(row=0, column=2, sticky="w", padx=4, pady=3)
        self.password_entry = ttk.Entry(input_grid, width=22)
        self.password_entry.grid(row=0, column=3, sticky="ew", padx=4, pady=3)

        ttk.Label(input_grid, text="Mật khẩu mới (nếu đổi):").grid(row=1, column=0, sticky="w", padx=4, pady=3)
        self.new_password_entry = ttk.Entry(input_grid, width=28)
        self.new_password_entry.grid(row=1, column=1, sticky="ew", padx=4, pady=3)

        ttk.Label(input_grid, text="Số luồng song song:").grid(row=1, column=2, sticky="w", padx=4, pady=3)
        self.max_threads_var = tk.StringVar(value="5")
        self.threads_entry = ttk.Spinbox(input_grid, from_=1, to=20, textvariable=self.max_threads_var, width=6)
        self.threads_entry.grid(row=1, column=3, sticky="w", padx=4, pady=3)

        # Checkbox tùy chọn dừng nếu không có SuperGrok
        self.stop_if_no_sg_var = tk.BooleanVar(value=True)
        self.chk_stop_no_sg = ttk.Checkbutton(
            input_grid,
            text="Dừng quy trình nếu không có SuperGrok (áp dụng cho Chạy tất cả)",
            variable=self.stop_if_no_sg_var,
        )
        self.chk_stop_no_sg.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # Nút thao tác nhập hàng đợi
        btn_box = ttk.Frame(input_grid)
        btn_box.grid(row=2, column=2, columnspan=2, sticky="e", padx=4, pady=4)

        self.btn_add = tk.Button(
            btn_box,
            text="➕ Thêm tài khoản",
            command=self.add_account,
            bg="#2563eb",
            fg="white",
            relief=tk.RAISED,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_add.pack(side=tk.LEFT, padx=3)

        self.btn_import = tk.Button(
            btn_box,
            text="📂 Nhập file .txt",
            command=self.import_from_file,
            bg="#4b5563",
            fg="white",
            relief=tk.RAISED,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_import.pack(side=tk.LEFT, padx=3)

        self.btn_clear_q = tk.Button(
            btn_box,
            text="🗑️ Xóa hàng đợi",
            command=self.clear_queue,
            bg="#6b7280",
            fg="white",
            relief=tk.RAISED,
            padx=8,
            pady=3,
            cursor="hand2",
        )
        self.btn_clear_q.pack(side=tk.LEFT, padx=3)

        # ---------------- 2. KHU VỰC CÁC NÚT KÍCH HOẠT CHỨC NĂNG ----------------
        action_group = ttk.LabelFrame(left_frame, text="Tùy chọn tác vụ & Điều khiển", padding=8)
        action_group.pack(fill=tk.X, pady=(0, 6))

        btn_flow_box = ttk.Frame(action_group)
        btn_flow_box.pack(fill=tk.X)

        self.btn_toggle_sg = self._create_toggle_btn(btn_flow_box, "enable_check_sg", "Check SG")
        self.btn_toggle_sg.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        self.btn_toggle_pwd = self._create_toggle_btn(btn_flow_box, "enable_change_pwd", "Đổi MK")
        self.btn_toggle_pwd.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        self.btn_toggle_signout = self._create_toggle_btn(btn_flow_box, "enable_sign_out", "Đăng xuất")
        self.btn_toggle_signout.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        # Aliases tương thích ngược
        self.btn_check_sg = self.btn_toggle_sg
        self.btn_change_pwd = self.btn_toggle_pwd
        self.btn_sign_out = self.btn_toggle_signout

        self.btn_start = tk.Button(
            btn_flow_box,
            text="🚀 Bắt đầu chạy",
            command=self.start_tasks,
            bg="#2563eb",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.RAISED,
            padx=8,
            pady=5,
            cursor="hand2",
        )
        self.btn_start.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        self.btn_stop = tk.Button(
            btn_flow_box,
            text="🛑 Dừng",
            command=self.stop_tasks,
            bg="#dc2626",
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief=tk.RAISED,
            padx=10,
            pady=5,
            state=tk.DISABLED,
            cursor="hand2",
        )
        self.btn_stop.pack(side=tk.LEFT, padx=3, expand=True, fill=tk.X)

        # ---------------- 3. BẢNG PHÒNG CHỜ (QUEUE TABLE) ----------------
        queue_group = ttk.LabelFrame(left_frame, text="Hàng đợi đang chờ (Nhấn Delete để xoá dòng chọn)", padding=4)
        queue_group.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        q_table_frame = ttk.Frame(queue_group)
        q_table_frame.pack(fill=tk.BOTH, expand=True)

        cols_q = ("stt", "email", "password", "new_pwd", "status")
        self.queue_table = ttk.Treeview(q_table_frame, columns=cols_q, show="headings", height=5)
        self.queue_table.heading("stt", text="STT")
        self.queue_table.heading("email", text="Email")
        self.queue_table.heading("password", text="Mật khẩu")
        self.queue_table.heading("new_pwd", text="Mật khẩu mới")
        self.queue_table.heading("status", text="Trạng thái")

        self.queue_table.column("stt", width=40, anchor="center")
        self.queue_table.column("email", width=180)
        self.queue_table.column("password", width=100)
        self.queue_table.column("new_pwd", width=100)
        self.queue_table.column("status", width=110, anchor="center")

        q_scroll = ttk.Scrollbar(q_table_frame, orient=tk.VERTICAL, command=self.queue_table.yview)
        self.queue_table.configure(yscrollcommand=q_scroll.set)
        self.queue_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        q_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.queue_table.tag_configure("pending", background="#ffffff")
        self.queue_table.tag_configure("running", background="#fff3cd")
        self.queue_table.tag_configure("stopped", background="#e2e3e5")
        self.queue_table.bind("<Delete>", self._on_queue_delete_key)
        self.queue_table.bind("<Double-1>", self._on_table_double_click)

        # ---------------- 4. BẢNG KẾT QUẢ THỰC THI (COMPLETED TABLE) ----------------
        res_group = ttk.LabelFrame(
            left_frame,
            text="Bảng kết quả (Nhấp đúp chuột để sao chép nội dung ô)",
            padding=4,
        )
        res_group.pack(fill=tk.BOTH, expand=True)

        c_table_frame = ttk.Frame(res_group)
        c_table_frame.pack(fill=tk.BOTH, expand=True)

        cols_c = ("stt", "email", "password", "supergrok", "signout", "pwd_changed", "status", "message")
        self.completed_table = ttk.Treeview(c_table_frame, columns=cols_c, show="headings", height=8)
        self.completed_table.heading("stt", text="STT")
        self.completed_table.heading("email", text="Email")
        self.completed_table.heading("password", text="Mật khẩu")
        self.completed_table.heading("supergrok", text="SuperGrok")
        self.completed_table.heading("signout", text="Đăng xuất")
        self.completed_table.heading("pwd_changed", text="Đổi MK")
        self.completed_table.heading("status", text="Kết quả")
        self.completed_table.heading("message", text="Chi tiết")

        self.completed_table.column("stt", width=40, anchor="center")
        self.completed_table.column("email", width=170)
        self.completed_table.column("password", width=105)
        self.completed_table.column("supergrok", width=85, anchor="center")
        self.completed_table.column("signout", width=80, anchor="center")
        self.completed_table.column("pwd_changed", width=80, anchor="center")
        self.completed_table.column("status", width=95, anchor="center")
        self.completed_table.column("message", width=190)

        c_scroll_y = ttk.Scrollbar(c_table_frame, orient=tk.VERTICAL, command=self.completed_table.yview)
        self.completed_table.configure(yscrollcommand=c_scroll_y.set)
        self.completed_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        c_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        self.completed_table.tag_configure("SUCCESS", background="#d4edda")
        self.completed_table.tag_configure("FAILED", background="#f8d7da")
        self.completed_table.tag_configure("BLOCKED", background="#ffe8cc")
        self.completed_table.tag_configure("STOPPED", background="#e2e3e5")
        self.completed_table.tag_configure("SKIPPED", background="#f3f4f6")
        self.completed_table.bind("<Double-1>", self._on_table_double_click)

        # Thanh xuất file & Thống kê
        export_bar = ttk.Frame(res_group)
        export_bar.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(export_bar, text="Bộ lọc xuất file:").pack(side=tk.LEFT, padx=(2, 4))
        self.filter_var = tk.StringVar(value="Tất cả")
        self.filter_cb = ttk.Combobox(
            export_bar,
            textvariable=self.filter_var,
            values=["Tất cả", "Có SuperGrok", "Không SuperGrok", "Đã đổi MK", "Thành công", "Lỗi"],
            state="readonly",
            width=15,
        )
        self.filter_cb.pack(side=tk.LEFT, padx=4)

        self.export_btn = tk.Button(
            export_bar,
            text="💾 Xuất file (.txt)",
            command=self.export_results,
            bg="#059669",
            fg="white",
            relief=tk.RAISED,
            padx=8,
            pady=2,
            state=tk.DISABLED,
            cursor="hand2",
        )
        self.export_btn.pack(side=tk.LEFT, padx=6)

        self.lbl_summary = ttk.Label(
            export_bar,
            text="Tổng: 0 | Thành công: 0 | Lỗi: 0 | SuperGrok: 0",
            font=("Segoe UI", 9, "italic"),
        )
        self.lbl_summary.pack(side=tk.RIGHT, padx=4)

        # ---------------- 5. KHU VỰC NHẬT KÝ (LOG PANEL - BÊN PHẢI) ----------------
        log_group = ttk.LabelFrame(right_frame, text="Nhật ký hoạt động (Log)", padding=6)
        log_group.pack(fill=tk.BOTH, expand=True)

        self.log_area = ScrolledText(
            log_group,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#ffffff",
            fg="#212529",
        )
        self.log_area.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.log_area.tag_config("INFO", foreground="#212529")
        self.log_area.tag_config("WARN", foreground="#b45309")
        self.log_area.tag_config("ERROR", foreground="#b91c1c")
        self.log_area.tag_config("SUCCESS", foreground="#047857")

        log_bottom_bar = ttk.Frame(log_group)
        log_bottom_bar.pack(fill=tk.X)

        self.lbl_system_status = ttk.Label(
            log_bottom_bar,
            text="Trạng thái: Sẵn sàng",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_system_status.pack(side=tk.LEFT, padx=2)

        btn_clear_log = tk.Button(
            log_bottom_bar,
            text="🧹 Xóa log",
            command=self.clear_log,
            bg="#6b7280",
            fg="white",
            relief=tk.RAISED,
            padx=8,
            pady=2,
            cursor="hand2",
        )
        btn_clear_log.pack(side=tk.RIGHT, padx=2)

    def _create_toggle_btn(self, parent, attr_name: str, label: str) -> tk.Button:
        """Tạo toggle button tự động đổi màu sắc, text và lưu trạng thái vào biến class."""
        btn = tk.Button(
            parent,
            font=("Segoe UI", 9, "bold"),
            relief=tk.RAISED,
            padx=6,
            pady=5,
            cursor="hand2",
        )

        def _update_ui(val: bool):
            btn.config(
                text=f"{label}: [Bật]" if val else f"{label}: [Tắt]",
                bg="#059669" if val else "#6b7280",
                fg="white",
            )

        def _on_click():
            new_val = not getattr(self, attr_name)
            setattr(self, attr_name, new_val)
            _update_ui(new_val)

        btn.config(command=_on_click)
        _update_ui(getattr(self, attr_name))
        return btn

    # ---------------- QUEUE CONSUMER PATTERN (BẮT BUỘC) ----------------

    def poll_queue(self):
        """Tiêu thụ định kỳ các thông điệp từ worker thread qua Queue trên main thread."""
        try:
            while True:
                msg = self.result_queue.get_nowait()
                msg_type = msg.get("type")
                if msg_type == "LOG":
                    self._append_log(msg.get("account", ""), msg.get("text", ""), msg.get("level", "INFO"))
                elif msg_type == "ROW_RUNNING":
                    self._set_row_running(msg.get("item_id"))
                elif msg_type == "RESULT":
                    self._update_table_row(msg.get("item_id"), msg.get("data", {}))
                elif msg_type == "DONE":
                    self._on_worker_done(msg.get("account", ""))
                elif msg_type == "ALL_DONE":
                    self._on_all_done()
        except queue.Empty:
            pass

        # Duy trì vòng lặp polling chừng nào còn tác vụ đang chạy hoặc còn worker chưa hoàn tất
        if self.is_running or self.active_tasks_count > 0:
            self.root.after(100, self.poll_queue)

    def _append_log(self, account: str, text: str, level: str = "INFO"):
        """Ghi dòng nhật ký có định dạng thời gian và màu sắc."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{account.split('@')[0]}] " if account and account != "SYSTEM" else ""
        formatted_msg = f"[{timestamp}] {prefix}{text}\n"

        level = level.upper()
        tag = level if level in ("INFO", "WARN", "ERROR", "SUCCESS") else "INFO"

        self.log_area.insert(tk.END, formatted_msg, tag)
        self.log_area.see(tk.END)

    def _set_row_running(self, item_id: str | None):
        """Chuyển trạng thái dòng trong hàng đợi sang đang chạy (màu vàng)."""
        if item_id and self.queue_table.exists(item_id):
            vals = list(self.queue_table.item(item_id, "values"))
            if len(vals) >= 5:
                vals[4] = "🚀 Đang chạy..."
                self.queue_table.item(item_id, values=vals, tags=("running",))

    def _update_table_row(self, item_id: str | None, data: dict):
        """Chuyển kết quả từ bảng hàng đợi sang bảng kết quả theo DataContract."""
        if item_id and self.queue_table.exists(item_id):
            self.queue_table.delete(item_id)

        stt = len(self.completed_table.get_children()) + 1
        email = data.get("account", "")
        final_pwd = data.get("final_password", "")
        sg = self._format_supergrok(data.get("supergrok", "N/A"))
        so = self._format_status_sub(data.get("signout", "N/A"), is_pwd=False)
        pc = self._format_status_sub(data.get("pwd_changed", "N/A"), is_pwd=True)
        status = str(data.get("status", "FAILED")).upper()
        msg = data.get("message", "")

        tag = status if status in ("SUCCESS", "FAILED", "BLOCKED", "STOPPED", "SKIPPED") else "FAILED"
        status_label = self._format_main_status(status)

        self.completed_table.insert(
            "",
            tk.END,
            values=(stt, email, final_pwd, sg, so, pc, status_label, msg),
            tags=(tag,),
        )

        # Cập nhật số liệu thống kê
        if status == "SUCCESS":
            self.stat_success += 1
        elif status == "BLOCKED":
            self.stat_blocked += 1
        elif status in ("STOPPED", "SKIPPED"):
            pass
        else:
            self.stat_failed += 1

        if data.get("supergrok") == "YES":
            self.stat_supergrok += 1

        self._update_summary_label()
        self.export_btn.config(state=tk.NORMAL)

    def _on_worker_done(self, account: str):
        """Xử lý sự kiện 1 worker kết thúc tác vụ."""
        self.active_tasks_count -= 1
        if self.active_tasks_count <= 0 and self.is_running:
            self._on_all_done()

    def _on_all_done(self):
        """Xử lý sự kiện hoàn tất toàn bộ hàng đợi."""
        self.is_running = False
        if self.executor:
            try:
                self.executor.shutdown(wait=False)
            except Exception:
                pass
            self.executor = None

        self._set_ui_state(running=False)
        self.lbl_system_status.config(text="Trạng thái: Đã hoàn tất")
        self._append_log("SYSTEM", "✨ Hoàn tất tất cả các tác vụ trong hàng đợi.", "SUCCESS")

    # ---------------- QUẢN LÝ TÁC VỤ & LUỒNG (THREAD POOL) ----------------

    def start_tasks(self):
        """Khởi động chạy các tài khoản trong hàng đợi với cấu hình tác vụ đã chọn."""
        self.start_action("RUN")

    def start_action(self, action: str = "RUN"):
        """Khởi động luồng thực thi tác vụ cho toàn bộ hàng đợi hiện tại."""
        if self.is_running:
            messagebox.showwarning("Cảnh báo", "Hệ thống đang chạy một tác vụ khác.")
            return

        items = self.queue_table.get_children()
        if not items:
            messagebox.showinfo("Thông báo", "Hàng đợi đang trống. Vui lòng thêm tài khoản trước.")
            return

        if not (self.enable_check_sg or self.enable_change_pwd or self.enable_sign_out):
            messagebox.showwarning("Cảnh báo", "Vui lòng bật ít nhất một tác vụ (Check SG, Đổi MK, Đăng xuất).")
            return

        global_new_pwd = self.new_password_entry.get().strip()

        # Cảnh báo nếu đổi mật khẩu nhưng tài khoản và ô mật khẩu chung đều trống
        if self.enable_change_pwd and not global_new_pwd:
            missing = []
            for it in items:
                v = self.queue_table.item(it, "values")
                if len(v) < 4 or not str(v[3]).strip():
                    missing.append(v[1])
            if missing:
                proceed = messagebox.askyesno(
                    "Thiếu mật khẩu mới",
                    f"Có {len(missing)} tài khoản chưa điền mật khẩu mới (và ô mật khẩu mới chung đang trống).\n"
                    "Các tài khoản này sẽ bị đánh dấu thất bại khi đổi MK.\n"
                    "Bạn có muốn tiếp tục chạy không?",
                )
                if not proceed:
                    return

        try:
            max_workers = int(self.max_threads_var.get().strip())
            max_workers = max(1, min(20, max_workers))
        except ValueError:
            max_workers = 5
            self.max_threads_var.set("5")

        self.is_running = True
        self.stop_requested.clear()
        self._set_ui_state(running=True)
        self.lbl_system_status.config(text=f"Trạng thái: Đang chạy [{action}]...")

        tasks = []
        stop_if_no_sg = self.stop_if_no_sg_var.get()
        for it in items:
            vals = self.queue_table.item(it, "values")
            row_new_pwd = str(vals[3]).strip() if len(vals) > 3 else ""
            task_dict = {
                "item_id": it,
                "email": str(vals[1]).strip(),
                "password": str(vals[2]).strip(),
                "new_pwd": row_new_pwd or global_new_pwd,
                "global_new_pwd": global_new_pwd,
                "enable_check_sg": self.enable_check_sg,
                "enable_change_pwd": self.enable_change_pwd,
                "enable_sign_out": self.enable_sign_out,
                "stop_if_no_sg": stop_if_no_sg,
            }
            tasks.append(task_dict)

        self.active_tasks_count = len(tasks)
        self.total_tasks_count = len(tasks)

        self._append_log(
            "SYSTEM",
            f"🚀 Bắt đầu thực thi [{action}] cho {self.total_tasks_count} tài khoản ({max_workers} luồng)...",
            "INFO",
        )

        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        for task_info in tasks:
            self.executor.submit(_worker_task, task_info, action, self.result_queue, self.stop_requested)

        # Bắt đầu vòng lặp tiêu thụ queue
        self.root.after(100, self.poll_queue)

    def stop_tasks(self):
        """Dừng an toàn toàn bộ tiến trình đang thực thi."""
        if not self.is_running:
            return

        self.is_running = False
        self.stop_requested.set()
        if self.executor:
            try:
                self.executor.shutdown(wait=False)
            except Exception:
                pass

        self._append_log("SYSTEM", "🛑 Đã gửi lệnh dừng. Đang đợi các luồng hiện tại ngắt kết nối...", "WARN")
        self.lbl_system_status.config(text="Trạng thái: Đang dừng...")
        self.btn_stop.config(state=tk.DISABLED)

    def _set_ui_state(self, running: bool):
        """Bật/tắt trạng thái các nút bấm tương ứng với trạng thái chạy/nghỉ."""
        state = tk.DISABLED if running else tk.NORMAL
        self.btn_clear_q.config(state=state)
        self.new_password_entry.config(state=state)
        self.threads_entry.config(state=state)
        self.chk_stop_no_sg.config(state=state)

        self.btn_toggle_sg.config(state=state)
        self.btn_toggle_pwd.config(state=state)
        self.btn_toggle_signout.config(state=state)
        self.btn_start.config(state=state)

        self.btn_stop.config(state=tk.NORMAL if running else tk.DISABLED)

        has_results = len(self.completed_table.get_children()) > 0
        self.export_btn.config(state=tk.NORMAL if has_results else tk.DISABLED)

    # ---------------- THAO TÁC HÀNG ĐỢI & NHẬP XUẤT ----------------

    def _submit_task_if_running(self, item_id, email, pwd, new_pwd):
        if not self.is_running or not self.executor:
            return

        global_new_pwd = self.new_password_entry.get().strip()
        stop_if_no_sg = self.stop_if_no_sg_var.get()

        task_dict = {
            "item_id": item_id,
            "email": email,
            "password": pwd,
            "new_pwd": new_pwd or global_new_pwd,
            "global_new_pwd": global_new_pwd,
            "enable_check_sg": self.enable_check_sg,
            "enable_change_pwd": self.enable_change_pwd,
            "enable_sign_out": self.enable_sign_out,
            "stop_if_no_sg": stop_if_no_sg,
        }
        self.active_tasks_count += 1
        self.total_tasks_count += 1
        self.executor.submit(_worker_task, task_dict, "RUN", self.result_queue, self.stop_requested)
        self.lbl_system_status.config(text=f"Trạng thái: Đang chạy [RUN] (Đã thêm luồng mới)...")

    def add_account(self):
        """Thêm 1 tài khoản vào bảng hàng đợi (chỉ thêm, không tự động chạy)."""
        email = self.email_entry.get().strip()
        pwd = self.password_entry.get().strip()
        new_pwd = self.new_password_entry.get().strip()

        if not email or not pwd:
            messagebox.showwarning("Thiếu dữ liệu", "Vui lòng nhập đủ Email và Mật khẩu.")
            return

        stt = len(self.queue_table.get_children()) + 1
        item_id = self.queue_table.insert(
            "",
            tk.END,
            values=(stt, email, pwd, new_pwd, "⏳ Chờ chạy"),
            tags=("pending",),
        )

        self.email_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.email_entry.focus_set()

        self._submit_task_if_running(item_id, email, pwd, new_pwd)

    def import_from_file(self):
        """Nạp danh sách tài khoản từ file .txt (hỗ trợ phân cách bởi | hoặc : hoặc tab)."""
        path = filedialog.askopenfilename(
            title="Chọn file danh sách tài khoản",
            filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return

        count = 0
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "|" in line:
                        parts = [p.strip() for p in line.split("|")]
                    elif ":" in line:
                        parts = [p.strip() for p in line.split(":")]
                    elif "\t" in line:
                        parts = [p.strip() for p in line.split("\t")]
                    else:
                        parts = line.split()

                    if len(parts) >= 2:
                        email = parts[0]
                        pwd = parts[1]
                        new_pwd = parts[2] if len(parts) >= 3 else ""
                        stt = len(self.queue_table.get_children()) + 1
                        item_id = self.queue_table.insert(
                            "",
                            tk.END,
                            values=(stt, email, pwd, new_pwd, "⏳ Chờ chạy"),
                            tags=("pending",),
                        )
                        self._submit_task_if_running(item_id, email, pwd, new_pwd)
                        count += 1

            self._append_log("SYSTEM", f"📂 Đã nạp thành công {count} tài khoản từ file: {os.path.basename(path)}", "INFO")
            messagebox.showinfo("Thành công", f"Đã nạp {count} tài khoản vào hàng đợi.")
        except Exception as e:
            messagebox.showerror("Lỗi đọc file", f"Không thể đọc file: {str(e)}")

    def clear_queue(self):
        """Xoá toàn bộ hàng đợi khi ở trạng thái nghỉ."""
        if self.is_running:
            messagebox.showwarning("Cảnh báo", "Không thể xoá hàng đợi khi đang chạy.")
            return
        for it in self.queue_table.get_children():
            self.queue_table.delete(it)
        self._append_log("SYSTEM", "🗑️ Đã xoá toàn bộ danh sách trong hàng đợi.", "INFO")

    def _on_queue_delete_key(self, event):
        """Xóa các dòng được chọn trong hàng đợi khi nhấn phím Delete."""
        if self.is_running:
            return
        selected = self.queue_table.selection()
        for item in selected:
            self.queue_table.delete(item)
        self._renumber_queue()

    def _renumber_queue(self):
        """Đánh lại STT cho hàng đợi."""
        for idx, item in enumerate(self.queue_table.get_children(), start=1):
            vals = list(self.queue_table.item(item, "values"))
            vals[0] = idx
            self.queue_table.item(item, values=vals)

    def _on_table_double_click(self, event):
        """Sao chép nội dung ô được nhấp đúp vào clipboard."""
        tree = event.widget
        row_id = tree.identify_row(event.y)
        col_id = tree.identify_column(event.x)
        if row_id and col_id:
            try:
                col_idx = int(col_id.replace("#", "")) - 1
                vals = tree.item(row_id, "values")
                if col_idx < len(vals):
                    val = str(vals[col_idx])
                    self.root.clipboard_clear()
                    self.root.clipboard_append(val)
                    self._append_log("CLIPBOARD", f"📋 Đã sao chép: {val}", "INFO")
            except Exception:
                pass

    def export_results(self):
        """Xuất danh sách kết quả ra file .txt định dạng email|password theo bộ lọc."""
        items = self.completed_table.get_children()
        if not items:
            messagebox.showinfo("Thông báo", "Bảng kết quả trống.")
            return

        path = filedialog.asksaveasfilename(
            title="Lưu danh sách kết quả",
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        )
        if not path:
            return

        f_val = self.filter_var.get()
        exported = 0
        try:
            with open(path, "w", encoding="utf-8") as f:
                for it in items:
                    v = self.completed_table.item(it, "values")
                    if len(v) < 8:
                        continue
                    stt, e, p, sg, so, pc, status, msg = v

                    if f_val == "Có SuperGrok" and "CÓ" not in sg:
                        continue
                    if f_val == "Không SuperGrok" and "KHÔNG" not in sg:
                        continue
                    if f_val == "Đã đổi MK" and "Đã đổi" not in pc:
                        continue
                    if f_val == "Thành công" and "SUCCESS" not in status:
                        continue
                    if f_val == "Lỗi" and "SUCCESS" in status:
                        continue

                    f.write(f"{e}|{p}\n")
                    exported += 1

            self._append_log("SYSTEM", f"💾 Đã xuất {exported} tài khoản theo bộ lọc '{f_val}' vào {path}", "SUCCESS")
            messagebox.showinfo("Thành công", f"Đã xuất thành công {exported} tài khoản vào:\n{path}")
        except Exception as e:
            messagebox.showerror("Lỗi xuất file", f"Không thể lưu file: {str(e)}")

    def clear_log(self):
        """Xóa trắng nội dung khu vực nhật ký."""
        self.log_area.delete("1.0", tk.END)

    def _update_summary_label(self):
        """Cập nhật nội dung hiển thị số liệu thống kê."""
        total = self.stat_success + self.stat_failed + self.stat_blocked
        self.lbl_summary.config(
            text=f"Tổng: {total} | Thành công: {self.stat_success} | Lỗi: {self.stat_failed} | Chặn: {self.stat_blocked} | SuperGrok: {self.stat_supergrok}"
        )

    # ---------------- FORMATTER TRỢ GIÚP ----------------

    @staticmethod
    def _format_supergrok(sg: str) -> str:
        sg = str(sg).upper()
        if sg == "YES":
            return "🌟 CÓ"
        if sg == "NO":
            return "⚪ KHÔNG"
        if sg == "UNKNOWN":
            return "⚠️ K.RÕ"
        if sg == "SKIPPED":
            return "-"
        return "—"

    @staticmethod
    def _format_status_sub(val: str, is_pwd: bool = False) -> str:
        val = str(val).upper()
        if val == "SUCCESS":
            return "✅ Đã đổi" if is_pwd else "✅ Xong"
        if val == "FAILED":
            return "❌ Lỗi"
        if val == "SKIPPED":
            return "-"
        return "—"

    @staticmethod
    def _format_main_status(status: str) -> str:
        status = str(status).upper()
        if status == "SUCCESS":
            return "✅ SUCCESS"
        if status == "BLOCKED":
            return "⛔ BLOCKED"
        if status == "STOPPED":
            return "⏹️ STOPPED"
        if status == "SKIPPED":
            return "-"
        return "❌ FAILED"

    def on_closing(self):
        """Xử lý sự kiện đóng cửa sổ an toàn."""
        if self.is_running:
            if messagebox.askyesno("Xác nhận đóng", "Tiến trình bot đang chạy. Bạn có chắc muốn ngắt và thoát?"):
                self.stop_requested.set()
                self.is_running = False
                if self.executor:
                    try:
                        self.executor.shutdown(wait=False)
                    except Exception:
                        pass
                self.root.destroy()
        else:
            self.root.destroy()


def run_gui():
    """Hàm khởi chạy giao diện chính của ứng dụng."""
    root = tk.Tk()
    app = App(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
