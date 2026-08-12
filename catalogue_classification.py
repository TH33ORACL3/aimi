"""Classify model routes from explicit endpoint modality metadata.

A model that accepts images is not necessarily an image-generation model. The
output contract is the deciding signal for generated media; image input with
text output is a vision/multimodal route.
"""
from __future__ import annotations

import re
from typing import Any


_MODALITY_SPLIT = re.compile(r"[+,\s]+")


def normalise_modalities(value: Any, side: str | None = None) -> list[str] | None:
    """Return lower-case modality names while preserving unknown values.

    Providers use both arrays (``["text", "image"]``) and compact strings such
    as ``text+image+file->text``. ``side`` selects the input or output half of
    the latter form.
    """
    if value is None:
        return None

    values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for item in values:
        if item is None:
            continue
        text = str(item).strip().lower()
        if not text:
            continue
        if "->" in text:
            halves = text.split("->", 1)
            text = halves[0 if side == "input" else 1] if side in {"input", "output"} else text
        for part in _MODALITY_SPLIT.split(text):
            if part and part not in result:
                result.append(part)
    return result or None


def extract_modalities(item: dict[str, Any], key: str) -> list[str] | None:
    """Read a provider item's explicit input/output modality contract."""
    architecture = item.get("architecture")
    architecture = architecture if isinstance(architecture, dict) else {}
    side = "input" if key == "input_modalities" else "output"

    value = item.get(key)
    if value is None:
        value = architecture.get(key)
    if value is None:
        value = item.get("modalities")
    return normalise_modalities(value, side)


def _name_category(model_id: str, name: str) -> str:
    """Legacy name fallback used only when endpoint metadata is absent."""
    text = f"{model_id} {name}".lower()
    if any(term in text for term in ("embed", "embedding")):
        return "embedding"
    if any(term in text for term in ("image", "imagen", "flux")):
        return "image"
    if any(term in text for term in ("video", "veo")):
        return "video"
    if any(term in text for term in ("tts", "audio", "voxtral", "speech", "whisper")):
        return "audio"
    if any(term in text for term in ("vision", "vl", "scout")):
        return "vision"
    if any(term in text for term in ("code", "coder", "codestral", "devstral", "fim")):
        return "code"
    if any(term in text for term in ("reason", "o1", "o3", "o4", "thinking", "magistral")):
        return "reasoning"
    if any(term in text for term in ("moderation", "guard", "safety")):
        return "safety"
    return "chat"


def classify_model_category(
    model_id: str,
    name: str = "",
    input_modalities: Any = None,
    output_modalities: Any = None,
) -> str:
    """Classify a route without confusing vision input with image output."""
    inputs = normalise_modalities(input_modalities, "input")
    outputs = normalise_modalities(output_modalities, "output")

    # Explicit output modalities take precedence over names and input support.
    if outputs:
        if "embedding" in outputs:
            return "embedding"
        if "video" in outputs:
            return "video"
        if "audio" in outputs:
            return "audio"
        if "image" in outputs:
            return "image"
        if "text" in outputs:
            if inputs and any(modality in inputs for modality in ("image", "video")):
                return "vision"
            # A text-output route named *image* is not an image generator.
            return _name_category_without_media(model_id, name)

    # An image-capable route whose output is unknown is still not proven to
    # generate images. Keep it in the vision bucket rather than locking it to
    # image generation.
    if inputs and any(modality in inputs for modality in ("image", "video")):
        return "vision"

    return _name_category(model_id, name)


def _name_category_without_media(model_id: str, name: str) -> str:
    """Name fallback for a route with a confirmed non-media output."""
    text = f"{model_id} {name}".lower()
    if any(term in text for term in ("embed", "embedding")):
        return "embedding"
    if any(term in text for term in ("code", "coder", "codestral", "devstral", "fim")):
        return "code"
    if any(term in text for term in ("reason", "o1", "o3", "o4", "thinking", "magistral")):
        return "reasoning"
    if any(term in text for term in ("moderation", "guard", "safety")):
        return "safety"
    if any(term in text for term in ("tts", "audio", "voxtral", "speech", "whisper")):
        return "audio"
    return "chat"


# Compatibility name for callers that used the original helper.
def category(
    model_id: str,
    name: str = "",
    input_modalities: Any = None,
    output_modalities: Any = None,
) -> str:
    return classify_model_category(model_id, name, input_modalities, output_modalities)
