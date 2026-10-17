import unittest

from app.exercise_names import display_name_from_filename


class DisplayNameFromFilenameTests(unittest.TestCase):
    def test_removes_extension_converted_suffix_and_normalizes_separators(self):
        self.assertEqual(
            display_name_from_filename(
                "Lever-Outdoor-Seated-Lat-Pulldown_Back__converted.gif"
            ),
            "Lever Outdoor Seated Lat Pulldown Back",
        )

    def test_preserves_gender_tag(self):
        self.assertEqual(
            display_name_from_filename("Dumbbell_Kickback-(female)_converted.gif"),
            "Dumbbell Kickback (female)",
        )

    def test_removes_numbered_converted_suffix_and_collapses_spaces(self):
        self.assertEqual(
            display_name_from_filename("  Cable--Row__converted 2.gif  "),
            "Cable Row",
        )


if __name__ == "__main__":
    unittest.main()
