"""Ace — AI-powered study assistant.

Entry point for the application. Instantiates and starts the main
CustomTkinter UI loop.
"""

from UI import ACEUI

if __name__ == "__main__":
    app = ACEUI()
    app.mainloop()
