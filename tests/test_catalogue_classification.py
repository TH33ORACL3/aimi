from __future__ import annotations

import unittest

from catalogue_classification import classify_model_category, extract_modalities, normalise_modalities


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
        # The common OpenRouter shape uses explicit input/output keys, while
        # these assertions protect the normaliser used by API adapters.
        self.assertEqual(normalise_modalities("text+image+file", "input"), ["text", "image", "file"])
        self.assertEqual(normalise_modalities("text+image+file->text", "output"), ["text"])
        self.assertEqual(extract_modalities({"modalities": "text+image->text"}, "input_modalities"), ["text", "image"])
        self.assertEqual(extract_modalities({"modalities": "text+image->text"}, "output_modalities"), ["text"])

    def test_name_fallback_is_preserved_without_endpoint_metadata(self) -> None:
        self.assertEqual(classify_model_category("gpt-image-2"), "image")
        self.assertEqual(classify_model_category("deepseek-v4-pro"), "chat")


if __name__ == "__main__":
    unittest.main()
