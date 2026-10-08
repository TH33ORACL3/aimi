#!/usr/bin/env python3
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import aimi_credentials


class TestAimiCredentials(unittest.TestCase):
    def test_parse_env_file_rejects_loose_permissions(self) -> None:
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("KEY=secret\n")
            tf.flush()
            path = Path(tf.name)
            try:
                path.chmod(0o644)
                parsed = aimi_credentials._parse_env_file(path)
                self.assertEqual(parsed, {})
            finally:
                path.unlink(missing_ok=True)

    def test_parse_env_file_reads_mode_600(self) -> None:
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("KEY=secret_val\nexport OTHER='another_val'\n")
            tf.flush()
            path = Path(tf.name)
            try:
                path.chmod(0o600)
                parsed = aimi_credentials._parse_env_file(path)
                self.assertEqual(parsed.get("KEY"), "secret_val")
                self.assertEqual(parsed.get("OTHER"), "another_val")
            finally:
                path.unlink(missing_ok=True)

    def test_load_aimi_credentials_routes_typesafe_key(self) -> None:
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            tf.write("AIMI_TYPESAFE_API_KEY=test_aimi_typesafe_secret\n")
            tf.flush()
            path = Path(tf.name)
            try:
                path.chmod(0o600)
                with patch.object(aimi_credentials, "CREDENTIALS_PATH", path):
                    with patch.dict(os.environ, {}, clear=True):
                        aimi_credentials.load_aimi_credentials()
                        self.assertEqual(
                            os.environ.get("TYPESAFE_API_KEY"),
                            "test_aimi_typesafe_secret",
                        )
                        self.assertEqual(
                            os.environ.get("TYPESAFE_JEV_API_KEY"),
                            "test_aimi_typesafe_secret",
                        )
            finally:
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
