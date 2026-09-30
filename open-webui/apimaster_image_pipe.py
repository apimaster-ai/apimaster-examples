"""
title: APIMaster Image
author: APIMaster
author_url: https://github.com/apimaster-ai
funding_url: https://github.com/apimaster-ai
version: 0.1.0
license: MIT
description: Generate images from the chat box through an OpenAI-compatible gateway. Adds each image model as a selectable model in Open WebUI.
requirements: requests
"""

# How it works
#
# Open WebUI's built-in image support expects an image backend it knows about, and its
# chat pipeline expects text. This function registers each image model as a *manifold*
# model, so you pick "APIMaster/gpt-image-2" from the model dropdown and your
# message becomes the prompt. The result comes back as markdown, so it renders inline
# and is part of the conversation history like any other message.
#
# Install: Workspace -> Functions -> + -> paste this file -> save -> set the API key in
# the valves (the gear icon), then enable it.

from __future__ import annotations

import time
from typing import Any, Dict, Generator, List, Union

import requests
from pydantic import BaseModel, Field

IMAGE_MODELS = ["gpt-image-2", "doubao-seedream-5-0-pro-260628", "gemini-3.1-flash-image", "midjourney-v8.2", "midjourney-niji-7"]
# Video is left out on purpose: the gateway serves finished videos only to requests that carry
# the API key, so a <video> tag in the chat cannot play them. Images are public URLs.

# Sync image generation is genuinely slow at high resolution; these mirror the
# documented client-side guidance. Too short a timeout aborts a job you still pay for.
SYNC_TIMEOUT = {"1k": 200, "2k": 320, "4k": 620}


