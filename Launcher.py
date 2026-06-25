import tkinter as tk
import threading
import subprocess
import sys
import os

root = tk.Tk()
root.title("Ace")
root.geometry("480x260")
root.configure(bg="#0D0E12")
root.resizable(False, False)
root.overrideredirect(True)  # removes title bar for clean look

# ── Center on screen ──────────────────────────────────
root.update_idletasks()
w = root.winfo_screenwidth()
h = root.winfo_screenheight()
root.geometry(f"480x260+{(w - 480) // 2}+{(h - 260) // 2}")

# ── Border frame ──────────────────────────────────────
border = tk.Frame(root, bg="#1E2433", padx=1, pady=1)
border.pack(fill="both", expand=True)

inner = tk.Frame(border, bg="#0D0E12")
inner.pack(fill="both", expand=True)

# ── App name ──────────────────────────────────────────
tk.Label(
    inner,
    text="Ace",
    font=("Segoe UI", 42, "bold"),
    bg="#0D0E12",
    fg="#E8EEFF",
).pack(pady=(42, 4))

# ── Tagline ───────────────────────────────────────────
tk.Label(
    inner,
    text="Your personal AI-powered Assistant",
    font=("Segoe UI", 11),
    bg="#0D0E12",
    fg="#2E3A50",
).pack()

# ── Animated status label ─────────────────────────────
status_var = tk.StringVar(value="Initializing")
status_label = tk.Label(
    inner,
    textvariable=status_var,
    font=("Segoe UI", 10),
    bg="#0D0E12",
    fg="#475569",
)
status_label.pack(pady=(28, 0))

# ── Thin accent bar at bottom ─────────────────────────
bar_canvas = tk.Canvas(inner, height=3, bg="#0D0E12", highlightthickness=0)
bar_canvas.pack(fill="x", padx=40, pady=(16, 0))
bar_rect = bar_canvas.create_rectangle(0, 0, 0, 3, fill="#4F46E5", outline="")

bar_width = [0]


def animate_bar():
    bar_canvas.update_idletasks()
    total = bar_canvas.winfo_width()
    if bar_width[0] < total:
        bar_width[0] = min(bar_width[0] + 4, total)
        bar_canvas.coords(bar_rect, 0, 0, bar_width[0], 3)
    root.after(30, animate_bar)


animate_bar()

# ── Dot animation ─────────────────────────────────────
dot_cycle = ["", ".", "..", "..."]
dot_index = [0]


def animate_dots():
    base = status_var.get().rstrip(".")
    dot_index[0] = (dot_index[0] + 1) % len(dot_cycle)
    status_var.set(base + dot_cycle[dot_index[0]])
    root.after(400, animate_dots)


animate_dots()

# ── Version ───────────────────────────────────────────
tk.Label(
    inner,
    text="v1.0.0",
    font=("Segoe UI", 9),
    bg="#0D0E12",
    fg="#1E2433",
).pack(side="bottom", pady=12)


# ── Launch logic ──────────────────────────────────────
def launch():
    ace_path = os.path.join(os.path.dirname(sys.executable), "Ace", "Ace.exe")

    status_var.set("Starting Ace")
    root.after(800, lambda: status_var.set("Loading AI engine"))

    process = subprocess.Popen([ace_path])

    # wait until process is confirmed running then close launcher
    process.wait()  # won't work for windowed — use time approach below


def launch_and_close():
    ace_path = os.path.join(os.path.dirname(sys.executable), "Ace", "Ace.exe")

    status_var.set("Starting Ace")
    root.update()

    import time

    time.sleep(0.5)
    status_var.set("Loading AI engine")
    root.update()

    subprocess.Popen([ace_path])

    # give the process time to initialize then close launcher
    time.sleep(13)
    root.destroy()


threading.Thread(target=launch_and_close, daemon=True).start()
root.mainloop()
