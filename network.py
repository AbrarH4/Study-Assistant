# network.py
import urllib.request
import shutil


def check_internet_connection(timeout=3):
    try:
        urllib.request.urlopen("https://google.com", timeout=timeout)
        return True
    except Exception:
        return False


def check_ollama_running():
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=2)
        return True
    except Exception:
        return False


def check_ollama_installed():
    return shutil.which("ollama") is not None
