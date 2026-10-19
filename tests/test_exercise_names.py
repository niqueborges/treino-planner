import unittest

from app.exercise_names import display_name_from_filename, exercise_display_name


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

    def test_uses_reviewed_portuguese_name_without_changing_source_name(self):
        source_name = "Dumbbell Alternate Shoulder Press (female) Shoulders.gif"
        self.assertEqual(exercise_display_name(source_name), "Desenvolvimento alternado com halteres")
        self.assertEqual(display_name_from_filename(source_name), "Dumbbell Alternate Shoulder Press (female) Shoulders")

    def test_untranslated_exercise_keeps_its_formatted_original_name(self):
        source_name = "Cable Row.gif"
        self.assertEqual(exercise_display_name(source_name), "Cable Row")

    def test_displays_the_four_recent_exercises_in_portuguese(self):
        translations = {
            "Dumbbell Front Squat (female) Thighs": "Agachamento frontal com halteres",
            "4 Punches Side Squat (female) Plyometrics": "Agachamento lateral com 4 socos",
            "Bodyweight Half Squat (male) Thighs": "Meio agachamento com peso corporal",
            "Band Low Chest Press (female) Chest": "Supino baixo com faixa elástica",
        }
        for original_name, translated_name in translations.items():
            with self.subTest(original_name=original_name):
                self.assertEqual(exercise_display_name(original_name + ".gif"), translated_name)
                self.assertEqual(display_name_from_filename(original_name + ".gif"), original_name)


if __name__ == "__main__":
    unittest.main()
