import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import threading
from src.bot import login

def run_gui():
    root = tk.Tk()
    root.title("X.ai Auto Login - Trình quản lý tài khoản")
    root.geometry("900x600")
    
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")

    # Layout chính: Trái (nhập liệu + 2 bảng), Phải (Log)
    left_frame = tk.Frame(root)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    right_frame = tk.Frame(root)
    right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    # -- Khu vực LOG (Bên phải) --
    tk.Label(right_frame, text="Nhật ký (Log):", font=("Arial", 10, "bold")).pack(anchor="w")
    log_area = ScrolledText(right_frame, height=35, width=50)
    log_area.pack(fill=tk.BOTH, expand=True)

    def log_msg(msg):
        root.after(0, lambda: log_area.insert(tk.END, msg + "\n"))
        root.after(0, lambda: log_area.see(tk.END))

    # -- Khu vực NHẬP LIỆU (Bên trái - Trên cùng) --
    input_frame = tk.Frame(left_frame)
    input_frame.pack(fill=tk.X, pady=5)

    tk.Label(input_frame, text="Email:").grid(row=0, column=0, sticky="w", pady=2)
    email_entry = tk.Entry(input_frame, width=35)
    email_entry.grid(row=0, column=1, padx=5, pady=2)

    tk.Label(input_frame, text="Mật khẩu:").grid(row=1, column=0, sticky="w", pady=2)
    password_entry = tk.Entry(input_frame, width=35)
    password_entry.grid(row=1, column=1, padx=5, pady=2)

    auto_change_var = tk.BooleanVar(value=False)
    auto_change_cb = tk.Checkbutton(input_frame, text="Đổi mật khẩu mới:", variable=auto_change_var)
    auto_change_cb.grid(row=2, column=0, sticky="w", pady=2)
    
    new_password_entry = tk.Entry(input_frame, width=35)
    new_password_entry.grid(row=2, column=1, padx=5, pady=2)

    def add_to_queue():
        email = email_entry.get().strip()
        pwd = password_entry.get().strip()
        auto_change = auto_change_var.get()
        new_pwd = new_password_entry.get().strip()
        
        if not email or not pwd:
            messagebox.showwarning("Thiếu", "Nhập đủ email và mật khẩu.")
            return
        if auto_change and not new_pwd:
            messagebox.showwarning("Thiếu", "Vui lòng nhập mật khẩu mới.")
            return
            
        stt = len(queue_table.get_children()) + 1
        queue_table.insert("", tk.END, values=(stt, email, pwd, "⏳ Đang chờ", str(auto_change), new_pwd))
        email_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
        
        # Luôn tự động chạy
        process_queue(auto_start=True)

    add_btn = tk.Button(input_frame, text="Thêm vào danh sách", command=add_to_queue)
    add_btn.grid(row=3, column=1, sticky="w", pady=5)
    
    tk.Label(input_frame, text="Số tài khoản chạy song song:").grid(row=4, column=0, sticky="w", pady=2)
    max_threads_var = tk.StringVar(value="5")
    max_threads_entry = tk.Entry(input_frame, textvariable=max_threads_var, width=10)
    max_threads_entry.grid(row=4, column=1, sticky="w", padx=5, pady=2)

    # -- Khu vực BẢNG PHÒNG CHỜ (Bên trái - Giữa) --
    tk.Label(left_frame, text="Đang chạy:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
    columns_q = ("stt", "email", "pass", "status", "auto_change", "new_pwd")
    queue_table = ttk.Treeview(left_frame, columns=columns_q, show="headings", height=8, displaycolumns=("stt", "email", "pass", "status"))
    queue_table.heading("stt", text="STT")
    queue_table.heading("email", text="Email")
    queue_table.heading("pass", text="Password")
    queue_table.heading("status", text="Trạng thái")
    queue_table.column("stt", width=40, anchor="center")
    queue_table.column("email", width=150)
    queue_table.column("pass", width=100)
    queue_table.column("status", width=100, anchor="center")
    queue_table.tag_configure("running", background="#fff3cd")
    queue_table.pack(fill=tk.BOTH, expand=True, pady=5)

    # -- LOGIC CHẠY HÀNG LOẠT --
    is_running = False

    def process_queue(auto_start=False):
        nonlocal is_running
        if is_running:
            if not auto_start:
                messagebox.showinfo("Thông báo", "Bot đang chạy rồi!")
            return
            
        items = queue_table.get_children()
        if not items:
            if not auto_start:
                messagebox.showinfo("Thông báo", "Danh sách trống, vui lòng thêm tài khoản.")
            return

        is_running = True
        
        try:
            max_t = int(max_threads_var.get())
        except ValueError:
            max_t = 5
            
        import queue
        task_queue = queue.Queue()
        active_tasks = 0
        active_lock = threading.Lock()
        
        def browser_worker():
            nonlocal active_tasks
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(
                        channel="chrome", 
                        headless=False,
                        args=['--disable-blink-features=AutomationControlled']
                    )
                except Exception as e:
                    log_msg(f"Lỗi khởi động trình duyệt: {e}")
                    return
                    
                while True:
                    task = task_queue.get()
                    if task is None: # Tín hiệu dừng
                        break
                        
                    with active_lock:
                        active_tasks += 1
                        
                    fi, item_stt, email, pwd, ac, np = task
                    
                    # Cập nhật GUI thành Đang chạy...
                    root.after(0, lambda i=fi, s=item_stt, e=email, p=pwd, ac=ac, np=np: queue_table.item(i, values=(s, e, p, "🚀 Đang chạy...", ac, np), tags=("running",)) if queue_table.exists(i) else None)
                    
                    prefix = email.split('@')[0]
                    def thread_log(msg):
                        log_msg(f"[{prefix}] {msg}")
                        
                    thread_log(f"--- Bắt đầu chạy ---")
                    status_text = "❌ Lỗi / Timeout"
                    signout_text = "N/A"
                    pwd_text = "N/A"
                    result_text = "Fail"
                    final_pwd = pwd
                    
                    try:
                        is_auto = (ac == "True")
                        res = login(browser, email, pwd, thread_log, auto_change=is_auto, new_pwd=np)
                        if res is not None:
                            has_sg, signed_out, pwd_changed = res
                            if has_sg is True:
                                status_text = "🌟 CÓ (SuperGrok)"
                            elif has_sg is False:
                                status_text = "⚪ KHÔNG (Thường)"
                            else:
                                status_text = "⚠️ KHÔNG RÕ"
                            signout_text = "✅ Rồi" if signed_out else "❌ Chưa"
                            pwd_text = "✅ Rồi" if pwd_changed else "❌ Chưa"
                            if pwd_changed:
                                final_pwd = np
                            
                            if has_sg and signed_out and pwd_changed:
                                result_text = "✅ Pass"
                            else:
                                result_text = "❌ Fail"
                    except Exception as ex:
                        log_msg(f"Lỗi Bot ({email}): {str(ex)}")
                    
                    def update_tables(f=fi, e2=email, p2=final_pwd, st=status_text, so=signout_text, pt=pwd_text, rt=result_text):
                        if queue_table.exists(f):
                            queue_table.delete(f)
                        completed_stt = len(completed_table.get_children()) + 1
                        tag = "pass" if "Pass" in rt else "fail"
                        completed_table.insert("", tk.END, values=(completed_stt, e2, p2, st, so, pt, rt), tags=(tag,))
                    
                    root.after(0, update_tables)
                    
                    with active_lock:
                        active_tasks -= 1
                    task_queue.task_done()
                    
                browser.close()

        def dispatcher():
            nonlocal is_running
            import time
            
            # Khởi tạo pool
            threads = []
            for _ in range(max_t):
                t = threading.Thread(target=browser_worker, daemon=True)
                t.start()
                threads.append(t)
                
            dispatched = set()
            
            while True:
                items = queue_table.get_children()
                pending_count = 0
                
                for item in items:
                    if item not in dispatched:
                        val = queue_table.item(item, "values")
                        if len(val) >= 4 and val[3] == "⏳ Đang chờ":
                            ac = val[4] if len(val) > 4 else "False"
                            np = val[5] if len(val) > 5 else ""
                            task_queue.put((item, val[0], val[1], val[2], ac, np))
                            dispatched.add(item)
                            pending_count += 1
                
                with active_lock:
                    current_active = active_tasks
                    
                # Hết việc
                if len(queue_table.get_children()) == 0 and task_queue.empty() and current_active == 0:
                    break
                    
                time.sleep(1)
                
            # Dừng các thread
            for _ in range(max_t):
                task_queue.put(None)
                
            is_running = False
            log_msg("\n--- Hoàn thành tất cả các tiến trình ---")

        threading.Thread(target=dispatcher, daemon=True).start()

    # -- Khu vực BẢNG ĐÃ CHẠY (Bên trái - Dưới cùng) --
    tk.Label(left_frame, text="Bảng kết quả:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
    columns_c = ("stt", "email", "pass", "supergrok", "signout", "pwd_changed", "result")
    completed_table = ttk.Treeview(left_frame, columns=columns_c, show="headings", height=8)
    completed_table.heading("stt", text="STT")
    completed_table.heading("email", text="Email")
    completed_table.heading("pass", text="Password")
    completed_table.heading("supergrok", text="SuperGrok")
    completed_table.heading("signout", text="Đăng xuất")
    completed_table.heading("pwd_changed", text="Đổi MK")
    completed_table.heading("result", text="Kết quả")
    completed_table.column("stt", width=40, anchor="center")
    completed_table.column("email", width=150)
    completed_table.column("pass", width=100)
    completed_table.column("supergrok", width=100, anchor="center")
    completed_table.column("signout", width=80, anchor="center")
    completed_table.column("pwd_changed", width=80, anchor="center")
    completed_table.column("result", width=80, anchor="center")
    completed_table.tag_configure("pass", background="#d4edda")
    completed_table.tag_configure("fail", background="#f8d7da")
    completed_table.pack(fill=tk.BOTH, expand=True, pady=5)

    def on_double_click(event):
        item = completed_table.identify_row(event.y)
        column = completed_table.identify_column(event.x)
        if item and column:
            try:
                col_idx = int(column.replace('#', '')) - 1
                values = completed_table.item(item, 'values')
                if col_idx < len(values):
                    cell_value = str(values[col_idx])
                    root.clipboard_clear()
                    root.clipboard_append(cell_value)
                    log_msg(f"📋 Đã copy: {cell_value}")
            except Exception:
                pass
                
    completed_table.bind("<Double-1>", on_double_click)

    export_frame = tk.Frame(left_frame)
    export_frame.pack(fill=tk.X, pady=5)
    
    tk.Label(export_frame, text="Lọc:").pack(side=tk.LEFT)
    filter_var = tk.StringVar(value="Tất cả")
    filter_cb = ttk.Combobox(export_frame, textvariable=filter_var, values=["Tất cả", "Có SuperGrok", "Không SuperGrok", "Lỗi"], state="readonly", width=15)
    filter_cb.pack(side=tk.LEFT, padx=5)
    
    def do_export():
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
        if not path:
            return
        
        f_val = filter_var.get()
        with open(path, "w", encoding="utf-8") as f:
            for item in completed_table.get_children():
                val = completed_table.item(item, "values")
                if len(val) < 7: continue
                stt, e, p, status, signout, pwd_changed_status, result_status = val
                
                if f_val == "Có SuperGrok" and "CÓ" not in status:
                    continue
                if f_val == "Không SuperGrok" and "KHÔNG" not in status:
                    continue
                if f_val == "Lỗi" and "Lỗi" not in status:
                    continue
                    
                f.write(f"{e}|{p}\n")
        messagebox.showinfo("Thành công", f"Đã xuất file {path}")
        
    export_btn = tk.Button(export_frame, text="Xuất file", command=do_export, state=tk.DISABLED)
    export_btn.pack(side=tk.LEFT, padx=5)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
