import unittest

from replacements import apply_replacements, replacement_prompt_notes


class TestApplyReplacements(unittest.TestCase):
    def test_mid_century_lowercase(self):
        self.assertEqual(
            apply_replacements(
                "A mid-century modern interior.",
                {"mid-century": "midcentury"},
            ),
            "A midcentury modern interior.",
        )

    def test_mid_century_title_case(self):
        self.assertEqual(
            apply_replacements(
                "TWA Flight Center 1962 Mid-Century Modern Poster Art",
                {"mid-century": "midcentury"},
            ),
            "TWA Flight Center 1962 Midcentury Modern Poster Art",
        )

    def test_mid_century_uppercase(self):
        self.assertEqual(
            apply_replacements(
                "MID-CENTURY MODERN",
                {"mid-century": "midcentury"},
            ),
            "MIDCENTURY MODERN",
        )

    def test_does_not_replace_partial_words(self):
        self.assertEqual(
            apply_replacements("mid-centurylike", {"mid-century": "midcentury"}),
            "mid-centurylike",
        )

    def test_longer_phrase_wins(self):
        self.assertEqual(
            apply_replacements(
                "mid-century modern furniture",
                {
                    "mid-century": "midcentury",
                    "mid-century modern": "midcentury modern",
                },
            ),
            "midcentury modern furniture",
        )

    def test_empty_mapping_is_noop(self):
        self.assertEqual(apply_replacements("mid-century", {}), "mid-century")

    def test_prompt_notes_include_pairs(self):
        notes = replacement_prompt_notes({"mid-century": "midcentury"})
        self.assertIn("midcentury", notes)
        self.assertIn("mid-century", notes)


if __name__ == "__main__":
    unittest.main()
