"""Keyword extraction and semantic note-ranking pipeline.

This module:

1. Strips stop words to extract content-bearing keywords (keyword()).
2. Scores every loaded note by combining keyword frequency with cosine
   similarity of sentence-transformer embeddings (Ranking_System()).
3. Retrieves the most semantically relevant paragraphs from a note file
   (get_relevant_chunks()).

The two-stage ranking (lexical + semantic) ensures files whose filename or
content contains an exact keyword are boosted, while the semantic score
catches paraphrases and conceptual matches.
"""

import loader
from config import STOP_WORDS_FILE
from sentence_transformers import util
import json


def load_stop_words():
    """Load the list of common English stop words from STOP_WORDS.json.

    Stop words (e.g. "the", "is", "and") are filtered out during keyword
    extraction so only content-bearing terms are passed to the ranker.

    Returns:
        A set of lowercase stop-word strings. Returns an empty set if the
        file is missing or malformed so the pipeline degrades gracefully.
    """
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


# Load stop words once at module import time to avoid repeated disk reads
Stop_words = load_stop_words()


def keyword(question: str = None) -> list:
    """Extract content-bearing keywords from a natural-language question.

    Splits the question on whitespace, strips common punctuation, lowercases
    each token, and filters out anything in Stop_words.

    Args:
        question: The user's question string. If None, falls back to input()
            for command-line use.

    Returns:
        A list of lowercase keyword strings with punctuation stripped.
    """
    if question is None:
        question = input()
    words = question.split()
    keywords = [
        word.strip("?!.,").lower() for word in words if word.lower() not in Stop_words
    ]
    return keywords


def get_relevant_chunks(file_content, encoded_question, top_k=5):
    """Return the top_k most semantically relevant paragraphs from a note.

    Splits the note into non-empty paragraphs longer than 50 characters,
    encodes them in batches, and ranks them by cosine similarity to the
    pre-encoded question tensor. The top paragraphs are returned in their
    original document order so the LLM sees coherent context.

    If the note contains no qualifying paragraphs, the first 3000 characters
    are returned as a fallback.

    Args:
        file_content: Raw plain-text content of the note file.
        encoded_question: Sentence-transformer tensor for the user's question.
        top_k: Maximum number of paragraphs to return. Defaults to 5.

    Returns:
        A string of selected paragraphs joined by double newlines, or the
        first 3000 characters of the note if no long paragraphs are found.
    """
    paragraphs = [
        p.strip() for p in file_content.split("\n") if p.strip() and len(p.strip()) > 50
    ]
    if not paragraphs:
        # Fallback: return a raw slice when there are no qualifying paragraphs
        return file_content[:3000]

    # Encode all paragraphs in one batched call for efficiency
    encoded_paras = loader.model.encode(
        paragraphs, convert_to_tensor=True, batch_size=32
    )

    # Compute cosine similarity between the question and every paragraph
    scores = util.cos_sim(encoded_question, encoded_paras)[0]

    # Pick top-k indices and sort them to preserve document order
    top_indices = scores.topk(min(top_k, len(paragraphs))).indices.tolist()
    top_chunks = [paragraphs[i] for i in sorted(top_indices)]

    return "\n\n".join(top_chunks)


def Ranking_System(keyword, question):
    """Rank all loaded notes by combined lexical and semantic relevance.

    Scoring is done in two passes:

    Lexical pass — for each note, each keyword earns:
    - +20 points if the keyword appears in the filename (strong signal).
    - +1 point for each occurrence in the note body.

    Semantic pass — cosine similarity between the question embedding and
    the pre-computed per-file embedding stored in loader.Embedding_cache.

    The two scores are summed and the top-3 notes are returned.

    Args:
        keyword: List of content-bearing keywords extracted by keyword().
        question: The original user question string used for semantic encoding.

    Returns:
        A (best_note_names, encoded_question_tensor) tuple, or None if
        keyword is empty.
    """
    if not keyword:
        loader.messagebox.showerror(
            "ERROR", "SORRY WE COULD'NT FIND THE BEST NOTES FOR YOU."
        )
        return None

    from sentence_transformers import util

    scores = {}
    semantic_scores = {}

    # Lexical pass — keyword frequency scoring
    for keys, notes in loader.Notes.items():
        if keys.lower() == "error.txt":
            continue  # Skip the reserved error placeholder file

        scores[keys] = 0
        notes_lower = notes.lower()
        for word in keyword:
            word_lower = word.lower()
            if word_lower in keys.lower():
                scores[keys] += 20  # Filename match is a strong relevance signal
            if word_lower in notes_lower:
                scores[keys] += 1   # Body match contributes one point per keyword

    # Encode the question once to compare against all cached note embeddings
    encoded_question = loader.model.encode(question, convert_to_tensor=True)

    # Semantic pass — cosine similarity scoring
    for keys, notes in loader.Notes.items():
        if keys.lower() == "error.txt":
            continue
        encoded_notes = loader.Embedding_cache[keys]
        score = util.cos_sim(encoded_question, encoded_notes)
        semantic_scores[keys] = score.item()

    # Combine lexical and semantic scores
    Final_Scores = {}
    for key in scores:
        if key.lower() == "error.txt":
            continue
        combined_score = scores[key] + semantic_scores.get(key, 0.0)
        Final_Scores[key] = combined_score

    if not Final_Scores:
        # Return a consistent tuple so the caller's unpacking never crashes
        return "error.txt", encoded_question

    # Select the top-3 notes sorted by descending combined score
    best_note = [
        note_name
        for note_name, score in sorted(
            Final_Scores.items(), key=lambda x: x[1], reverse=True
        )[:3]
    ]

    print(f"Selected Notes: {best_note}")
    return best_note, encoded_question
