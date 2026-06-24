# quiz.py
import loader
import retrieval


def get_quiz_context(topic=""):
    if not loader.Notes:
        return None
    if topic:
        keywords = retrieval.keyword(topic)
        ranking_result = retrieval.Ranking_System(keywords, topic)
        if not ranking_result:
            return None
        winning_files, encoded_topic = ranking_result
        context = ""
        for filename in winning_files:
            if filename in loader.Notes:
                chunks = retrieval.get_relevant_chunks(
                    loader.Notes[filename], encoded_topic
                )
                context += f"SOURCE: {filename}\n{chunks}\n\n"
        return context if context else None
    else:
        return "\n\n".join(
            f"SOURCE: {filename}\n{content}"
            for filename, content in loader.Notes.items()
        )


def test_evaluation(correct_answer, user_answer, explanation):
    user_clean = user_answer.strip().split(".")[0].strip().lower()
    correct_clean = correct_answer.strip().lower()
    correct = user_clean == correct_clean
    return {
        "correct": correct,
        "user_answer": user_answer,
        "correct_answer": correct_answer,
        "explanation": explanation,
    }
