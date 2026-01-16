"""Translation functionality for processing pipeline using Papago."""

import base64
import hmac
import json
import re
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


class PapagoTranslationError(Exception):
    """Raised when Papago translation fails."""

    pass


def _get_papago_version() -> str:
    """Fetch the current Papago API version from their website.

    Returns:
        The version string needed for API authentication.

    Raises:
        PapagoTranslationError: If version cannot be fetched.
    """
    try:
        script = requests.get("https://papago.naver.com", timeout=10)
        main_js_match = re.search(r"\/(main.*\.js)", script.text)
        if not main_js_match:
            raise PapagoTranslationError("Could not find Papago main.js")

        main_js = main_js_match.group(1)
        papago_ver_data = requests.get(f"https://papago.naver.com/{main_js}", timeout=10)
        ver_match = re.search(r'"PPG .*,"(v[^"]*)', papago_ver_data.text)
        if not ver_match:
            raise PapagoTranslationError("Could not extract Papago version")

        return ver_match.group(1)
    except requests.RequestException as e:
        raise PapagoTranslationError(f"Failed to fetch Papago version: {e}") from e


def _translate_text_papago(text: str, papago_version: str) -> str:
    """Translate a single text string from Korean to English using Papago.

    Args:
        text: Korean text to translate.
        papago_version: Papago API version string.

    Returns:
        Translated English text.

    Raises:
        PapagoTranslationError: If translation fails.
    """
    if not text.strip():
        return ""

    papago_url = "https://papago.naver.com/apis/n2mt/translate"
    guid = str(uuid.uuid4())
    timestamp = int(time.time() * 1000)

    # Generate authentication token
    key = papago_version.encode("utf-8")
    code = f"{guid}\n{papago_url}\n{timestamp}".encode("utf-8")
    token = base64.b64encode(hmac.new(key, code, "MD5").digest()).decode("utf-8")

    headers = {
        "Authorization": f"PPG {guid}:{token}",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Timestamp": str(timestamp),
    }

    data = {
        "source": "ko",
        "target": "en",
        "text": text,
        "honorific": "false",
    }

    try:
        resp = requests.post(papago_url, data=data, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result.get("translatedText", "")
    except requests.RequestException as e:
        raise PapagoTranslationError(f"Papago API request failed: {e}") from e
    except (KeyError, json.JSONDecodeError) as e:
        raise PapagoTranslationError(f"Invalid Papago response: {e}") from e


def run_translation(ocr_result: dict, source_ocr_path: str | None = None) -> dict:
    """Translate OCR result from Korean to English using Papago.

    Args:
        ocr_result: OCR result dict with 'lines' array, each containing 'text'.
        source_ocr_path: Optional path to source OCR file for reference.

    Returns:
        Translation result dict with same line order as input.

    Raises:
        PapagoTranslationError: If translation fails.
    """
    # Get Papago version for authentication
    papago_version = _get_papago_version()

    # Extract lines from OCR result
    ocr_lines = ocr_result.get("lines", [])

    # Translate each line independently, preserving order
    translated_lines = []
    for line in ocr_lines:
        source_text = line.get("text", "")
        try:
            translated_text = _translate_text_papago(source_text, papago_version)
        except PapagoTranslationError:
            # Re-raise to fail the entire translation
            raise

        translated_lines.append(
            {
                "source_text": source_text,
                "translated_text": translated_text,
                "confidence": None,  # Papago doesn't provide confidence scores
            }
        )

    # Construct translation result
    translation_result = {
        "engine": "papago",
        "source_language": "ko",
        "target_language": "en",
        "lines": translated_lines,
        "source_ocr": source_ocr_path,
        "created_at": datetime.utcnow().isoformat(),
    }

    return translation_result


def write_translation_result(translation_result: dict, output_path: Path) -> None:
    """Write translation result to JSON file.

    Args:
        translation_result: Translation result dict to write.
        output_path: Path to write JSON file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(translation_result, f, indent=2, ensure_ascii=False)
