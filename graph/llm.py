"""
Shared LLM access for all pipeline nodes.

Groq is primary (fast, free-tier). If Groq fails (rate limit, outage,
bad response), we fall back to Gemini, trying several Gemini model
candidates in order since free-tier quotas vary a lot by model.

Temporary: SKIP_GROQ=True bypasses Groq entirely while its daily
quota is known to be exhausted, to save time during testing. Flip
back to False once Groq's daily limit resets.
"""

import os
import time
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

SKIP_GROQ = True

_groq = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.environ["GROQ_API_KEY"],
    temperature=0,
)

_GEMINI_MODEL_CANDIDATES = [
    "gemini-flash-lite-latest",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
]


def _extract_text(content) -> str:
    """
    Some providers/models return content as a plain string, others
    return a list of content blocks (e.g. [{"type": "text", "text": "...", ...}]).
    This normalizes either shape into plain text.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _try_gemini(prompt: str) -> str:
    """
    Tries each candidate Gemini model in order, moving to the next
    only on a quota/rate-limit error. Raises the last error if all
    candidates are exhausted.
    """
    last_error = None
    for model_name in _GEMINI_MODEL_CANDIDATES:
        try:
            client = ChatGoogleGenerativeAI(
                model=model_name,
                api_key=os.environ["GOOGLE_API_KEY"],
                temperature=0,
            )
            response = client.invoke(prompt)
            return _extract_text(response.content)
        except Exception as e:
            print(f"[llm] Gemini model '{model_name}' failed ({e}), trying next...")
            last_error = e
    raise RuntimeError(f"All Gemini model candidates exhausted. Last error: {last_error}")


def invoke_llm(prompt: str) -> str:
    if not SKIP_GROQ:
        try:
            response = _groq.invoke(prompt)
            return _extract_text(response.content)
        except Exception as groq_error:
            print(f"[llm] Groq failed ({groq_error}), waiting 10s and falling back to Gemini...")
            time.sleep(10)
            try:
                return _try_gemini(prompt)
            except Exception as gemini_error:
                raise RuntimeError(
                    f"Both LLM providers failed. Groq: {groq_error} | Gemini: {gemini_error}"
                )

    return _try_gemini(prompt)


def invoke_llm_json(prompt: str, max_repair_attempts: int = 2) -> dict:
    """
    Like invoke_llm, but for prompts that must return JSON.

    If the model's output isn't valid JSON, we don't just fail --
    we feed the broken output and the parse error back to the model
    and ask it to fix its own mistake. This is the "retry-with-repair"
    node from the plan, implemented as a wrapper so every JSON-calling
    node gets this behavior automatically.
    """
    raw = invoke_llm(prompt)

    for attempt in range(max_repair_attempts + 1):
        cleaned = raw.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            if attempt == max_repair_attempts:
                raise ValueError(
                    f"Model did not return valid JSON after {max_repair_attempts} "
                    f"repair attempts. Raw output:\n{raw}\n\nError: {e}"
                )

            print(f"[llm] JSON parse failed (attempt {attempt + 1}), asking model to repair its own output...")

            repair_prompt = f"""You previously produced output that was supposed to
be valid JSON, but it failed to parse.

Your previous output:
\"\"\"{raw}\"\"\"

The JSON parser error was:
{e}

Respond with ONLY the corrected, valid JSON. No markdown fences, no
explanation, no extra text -- just the fixed JSON object.
"""
            raw = invoke_llm(repair_prompt)

    # Unreachable, but keeps type-checkers happy
    raise ValueError("invoke_llm_json: exhausted repair attempts unexpectedly.")