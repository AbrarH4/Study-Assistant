"""Main application window and all UI logic for Ace.

This module contains:

- AnswerSystem() — assembles retrieved note chunks into an LLM prompt
  and returns the generated answer.
- ACEUI — the single CTk root window that manages the splash screen,
  the main chat interface, the quiz flow, and all supporting dialogs.

Threading model:
    Heavy operations (model loading, re-indexing, LLM calls) run in daemon
    threads. All widget mutations from those threads are dispatched to the
    main thread via self.after(0, callback) to comply with tkinter's
    single-thread restriction.
"""
import re
import customtkinter as ctk
import sys
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox
from loader import load_folder_path, load_notes_from_path, Notes, bg_model_loading
import json

# UI for main.py
# ── Own modules ────────────────────────────────────────
from config import (
    APP_VERSION,
    BG_MAIN,
    BG_CARD,
    BORDER_COLOR,
    ACCENT_COLOR,
    ACCENT_HOVER,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    TEXT_DISABLED,
    SETTINGS_FILE,
)
from quiz import get_quiz_context, test_evaluation
from provider import GenerateQuiz, chat_history, GenerateAnswer
from network import check_ollama_installed
from retrieval import keyword, Ranking_System, get_relevant_chunks

model_loaded = True if bg_model_loading else False

# =====================================================================
# PREMIUM THEME CONFIGURATION (Silicon Valley Corporate Aesthetic)
# =====================================================================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
# =====================================================================
#  ----------------------------------
# =====================================================================
# ANSWER SYSTEM


def AnswerSystem(winning_file_names, encoded_question, original_question):
    """Retrieve relevant chunks from each winning note and call the LLM.

    For every note in winning_file_names, the top semantically relevant
    paragraphs are extracted and concatenated with a SOURCE: <filename> header.
    The assembled context is then passed to GenerateAnswer().

    Args:
        winning_file_names: Ordered list of note filenames from the ranker.
        encoded_question: Pre-computed sentence-transformer tensor for the
            user's question, used to score paragraph relevance.
        original_question: The raw question string forwarded to the LLM.

    Returns:
        The LLM's answer string, or raw context if the LLM call fails,
        or an error message string if an exception occurs.
    """
    try:
        all_context = ""
        for filename in winning_file_names:
            if filename in Notes:
                relevant = get_relevant_chunks(Notes[filename], encoded_question)
                all_context += f"SOURCE: {filename}\n{relevant}\n\n"

        if not all_context:
            return "No relevant context found in selected notes."

        ai_response = GenerateAnswer(original_question, all_context)
        return ai_response if ai_response else all_context

    except Exception as e:
        print(f"Extraction Error: {e}")
        return f"An operational breakdown occurred: {str(e)}"


# =====================================================================


