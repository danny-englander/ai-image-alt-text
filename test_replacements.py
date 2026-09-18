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

    def test_em_dash_with_spaces_becomes_hyphen(self):
        self.assertEqual(
            apply_replacements("Wanderer — Beneath a Burning Sky", {}),
            "Wanderer - Beneath a Burning Sky",
        )

    def test_em_dash_without_spaces_becomes_hyphen(self):
        self.assertEqual(
            apply_replacements("She paused—then ran.", {}),
            "She paused-then ran.",
        )

    def test_em_dash_stripped_along_with_phrase_replacements(self):
        self.assertEqual(
            apply_replacements(
                "A mid-century lounge — low sofa",
                {"mid-century": "midcentury"},
            ),
            "A midcentury lounge - low sofa",
        )

    def test_prompt_notes_include_pairs(self):
        notes = replacement_prompt_notes({"mid-century": "midcentury"})
        self.assertIn("midcentury", notes)
        self.assertIn("mid-century", notes)
        self.assertIn("em dashes", notes)

    def test_prompt_notes_always_forbid_em_dashes(self):
        notes = replacement_prompt_notes({})
        self.assertIn("em dashes", notes)
        self.assertIn("\u2014", notes)


if __name__ == "__main__":
    unittest.main()
