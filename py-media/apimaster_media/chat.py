"""Streaming multi-turn chat through the OpenAI SDK, pointed at a gateway.

    python -m apimaster_media.chat "why is time to first token the metric that matters?"

The important detail: the whole message history goes out on every request. Server-side
continuation (previous_response_id / store) is not reliable on this gateway, and code
that relies on it loses context silently in production.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Dict, List

from openai import OpenAI

from .client import BASE_URL, api_key

MODEL = os.environ.get("MODEL", "gpt-5.5")

client = OpenAI(base_url=BASE_URL, api_key=api_key())


def ask(history: List[Dict[str, str]], question: str) -> str:
    history.append({"role": "user", "content": question})

    started = time.time()
    first_token_at = None
    answer = ""

    stream = client.chat.completions.create(
        model=MODEL,
        messages=history,
        temperature=0.3,
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if not delta:
            continue
        if first_token_at is None:
            first_token_at = time.time()
        answer += delta
        sys.stdout.write(delta)
        sys.stdout.flush()

    sys.stdout.write("\n")
    ttft = f"{(first_token_at - started) * 1000:.0f} ms" if first_token_at else "?"
    print(f"  [{MODEL}] first token {ttft} · total {(time.time() - started) * 1000:.0f} ms")

    history.append({"role": "assistant", "content": answer})
    return answer


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Name three things that make a CLI feel fast."
    history: List[Dict[str, str]] = [
        {"role": "system", "content": "You are concise. Answer in at most three sentences."}
    ]
    ask(history, question)
    # This follow-up only resolves because the full history is resent above.
    ask(history, "Now say the same thing in one sentence.")


if __name__ == "__main__":
    main()
