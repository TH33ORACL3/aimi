from __future__ import annotations

import unittest

from catalogue_classification import (
    classify_capability_tags,
    classify_input_type,
    classify_model_category,
    classify_output_type,
    extract_modalities,
    normalise_modalities,
)


class CatalogueClassificationTests(unittest.TestCase):
    def test_grok_multimodal_text_route_is_vision_not_image_generation(self) -> None:
        self.assertEqual(
            classify_model_category(
                "x-ai/grok-4.6",
                "SpaceXAI: Grok 4.6",
                ["text", "image", "file"],
                ["text"],
            ),
            "vision",
        )

    def test_image_output_remains_image_category(self) -> None:
        self.assertEqual(
            classify_model_category(
                "qwen/qwen-image-3",
                "Qwen: Qwen Image 3",
                ["text", "image"],
                ["image"],
            ),
            "image",
        )

    def test_text_output_overrides_image_in_display_name(self) -> None:
        self.assertEqual(
            classify_model_category(
                "gemini-3.1-flash-image",
                "Nano Banana 2",
                ["text", "image"],
                ["text"],
            ),
            "vision",
        )

    def test_compact_provider_modality_strings_are_split_by_side(self) -> None:
        self.assertEqual(normalise_modalities("text+image+file", "input"), ["text", "image", "file"])
        self.assertEqual(normalise_modalities("text+image+file->text", "output"), ["text"])
        self.assertEqual(extract_modalities({"modalities": "text+image->text"}, "input_modalities"), ["text", "image"])
        self.assertEqual(extract_modalities({"modalities": "text+image->text"}, "output_modalities"), ["text"])
        self.assertEqual(extract_modalities({"architecture": {"modality": "text+image+video->text"}}, "input_modalities"), ["text", "image", "video"])
        self.assertEqual(extract_modalities({"architecture": {"modality": "text+image+video->text"}}, "output_modalities"), ["text"])

    def test_name_fallback_is_preserved_without_endpoint_metadata(self) -> None:
        self.assertEqual(classify_model_category("gpt-image-2"), "image")
        self.assertEqual(classify_model_category("deepseek-v4-pro"), "chat")

    def test_classify_input_type(self) -> None:
        self.assertEqual(classify_input_type(["text"]), "text-input")
        self.assertEqual(classify_input_type(["text", "file"]), "text-input")
        self.assertEqual(classify_input_type(["image"]), "image-input")
        self.assertEqual(classify_input_type(["text", "image"]), "text+image-input")
        self.assertEqual(classify_input_type(["text", "image", "file"]), "text+image-input")
        self.assertEqual(classify_input_type(["text", "audio"]), "text+audio-input")
        self.assertEqual(classify_input_type(["audio"]), "audio-input")
        self.assertEqual(classify_input_type(["text", "image", "video"]), "multimodal-input")
        self.assertEqual(classify_input_type(["text", "image", "audio", "video"]), "multimodal-input")

    def test_classify_output_type(self) -> None:
        self.assertEqual(classify_output_type(["text"]), "text-output")
        self.assertEqual(classify_output_type(None), "text-output")
        self.assertEqual(classify_output_type(["image"]), "image-output")
        self.assertEqual(classify_output_type(["text", "image"]), "image-output")
        self.assertEqual(classify_output_type(["video"]), "video-output")
        self.assertEqual(classify_output_type(["audio"]), "speech-output")
        self.assertEqual(classify_output_type(["embedding"]), "embedding-output")

    def test_classify_capability_tags(self) -> None:
        # Vision model (image in, text out)
        tags_vision = classify_capability_tags(["text", "image"], ["text"], {"reasoning": 1, "tools": 1})
        self.assertIn("vision", tags_vision)
        self.assertIn("image-understanding", tags_vision)
        self.assertNotIn("image-generation", tags_vision)
        self.assertIn("reasoning", tags_vision)
        self.assertIn("tools", tags_vision)

        # Image generation model (text in, image out)
        tags_gen = classify_capability_tags(["text"], ["image"])
        self.assertIn("image-generation", tags_gen)
        self.assertNotIn("vision", tags_gen)

        # Image-to-image model (image in, image out)
        tags_i2i = classify_capability_tags(["text", "image"], ["image", "text"])
        self.assertIn("vision", tags_i2i)
        self.assertIn("image-generation", tags_i2i)
        self.assertIn("image-to-image", tags_i2i)

        # Video understanding
        tags_video = classify_capability_tags(["text", "video"], ["text"])
        self.assertIn("video-understanding", tags_video)

        # Speech model
        tags_speech = classify_capability_tags(["audio"], ["text", "audio"])
        self.assertIn("speech-transcription", tags_speech)
        self.assertIn("speech-synthesis", tags_speech)


if __name__ == "__main__":
    unittest.main()
