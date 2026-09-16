import sys
import os

# Thêm đường dẫn hiện tại vào sys.path để import src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.gui import run_gui

if __name__ == "__main__":
    run_gui()
