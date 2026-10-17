from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "app.js").read_text()


class WeeklyStartActionTests(unittest.TestCase):
    def test_start_button_is_rendered_only_for_days_with_exercises(self):
        self.assertRegex(
            APP_JS,
            re.compile(
                r"\$\{day\.exercises\.length\?`<button[^`]*"
                r"data-start-weekday=\"\$\{day\.weekday\}\"[^`]*`:''\}"
            ),
        )

    def test_start_button_routes_its_weekday_to_existing_execution_flow(self):
        self.assertIn(
            "await startPlannedWorkout(Number(start.dataset.startWeekday))",
            APP_JS,
        )

    def test_add_exercise_action_remains_in_each_day_card(self):
        self.assertIn('data-add-day="${day.id}"', APP_JS)
        self.assertIn('＋ Adicionar exercício', APP_JS)


if __name__ == "__main__":
    unittest.main()
