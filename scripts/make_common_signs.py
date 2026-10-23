"""Make sign animations ahead of time, so uploads don't wait for them.

The app makes each sign's animation the first time it's needed, which takes a few seconds of
MediaPipe tracking per sign. This runs the same steps for the words in
asl_util/data/common_words.txt (or a word list you pass), skipping signs already made. Each word
goes through the same translation an upload uses, so "running" makes RUN and "the" makes nothing.
With --all it makes every entry in the Signbank gloss list instead, so no sign is ever made
while someone watches.

Usage:
    python scripts/make_common_signs.py [WORDS.txt] [--workers N]
    python scripts/make_common_signs.py --all [--workers N]

Animations go to $SIGNMEUP_CACHE_DIR/poses, like the app's. It can be stopped and run again.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asl_util.poses import PoseStore  # noqa: E402
from asl_util.signbank import GlossIndex, SignMedia, VideoResolver  # noqa: E402
from asl_util.translate import StanzaGlosser  # noqa: E402

COMMON_WORDS = Path(__file__).resolve().parent.parent / "asl_util" / "data" / "common_words.txt"


def read_words(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("words", nargs="?", type=Path, default=COMMON_WORDS)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--all", action="store_true", help="every Signbank entry, not a word list")
    args = parser.parse_args()

    cache_dir = Path(os.environ.get("SIGNMEUP_CACHE_DIR", Path(tempfile.gettempdir()) / "signmeup-cache"))
    index, resolver, poses = GlossIndex.load(), VideoResolver(cache_dir / "signbank_videos.json"), PoseStore(cache_dir / "poses")
    if args.all:
        make_all(index, resolver, poses, args.workers)
        return
    media = SignMedia(index, resolver, poses, workers=args.workers)
    glosser = StanzaGlosser()
    signs = [s for word in read_words(args.words) for s in glosser.to_signs(word) if s.kind == "sign"]
    print(f"{len(signs)} words to sign, writing to {cache_dir / 'poses'}", flush=True)

    started = time.time()

    def progress(done: int, total: int) -> None:
        if done % 25 == 0 or done == total:
            print(f"{done}/{total} words, {time.time() - started:.0f}s", flush=True)

    found = media.for_signs(signs, on_progress=progress)
    animated = {m["id"] for m in found if m and "pose" in m}
    print(f"Done: {len(animated)} signs animated in {time.time() - started:.0f}s")


def make_all(index: GlossIndex, resolver: VideoResolver, poses: PoseStore, workers: int) -> None:
    entries = index.entries()
    print(f"{len(entries)} Signbank entries, writing to {poses.cache_dir}", flush=True)
    started = time.time()

    def make(gloss: str, entry_id: int) -> bool:
        url = resolver.video_url(entry_id)
        return bool(url) and poses.ensure(entry_id, gloss, url)

    animated = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(make, gloss, entry_id) for gloss, entry_id in entries]
        for done, future in enumerate(as_completed(futures), start=1):
            animated += future.result()
            if done % 100 == 0 or done == len(entries):
                print(f"{done}/{len(entries)} entries, {animated} animated, {time.time() - started:.0f}s", flush=True)
    print(f"Done: {animated} of {len(entries)} entries animated in {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