class Pipe:
    class Valves(BaseModel):
        APIMASTER_API_KEY: str = Field(
            default="",
            description="API key. Get one at https://apimaster.ai/docs/getting-started/api-key",
        )
        BASE_URL: str = Field(
            default="https://apimaster.ai/v1",
            description="OpenAI-compatible base URL, including /v1",
        )
        IMAGE_SIZE: str = Field(
            default="1:1",
            description="Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4, 21:9 ... or pixels like 1881x836",
        )
        IMAGE_RESOLUTION: str = Field(default="1k", description="1k, 2k or 4k")
        ASYNC_IMAGES: bool = Field(
            default=False,
            description="Submit images to the async endpoint and poll. Recommended for 2k and 4k.",
        )

    def __init__(self):
        self.type = "manifold"
        self.id = "apimaster_image"
        self.name = "APIMaster/"
        self.valves = self.Valves()

    # -- model list shown in the Open WebUI dropdown ---------------------------

    def pipes(self) -> List[Dict[str, str]]:
        return [{"id": model, "name": model} for model in IMAGE_MODELS]

    # -- helpers --------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.valves.APIMASTER_API_KEY}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, body: Dict[str, Any], timeout: int) -> Dict[str, Any]:
        response = requests.post(
            f"{self.valves.BASE_URL.rstrip('/')}{path}",
            headers=self._headers(),
            json=body,
            timeout=timeout,
        )
        if not response.ok:
            raise RuntimeError(self._explain(response))
        return response.json()

    def _poll(self, path: str, failures: List[int]) -> Dict[str, Any] | None:
        """One status check. A dropped connection or a 5xx returns None instead of raising:
        the job keeps running server-side and is already paid for, so a single network blip
        must not throw it away. Five failures in a row do raise."""
        try:
            response = requests.get(
                f"{self.valves.BASE_URL.rstrip('/')}{path}", headers=self._headers(), timeout=30
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            failures[0] += 1
            if failures[0] >= 5:
                raise RuntimeError(f"Lost contact with the gateway while polling: {exc}") from exc
            return None
        if response.status_code >= 500:
            failures[0] += 1
            if failures[0] >= 5:
                raise RuntimeError(self._explain(response))
            return None
        if not response.ok:
            raise RuntimeError(self._explain(response))
        failures[0] = 0
        return response.json()

    @staticmethod
    def _explain(response: requests.Response) -> str:
        hints = {
            400: "Bad request — check the model id and parameters.",
            401: "Unauthorized — set the API key in this function's valves, and check it has no stray whitespace.",
            402: "Insufficient balance.",
            404: "Not found — the base URL should end with /v1.",
            408: "Generation timed out — lower the resolution, or turn on ASYNC_IMAGES.",
            429: "Rate limited — try again shortly.",
        }
        hint = hints.get(response.status_code, "Request failed.")
        return f"HTTP {response.status_code}: {hint} {response.text[:200]}"

    @staticmethod
    def _last_user_message(messages: List[Dict[str, Any]]) -> str:
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            content = message.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # Multimodal content: keep the text parts only.
                return " ".join(part.get("text", "") for part in content if part.get("type") == "text")
        return ""

    # -- generation -----------------------------------------------------------

    def _image(self, model: str, prompt: str) -> str:
        body = {
            "model": model,
            "prompt": prompt,
            "size": self.valves.IMAGE_SIZE,
            "resolution": self.valves.IMAGE_RESOLUTION,
        }

        if self.valves.ASYNC_IMAGES:
            submit = self._post("/images/generations/async", body, timeout=60)
            task_id = (submit.get("data") or [{}])[0].get("task_id")
            if not task_id:
                raise RuntimeError(f"No task_id in response: {submit}")
            time.sleep(12)
            failures = [0]
            for _ in range(200):
                status_payload = self._poll(f"/tasks/{task_id}?model={model}", failures)
                if status_payload is None:
                    time.sleep(4)
                    continue
                payload = status_payload.get("data", status_payload)
                status = payload.get("status")
                if status == "completed":
                    images = (payload.get("result") or {}).get("images") or []
                    urls: List[str] = []
                    for image in images:
                        url = image.get("url")
                        urls.extend(url if isinstance(url, list) else [url] if url else [])
                    return self._render_images(prompt, urls)
                if status in ("failed", "error", "cancelled"):
                    raise RuntimeError(f"Task {status}: {status_payload}")
                time.sleep(4)
            raise RuntimeError("Gave up polling the image task.")

        timeout = SYNC_TIMEOUT.get(self.valves.IMAGE_RESOLUTION, 200)
        response = self._post("/images/generations", body, timeout=timeout)
        urls = [item.get("url") for item in response.get("data", []) if item.get("url")]
        return self._render_images(prompt, urls)

    @staticmethod
    def _render_images(prompt: str, urls: List[str]) -> str:
        if not urls:
            return "The endpoint returned no image URL."
        alt = prompt[:60].replace("]", " ")
        body = "\n\n".join(f"![{alt}]({url})" for url in urls)
        return f"{body}\n\n<sub>Media URLs expire — save anything you want to keep.</sub>"

    @staticmethod
    def _resolve_model(raw: str) -> str:
        # Open WebUI prefixes the model id with the function id, e.g. "apimaster_image.midjourney-v8.2".
        # Model ids contain dots too, so match known ids instead of splitting on the last dot
        # (which turned "midjourney-v8.2" into "2").
        for known in IMAGE_MODELS:
            if raw == known or raw.endswith("." + known):
                return known
        return raw.split(".", 1)[-1]

    # -- entrypoint -----------------------------------------------------------

    def pipe(self, body: Dict[str, Any], __user__: Dict[str, Any] | None = None) -> Union[str, Generator]:
        if not self.valves.APIMASTER_API_KEY:
            return "Set APIMASTER_API_KEY in this function's valves first (the gear icon next to the function)."

        model = self._resolve_model(str(body.get("model", "")))
        prompt = self._last_user_message(body.get("messages", []))
        if not prompt.strip():
            return "Send a prompt describing the image you want."

        try:
            return self._image(model or "gpt-image-2", prompt)
        except requests.Timeout:
            return (
                "The request timed out. For 2k/4k images turn on ASYNC_IMAGES in the valves, "
                "or lower IMAGE_RESOLUTION."
            )
        except Exception as exc:  # surfaced in the chat, which is where the user is looking
            return f"**Generation failed.** {exc}"
