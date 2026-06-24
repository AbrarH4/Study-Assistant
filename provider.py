# providers.py
import json
from collections import deque
from openai import OpenAI
from config import PROVIDERS

chat_history = deque(maxlen=5)


def turn_to_history(question, answer):
    turn = (
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    )
    chat_history.append(turn)


def get_messages(system_prompt):
    messages = [{"role": "system", "content": system_prompt}]
    for turn in chat_history:
        messages.extend(turn)
    return messages


def GenerateAnswer(question, context):
    system_prompt = (
        "You are an intelligent and highly capable study assistant.\n"
        "Your primary source of truth is the provided notebook context.\n\n"
        "CORE RULES:\n"
        "1. Use the notebook context as the factual source for your answers.\n"
        "2. You may rephrase, simplify, summarize, and explain in your own words.\n"
        "3. Do NOT invent facts not supported by the notebook context.\n"
        "4. Do NOT contradict the notebook context.\n"
        "5. If context is partial, answer with available info and note missing details.\n"
        "6. Only say information is unavailable when context has no relevant info at all.\n"
        "7. Prioritize understanding over memorization.\n"
        "8. Use examples whenever they improve understanding.\n"
        "9. Keep answers clear, accurate, and educational.\n\n"
        "TEACHING MODES:\n"
        "1. Simple/ELI5 request → simple language, analogies, everyday examples.\n"
        "2. Detailed/technical request → deeper detail using notebook context.\n"
        "3. Examples requested → provide examples whenever possible.\n"
        "4. Comparison requested → compare using only notebook context.\n\n"
        "ANSWERING STYLE:\n"
        "1. Start with a direct answer.\n"
        "2. Follow with a short explanation.\n"
        "3. Add examples when helpful.\n"
        "4. Avoid copying notes word-for-word.\n"
        "5. Focus on helping the user understand.\n\n"
        "LAYOUT RULES:\n"
        "- Headings: '## heading'\n"
        "- Dividers: '---'\n"
        "- Bullets: '- point'\n"
        "- No '**bold**' inside headers or bullets.\n\n"
        "Do not fabricate. Do not use outside knowledge."
    )
    messages = get_messages(system_prompt)
    user_content = f"QUESTION:\n{question}\n\nNOTEBOOK CONTEXT:\n{context}"
    messages.append({"role": "user", "content": user_content})

    for provider in PROVIDERS:
        if not provider["key"] and provider["name"] != "Ollama (Local)":
            print(f"Skipping {provider['name']}: No API key.")
            continue
        try:
            print(f"Connecting to: {provider['name']}...")
            client = OpenAI(base_url=provider["url"], api_key=provider["key"])
            response = client.chat.completions.create(
                model=provider["model"],
                messages=messages,
                temperature=0.1,
            )
            print(f"[SUCCESS] {provider['name']}")
            turn_to_history(question, response.choices[0].message.content)
            return response.choices[0].message.content
        except Exception as error:
            print(f"Warning: {provider['name']} failed: {error}")
            continue

    return "CRITICAL FAILURE: All providers exhausted."


def GenerateQuiz(context, quiz_count=5, quiz_type="mixed", difficulty=None, topic=None):
    system_prompt = (
        "You are a quiz generator for a study assistant app.\n"
        "Your only job is to generate quiz questions strictly from the provided notebook context.\n\n"
        "STRICT RULES:\n"
        "1. Use ONLY information found in the notebook context.\n"
        "2. Return ONLY a valid JSON array. No explanation, no markdown, no preamble, no code fences.\n"
        "3. The first character of your response must be '[' and the last must be ']'.\n"
        "4. Every question must be clearly answerable from the notebook context alone.\n"
        "5. Do not repeat questions or paraphrase the same concept twice.\n"
        "6. For MCQ: answer field must be ONLY 'A', 'B', 'C', or 'D'.\n"
        "7. For True/False: answer field must be ONLY 'True' or 'False'.\n"
        "8. Answer field must never contain option text or explanations.\n\n"
        f"QUIZ SETTINGS:\n"
        f"- Number of questions: {quiz_count}\n"
        f"- Question type: {quiz_type}\n"
        f"- Topic focus: {topic if topic else 'entire notebook context'}\n\n"
        "OUTPUT SCHEMA:\n"
        'MCQ: [{"question":"...","options":["A. ...","B. ...","C. ...","D. ..."],"answer":"A","explanation":"..."}]\n'
        'T/F: [{"question":"...","options":["True","False"],"answer":"True","explanation":"..."}]\n\n'
        "QUALITY RULES:\n"
        "- MCQ wrong options must be plausible.\n"
        "- Vary difficulty across the question set.\n"
        "- Test understanding, not memorization.\n\n"
        "CRITICAL: Output raw JSON only. Any text outside the array breaks the application."
    )
    if difficulty:
        system_prompt += f"\nDifficulty: {difficulty}."

    messages = [{"role": "system", "content": system_prompt}]
    user_content = (
        f"Generate a {quiz_type} quiz with exactly {quiz_count} questions from the notebook context below.\n\n"
        "Return ONLY a valid JSON array. First character must be '['.\n\n"
        'Schema: {"question":"...","options":[...],"answer":"A","explanation":"..."}\n'
        'For True/False: options=["True","False"], answer="True" or "False".\n'
        "For MCQ: 4 options labeled A B C D.\n\n"
        f"NOTEBOOK CONTEXT:\n{context}"
    )
    messages.append({"role": "user", "content": user_content})

    for provider in PROVIDERS:
        if not provider["key"] and provider["name"] != "Ollama (Local)":
            continue
        try:
            client = OpenAI(base_url=provider["url"], api_key=provider["key"])
            response = client.chat.completions.create(
                model=provider["model"],
                messages=messages,
                temperature=0.3,
            )
            raw = response.choices[0].message.content
            try:
                quiz_data = json.loads(raw.strip())
            except json.JSONDecodeError:
                start = raw.find("[")
                end = raw.rfind("]")
                if start != -1 and end != -1 and end > start:
                    quiz_data = json.loads(raw[start : end + 1])
                else:
                    raise
            if not isinstance(quiz_data, list) or len(quiz_data) == 0:
                raise ValueError("Invalid quiz array.")
            return quiz_data
        except Exception as error:
            print(f"Warning: {provider['name']} failed: {error}")
            continue
    return None
