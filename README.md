## Installation

This project generates image alt text using an LLM (via the `llm` CLI) and can write it into image files as XMP Alt Text (Accessibility).

These instructions assume macOS or Linux. Windows should work with equivalent tools, but commands may differ.

This code is loosely based on [Dries Buytaert's "Image Caption"](https://github.com/dbuytaert/image-caption). The key difference is in how the generated alt text is stored. Dries' script sends a PATCH request to a remote API, where the alt text is stored server-side and matched to the image by album name and filename. This script instead writes the alt text directly into the image file itself, using `exiftool` to set the `AltTextAccessibility` XMP metadata field, so the alt text is embedded in the image itself.

---

## 1. Prerequisites

- **Python**: 3.10+ (3.11/3.12 recommended)
- **Git**
- **System tools**:
  - `exiftool` (for writing XMP Alt Text into images)
- **LLM CLI tooling**:
  - [`llm`](https://llm.datasette.io/) (CLI wrapper)
  - At least one model/plugin configured (e.g. `llm-anthropic`, or local models via Ollama)

### Install system dependencies (macOS)

```bash
# exiftool
brew install exiftool
```

If you don’t have Homebrew installed, you can install it by following the instructions at the [Homebrew website](https://brew.sh/).

The `llm` CLI is installed later via `pip install -r requirements.txt`, so you don’t need to install it separately.

### Configure an LLM provider

You have two main options: a **cloud model** (Anthropic/OpenAI/etc.) or a **local model** (via Ollama).

#### Option A: Anthropic (cloud, recommended default)

1. **Install the plugin**:

   ```bash
   llm install llm-anthropic
   ```

2. **Set your API key**:

   ```bash
   llm keys set anthropic
   # Paste your Anthropic API key when prompted
   ```

The default model used by `update-images.py` is `claude-sonnet-4-5`, which is preconfigured in `models.yaml`.

#### Option B: Local models via Ollama

1. **Install Ollama** and pull at least one vision-capable model, e.g.:

   ```bash
   # See https://ollama.com/ for installation instructions
   ollama pull llama3.2-vision:11b-instruct-q8_0
   ```

2. **Install the Ollama plugin for `llm`** (if required by your setup):

   ```bash
   llm install llm-ollama  # plugin name may vary; see Ollama + llm docs
   ```

3. Use one of the local model IDs configured in `models.yaml`, such as:

   - `llama-vision`
   - `llava-13b`
   - `llava-34b`
   - `llava-llama3`
   - `minicpm-v`
   - `qwen2.5vl-7b`
   - `qwen2.5vl-32b`
   - `gemma3-12b`
   - `gemma3-27b`
   - `mistral-3.1-24b`
   - `llama4-16x17b`

---

## 2. Clone the repository

```bash
git clone https://github.com/<your-username>/image-caption.git
cd image-caption
```

Replace the URL with the actual repo URL if different.

---

## 3. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

---

## 4. Install Python dependencies

From the project root:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

`requirements.txt` includes:

- `llm`
- `pillow`
- `ollama`
- `pyyaml`
- `requests`
- `python-dotenv`

---

## 5. Models configuration (`models.yaml`)

The file `models.yaml` (already in the repo) defines the available models and prompts for image captioning.

- It includes cloud models (e.g. `claude-sonnet-4-5`, `gpt-5`, `gpt-5.2`, `pixtral-*`) and local/Ollama models.
- `update-images.py` will automatically set the `IMAGE_CAPTION_CONFIG` environment variable to point to this file, so you normally do **not** need to configure it manually.

If you create your own config file elsewhere, you can override the default by setting:

```bash
export IMAGE_CAPTION_CONFIG=/absolute/path/to/your-models.yaml
```

---

## 6. Basic usage (local XMP alt text workflow)

The primary script in this repo is `update-images.py`, which:

- Scans a folder of images.
- Uses `caption.py` + `llm` to generate alt text.
- Writes the caption into the image’s **XMP Alt Text (Accessibility)** field via `exiftool`.

### Supported image formats

- `.jpg`, `.jpeg`, `.png`, `.gif`, `.heic`, `.webp`

### Run the script

From the project root:

```bash
# Activate your virtualenv if not already active
source .venv/bin/activate

# Basic run (uses default model from models.yaml: claude-sonnet-4-5)
python update-images.py /path/to/image/folder
```

You can provide optional context to improve captions:

```bash
python update-images.py /path/to/image/folder \
  --context "Cherry blossoms at Japanese Friendship Garden"
```

Or using the positional context argument:

```bash
python update-images.py /path/to/image/folder \
  "Cherry blossoms at Japanese Friendship Garden"
```

To choose a specific model defined in `models.yaml`:

```bash
python update-images.py /path/to/image/folder \
  --model claude-sonnet-4-5
```

To overwrite existing alt text in images:

```bash
python update-images.py /path/to/image/folder --force
```

---

## 7. Verifying the installation

### 7.1. Dry run on a small folder

1. Create a test folder with a few images, or use `test-images` if included in the repo.
2. Run:

   ```bash
   python update-images.py test-images
   ```

3. Check output:
   - You should see logs like `🟢 <caption…>` and `✓ Written to XMP AltTextAccessibility`.

### 7.2. Run unit tests

There is at least one test module (`test_caption.py`) exercising caption cleaning:

```bash
python -m unittest test_caption.py
```

All tests should pass.

---

## 8. Troubleshooting

- **`exiftool not found`**
  Install it with:

  ```bash
  brew install exiftool  # macOS
  ```

- **`caption.py error` or JSON decode errors**
  Often means `llm` is misconfigured or your LLM provider is not accessible. Check:

  ```bash
  llm models
  ```

  Confirm that the model you are using (e.g. `claude-sonnet-4-5` or `llama-vision`) is listed and working.

- **LLM API key issues**
  Re-run:

  ```bash
  llm keys list
  llm keys set anthropic
  ```

  And verify on your provider’s dashboard that the key is valid.

---

## 9. Summary

1. Install `exiftool`, `llm`, and configure at least one model (Anthropic or local).
2. Create and activate a Python virtualenv.
3. `pip install -r requirements.txt`.
4. Run:

   ```bash
   python update-images.py /path/to/images [--context ...] [--model ...] [--force]
   ```

   to generate and embed alt text in your images.

