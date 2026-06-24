from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()
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
# =====================================================================

# Premium User-Defined Palette Hex Codes
BG_MAIN = "#0D0E12"  # Deep Obsidian Base
BG_CARD = "#161920"  # Elevated Slate Containers
BORDER_COLOR = "#262930"  # Subtle crisp border
ACCENT_COLOR = "#4F46E5"  # Premium Indigo Action Button
ACCENT_HOVER = "#4338CA"  # Deep Indigo Hover

TEXT_PRIMARY = "#E2E8F0"  # Crisp White-Slate (High Contrast Headers)
TEXT_SECONDARY = "#94A3B8"  # Muted Slate Gray (Comfortable Body Text)
TEXT_DISABLED = "#475569"  # Receding Hint/Placeholder Gray
TEXT_INTERACTIVE = "#F2F0E8"  # Saffron Yellow Accent Highlight

# =====================================================================
# LOGIC ENGINE
# =====================================================================
BASE_DIR = Path(__file__).parent

SETTINGS_FILE = BASE_DIR / "settings.json"
STOP_WORDS_FILE = BASE_DIR / "STOP_WORDS.json"

APP_VERSION = "1.0.0"
EMBEDDINGS_CACHE_FILE = BASE_DIR / "embeddings_cache.pkl"

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".pptx"}
