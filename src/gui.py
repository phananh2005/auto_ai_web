import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import threading
from src.bot import login

def run_gui():
    root = tk.Tk()
    root.title("X.ai Auto Login - Trình quản lý tài khoản")
    root.geometry("900x600")

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
    password_entry = tk.Entry(input_frame, width=35, show="*")
    password_entry.grid(row=1, column=1, padx=5, pady=2)

    def add_to_queue():
        email = email_entry.get().strip()
        pwd = password_entry.get().strip()
        if not email or not pwd:
            messagebox.showwarning("Thiếu", "Nhập đủ email và mật khẩu.")
            return
        stt = len(queue_table.get_children()) + 1
        queue_table.insert("", tk.END, values=(stt, email, pwd, "⏳ Đang chờ"))
        email_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
        
        # Luôn tự động chạy
        process_queue(auto_start=True)

    add_btn = tk.Button(input_frame, text="Thêm vào danh sách", command=add_to_queue)
    add_btn.grid(row=2, column=1, sticky="w", pady=5)
    
    tk.Label(input_frame, text="Số tài khoản chạy song song:").grid(row=3, column=0, sticky="w", pady=2)
    max_threads_var = tk.StringVar(value="5")
    max_threads_entry = tk.Entry(input_frame, textvariable=max_threads_var, width=10)
    max_threads_entry.grid(row=3, column=1, sticky="w", padx=5, pady=2)

    # -- Khu vực BẢNG PHÒNG CHỜ (Bên trái - Giữa) --
    tk.Label(left_frame, text="Đang chạy:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
    columns_q = ("stt", "email", "pass", "status")
    queue_table = ttk.Treeview(left_frame, columns=columns_q, show="headings", height=8)
    queue_table.heading("stt", text="STT")
    queue_table.heading("email", text="Email")
    queue_table.heading("pass", text="Password")
    queue_table.heading("status", text="Trạng thái")
    queue_table.column("stt", width=40, anchor="center")
    queue_table.column("email", width=150)
    queue_table.column("pass", width=100)
    queue_table.column("status", width=100, anchor="center")
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
        
        def worker():
            nonlocal is_running
            import time
            while True:
                items = queue_table.get_children()
                running_count = sum(1 for item in items if queue_table.item(item, "values")[3] == "🚀 Đang chạy...")
                
                try:
                    max_t = int(max_threads_var.get())
                except ValueError:
                    max_t = 5
                    
                pending_items = []
                for item in items:
                    val = queue_table.item(item, "values")
                    if len(val) >= 4 and val[3] == "⏳ Đang chờ":
                        pending_items.append((item, val[0], val[1], val[2]))
                
                if not pending_items:
                    # Kiểm tra xem có đang chạy cái nào không
                    if running_count == 0:
                        break # Xong tất cả
                    time.sleep(1)
                    continue
                
                # Nếu đã chạy tối đa số luồng thì đợi
                if running_count >= max_t:
                    time.sleep(1)
                    continue
                
                # Số lượng tài khoản được phép mở thêm
                allowed_to_start = max_t - running_count
                items_to_start = pending_items[:allowed_to_start]
                
                for item_info in items_to_start:
                    fi, item_stt, email, pwd = item_info
                    
                    # Cập nhật GUI thành Đang chạy...
                    root.after(0, lambda i=fi, s=item_stt, e=email, p=pwd: queue_table.item(i, values=(s, e, p, "🚀 Đang chạy...")))
                    
                    def run_account(fi_cb=fi, e_cb=email, p_cb=pwd):
                        log_msg(f"\n--- Bắt đầu chạy: {e_cb} ---")
                        status_text = "❌ Lỗi / Timeout"
                        signout_text = "N/A"
                        try:
                            res = login(e_cb, p_cb, log_msg)
                            if res is not None:
                                has_sg, signed_out = res
                                if has_sg is True:
                                    status_text = "🌟 CÓ (SuperGrok)"
                                elif has_sg is False:
                                    status_text = "⚪ KHÔNG (Thường)"
                                else:
                                    status_text = "⚠️ KHÔNG RÕ"
                                signout_text = "✅ Rồi" if signed_out else "❌ Chưa"
                        except Exception as ex:
                            log_msg(f"Lỗi Bot ({e_cb}): {str(ex)}")
                        
                        def update_tables(f=fi_cb, e2=e_cb, p2=p_cb, st=status_text, so=signout_text):
                            if queue_table.exists(f):
                                queue_table.delete(f)
                            completed_stt = len(completed_table.get_children()) + 1
                            completed_table.insert("", tk.END, values=(completed_stt, e2, p2, st, so))
                        
                        root.after(0, update_tables)
                    
                    # Khởi chạy thread riêng cho tài khoản này
                    threading.Thread(target=run_account, daemon=True).start()
                    time.sleep(1.5) # Tránh mở quá nhiều tab cùng 1 giây gây đơ máy
            
            is_running = False
            log_msg("\n--- Hoàn thành tất cả các tiến trình ---")

        threading.Thread(target=worker, daemon=True).start()

    # -- Khu vực BẢNG ĐÃ CHẠY (Bên trái - Dưới cùng) --
    tk.Label(left_frame, text="Bảng kết quả:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
    columns_c = ("stt", "email", "pass", "supergrok", "signout")
    completed_table = ttk.Treeview(left_frame, columns=columns_c, show="headings", height=8)
    completed_table.heading("stt", text="STT")
    completed_table.heading("email", text="Email")
    completed_table.heading("pass", text="Password")
    completed_table.heading("supergrok", text="SuperGrok")
    completed_table.heading("signout", text="Đăng xuất")
    completed_table.column("stt", width=40, anchor="center")
    completed_table.column("email", width=150)
    completed_table.column("pass", width=100)
    completed_table.column("supergrok", width=100, anchor="center")
    completed_table.column("signout", width=80, anchor="center")
    completed_table.pack(fill=tk.BOTH, expand=True, pady=5)

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
                if len(val) < 5: continue
                stt, e, p, status, signout = val
                
                if f_val == "Có SuperGrok" and "CÓ" not in status:
                    continue
                if f_val == "Không SuperGrok" and "KHÔNG" not in status:
                    continue
                if f_val == "Lỗi" and "Lỗi" not in status:
                    continue
                    
                f.write(f"{e}|{p}\n")
        messagebox.showinfo("Thành công", f"Đã xuất file {path}")
        
    export_btn = tk.Button(export_frame, text="Xuất file", command=do_export)
    export_btn.pack(side=tk.LEFT, padx=5)

    root.mainloop()

if __name__ == "__main__":
    run_gui()
