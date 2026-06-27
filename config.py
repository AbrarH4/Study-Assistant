"""Application-wide configuration: paths, theme constants, and provider list."""

import sys
from dotenv import load_dotenv
from pathlib import Path
import os

# Load environment variables from .env file (API keys etc.)
load_dotenv()

# Each provider is tried in order until one succeeds. Ollama is listed first
# so offline / local inference is preferred when the daemon is running.
# Cloud providers are skipped automatically if their key is missing.
PROVIDERS = [
    {
        "name": "Ollama (Local)",
        "url": "http://localhost:11434/v1",
        "key": "ollama",
        "model": "llama3.2",
    },
    {
        "name": "Google AI Studio",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key": os.getenv("GEMINI_API_KEY"),
        "model": "gemini-2.5-flash",
    },
    {
        "name": "Groq Cloud",
        "url": "https://api.groq.com/openai/v1",
        "key": os.getenv("GROQ_API_KEY"),
        "model": "llama-3.3-70b-versatile",
    },
    {
        "name": "OpenRouter Free",
        "url": "https://openrouter.ai/api/v1",
        "key": os.getenv("OPENROUTER_API_KEY"),
        "model": "openrouter/free",
    },
]

# UI colour palette
BG_MAIN = "#0D0E12"        # Deep obsidian base, root window background
BG_CARD = "#161920"        # Slightly elevated slate for card / panel surfaces
BORDER_COLOR = "#262930"   # Subtle border that separates cards
ACCENT_COLOR = "#4F46E5"   # Primary indigo, CTAs and progress indicators
ACCENT_HOVER = "#4338CA"   # Darker indigo for button hover state

TEXT_PRIMARY = "#E2E8F0"       # High-contrast white-slate for headings and labels
TEXT_SECONDARY = "#94A3B8"     # Muted slate gray for body copy
TEXT_DISABLED = "#475569"      # Receding gray for placeholders and hints
TEXT_INTERACTIVE = "#F2F0E8"   # Warm off-white for interactive accent highlights


def get_resource_path(filename):
    """Resolve a resource file path for both development and PyInstaller builds.

    Args:
        filename: Name of the resource file (e.g. ``"STOP_WORDS.json"``).

    Returns:
        A pathlib.Path pointing to the resource, whether the app is running
        from source or from a PyInstaller bundle (sys._MEIPASS).
    """
    if getattr(sys, "frozen", False):
        # PyInstaller extracts bundled files to a temp directory at runtime
        return Path(sys._MEIPASS) / filename

    return Path(__file__).parent / filename


# Persistent application directory in the user's APPDATA folder
APP_DIR = Path(os.getenv("APPDATA")) / "Ace"
APP_DIR.mkdir(parents=True, exist_ok=True)   # Create on first run if absent

# JSON file that stores user preferences (e.g. notes folder path)
SETTINGS_FILE = APP_DIR / "settings.json"

# JSON list of common English stop words used during keyword extraction
STOP_WORDS_FILE = get_resource_path("STOP_WORDS.json")

APP_VERSION = "1.0.0"

# Cached sentence-transformer embeddings persisted between sessions to avoid
# re-encoding unchanged files on every launch
EMBEDDINGS_CACHE_FILE = APP_DIR / "embeddings_cache.pkl"

# File extensions that the note loader will read and index
ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx"}
