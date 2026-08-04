#!/usr/bin/env python3
"""
Generate alt text for images using caption.py (Anthropic/LLM) and write to the
XMP Alt Text (Accessibility) field in each image. Optionally (--iptc) also
generate and overwrite IPTC Title, Description, and Keywords for Adobe Bridge.
Requires: exiftool (brew install exiftool), llm + llm-anthropic, API key via llm keys set anthropic.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from tempfile import gettempdir
from typing import Optional

import yaml
from PIL import Image

# IPTC limit for AltTextAccessibility
ALT_TEXT_MAX_LEN = 250
KEYWORDS_TARGET_LEN = 500
# IPTC ObjectName max is 64; stay under that so titles don't truncate mid-word.
TITLE_MAX_LEN = 59

DEFAULT_MODEL = "claude-sonnet-4-5"
DELAY_BETWEEN_REQUESTS = 2  # seconds
SCRIPT_DIR = Path(__file__).resolve().parent
CAPTION_SCRIPT = SCRIPT_DIR / "caption.py"
MODELS_CONFIG = SCRIPT_DIR / "models.yaml"

IPTC_META_PROMPT = """You are helping tag a photograph for Adobe Bridge IPTC Core metadata.
Given the image and this short alt text: {alt}

Produce ONLY a JSON object (no markdown fences, no other text) with exactly these keys:
- "title": a concise marketplace-style title for the artwork. Use as much of {title_len} characters as possible without exceeding {title_len}. Prefer subject, place/year if visible in the image, and style. Title Case. No Midjourney prompts, job IDs, or file names.
- "description": 3-4 complete sentences expanding on the alt text. Describe subject, setting, style, and notable details in clear prose. Do not include Midjourney prompts, job IDs, or technical generation parameters.
- "keywords": a single comma-separated string of relevant search keywords/tags. Aim for approximately {keywords_len} characters total. Prefer concrete nouns, styles, subjects, and themes. No duplicates.

{context_block}"""

TITLE_ONLY_PROMPT = """You are helping tag a photograph for Adobe Bridge IPTC Core metadata.
Look at the image{hint_clause}.

Produce ONLY a JSON object (no markdown fences, no other text) with exactly this key:
- "title": a concise marketplace-style title for the artwork. Use as much of {title_len} characters as possible without exceeding {title_len}. Prefer subject, place/year if visible in the image, and style. Title Case. No Midjourney prompts, job IDs, or file names.

{context_block}"""


def get_existing_alt_text(image_path: Path) -> Optional[str]:
    """Read current AltTextAccessibility from image via exiftool. Returns None if not set or exiftool missing."""
    return read_exif_field(image_path, "AltTextAccessibility")


def read_exif_field(image_path: Path, tag: str) -> Optional[str]:
    """Read a single tag from image via exiftool. Returns None if not set or exiftool missing."""
    exiftool = shutil.which("exiftool")
    if not exiftool:
        return None
    try:
        result = subprocess.run(
            [exiftool, f"-{tag}", "-s3", "-n", str(image_path)],
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
            [
                exiftool,
                "-overwrite_original",
                f"-AltTextAccessibility={text}",
                str(image_path),
            ],
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


def truncate_keywords(keywords: str, max_len: int = KEYWORDS_TARGET_LEN) -> str:
    """Trim keywords to max_len at the last complete comma-separated keyword."""
    text = re.sub(r"\s+", " ", keywords.replace("\n", " ")).strip().strip(",")
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if "," in cut:
        cut = cut.rsplit(",", 1)[0]
    return cut.strip().rstrip(",")


def truncate_title(title: str, max_len: int = TITLE_MAX_LEN) -> str:
    """Trim title to max_len at the last complete word."""
    text = re.sub(r"\s+", " ", title.replace("\n", " ")).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rstrip()
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.strip()


def write_iptc_metadata(
    image_path: Path, title: str, description: str, keywords: str
) -> bool:
    """Overwrite Title, ObjectName, Description, Caption-Abstract, Keywords, and Subject via exiftool."""
    exiftool = shutil.which("exiftool")
    if not exiftool:
        print("❌ exiftool not found. Install with: brew install exiftool")
        return False
    title = truncate_title(title)
    description = description.replace("\n", " ").strip()
    keywords = truncate_keywords(keywords)
    if not title or not description or not keywords:
        return False
    try:
        # Clear Keywords/Subject first so Bridge shows a full replace, not append.
        result = subprocess.run(
            [
                exiftool,
                "-overwrite_original",
                "-Keywords=",
                "-XMP-dc:Subject=",
                "-sep",
                ", ",
                f"-Title={title}",
                f"-ObjectName={title}",
                f"-Keywords={keywords}",
                f"-XMP-dc:Subject={keywords}",
                f"-Description={description}",
                f"-Caption-Abstract={description}",
                str(image_path),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            print(f"  ❌ exiftool IPTC error: {result.stderr or result.stdout}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  ❌ exiftool timed out writing IPTC")
        return False


def write_title_only(image_path: Path, title: str) -> bool:
    """Overwrite only Title and ObjectName via exiftool. Leaves other IPTC fields alone."""
    exiftool = shutil.which("exiftool")
    if not exiftool:
        print("❌ exiftool not found. Install with: brew install exiftool")
        return False
    title = truncate_title(title)
    if not title:
        return False
    try:
        result = subprocess.run(
            [
                exiftool,
                "-overwrite_original",
                f"-Title={title}",
                f"-ObjectName={title}",
                str(image_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            print(f"  ❌ exiftool title error: {result.stderr or result.stdout}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print("  ❌ exiftool timed out writing title")
        return False


def resolve_llm_model_id(model_name: str) -> Optional[str]:
    """Map models.yaml key (e.g. claude-sonnet-4-5) to llm -m id."""
    try:
        with open(MODELS_CONFIG) as f:
            models = yaml.safe_load(f)
        config = models.get(model_name)
        if not config:
            print(f"  ❌ Unknown model in models.yaml: {model_name}")
            return None
        return config.get("model")
    except (OSError, yaml.YAMLError) as e:
        print(f"  ❌ Failed to load models.yaml: {e}")
        return None


def resize_image_for_llm(image_path: Path, max_dimension: int = 1024) -> Path:
    """Return path to a resized image for LLM processing (temp file if resized)."""
    with Image.open(image_path) as img:
        if max(img.size) <= max_dimension:
            return image_path
        img.thumbnail((max_dimension, max_dimension))
        temp_path = Path(gettempdir()) / f"resized-llm-iptc{image_path.suffix}"
        img.save(temp_path, optimize=True)
        return temp_path


def parse_iptc_json(raw: str) -> Optional[dict]:
    """Parse JSON object from model output, stripping markdown fences if present."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to find first {...} block
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    return data


