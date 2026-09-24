"""Text-to-image and image-to-image.

    python -m apimaster_media.image "a corgi astronaut on the moon" --size 16:9 --resolution 2k
    python -m apimaster_media.image "desert sunset background" --ref https://example.com/a.png
    python -m apimaster_media.image "a detailed matte painting" --resolution 4k --async
"""

from __future__ import annotations

import argparse
import time

from .client import SYNC_TIMEOUT, ApiError, api, download, poll


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prompt", nargs="+")
    parser.add_argument("--model", default="gpt-image-2")
    parser.add_argument("--size", help="1:1, 16:9, 9:16, 4:3 ... or pixels like 1881x836")
    parser.add_argument("--resolution", default="1k", choices=["1k", "2k", "4k"])
    parser.add_argument("--ref", action="append", default=[], help="reference image URL, repeatable")
    parser.add_argument("--mask", help="mask URL for inpainting")
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--async", dest="is_async", action="store_true", help="submit and poll instead of waiting")
    parser.add_argument("--out", default="out")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prompt = " ".join(args.prompt)

    body = {"model": args.model, "prompt": prompt, "resolution": args.resolution}
    if args.size:
        body["size"] = args.size
    if args.n > 1:
        body["n"] = args.n
    if args.ref:
        # Public URLs and data: URIs can be mixed, up to 16 references.
        body["image_urls"] = args.ref
    if args.mask:
        body["mask_url"] = args.mask

    print(f"generating with {args.model} ({args.resolution}{', ' + args.size if args.size else ''})")
    started = time.time()

    if args.is_async:
        submit = api("/images/generations/async", method="POST", body=body)
        task_id = (submit.get("data") or [{}])[0].get("task_id")
        if not task_id:
            raise SystemExit(f"no task_id in response: {submit}")
        print(f"  task {task_id}")

        done = poll(
            lambda: api(f"/tasks/{task_id}?model={args.model}", timeout=30),
            lambda value: (value.get("data") or {}).get("status") == "completed",
            lambda value: (value.get("data") or {}).get("status") in ("failed", "error", "cancelled"),
            label="image",
        )
        urls = []
        for image in ((done.get("data") or {}).get("result") or {}).get("images", []):
            url = image.get("url")
            urls.extend(url if isinstance(url, list) else [url] if url else [])
    else:
        try:
            response = api(
                "/images/generations",
                method="POST",
                body=body,
                timeout=SYNC_TIMEOUT.get(args.resolution, 200),
                retries=0,
            )
        except ApiError as exc:
            if exc.status == 408:
                raise SystemExit("Sync generation timed out. Re-run the same command with --async.") from None
            raise
        urls = [item["url"] for item in response.get("data", []) if item.get("url")]

    if not urls:
        raise SystemExit("the endpoint returned no image URLs")

    for index, url in enumerate(urls, start=1):
        path = f"{args.out}/image-{int(time.time())}-{index}.png"
        size = download(url, path)
        print(f"  saved {path} ({size // 1024} KB)")
    print(f"done in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
