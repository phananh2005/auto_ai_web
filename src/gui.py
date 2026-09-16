import tkinter as tk
from tkinter import messagebox
import threading
from src.bot import login

def run_gui():
    def on_login():
        email = email_entry.get()
        password = password_entry.get()
        if not email or not password:
            messagebox.showwarning("Thiếu", "Nhập đủ email và mật khẩu.")
            return
        
        def bot_thread():
            try:
                login(email, password)
            except Exception as e:
                messagebox.showerror("Lỗi Bot", str(e))
                
        threading.Thread(target=bot_thread).start()

    root = tk.Tk()
    root.title("X.ai Auto Login")
    root.geometry("300x200")

    tk.Label(root, text="Email:").pack(pady=5)
    email_entry = tk.Entry(root, width=30)
    email_entry.pack()

    tk.Label(root, text="Mật khẩu:").pack(pady=5)
    password_entry = tk.Entry(root, width=30, show="*")
    password_entry.pack()

    btn = tk.Button(root, text="Đăng nhập", command=on_login, width=15, height=2)
    btn.pack(pady=15)

    root.mainloop()