def generate_iptc_metadata(
    image_path: Path,
    model: str,
    alt: str,
    context: Optional[str],
) -> Optional[tuple[str, str, str]]:
    """Run llm vision call for title + description + keywords.

    Returns (title, description, keywords) or None.
    """
    llm_model = resolve_llm_model_id(model)
    if not llm_model:
        return None

    context_block = ""
    if context:
        context_block = f"Additional context: {context}\n"

    prompt = IPTC_META_PROMPT.format(
        alt=alt,
        title_len=TITLE_MAX_LEN,
        keywords_len=KEYWORDS_TARGET_LEN,
        context_block=context_block,
    )
    small_image = resize_image_for_llm(image_path)
    cmd = ["llm", "-m", llm_model, "-a", str(small_image), prompt]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=SCRIPT_DIR
        )
        if result.returncode != 0:
            print(
                f"  ❌ llm IPTC error: exit {result.returncode}."
            )
            if result.stderr:
                print(f"  stderr: {result.stderr.strip()}")
            return None
        data = parse_iptc_json(result.stdout)
        if not data:
            print("  ❌ Could not parse IPTC JSON from model output.")
            if result.stdout:
                print(f"  stdout: {result.stdout.strip()[:200]}...")
            return None
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        keywords = (data.get("keywords") or "").strip()
        if isinstance(keywords, list):
            keywords = ", ".join(str(k).strip() for k in keywords if str(k).strip())
        if not title or not description or not keywords:
            print("  ❌ IPTC JSON missing title, description, or keywords.")
            return None
        return truncate_title(title), description, truncate_keywords(keywords)
    except subprocess.TimeoutExpired:
        print("  ❌ llm timed out generating IPTC metadata.")
        return None


