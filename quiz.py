"""Quiz context assembly and answer evaluation helpers.

This module bridges the retrieval pipeline (retrieval.py) and the LLM quiz
generator (provider.py). It handles two responsibilities:

1. Context assembly — get_quiz_context() retrieves the most relevant note
   content for a given topic (or all notes when no topic is given) and
   formats it as a SOURCE: <filename> string ready for the LLM prompt.
2. Answer evaluation — test_evaluation() compares the user's selected answer
   against the correct answer and packages the result for the quiz UI.
"""

# quiz.py
import loader
import retrieval


def get_quiz_context(topic=""):
    """Build the LLM context string for a quiz session.

    When topic is provided, the retrieval pipeline ranks all loaded notes and
    returns only the most relevant paragraphs. When topic is empty, the full
    content of every note is concatenated so the quiz covers the entire folder.

    Args:
        topic: Optional topic string entered by the user in the quiz setup
            dialog. Pass an empty string to use all notes.

    Returns:
        A formatted context string, or None if no notes are loaded or no
        relevant content is found for the given topic.
    """
    if not loader.Notes:
        # No notes have been indexed yet — cannot generate a quiz
        return None
    if topic:
        # Extract keywords and rank notes by relevance to the topic
        keywords = retrieval.keyword(topic)
        ranking_result = retrieval.Ranking_System(keywords, topic)
        if not ranking_result:
            return None
        winning_files, encoded_topic = ranking_result

        # Collect the top relevant chunks from each winning file
        context = ""
        for filename in winning_files:
            if filename in loader.Notes:
                chunks = retrieval.get_relevant_chunks(
                    loader.Notes[filename], encoded_topic
                )
                context += f"SOURCE: {filename}\n{chunks}\n\n"
        return context if context else None
    else:
        # No topic — concatenate full content of every note
        return "\n\n".join(
            f"SOURCE: {filename}\n{content}"
            for filename, content in loader.Notes.items()
        )


def test_evaluation(correct_answer, user_answer, explanation):
    """Evaluate a single quiz answer and return a result dict.

    Comparison is case-insensitive and considers only the letter portion
    of the answer (before the first period) to handle both raw letter
    answers ("A") and full option strings ("A. Photosynthesis").

    Args:
        correct_answer: The expected answer as stored in the quiz JSON
            (e.g. "A" or "True").
        user_answer: The answer string selected by the user.
        explanation: The explanation string from the quiz JSON.

    Returns:
        A dict with keys: correct (bool), user_answer, correct_answer,
        explanation.
    """
    user_clean = user_answer.strip().split(".")[0].strip().lower()
    correct_clean = correct_answer.strip().lower()
    correct = user_clean == correct_clean
    return {
        "correct": correct,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
        "explanation": explanation,
    }
