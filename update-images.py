#!/usr/bin/env python3
"""
Generate alt text for images using caption.py (Anthropic/LLM) and write to the
XMP Alt Text (Accessibility) field in each image. No remote API or AUTH_TOKEN.
Requires: exiftool (brew install exiftool), llm + llm-anthropic, API key via llm keys set anthropic.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# IPTC limit for AltTextAccessibility
ALT_TEXT_MAX_LEN = 250

DEFAULT_MODEL = "claude-sonnet-4-5"
DELAY_BETWEEN_REQUESTS = 2  # seconds
SCRIPT_DIR = Path(__file__).resolve().parent
CAPTION_SCRIPT = SCRIPT_DIR / "caption.py"


def get_existing_alt_text(image_path: Path) -> Optional[str]:
    """Read current AltTextAccessibility from image via exiftool. Returns None if not set or exiftool missing."""
    exiftool = shutil.which("exiftool")
    if not exiftool:
        return None
    try:
        result = subprocess.run(
            [exiftool, "-AltTextAccessibility", "-s3", "-n", str(image_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout:
            return None
        value = result.stdout.strip()
        return value if value else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def write_alt_text(image_path: Path, alt_text: str) -> bool:
    """Write AltTextAccessibility to image via exiftool. Truncates to 250 chars. Returns True on success."""
    exiftool = shutil.which("exiftool")
    if not exiftool:
        print("❌ exiftool not found. Install with: brew install exiftool")
        return False
    # IPTC limit; replace newlines with space
    text = alt_text[:ALT_TEXT_MAX_LEN].replace("\n", " ").strip()
    if not text:
        return False
    try:
        # -overwrite_original to avoid leaving _original backups in the gallery
        result = subprocess.run(
            [exiftool, "-overwrite_original", f"-AltTextAccessibility={text}", str(image_path)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            print(f"  ❌ exiftool error: {result.stderr or result.stdout}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  ❌ exiftool timed out")
        return False


def generate_alt_text(image_path: Path, model: str, context: Optional[str]) -> Optional[str]:
    """Run caption.py for one image and return the caption for the given model, or None on failure."""
    cmd = [str(CAPTION_SCRIPT), str(image_path), "--model", model]
    if context:
        cmd.extend(["--context", context])
    env = dict(os.environ)
    env["IMAGE_CAPTION_CONFIG"] = str(SCRIPT_DIR / "models.yaml")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=SCRIPT_DIR, env=env)
        if result.returncode != 0:
            print(f"  ❌ caption.py error: Command {result.args!r} returned exit status {result.returncode}.")
            if result.stderr:
                print(f"  stderr: {result.stderr.strip()}")
            if result.stdout and not result.stderr:
                print(f"  stdout: {result.stdout.strip()}")
            return None
        data = json.loads(result.stdout)
        captions = data.get("captions", {})
        alt = captions.get(model)
        if isinstance(alt, dict):
            alt = alt.get("caption") or alt.get("alt")
        return (alt or "").strip() or None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"  ❌ caption.py error: {e}")
        return None


def process_directory(
    directory: Path,
    model: str = DEFAULT_MODEL,
    context: Optional[str] = None,
    force: bool = False,
) -> None:
    """Process all images in directory: generate alt text and write to XMP AltTextAccessibility."""
    if not directory.is_dir():
        print(f"❌ Not a directory: {directory}")
        sys.exit(1)

    extensions = (".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp")
    image_paths = sorted(
        p for p in directory.iterdir()
        if p.is_file() and p.suffix.lower() in extensions
    )
    total = len(image_paths)
    if total == 0:
        print(f"No images found in {directory}")
        return

    print(f"Found {total} images in {directory}")
    print(f"Model: {model}")
    if context:
        print(f"Context: {context}")
    print()

    for idx, image_path in enumerate(image_paths, 1):
        time.sleep(DELAY_BETWEEN_REQUESTS)
        print(f"[{idx}/{total}] {image_path.name}")

        if not force:
            existing = get_existing_alt_text(image_path)
            if existing:
                print(f"  💠 Skipped (already has alt text). Use --force to overwrite.")
                continue

        alt = generate_alt_text(image_path, model, context)
        if not alt:
            print("  ❌ No alt text generated, skipping.")
            continue
        # Never write error messages into the image metadata
        if alt.strip().lower().startswith("error") or "unknown model" in alt.lower():
            print(f"  ❌ Caption failed (not written): {alt[:60]}...")
            continue
        if len(alt) > ALT_TEXT_MAX_LEN:
            alt = alt[:ALT_TEXT_MAX_LEN - 3] + "..."
            print(f"  ℹ️ Truncated to {ALT_TEXT_MAX_LEN} chars.")
        print(f"  🟢 {alt[:80]}{'...' if len(alt) > 80 else ''}")

        if write_alt_text(image_path, alt):
            print("  ✓ Written to XMP AltTextAccessibility")
        else:
            print("  ❌ Failed to write metadata.")

    print("\nDone.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate alt text with LLM (e.g. Anthropic) and write to XMP Alt Text (Accessibility) in images."
    )
    parser.add_argument(
        "directory",
        type=Path,
        help="Folder containing images (e.g. path/to/image/folder)",
    )
    parser.add_argument(
        "context",
        nargs="?",
        default=None,
        help="Brief description of the images (optional; can also use -c/--context)",
    )
    parser.add_argument(
        "-c",
        "--context",
        dest="context",
        help="Context for better captions (e.g. 'Cherry blossoms at Japanese Friendship Garden')",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model for caption.py (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing AltTextAccessibility",
    )
    args = parser.parse_args()
    process_directory(args.directory, args.model, args.context, args.force)


if __name__ == "__main__":
    main()