def generate_title_only(
    image_path: Path,
    model: str,
    context: Optional[str],
) -> Optional[str]:
    """Run llm vision call for title only. Uses existing Description/alt as hints when present."""
    llm_model = resolve_llm_model_id(model)
    if not llm_model:
        return None

    description = read_exif_field(image_path, "Description")
    alt = get_existing_alt_text(image_path)
    hints = []
    if description:
        hints.append(f"existing description: {description}")
    if alt:
        hints.append(f"existing alt text: {alt}")
    hint_clause = f" ({'; '.join(hints)})" if hints else ""

    context_block = ""
    if context:
        context_block = f"Additional context: {context}\n"

    prompt = TITLE_ONLY_PROMPT.format(
        hint_clause=hint_clause,
        title_len=TITLE_MAX_LEN,
        context_block=context_block,
    )
    small_image = resize_image_for_llm(image_path)
    cmd = ["llm", "-m", llm_model, "-a", str(small_image), prompt]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=SCRIPT_DIR
        )
        if result.returncode != 0:
            print(f"  ❌ llm title error: exit {result.returncode}.")
            if result.stderr:
                print(f"  stderr: {result.stderr.strip()}")
            return None
        data = parse_iptc_json(result.stdout)
        if not data:
            print("  ❌ Could not parse title JSON from model output.")
            if result.stdout:
                print(f"  stdout: {result.stdout.strip()[:200]}...")
            return None
        title = (data.get("title") or "").strip()
        if not title:
            print("  ❌ Title JSON missing title.")
            return None
        return truncate_title(title)
    except subprocess.TimeoutExpired:
        print("  ❌ llm timed out generating title.")
        return None


def generate_alt_text(
    image_path: Path, model: str, context: Optional[str]
) -> Optional[str]:
    """Run caption.py for one image and return the caption for the given model, or None on failure."""
    cmd = [str(CAPTION_SCRIPT), str(image_path), "--model", model]
    if context:
        cmd.extend(["--context", context])
    env = dict(os.environ)
    env["IMAGE_CAPTION_CONFIG"] = str(MODELS_CONFIG)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=SCRIPT_DIR, env=env
        )
        if result.returncode != 0:
            print(
                f"  ❌ caption.py error: Command {result.args!r} returned exit status {result.returncode}."
            )
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
    iptc: bool = False,
    title_only: bool = False,
) -> None:
    """Process all images in directory: generate alt text and write to XMP AltTextAccessibility."""
    if not directory.is_dir():
        print(f"❌ Not a directory: {directory}")
        sys.exit(1)

    extensions = (".jpg", ".jpeg", ".png", ".gif", ".heic", ".webp")
    image_paths = sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in extensions
    )
    total = len(image_paths)
    if total == 0:
        print(f"No images found in {directory}")
        return

    print(f"Found {total} images in {directory}")
    print(f"Model: {model}")
    if context:
        print(f"Context: {context}")
    if title_only:
        print("Title only: will overwrite Title/ObjectName; leave alt, description, keywords alone")
    elif iptc:
        print("IPTC: will overwrite Title, Description, and Keywords")
    print()

    for idx, image_path in enumerate(image_paths, 1):
        time.sleep(DELAY_BETWEEN_REQUESTS)
        print(f"[{idx}/{total}] {image_path.name}")

        if title_only:
            title = generate_title_only(image_path, model, context)
            if not title:
                print("  ❌ Failed to generate title.")
                continue
            print(f"  📌 Title ({len(title)} chars): {title}")
            if write_title_only(image_path, title):
                print("  ✓ Written IPTC Title only")
            else:
                print("  ❌ Failed to write title.")
            continue

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
            alt = alt[: ALT_TEXT_MAX_LEN - 3] + "..."
            print(f"  ℹ️ Truncated to {ALT_TEXT_MAX_LEN} chars.")
        print(f"  🟢 📸 🟢  {alt}")

        if write_alt_text(image_path, alt):
            print("  ✓ Written to XMP AltTextAccessibility")
        else:
            print("  ❌ Failed to write metadata.")
            continue

        if iptc:
            meta = generate_iptc_metadata(image_path, model, alt, context)
            if not meta:
                print("  ❌ Failed to generate IPTC title/description/keywords.")
                continue
            title, description, keywords = meta
            preview_desc = (
                description[:120] + "..." if len(description) > 120 else description
            )
            preview_kw = keywords[:120] + "..." if len(keywords) > 120 else keywords
            print(f"  📌 Title ({len(title)} chars): {title}")
            print(f"  📝 Description: {preview_desc}")
            print(f"  🏷️  Keywords ({len(keywords)} chars): {preview_kw}")
            if write_iptc_metadata(image_path, title, description, keywords):
                print("  ✓ Written IPTC Title, Description, and Keywords")
            else:
                print("  ❌ Failed to write IPTC metadata.")

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
    parser.add_argument(
        "--iptc",
        action="store_true",
        help="Also generate and overwrite IPTC Title, Description, and Keywords (Adobe Bridge IPTC Core)",
    )
    parser.add_argument(
        "--title-only",
        action="store_true",
        help="Only generate and overwrite Title/ObjectName; leave alt, description, and keywords unchanged",
    )
    args = parser.parse_args()
    if args.title_only and args.iptc:
        parser.error("Use either --title-only or --iptc, not both")
    process_directory(
        args.directory,
        args.model,
        args.context,
        args.force,
        args.iptc,
        args.title_only,
    )


if __name__ == "__main__":
    main()
