# py-media

Text, image and video generation against an OpenAI-compatible gateway, in Python.

```bash
python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env     # then paste your key, or just export APIMASTER_API_KEY

python -m apimaster_media.chat  "why does time to first token matter?"
python -m apimaster_media.image "a corgi astronaut on the moon" --size 16:9 --resolution 2k
python -m apimaster_media.video "a waterfall forming a rainbow, cinematic" --duration 4
```

Output lands in `out/`.

## Files

| File | What to steal from it |
| --- | --- |
| `apimaster_media/client.py` | `ApiError` with a `retryable` property, backoff, polling, download |
| `apimaster_media/chat.py` | Streaming chat with TTFT, multi-turn by resending full history |
| `apimaster_media/image.py` | `--async` submit-and-poll, 408 handling, `--ref` image-to-image, `--mask` inpainting |
| `apimaster_media/video.py` | Submit → poll → download, with the model/resolution guard |

## Environment

```bash
export APIMASTER_API_KEY=sk-...
export APIMASTER_BASE_URL=https://apimaster.ai/v1   # any OpenAI-compatible gateway
export MODEL=claude-sonnet-4-6                      # optional, chat.py only
```

`.env` is read by your shell or a loader of your choice — the code reads plain
environment variables so it works the same in Docker, CI and a notebook.
