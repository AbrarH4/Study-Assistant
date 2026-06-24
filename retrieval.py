import loader
from config import STOP_WORDS_FILE
from sentence_transformers import util
import json


def load_stop_words():
    try:
        with open(STOP_WORDS_FILE, "r", encoding="utf-8") as file:
            word_list = json.load(file)
            return set(word_list)

    except FileNotFoundError:
        print("WARNING: STOP_WORDS.json not found.")
        return set()

    except Exception as e:
        print(f"Failed to load stop words: {e}")
        return set()


Stop_words = load_stop_words()


def keyword(question: str = None) -> list:
    if question is None:
        question = input()
    words = question.split()
    keywords = [
        word.strip("?!.,").lower() for word in words if word.lower() not in Stop_words
    ]
    return keywords


def get_relevant_chunks(file_content, encoded_question, top_k=5):
    paragraphs = [
        p.strip() for p in file_content.split("\n") if p.strip() and len(p.strip()) > 50
    ]
    if not paragraphs:
        return file_content[:3000]
    encoded_paras = loader.model.encode(
        paragraphs, convert_to_tensor=True, batch_size=32
    )
    scores = util.cos_sim(encoded_question, encoded_paras)[0]
    top_indices = scores.topk(min(top_k, len(paragraphs))).indices.tolist()
    top_chunks = [paragraphs[i] for i in sorted(top_indices)]

    return "\n\n".join(top_chunks)


def Ranking_System(keyword, question):
    if not keyword:
        loader.messagebox.showerror(
            "ERROR", "SORRY WE COULD'NT FIND THE BEST NOTES FOR YOU."
        )
        return None

    from sentence_transformers import util

    scores = {}
    semantic_scores = {}

    for keys, notes in loader.Notes.items():
        if keys.lower() == "error.txt":
            continue

        scores[keys] = 0
        notes_lower = notes.lower()
        for word in keyword:
            word_lower = word.lower()
            if word_lower in keys.lower():
                scores[keys] += 20
            if word_lower in notes_lower:
                scores[keys] += 1

    encoded_question = loader.model.encode(question, convert_to_tensor=True)

    for keys, notes in loader.Notes.items():
        if keys.lower() == "error.txt":
            continue
        encoded_notes = loader.Embedding_cache[keys]
        score = util.cos_sim(encoded_question, encoded_notes)
        semantic_scores[keys] = score.item()

    Final_Scores = {}
    for key in scores:
        if key.lower() == "error.txt":
            continue
        combined_score = scores[key] + semantic_scores.get(key, 0.0)
        Final_Scores[key] = combined_score

    if not Final_Scores:
        # FIX #1: return a consistent (list_or_str, tensor) tuple so the caller's
        # unpacking `winning_file_name, encoded_question_tensor = ranking_result`
        # never crashes.
        return "error.txt", encoded_question

    best_note = [
        note_name
        for note_name, score in sorted(
            Final_Scores.items(), key=lambda x: x[1], reverse=True
        )[:3]
    ]

    print(f"Selected Notes: {best_note}")
    return best_note, encoded_question
