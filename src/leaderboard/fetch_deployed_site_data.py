"""Fetch the JSON payload currently deployed on GitHub Pages.

The generated docs/site/data*.json files are intentionally ignored by git to
avoid recurring merge conflicts. This helper refreshes the local ignored copies
from the public Pages deployment when you want to inspect exactly what the live
site is reading.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
SITE_DIR = ROOT / "docs" / "site"
DEFAULT_BASE_URL = "https://wzk1015.github.io/WorldCupArena"
FILES = ("data.json", "data.zh.json", "data.en.json")


def _fetch(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"site base URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=SITE_DIR,
        help=f"directory to write data files (default: {SITE_DIR})",
    )
    parser.add_argument(
        "--file",
        choices=FILES,
        action="append",
        help="fetch only one payload file; repeat for multiple files",
    )
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    files = tuple(args.file or FILES)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name in files:
        url = f"{base_url}/{name}"
        target = args.out_dir / name
        target.write_bytes(_fetch(url))
        print(f"wrote {target} from {url}")


if __name__ == "__main__":
    main()
