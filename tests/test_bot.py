import pytest
from src.bot import login

def test_bot_import():
    """Kiểm tra bot import thành công"""
    assert callable(login)
