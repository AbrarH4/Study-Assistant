"""Network and Ollama connectivity helpers.

These lightweight checks are called at startup to decide which providers
are available before the main UI is displayed to the user.
"""

import urllib.request
import shutil


def check_internet_connection(timeout=3):
    """Check whether the machine has a live internet connection.

    Attempts a GET to Google's homepage within *timeout* seconds.
    Any exception (DNS failure, timeout, refused connection) is treated as
    offline so the function never raises.

    Args:
        timeout: Maximum seconds to wait for a response. Defaults to 3.

    Returns:
        True if the request succeeds, False otherwise.
    """
    try:
        urllib.request.urlopen("https://google.com", timeout=timeout)
        return True
    except Exception:
        return False


def check_ollama_running():
    """Check whether the Ollama local inference daemon is reachable.

    Pings the Ollama REST API root at http://localhost:11434. A successful
    response means the daemon is running and models can be queried locally
    without an internet connection.

    Returns:
        True if Ollama responds within 2 seconds, False otherwise.
    """
    try:
        urllib.request.urlopen("http://localhost:11434", timeout=2)
        return True
    except Exception:
        return False


def check_ollama_installed():
    """Check whether the ``ollama`` CLI binary is present on PATH.

    Uses shutil.which which performs the same lookup the shell would.
    This does not check whether the daemon is running, only that the
    executable exists on disk.

    Returns:
        True if ``ollama`` is found on PATH, False otherwise.
    """
    return shutil.which("ollama") is not None
