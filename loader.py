# loaders.py
import os
import json
import hashlib
import pickle
from pathlib import Path
from tkinter import filedialog, messagebox
import pdfplumber
from docx import Document
from pptx import Presentation
from config import SETTINGS_FILE, EMBEDDINGS_CACHE_FILE, ALLOWED_EXTENSIONS
from network import check_internet_connection

Notes = {}
Embedding_cache = {}
Notes_Cache = {}
model = None
model_loaded = False


def load_notes_from_path(folder_path):
    global Notes
    Notes.clear()
    Embedding_cache.clear()
    Notes_Cache.clear()
    disk_cache = {}
    if EMBEDDINGS_CACHE_FILE.exists():
        with open(EMBEDDINGS_CACHE_FILE, "rb") as f:
            disk_cache = pickle.load(f)
    notes_changed = False
    for files in os.listdir(folder_path):
        path = os.path.join(folder_path, files)
        if Path(path).suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if os.path.isfile(path):
            try:
                if Path(path).suffix.lower() == ".pdf":
                    content = pdf_loader(path)
                elif Path(path).suffix.lower() == ".docx":
                    content = docx_loader(path)
                elif Path(path).suffix.lower() == ".pptx":
                    content = presentation_loader(path)
                else:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                if not content:
                    print(f"Skipping empty file: {files}")
                    continue
                Notes[files] = content
                file_hash = get_hash(path)
                if files in disk_cache and disk_cache[files][0] == file_hash:
                    Embedding_cache[files] = disk_cache[files][1]
                else:
                    Embedding_cache[files] = model.encode(
                        content, convert_to_tensor=True
                    )
                    disk_cache[files] = (file_hash, Embedding_cache[files])
                    notes_changed = True
            except Exception as e:
                print(f"Skipping unreadable asset {files}: {e}")
    disk_cache = {k: v for k, v in disk_cache.items() if k in Notes}
    if notes_changed:
        with open(EMBEDDINGS_CACHE_FILE, "wb") as f:
            pickle.dump(disk_cache, f)


def check_if_path_exists():
    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        settings = json.load(f)
        if "path_notes" in settings and settings["path_notes"]:
            if os.path.exists(settings["path_notes"]):
                return settings["path_notes"]


def load_folder():
    if SETTINGS_FILE.exists():
        existing = check_if_path_exists()
        if existing:
            return existing
    path_notes = filedialog.askdirectory(title="CHOOSE YOUR NOTES FOLDER.")
    if path_notes:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({"path_notes": path_notes}, f, indent=4)
    return path_notes


def bg_model_loading(ui_instance):
    global model, model_loaded, is_online
    is_online = check_internet_connection()

    ui_instance.after(
        0, lambda: ui_instance.update_loading_status("LOADING EMBEDDINGS ENGINE...")
    )

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    if load_folder():
        load_notes_from_path(load_folder())

    model_loaded = True
    ui_instance.after(0, ui_instance.transition_to_main_ui)
    return model, model_loaded


def get_hash(filepath):
    with open(filepath, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def pdf_loader(file_path):
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text.strip()


def docx_loader(filepath):
    text = ""
    doc = Document(filepath)
    for paragraph in doc.paragraphs:
        text += paragraph.text or ""
    return text.strip()


def presentation_loader(file_path):
    text = ""
    prs = Presentation(file_path)
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text += paragraph.text or ""
    return text.strip()
