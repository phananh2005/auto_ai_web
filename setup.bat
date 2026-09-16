@echo off
echo Kiem tra Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Ban chua cai Python! May tinh se tu mo web de ban tai.
    start https://www.python.org/downloads/
    pause
    exit /b
)

echo Tao moi truong ao (venv)...
python -m venv venv
call venv\Scripts\activate.bat

echo Cai dat thu vien...
pip install -r requirements.txt

echo Cai dat trinh duyet cho bot...
playwright install chromium

echo Hoan tat! 
echo De chay tool: click dup vao file "run.bat" (chua co thi tao run.bat voi lenh: call venv\Scripts\activate.bat ^& python main.py)
pause