class ACEUI(ctk.CTk):
    """Root application window.

    Manages two top-level states:

    1. Splash / loading — shown while bg_model_loading runs in a background
       thread. Displays a progress bar and status text.
    2. Main UI — shown after the model and notes are ready. Contains the
       search entry, chat history panel, and toolbar buttons.

    The quiz flow replaces the main canvas temporarily with a quiz canvas,
    then restores the main canvas when the user exits.

    Attributes:
        _quiz_data (list): Current quiz question list from the LLM.
        _quiz_index (int): Index of the question currently displayed.
        _quiz_score (int): Number of correct answers in the current session.
        _quiz_answered (bool): Whether the current question has been answered.
    """
    def __init__(self):
        super().__init__()
        self.title("ACE")
        # Quiz state
        self._quiz_data = []
        self._quiz_index = 0
        self._quiz_score = 0
        self._quiz_answered = False
        self.after(0, lambda: self.wm_state("zoomed"))
        if sys.platform.startswith("linux"):
            self.attributes("-zoomed", True)
        else:
            self.state("zoomed")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ------------------- SPLASH SCREEN -------------------
        self.loading_frame = ctk.CTkFrame(self, fg_color=BG_MAIN)
        self.loading_frame.grid(row=0, column=0, sticky="nsew")
        self.loading_frame.grid_rowconfigure(0, weight=1)
        self.loading_frame.grid_rowconfigure(1, weight=0)
        self.loading_frame.grid_rowconfigure(2, weight=0)
        self.loading_frame.grid_rowconfigure(3, weight=0)
        self.loading_frame.grid_rowconfigure(4, weight=0)
        self.loading_frame.grid_rowconfigure(5, weight=1)
        self.loading_frame.grid_rowconfigure(6, weight=0)
        self.loading_frame.grid_rowconfigure(7, weight=0)
        self.loading_frame.grid_columnconfigure(0, weight=1)

        # App name — large, centered, indigo-tinted white
        self.loading_app_name = ctk.CTkLabel(
            self.loading_frame,
            text="ACE",
            font=ctk.CTkFont(family="Segoe UI", size=42, weight="bold"),
            text_color="#E8EEFF",
        )
        self.loading_app_name.grid(row=1, column=0, pady=(0, 6))

        # Tagline — small, muted, below the name
        self.loading_tagline = ctk.CTkLabel(
            self.loading_frame,
            text="Your personal AI-powered notebook",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#4F6080",
        )
        self.loading_tagline.grid(row=2, column=0, pady=(0, 48))

        # Status text — updates as each stage completes
        self.loading_text = ctk.CTkLabel(
            self.loading_frame,
            text="Checking connection…",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#475569",
        )
        self.loading_text.grid(row=3, column=0, pady=(0, 10))

        # Thin progress bar — full width, barely 4px tall
        self.progress_bar = ctk.CTkProgressBar(
            self.loading_frame,
            height=3,
            corner_radius=2,
            fg_color="#1E2433",
            progress_color=ACCENT_COLOR,
        )
        self.progress_bar.grid(row=4, column=0, padx=200, pady=(0, 0), sticky="ew")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        # Version tag — bottom left, barely visible
        self.loading_version = ctk.CTkLabel(
            self.loading_frame,
            text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#262930",
        )
        self.loading_version.grid(row=5, column=0, pady=(0, 20))
        # ------------------- MAIN INTERFACE (Hidden Initially) -------------------
        self.main_canvas = ctk.CTkFrame(self, fg_color="transparent")
        self.main_canvas.grid_columnconfigure(0, weight=1)
        self.main_canvas.grid_rowconfigure(3, weight=1)

        self.header_label = ctk.CTkLabel(
            self.main_canvas,
            text=f" ACE {APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="center",
        )
        self.header_label.grid(row=0, column=0, pady=(0, 5), sticky="ew")

        display_path = load_folder_path() if load_folder_path() else "No Path Indexed"
        self.sub_header = ctk.CTkLabel(
            self.main_canvas,
            text=f"• DIRECTORY: {Path(display_path).name}",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#677EB6",
            anchor="center",
        )
        self.sub_header.grid(row=1, column=0, pady=(0, 20), sticky="ew")

        self.control_panel = ctk.CTkFrame(
            self.main_canvas,
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=12,
        )
        self.control_panel.grid(row=2, column=0, pady=(0, 20), sticky="ew")
        self.control_panel.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            self.control_panel,
            placeholder_text="Ask your question here...",
            height=45,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color=BG_MAIN,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_DISABLED,
            corner_radius=8,
            justify="center",
        )
        self.search_entry.grid(row=0, column=0, padx=(20, 10), pady=20, sticky="ew")
        self.search_entry.bind("<Return>", lambda event: self.ui_trigger_search_flow())

        self.btn_frame = ctk.CTkFrame(self.control_panel, fg_color="transparent")
        self.btn_frame.grid(row=0, column=1, padx=(0, 20), pady=20)

        self.search_btn = ctk.CTkButton(
            self.btn_frame,
            text="Analyze",
            height=45,
            width=100,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            command=self.ui_trigger_search_flow,
        )
        self.search_btn.grid(row=0, column=0, padx=(0, 5))

        self.path_btn = ctk.CTkButton(
            self.btn_frame,
            text="⚙ Path",
            height=45,
            width=80,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#1F2937",
            hover_color="#374151",
            text_color=TEXT_PRIMARY,
            corner_radius=8,
            command=self.ui_change_path_flow,
        )
        self.path_btn.grid(row=0, column=1, padx=(0, 5))

        self.quiz_btn = ctk.CTkButton(
            self.btn_frame,
            text="⚡ Quiz Me",
            height=45,
            width=90,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#1E1B4B",
            hover_color="#312E81",
            text_color="#818CF8",
            corner_radius=8,
            command=self.open_quiz_setup,
        )
        self.quiz_btn.grid(row=0, column=2)

        # ── CHAT PANEL ────────────────────────────────────────────────
        self.chat_frame = ctk.CTkScrollableFrame(
            self.main_canvas,
            fg_color="#0F1117",
            border_color="#1E2433",
            border_width=1,
            corner_radius=14,
            scrollbar_button_color="#1E2433",
            scrollbar_button_hover_color="#2A3550",
        )
        self.chat_frame.grid(row=3, column=0, sticky="nsew")
        self.chat_frame.grid_columnconfigure(0, weight=1)

        # Welcome message
        self._add_system_message("Ready. Ask your first question.")
        self._last_answer_widget = None

        threading.Thread(target=bg_model_loading, args=(self,), daemon=True).start()

    # ── MESSAGE BUILDERS ───────────────────────────────────────────────

    def _add_system_message(self, text):
        """Small centered system notice — used for ready state, reindex confirmation etc."""
        label = ctk.CTkLabel(
            self.chat_frame,
            text=text,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color="#59709B",
            anchor="center",
        )
        label.grid(pady=(12, 4), padx=20, sticky="ew")

    def _add_user_bubble(self, question):
        """User question — muted, italic, left-aligned with a dot marker."""
        frame = ctk.CTkFrame(
            self.chat_frame,
            fg_color="transparent",
            border_width=0,
        )
        frame.grid(pady=(20, 2), padx=(20, 60), sticky="ew")
        frame.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            frame,
            text=f"● {question}",
            font=ctk.CTkFont(family="Segoe UI", size=12, slant="italic"),
            text_color="#435C86",
            anchor="w",
            justify="left",
            wraplength=900,
        )
        label.grid(row=0, column=0, sticky="ew")

    def _add_answer_bubble(self):
        """
        AI answer bubble — dark card with a copy button.
        Returns (textbox, copy_button) so the streamer can write into it.
        """
        outer = ctk.CTkFrame(
            self.chat_frame,
            fg_color="#131822",
            border_color="#1E2D45",
            border_width=1,
            corner_radius=12,
        )
        outer.grid(pady=(4, 8), padx=(20, 20), sticky="ew")
        outer.grid_columnconfigure(0, weight=1)

        # Header row — tiny "AI" label on left, copy button on right
        header = ctk.CTkFrame(outer, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(10, 0), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ai_label = ctk.CTkLabel(
            header,
            text="ACE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color="#2A3D5C",
            anchor="w",
        )
        ai_label.grid(row=0, column=0, sticky="w")

        copy_btn = ctk.CTkButton(
            header,
            text="⎘ Copy",
            width=60,
            height=22,
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color="#1A2540",
            hover_color="#243050",
            text_color="#3D5070",
            corner_radius=6,
            border_width=0,
        )
        copy_btn.grid(row=0, column=1, sticky="e")

        # Answer textbox — auto-sized, no scrollbar, disabled until written
        answer_box = ctk.CTkTextbox(
            outer,
            fg_color="transparent",
            border_width=0,
            text_color="#C8D0E0",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            wrap="word",
            activate_scrollbars=False,
            height=40,
            spacing1=3,
            spacing2=2,
            spacing3=6,
        )
        answer_box.grid(row=1, column=0, padx=14, pady=(6, 14), sticky="ew")

        # Configure tags on the answer box
        tb = answer_box._textbox
        tb.tag_config(
            "h1",
            font=("Segoe UI", 20, "bold"),
            foreground="#E8EEFF",
            spacing1=16,
            spacing3=4,
        )
        tb.tag_config(
            "h2",
            font=("Segoe UI", 14, "bold"),
            foreground="#F0F4FF",
            spacing1=12,
            spacing3=2,
        )
        tb.tag_config(
            "body", font=("Segoe UI", 14), foreground="#D7DDEA", spacing1=2, spacing3=4
        )
        tb.tag_config(
            "bullet_marker", font=("Segoe UI", 14, "bold"), foreground="#306278"
        )
        tb.tag_config(
            "bullet_text", font=("Segoe UI", 14), foreground="#EDF0F3", spacing3=3
        )
        tb.tag_config(
            "divider",
            font=("Segoe UI", 6),
            foreground="#2E3955",
            spacing1=8,
            spacing3=8,
        )
        tb.tag_config(
            "source_label",
            font=("Segoe UI", 10, "bold"),
            foreground="#2C384A",
            spacing1=12,
            spacing3=2,
        )
        tb.tag_config(
            "source_item", font=("Segoe UI", 11), foreground="#425B86", spacing3=2
        )

        answer_box.configure(state="disabled")

        # Wire copy button to this specific answer box
        def do_copy():
            """Copy the answer card's plain text to the system clipboard."""
            content = answer_box._textbox.get("1.0", ctk.END).strip()
            if not content:
                return
            self.clipboard_clear()
            self.clipboard_append(content)
            copy_btn.configure(text="✓ Copied", text_color="#38BDF8")
            self.after(
                1500, lambda: copy_btn.configure(text="⎘ Copy", text_color="#3D5070")
            )

        copy_btn.configure(command=do_copy)

        return answer_box, outer

    def _resize_answer_box(self, answer_box):
        """Grow the textbox height to fit its content after each line is added."""
        answer_box._textbox.update_idletasks()
        line_count = int(answer_box._textbox.index("end-1c").split(".")[0])
        answer_box.configure(height=max(40, line_count * 22))

    def _scroll_to_bottom(self):
        """Force the scrollable frame to scroll to the bottom."""
        self.chat_frame._parent_canvas.yview_moveto(1.0)

    def open_quiz_setup(self):
        """Opens the quiz configuration dialog."""
        if not model_loaded:
            messagebox.showerror("Not Ready", "Model is still loading, please wait.")
            return
        if not Notes:
            messagebox.showerror(
                "No Notes", "No notes are indexed. Please select a notes folder first."
            )
            return

        # ── Setup dialog ──
        dialog = ctk.CTkToplevel(self)
        dialog.title("Quiz Setup")
        dialog.geometry("420x380")
        dialog.resizable(False, False)
        dialog.configure(fg_color=BG_MAIN)
        dialog.grab_set()  # modal

        ctk.CTkLabel(
            dialog,
            text="Quiz Setup",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            dialog,
            text="Configure your quiz session",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_DISABLED,
        ).pack(pady=(0, 24))

        # Topic
        ctk.CTkLabel(
            dialog,
            text="Topic  (leave blank for all notes)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=32)
        topic_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="e.g. photosynthesis, neural networks…",
            height=38,
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_DISABLED,
            corner_radius=8,
        )
        topic_entry.pack(fill="x", padx=32, pady=(4, 14))

        # Question count
        ctk.CTkLabel(
            dialog,
            text="Number of questions",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=32)
        count_var = ctk.StringVar(value="5")
        count_menu = ctk.CTkOptionMenu(
            dialog,
            values=["3", "5", "10", "15", "20"],
            variable=count_var,
            fg_color=BG_CARD,
            button_color=ACCENT_COLOR,
            button_hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
            corner_radius=8,
        )
        count_menu.pack(fill="x", padx=32, pady=(4, 14))

        # Question type
        ctk.CTkLabel(
            dialog,
            text="Question type",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=32)
        type_var = ctk.StringVar(value="mixed")
        type_menu = ctk.CTkOptionMenu(
            dialog,
            values=["mixed", "mcq", "true/false"],
            variable=type_var,
            fg_color=BG_CARD,
            button_color=ACCENT_COLOR,
            button_hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
            corner_radius=8,
        )
        type_menu.pack(fill="x", padx=32, pady=(4, 24))

        def start_quiz():
            """Collect dialog values, close dialog, and launch the quiz."""
            topic = topic_entry.get().strip()
            count = int(count_var.get())
            qtype = type_var.get()
            dialog.destroy()
            self.launch_quiz(topic, count, qtype)

        ctk.CTkButton(
            dialog,
            text="Generate Quiz  →",
            height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            command=start_quiz,
        ).pack(fill="x", padx=32)

    def launch_quiz(self, topic, count, qtype):
        """Fetches context, generates quiz in background, then builds UI."""
        self.quiz_btn.configure(state="disabled", text="Generating…")

        def worker():
            """Fetch context and call the LLM quiz generator off the main thread."""
            context = get_quiz_context(topic)
            if not context:
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "No Context", "Could not find relevant notes for that topic."
                    ),
                )
                self.after(
                    0,
                    lambda: self.quiz_btn.configure(state="normal", text="⚡ Quiz Me"),
                )
                return

            quiz = GenerateQuiz(
                context,
                quiz_count=count,
                quiz_type=qtype,
                topic=topic if topic else None,
            )
            if not quiz:
                self.after(
                    0,
                    lambda: messagebox.showerror(
                        "Generation Failed", "Could not generate quiz. Try again."
                    ),
                )
                self.after(
                    0,
                    lambda: self.quiz_btn.configure(state="normal", text="⚡ Quiz Me"),
                )
                return

            self._quiz_data = quiz
            self._quiz_index = 0
            self._quiz_score = 0
            self._quiz_answered = False
            self.after(0, self._build_quiz_ui)

        threading.Thread(target=worker, daemon=True).start()

    def _build_quiz_ui(self):
        """Replaces the main canvas with the quiz panel."""
        self.quiz_btn.configure(state="normal", text="⚡ Quiz Me")

        # Hide main canvas
        self.main_canvas.grid_forget()

        # ── Quiz canvas ──
        self.quiz_canvas = ctk.CTkFrame(self, fg_color="transparent")
        self.quiz_canvas.grid(row=0, column=0, padx=40, pady=30, sticky="nsew")
        self.quiz_canvas.grid_columnconfigure(0, weight=1)
        self.quiz_canvas.grid_rowconfigure(2, weight=1)

        # Top bar
        top_bar = ctk.CTkFrame(self.quiz_canvas, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        top_bar.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            top_bar,
            text="← Back to Chat",
            height=34,
            width=130,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color="#1F2937",
            hover_color="#374151",
            text_color=TEXT_SECONDARY,
            corner_radius=8,
            command=self._exit_quiz,
        ).grid(row=0, column=0, sticky="w")

        self.quiz_progress_label = ctk.CTkLabel(
            top_bar,
            text=f"Question 1 of {len(self._quiz_data)}",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_DISABLED,
            anchor="center",
        )
        self.quiz_progress_label.grid(row=0, column=1, sticky="ew")

        self.quiz_score_label = ctk.CTkLabel(
            top_bar,
            text="Score  0",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#818CF8",
            anchor="e",
        )
        self.quiz_score_label.grid(row=0, column=2, sticky="e")

        # Progress bar
        self.quiz_progress_bar = ctk.CTkProgressBar(
            self.quiz_canvas,
            height=3,
            corner_radius=2,
            fg_color="#1E2433",
            progress_color=ACCENT_COLOR,
        )
        self.quiz_progress_bar.grid(row=1, column=0, sticky="ew", pady=(0, 20))
        self.quiz_progress_bar.set(0)

        # Question area — scrollable so long questions never overflow
        self.quiz_scroll = ctk.CTkScrollableFrame(
            self.quiz_canvas,
            fg_color="transparent",
            border_width=0,
            scrollbar_button_color="#1E2433",
            scrollbar_button_hover_color="#2A3550",
        )
        self.quiz_scroll.grid(row=2, column=0, sticky="nsew")
        self.quiz_scroll.grid_columnconfigure(0, weight=1)

        self._render_question()

    def _render_question(self):
        """Clears quiz scroll area and renders current question + options."""
        # Clear previous widgets
        for w in self.quiz_scroll.winfo_children():
            w.destroy()

        self._quiz_answered = False
        q = self._quiz_data[self._quiz_index]
        total = len(self._quiz_data)

        # Update top bar
        self.quiz_progress_label.configure(
            text=f"Question {self._quiz_index + 1} of {total}"
        )
        self.quiz_progress_bar.set((self._quiz_index) / total)

        # Question card
        q_card = ctk.CTkFrame(
            self.quiz_scroll,
            fg_color="#131822",
            border_color="#1E2D45",
            border_width=1,
            corner_radius=14,
        )
        q_card.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 20))
        q_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            q_card,
            text=f"Q{self._quiz_index + 1}",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color="#2A3D5C",
            anchor="w",
        ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="w")

        ctk.CTkLabel(
            q_card,
            text=q.get("question", ""),
            font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
            text_color="#E8EEFF",
            wraplength=800,
            justify="left",
            anchor="w",
        ).grid(row=1, column=0, padx=20, pady=(0, 20), sticky="w")

        # Options
        options = q.get("options", [])
        self._option_buttons = []

        for i, opt in enumerate(options):
            btn = ctk.CTkButton(
                self.quiz_scroll,
                text=opt,
                height=52,
                font=ctk.CTkFont(family="Segoe UI", size=14),
                fg_color="#0F1117",
                hover_color="#1A2235",
                text_color="#94A3B8",
                border_color="#1E2433",
                border_width=1,
                corner_radius=10,
                anchor="w",
                command=lambda o=opt: self._handle_answer(o),
            )
            btn.grid(row=i + 1, column=0, sticky="ew", padx=4, pady=5)
            self._option_buttons.append(btn)

        # Next / finish placeholder — hidden until answered
        self._next_btn = ctk.CTkButton(
            self.quiz_scroll,
            text="Next  →"
            if self._quiz_index < len(self._quiz_data) - 1
            else "See Results  →",
            height=44,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            command=self._next_question,
        )
        self._next_btn.grid(
            row=len(options) + 2, column=0, sticky="e", padx=4, pady=(16, 4)
        )
        self._next_btn.grid_remove()  # hidden until answered

        # Feedback label placeholder
        self._feedback_label = ctk.CTkLabel(
            self.quiz_scroll,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#E2E8F0",
            wraplength=800,
            justify="left",
            anchor="w",
        )
        self._feedback_label.grid(
            row=len(options) + 1, column=0, sticky="ew", padx=4, pady=(12, 0)
        )

    def _handle_answer(self, chosen):
        """Evaluates the chosen answer and shows feedback."""
        if self._quiz_answered:
            return
        self._quiz_answered = True

        q = self._quiz_data[self._quiz_index]
        result = test_evaluation(
            correct_answer=q.get("answer", ""),
            user_answer=chosen,
            explanation=q.get("explanation", ""),
        )

        if result["correct"]:
            self._quiz_score += 1
            self.quiz_score_label.configure(text=f"Score  {self._quiz_score}")
            feedback_text = f"✓  Correct!\n{result['explanation']}"
            feedback_color = "#22C55E"
        else:
            feedback_text = f"✗  Incorrect.  Correct answer: {result['correct_answer']}\n{result['explanation']}"
            feedback_color = "#EF4444"

        # Color the chosen button
        for btn in self._option_buttons:
            btn_text = btn.cget("text")
            # extract just the letter if option is "A. something"
            btn_letter = (
                btn_text.split(".")[0].strip() if "." in btn_text else btn_text.strip()
            )
            chosen_letter = (
                chosen.split(".")[0].strip() if "." in chosen else chosen.strip()
            )
            correct_letter = (
                result["correct_answer"].split(".")[0].strip()
                if "." in result["correct_answer"]
                else result["correct_answer"].strip()
            )

            if btn_letter == chosen_letter and not result["correct"]:
                btn.configure(
                    fg_color="#3B0F0F", border_color="#EF4444", text_color="#EF4444"
                )
            elif btn_letter == correct_letter:
                btn.configure(
                    fg_color="#0F2A1A", border_color="#22C55E", text_color="#22C55E"
                )
            btn.configure(state="disabled")

        self._feedback_label.configure(text=feedback_text, text_color=feedback_color)
        self._next_btn.grid()  # reveal next button

    def _next_question(self):
        """Advances to the next question or shows score screen."""
        self._quiz_index += 1
        if self._quiz_index < len(self._quiz_data):
            self._render_question()
        else:
            self._show_score()

    def _show_score(self):
        """Replaces quiz scroll with final score card."""
        for w in self.quiz_scroll.winfo_children():
            w.destroy()

        total = len(self._quiz_data)
        score = self._quiz_score
        pct = int(score / total * 100) if total else 0

        grade, grade_color = (
            ("Outstanding", "#818CF8")
            if pct >= 90
            else ("Great work", "#38BDF8")
            if pct >= 75
            else ("Good effort", "#22C55E")
            if pct >= 60
            else ("Keep studying", "#F59E0B")
        )

        # Score card
        card = ctk.CTkFrame(
            self.quiz_scroll,
            fg_color="#131822",
            border_color="#1E2D45",
            border_width=1,
            corner_radius=16,
        )
        card.grid(row=0, column=0, sticky="ew", padx=4, pady=40)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            card,
            text=f"{score}/{total}",
            font=ctk.CTkFont(family="Segoe UI", size=64, weight="bold"),
            text_color="#E8EEFF",
        ).grid(row=0, column=0, pady=(40, 4))

        ctk.CTkLabel(
            card,
            text=grade,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=grade_color,
        ).grid(row=1, column=0, pady=(0, 6))

        ctk.CTkLabel(
            card,
            text=f"{pct}% correct",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=TEXT_DISABLED,
        ).grid(row=2, column=0, pady=(0, 32))

        self.quiz_progress_bar.set(1.0)
        self.quiz_progress_label.configure(text="Quiz Complete")

        # Buttons row
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.grid(row=3, column=0, pady=(0, 32))

        ctk.CTkButton(
            btn_row,
            text="Try Again",
            height=40,
            width=130,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color="#1F2937",
            hover_color="#374151",
            text_color=TEXT_PRIMARY,
            corner_radius=8,
            command=lambda: self.launch_quiz("", total, "mixed"),
        ).grid(row=0, column=0, padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="← Back to Chat",
            height=40,
            width=130,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            command=self._exit_quiz,
        ).grid(row=0, column=1)

    def _exit_quiz(self):
        """Destroys quiz canvas and restores main chat UI."""
        if hasattr(self, "quiz_canvas"):
            self.quiz_canvas.destroy()
        self.main_canvas.grid(row=0, column=0, padx=40, pady=30, sticky="nsew")

        # ── Setup dialog ──
        dialog = ctk.CTkToplevel(self)
        dialog.title("Quiz Setup")
        dialog.geometry("420x380")
        dialog.resizable(False, False)
        dialog.configure(fg_color=BG_MAIN)
        dialog.grab_set()  # modal

        ctk.CTkLabel(
            dialog,
            text="Quiz Setup",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            dialog,
            text="Configure your quiz session",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_DISABLED,
        ).pack(pady=(0, 24))

        # Topic
        ctk.CTkLabel(
            dialog,
            text="Topic  (leave blank for all notes)",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=32)
        topic_entry = ctk.CTkEntry(
            dialog,
            placeholder_text="e.g. photosynthesis, neural networks…",
            height=38,
            fg_color=BG_CARD,
            border_color=BORDER_COLOR,
            text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_DISABLED,
            corner_radius=8,
        )
        topic_entry.pack(fill="x", padx=32, pady=(4, 14))

        # Question count
        ctk.CTkLabel(
            dialog,
            text="Number of questions",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=32)
        count_var = ctk.StringVar(value="5")
        count_menu = ctk.CTkOptionMenu(
            dialog,
            values=["3", "5", "10", "15", "20"],
            variable=count_var,
            fg_color=BG_CARD,
            button_color=ACCENT_COLOR,
            button_hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
            corner_radius=8,
        )
        count_menu.pack(fill="x", padx=32, pady=(4, 14))

        # Question type
        ctk.CTkLabel(
            dialog,
            text="Question type",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=32)
        type_var = ctk.StringVar(value="mixed")
        type_menu = ctk.CTkOptionMenu(
            dialog,
            values=["mixed", "mcq", "true/false"],
            variable=type_var,
            fg_color=BG_CARD,
            button_color=ACCENT_COLOR,
            button_hover_color=ACCENT_HOVER,
            text_color=TEXT_PRIMARY,
            corner_radius=8,
        )
        type_menu.pack(fill="x", padx=32, pady=(4, 24))

        def start_quiz():
            """Collect dialog values, close dialog, and launch the quiz."""
            topic = topic_entry.get().strip()
            count = int(count_var.get())
            qtype = type_var.get()
            dialog.destroy()
            self.launch_quiz(topic, count, qtype)

        ctk.CTkButton(
            dialog,
            text="Generate Quiz  →",
            height=42,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            command=start_quiz,
        ).pack(fill="x", padx=32)

    # ── NETWORK ERROR ──────────────────────────────────────────────────

    def display_critical_network_error(self, message):
        """Replace the splash progress bar with an offline error state.

        If Ollama is installed but not running, shows instructions to start it.
        If Ollama is not installed, shows a download button.

        Args:
            message: Error detail string available for logging.
        """
        self.progress_bar.stop()
        self.progress_bar.configure(progress_color="#EF4444")
        self.loading_app_name.configure(text_color="#EF4444")
        self.loading_text.configure(
            text="No internet connection detected.", text_color="#EF4444"
        )

        if check_ollama_installed():
            self.loading_tagline.configure(
                text="Ollama is installed but not running.\nOpen a terminal and run:  ollama serve",
                text_color="#475569",
            )
        else:
            self.loading_tagline.configure(
                text="Connect to the internet for cloud AI responses,\nor install Ollama for offline assistance.",
                text_color="#475569",
            )
            self.ollama_btn = ctk.CTkButton(
                self.loading_frame,
                text="⬇  Download Ollama",
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                fg_color=ACCENT_COLOR,
                hover_color=ACCENT_HOVER,
                text_color="#FFFFFF",
                corner_radius=8,
                height=38,
                width=200,
                command=lambda: webbrowser.open("https://ollama.com/download"),
            )
            self.ollama_btn.grid(row=6, column=0, pady=(24, 4))
            self.ollama_size_label = ctk.CTkLabel(
                self.loading_frame,
                text="Ollama installer  ~150 MB  ·  Model (llama3.2)  ~2 GB",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color="#2E3A50",
            )
            self.ollama_size_label.grid(row=7, column=0, pady=(0, 0))

    def update_loading_status(self, text_status):
        """Update the splash screen status label text.

        Called from the background loading thread via self.after(0, ...) so
        the update happens on the main thread.

        Args:
            text_status: The new status string to display.
        """
        self.loading_text.configure(text=text_status)

    def transition_to_main_ui(self):
        """Hide the splash screen and reveal the main chat UI.

        Called on the main thread via self.after(0, ...) once
        bg_model_loading has finished.
        """
        self.progress_bar.stop()
        self.loading_frame.grid_forget()
        self.main_canvas.grid(row=0, column=0, padx=40, pady=30, sticky="nsew")

    # ── PATH CHANGE ────────────────────────────────────────────────────

    def ui_change_path_flow(self):
        """Open a folder picker and re-index notes from the new path.

        Saves the chosen path to SETTINGS_FILE, disables controls during
        re-indexing, then restores them via finish_reindex() on the main thread.
        """
        path_notes = filedialog.askdirectory(title="CHOOSE YOUR NEW NOTES FOLDER.")
        if not path_notes:
            return
        if not model_loaded:
            messagebox.showerror("ERROR", "Model is still loading, please wait.")
            return

        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"path_notes": path_notes}, f, indent=4)

        self.path_btn.configure(state="disabled")
        self.search_btn.configure(state="disabled")

        def reindex_worker():
            """Re-encode all notes in the new folder off the main thread."""
            load_notes_from_path(path_notes)
            self.after(0, lambda: self.finish_reindex(path_notes))

        threading.Thread(target=reindex_worker, daemon=True).start()

    def finish_reindex(self, path_notes):
        """Restore UI state after re-indexing completes.

        Clears conversation history, removes all chat widgets, updates the
        directory sub-header, and shows a confirmation system message.

        Args:
            path_notes: The newly indexed folder path.
        """
        chat_history.clear()
        # Clear all chat widgets
        for widget in self.chat_frame.winfo_children():
            widget.destroy()
        self.sub_header.configure(text=f"• DIRECTORY: {Path(path_notes).name}")
        self._add_system_message(
            f"Indexed  →  {Path(path_notes).name}   Ask your first question."
        )
        self.path_btn.configure(state="normal")
        self.search_btn.configure(state="normal")

    # ── SEARCH FLOW ────────────────────────────────────────────────────

    def ui_trigger_search_flow(self):
        """Handle a user search: add bubbles, animate, and run the pipeline.

        Entry point for the Analyze button and Enter key. Clears the search
        entry, adds a user bubble and an empty answer card, starts a spinner
        animation, and dispatches the ranking + LLM pipeline to a background
        thread.
        """
        if not model_loaded:
            return
        query_text = self.search_entry.get()
        self.search_entry.delete(0, ctk.END)
        if not query_text.strip():
            return

        self.search_btn.configure(state="disabled")
        self.search_entry.configure(state="disabled")

        # Add user bubble immediately
        self._add_user_bubble(query_text)

        # Add answer bubble and get reference to write into
        answer_box, answer_frame = self._add_answer_bubble()
        self._last_answer_widget = answer_box

        # Show thinking indicator inside the answer box
        answer_box.configure(state="normal")
        answer_box._textbox.insert("1.0", "  ⠋  Thinking…", "source_label")
        answer_box.configure(state="disabled")
        self._scroll_to_bottom()

        is_loading = True

        def animate_terminal_loading(tick=0):
            """Cycle through Braille spinner frames until the pipeline completes."""
            if not is_loading:
                return
            frames = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]
            spinner = frames[tick % len(frames)]
            answer_box.configure(state="normal")
            answer_box._textbox.delete("1.0", ctk.END)
            answer_box._textbox.insert("1.0", f"  {spinner}  Thinking…", "source_label")
            answer_box.configure(state="disabled")
            self.after(120, lambda: animate_terminal_loading(tick + 1))

        animate_terminal_loading()

        def async_search_pipeline():
            """Run keyword extraction, ranking, and LLM call in a background thread."""
            nonlocal is_loading
            global input
            old_input = input
            input = lambda: query_text

            extracted_keywords = keyword(query_text)
            ranking_result = Ranking_System(extracted_keywords, query_text)
            input = old_input

            if not ranking_result:
                is_loading = False
                self.after(
                    0,
                    lambda: self.render_fallback_msg(
                        answer_box, "No matching notes found for that query."
                    ),
                )
                return

            winning_file_name, encoded_question_tensor = ranking_result

            if winning_file_name:
                target_text_payload = AnswerSystem(
                    winning_file_name, encoded_question_tensor, query_text
                )
                is_loading = False
                self.after(
                    0,
                    lambda: self.execute_typewriter_stream(
                        answer_box, target_text_payload, winning_file_name
                    ),
                )
            else:
                is_loading = False
                self.after(
                    0,
                    lambda: self.render_fallback_msg(
                        answer_box, "No matching notes found for that query."
                    ),
                )

        threading.Thread(target=async_search_pipeline, daemon=True).start()

    def render_fallback_msg(self, answer_box, msg):
        """Write a plain fallback message into an answer card.

        Used when the ranking pipeline finds no matching notes or the LLM
        pipeline fails entirely.

        Args:
            answer_box: The CTkTextbox card to write into.
            msg: The message to display.
        """
        answer_box.configure(state="normal")
        answer_box._textbox.delete("1.0", ctk.END)
        answer_box._textbox.insert("1.0", msg, "body")
        answer_box.configure(state="disabled")
        self._resize_answer_box(answer_box)
        self._scroll_to_bottom()
        self.search_btn.configure(state="normal")
        self.search_entry.configure(state="normal")

    # ── TYPEWRITER STREAM ──────────────────────────────────────────────

    def execute_typewriter_stream(self, answer_box, target_text_payload, file_sources):
        """Stream the LLM answer into the card one line at a time.

        Parses the LLM's markdown-like output and applies the appropriate
        text tag (h1, h2, body, bullet_marker, bullet_text, divider) per line.
        Each line is scheduled 40ms after the previous via self.after to create
        a typewriter effect without blocking the UI. A source footer listing
        contributing filenames is appended after all lines are written.

        Args:
            answer_box: The CTkTextbox card to stream into.
            target_text_payload: The raw LLM response string.
            file_sources: List of filenames or a single filename string
                indicating which notes contributed to the answer.
        """
        answer_box.configure(state="normal")
        answer_box._textbox.delete("1.0", ctk.END)
        answer_box.configure(state="disabled")

        payload_lines = target_text_payload.strip().splitlines()
        tb = answer_box._textbox

        def clean(line):
            """Strip markdown bold/italic markers the LLM may emit."""
            s = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
            s = re.sub(r"__(.*?)__", s, s)
            s = re.sub(r"\*(.*?)\*", r"\1", s)
            return s

        def stream_line_by_line(line_idx=0):
            """Recursively schedule the next line insert via self.after."""
            if line_idx < len(payload_lines):
                answer_box.configure(state="normal")
                raw = payload_lines[line_idx]
                stripped = raw.strip()

                if stripped.startswith("## "):
                    text = clean(stripped[3:]).strip()
                    tb.insert(ctk.END, f"\n{text}\n", "h1")
                elif stripped.startswith("# "):
                    text = clean(stripped[2:]).strip()
                    tb.insert(ctk.END, f"\n{text}\n", "h2")
                elif stripped == "---":
                    tb.insert(ctk.END, "\n" + "─" * 52 + "\n", "divider")
                elif stripped.startswith("- "):
                    text = clean(stripped[2:]).strip()
                    tb.insert(ctk.END, "  ◆  ", "bullet_marker")
                    tb.insert(ctk.END, f"{text}\n", "bullet_text")
                elif stripped == "":
                    tb.insert(ctk.END, "\n")
                else:
                    tb.insert(ctk.END, f"{clean(raw)}\n", "body")

                self._resize_answer_box(answer_box)
                self._scroll_to_bottom()
                answer_box.configure(state="disabled")
                self.after(40, lambda: stream_line_by_line(line_idx + 1))

            else:
                # Source footer
                answer_box.configure(state="normal")
                tb.insert(ctk.END, "\n" + "─" * 52 + "\n", "divider")
                tb.insert(ctk.END, "SOURCES\n", "source_label")

                sources = (
                    file_sources if isinstance(file_sources, list) else [file_sources]
                )
                for src in sources:
                    tb.insert(ctk.END, f"  {src.upper()}\n", "source_item")

                self._resize_answer_box(answer_box)
                self._scroll_to_bottom()
                answer_box.configure(state="disabled")

                self.search_btn.configure(state="normal")
                self.search_entry.configure(state="normal")
                self.search_entry.focus()

        stream_line_by_line()
