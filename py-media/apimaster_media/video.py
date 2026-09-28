"""Text-to-video and image-to-video, with polling and download.

    python -m apimaster_media.video "a waterfall forming a rainbow, cinematic" --duration 4
    python -m apimaster_media.video "slow push-in" --ref https://example.com/face.jpg --aspect 9:16
"""

from __future__ import annotations

import argparse
import time

from .client import BASE_URL, api, download, poll


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("prompt", nargs="+")
    parser.add_argument("--model", default="seedance-2.5")
    parser.add_argument("--duration", type=int, default=4, choices=[4, 8, 12, 16, 20])
    parser.add_argument("--resolution", default="720p", choices=["720p", "1024p", "1080p"])
    parser.add_argument(
        "--aspect",
        default="16:9",
        choices=["16:9", "9:16"],
        help="always set this explicitly for image-to-video; a portrait reference is treated as 16:9 otherwise",
    )
    parser.add_argument("--ref", help="reference image URL for image-to-video")
    parser.add_argument("--out", default="out")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prompt = " ".join(args.prompt)

    body = {
        "model": args.model,
        "prompt": prompt,
        "duration": args.duration,
        "resolution": args.resolution,
        "aspect_ratio": args.aspect,
    }
    if args.ref:
        body["image_urls"] = [args.ref]

    print(f"submitting {args.model}: {args.duration}s {args.resolution} {args.aspect}")
    started = time.time()

    submit = api("/videos/generations", method="POST", body=body)
    task_id = (submit.get("data") or [{}])[0].get("task_id") or submit.get("id")
    if not task_id:
        raise SystemExit(f"no task id in response: {submit}")
    print(f"  task {task_id} — video is slow, often 10-15 minutes")

    done = poll(
        lambda: api(f"/videos/{task_id}", timeout=30),
        lambda value: value.get("status") == "completed",
        lambda value: value.get("status") in ("failed", "error", "cancelled"),
        initial_delay=15.0,
        timeout=1800.0,  # seedance-2.5 took ~15 minutes for 4 seconds
        label="video",
    )

    content_url = done.get("url") or f"{BASE_URL}/videos/{task_id}/content"
    path = f"{args.out}/{args.model}-{task_id[-8:]}.mp4"
    size = download(content_url, path)
    print(f"  saved {path} ({size / 1e6:.1f} MB) in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
