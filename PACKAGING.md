# Hướng dẫn đóng gói ứng dụng Auto AI Web cho Windows

Tài liệu hướng dẫn đóng gói dự án **auto_ai_web** thành thư mục chạy độc lập (Portable Folder) cho Windows mà không cần cài đặt Python trên máy đích.

---

## 1. Yêu cầu môi trường build

Trước khi thực hiện đóng gói, máy tính cần có:
- **Python 3.10+** (đã cài đặt các gói trong `requirements.txt`).
- **Playwright Chromium**: đã cài đặt thông qua `playwright install chromium`.
- **PyInstaller**: sẽ tự động được kiểm tra và cài đặt trong `build.bat` nếu chưa có.

---

## 2. Quy trình đóng gói tự động

Chỉ cần chạy file `build.bat`:
```cmd
build.bat
```

Script sẽ thực hiện tuần tự:
1. Kiểm tra môi trường Python.
2. Kiểm tra hoặc cài đặt `pyinstaller`.
3. Đóng gói mã nguồn theo file cấu hình `auto_ai_web.spec` (chế độ `--onedir`).
4. Tự động sao chép thư mục trình duyệt Playwright từ `%LOCALAPPDATA%\ms-playwright` vào `dist\auto_ai_web\ms-playwright`.

---

## 3. Cấu trúc thư mục sau khi build

Sau khi build thành công, thư mục `dist\auto_ai_web\` sẽ có cấu trúc như sau:

```
dist/
└── auto_ai_web/
    ├── auto_ai_web.exe         <- File thực thi chính để mở tool
    ├── _internal/              <- Python runtime, thư viện và playwright driver
    └── ms-playwright/          <- Trình duyệt Chromium đi kèm (chạy offline)
        └── chromium-xxxx/
```

---

## 4. Cách thức phân phối

1. Nén toàn bộ thư mục `dist\auto_ai_web\` thành file `.zip` (ví dụ `auto_ai_web_portable.zip`).
2. Gửi file nén cho người dùng trên bất kỳ máy Windows nào (Windows 10/11 64-bit).
3. Người dùng giải nén và chỉ cần nhấp đúp vào `auto_ai_web.exe` để sử dụng trực tiếp mà không cần cài đặt Python hay thư viện nào khác.

---

## 5. Xử lý sự cố thường gặp

- **Lỗi không tìm thấy trình duyệt Playwright**:
  - Đảm bảo thư mục `ms-playwright` nằm ngay cạnh file `auto_ai_web.exe`.
  - Hoặc trên máy đích có sẵn Google Chrome chuẩn (tool sẽ tự động phát hiện và sử dụng Chrome).
  - Hoặc mở CMD tại máy đích và chạy: `playwright install chromium`.

- **Màn hình console đen**:
  - File `.spec` hiện để `console=True` để người dùng dễ theo dõi log khởi động và bắt lỗi. Nếu muốn ẩn cửa sổ console này, mở file `auto_ai_web.spec`, sửa `console=False` và chạy lại `build.bat`.
