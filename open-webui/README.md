# Open WebUI image function

[`apimaster_image_pipe.py`](apimaster_image_pipe.py) is an [Open WebUI](https://github.com/open-webui/open-webui)
function that generates images from the chat box. Pick an image model from the model dropdown,
type what you want, and the picture comes back inline in the conversation.

**Models:** `gpt-image-2`, `doubao-seedream-5-0-pro-260628` (Seedream 5.0 Pro), `gemini-3.1-flash-image`,
`midjourney-v8.2`, `midjourney-niji-7`

It works with [APIMaster](https://apimaster.ai/docs) out of the box, and with any other
OpenAI-compatible gateway that implements `/v1/images/generations`: change `BASE_URL` in the valves.

## Install

1. In Open WebUI, open **Admin Panel → Functions** (older versions: **Workspace → Functions**) and click **+**.
2. Paste the contents of [`apimaster_image_pipe.py`](apimaster_image_pipe.py) and save.
3. Open the function's valves (the gear icon), paste your API key into `APIMASTER_API_KEY`, and enable the function.
4. In a new chat, pick `APIMaster/gpt-image-2` (or another image model) from the model dropdown and describe the image.

Self-hosting Open WebUI to try it:

```bash
docker run -d -p 3000:8080 -v open-webui:/app/backend/data \
  --name open-webui ghcr.io/open-webui/open-webui:main
```

## Valves

| Valve | Default | What it does |
| --- | --- | --- |
| `APIMASTER_API_KEY` | (empty) | Your API key. Required. |
| `BASE_URL` | `https://apimaster.ai/v1` | Any OpenAI-compatible endpoint, including `/v1`. |
| `IMAGE_SIZE` | `1:1` | An aspect ratio (`16:9`, `9:16`, `4:3`, ...) or pixels like `1881x836`. |
| `IMAGE_RESOLUTION` | `1k` | One of `1k`, `2k` or `4k`. |
| `ASYNC_IMAGES` | off | Submit the job and poll instead of waiting on one request. Turn it on for `2k` and `4k`, which can exceed a single request's timeout. |

## Good to know

- **Image generation is slow**: from about half a minute to a few minutes for a 1k image, longer for 4k. The function waits for it.
- **Image links expire.** The chat stores the link, not the file, so save anything you want to keep.
- **Errors show up in the chat** as a readable message (wrong key, missing `/v1`, insufficient balance) rather than a stack trace.
- **Model ids with dots** such as `midjourney-v8.2` are handled correctly, and a dropped connection while polling an async job is retried instead of losing a job you have already paid for.
- **No video in this version**: the gateway serves finished videos only to requests that carry the API key, so a `<video>` tag in the chat cannot play them.

Disclosure: this function is published by APIMaster, the gateway it connects to by default.
