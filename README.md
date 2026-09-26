# Auto AI Web

Công cụ tự động hóa tài khoản X.ai và Grok với giao diện Tkinter đa luồng và Playwright.

---

## 1. Tính năng chính

- Đăng nhập tự động tài khoản X.ai / Grok.
- Kiểm tra trạng thái gói đăng ký SuperGrok trên Grok.com.
- Đăng xuất tài khoản khỏi tất cả thiết bị trên X.ai.
- Đổi mật khẩu tài khoản X.ai tự động.
- Giao diện Tkinter đa luồng, hỗ trợ import danh sách tài khoản, hiển thị tiến độ và log chi tiết.

---

## 2. Cài đặt và chạy từ mã nguồn

### Yêu cầu
- Windows 10/11 64-bit
- Python 3.10+

### Thiết lập ban đầu
Chạy script cài đặt tự động:
```cmd
setup.bat
```
Hoặc thủ công:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### Chạy ứng dụng
```cmd
run.bat
```
Hoặc:
```cmd
python main.py
```

---

## 3. Đóng gói thành file chạy độc lập (.exe)

Ứng dụng có thể đóng gói thành thư mục portable chạy trên Windows mà không cần cài đặt Python.

Chi tiết xem tại [PACKAGING.md](PACKAGING.md).

Để đóng gói nhanh:
```cmd
build.bat
```
Kết quả sau khi build nằm tại `dist\auto_ai_web\auto_ai_web.exe`.
