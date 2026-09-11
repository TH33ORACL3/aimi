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
        value = architecture.get("modality")
    if value is None:
        value = item.get("modalities")
    return normalise_modalities(value, side)


def classify_input_type(input_modalities: Any) -> str:
    """Return canonical input type label.

    Categorization contract:
    - Text only (or text+file): 'text-input'
    - Image only: 'image-input'
    - Text and image: 'text+image-input'
    - Text and audio: 'text+audio-input'
    - Audio only: 'audio-input'
    - 3+ modalities or video: 'multimodal-input'
    """
    inputs = set(normalise_modalities(input_modalities, "input") or ["text"])
    media = inputs - {"file"}
    if not media or media == {"text"}:
        return "text-input"
    if media == {"image"}:
        return "image-input"
    if media == {"text", "image"}:
        return "text+image-input"
    if media == {"text", "audio"}:
        return "text+audio-input"
    if media == {"audio"}:
        return "audio-input"
    if len(media) >= 3 or "video" in media:
        return "multimodal-input"
    return "+".join(sorted(media)) + "-input"


def classify_output_type(output_modalities: Any) -> str:
    """Return non-text output types when present; default to 'text-output' otherwise."""
    outputs = set(normalise_modalities(output_modalities, "output") or ["text"])
    if "image" in outputs:
        return "image-output"
    if "video" in outputs:
        return "video-output"
    if "audio" in outputs:
        return "speech-output"
    if "embedding" in outputs:
        return "embedding-output"
    return "text-output"


def classify_capability_tags(
    input_modalities: Any,
    output_modalities: Any,
    metadata: dict[str, Any] | None = None,
) -> list[str]:
    """Return granular, accurate capability tags replacing the misleading 'image' label."""
    inputs = set(normalise_modalities(input_modalities, "input") or [])
    outputs = set(normalise_modalities(output_modalities, "output") or ["text"])
    meta = metadata or {}
    tags: list[str] = []

    # Visual modalities
    has_image_in = "image" in inputs
    has_image_out = "image" in outputs
    if has_image_in and not has_image_out:
        tags.extend(["vision", "image-understanding"])
    elif has_image_in and has_image_out:
        tags.extend(["vision", "image-generation", "image-to-image"])
    elif has_image_out:
        tags.append("image-generation")

    # Video modalities
    if "video" in inputs:
        tags.append("video-understanding")
    if "video" in outputs:
        tags.append("video-generation")

    # Audio modalities
    if "audio" in inputs:
        tags.extend(["audio-input", "speech-transcription"])
    if "audio" in outputs:
        tags.extend(["speech-output", "speech-synthesis"])

    # Functional capabilities
    if meta.get("reasoning") or meta.get("supports_reasoning") or meta.get("thinking"):
        tags.append("reasoning")
    if meta.get("tools") or meta.get("supports_tools") or meta.get("function_calling"):
        tags.append("tools")
    if meta.get("structured_outputs") or meta.get("supports_structured_output"):
        tags.append("structured-outputs")
    if meta.get("streaming") or meta.get("supports_streaming"):
        tags.append("streaming")

    return sorted(list(dict.fromkeys(tags)))


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
