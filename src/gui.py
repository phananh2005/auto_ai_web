import tkinter as tk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
import threading
from src.bot import login

def run_gui():
    root = tk.Tk()
    root.title("X.ai Auto Login")
    root.geometry("400x350")

    def log_msg(msg):
        root.after(0, lambda: log_area.insert(tk.END, msg + "\n"))
        root.after(0, lambda: log_area.see(tk.END))

    def on_login():
        email = email_entry.get()
        password = password_entry.get()
        if not email or not password:
            messagebox.showwarning("Thiếu", "Nhập đủ email và mật khẩu.")
            return
        
        log_msg("--- Bắt đầu ---")
        def bot_thread():
            try:
                login(email, password, log_msg)
            except Exception as e:
                log_msg(f"Lỗi Bot: {str(e)}")
                
        threading.Thread(target=bot_thread).start()

    tk.Label(root, text="Email:").pack(pady=5)
    email_entry = tk.Entry(root, width=40)
    email_entry.pack()

    tk.Label(root, text="Mật khẩu:").pack(pady=5)
    password_entry = tk.Entry(root, width=40, show="*")
    password_entry.pack()

    def toggle_password():
        if show_pass_var.get():
            password_entry.config(show="")
        else:
            password_entry.config(show="*")
            
    show_pass_var = tk.BooleanVar()
    tk.Checkbutton(root, text="Hiện mật khẩu", variable=show_pass_var, command=toggle_password).pack()

    btn = tk.Button(root, text="Đăng nhập", command=on_login, width=15, height=2)
    btn.pack(pady=10)

    log_area = ScrolledText(root, height=8, width=45)
    log_area.pack(pady=5)

    root.mainloop()
