# Examples

Two small, runnable projects that call an OpenAI-compatible gateway for text, images and
video. They are written to be copied into real code: real error handling, real timeouts,
real polling — not three-line toy snippets.

| Project | Stack | Run |
| --- | --- | --- |
| [`ts-media`](ts-media) | TypeScript, `openai` SDK, `tsx` | `npm i && npm run image -- "a corgi on the moon"` |
| [`py-media`](py-media) | Python 3.9+, `openai` + `requests` | `pip install -r requirements.txt && python -m apimaster_media.image "a corgi on the moon"` |

Both read `APIMASTER_API_KEY` and `APIMASTER_BASE_URL` from the environment, so the same
code runs against any other gateway by changing one variable.

## What they demonstrate

- **Streaming chat with a measured time-to-first-token**, and multi-turn done the way
  that actually works on an aggregator: the full history is resent every turn.
- **Image generation, sync and async.** Sync is simpler; 2k/4k jobs can exceed the
  gateway timeout and return 408, and the code tells you to switch to async when that
  happens instead of failing cryptically.
- **Video generation with polling and download**, including the aspect-ratio trap that
  makes portrait image-to-video come back letterboxed.
- **Retry policy that matches reality**: 429 and 5xx back off; 400/401/402 fail fast.

## The four rules these examples encode

1. Send the whole conversation history every turn — `previous_response_id` and `store`
   do not hold context on this gateway.
2. Use `/chat/completions` for Claude model ids; `/responses` returns 500 for them.
3. When parsing `/responses`, find the `output` item with `type == "message"` rather
   than indexing `output[0]` — a `reasoning` item can come first.
4. Never hardcode a model id you have not listed with `GET /v1/models`.
