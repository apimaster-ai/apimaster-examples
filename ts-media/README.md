# ts-media

Text, image and video generation against an OpenAI-compatible gateway, in TypeScript.

```bash
npm install
cp .env.example .env     # then paste your key
npm run chat  -- "why does time to first token matter?"
npm run image -- "a corgi astronaut on the moon" --size 16:9 --resolution 2k
npm run video -- "a waterfall forming a rainbow, cinematic" --duration 4
```

Output lands in `out/`.

## Files

| File | What to steal from it |
| --- | --- |
| `src/client.ts` | Retry policy (429/5xx only), per-resolution timeouts, the polling loop, authenticated download |
| `src/chat.ts` | Streaming with a measured TTFT, and multi-turn done by resending full history |
| `src/image.ts` | Sync vs async generation, 408 handling, image-to-image with `--ref` |
| `src/video.ts` | Job submit → poll → download MP4, with the aspect-ratio rule |

## Flags worth knowing

```bash
npm run image -- "..." --resolution 4k --async    # 2k/4k should go async
npm run image -- "..." --ref https://…/a.png --ref https://…/b.png
npm run video -- "..." --ref https://…/face.jpg --aspect 9:16   # portrait needs this
MODEL=claude-sonnet-4-6 npm run chat -- "hello"
```

## Point it somewhere else

```bash
APIMASTER_BASE_URL=https://api.openai.com/v1 APIMASTER_API_KEY=$OPENAI_API_KEY npm run chat -- hi
```
