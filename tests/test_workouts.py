from __future__ import annotations

import tempfile
import unittest
import zipfile
import sqlite3
from pathlib import Path

from app.db import connect
from app.importer import import_dataset
from app import workouts
from app import users


class WorkoutPlannerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "planner.sqlite3"
        archive_path = self.root / "dataset.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("GIFS/FEMININO/ACADEMIA/PERNAS/agachamento.gif", b"GIF89a-test")
            archive.writestr("GIFS/MASCULINO/FUNCIONAL/CARDIO/corrida.gif", b"GIF89a-test2")
        import_dataset([archive_path], self.db_path)
        self.conn = connect(self.db_path)
        self.user_id = users.require_user(self.conn, None)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_plan_days_exercise_sets_edits_reorder_remove_and_reload(self):
        plan = workouts.create_plan(self.conn, self.user_id, "Força")
        self.assertEqual(len(plan["days"]), 7)
        monday = plan["days"][0]
        tuesday = plan["days"][1]
        workouts.update_day(self.conn, self.user_id, tuesday["id"], title="Pernas + caminhada")
        exercise_ids = [r[0] for r in self.conn.execute("SELECT id FROM exercise ORDER BY id")]
        first = workouts.add_exercise(self.conn, self.user_id, monday["id"], exercise_ids[0])
        second = workouts.add_exercise(self.conn, self.user_id, monday["id"], exercise_ids[1])
        self.assertEqual(first["position"], 1)
        self.assertEqual(len(self.conn.execute("SELECT id FROM workout_set WHERE workout_exercise_id=?", (first["id"],)).fetchall()), 3)
        new_set = workouts.add_set(self.conn, self.user_id, first["id"])
        edited = workouts.update_set(self.conn, self.user_id, new_set["id"], {"load_value": 10, "load_unit": "kg", "repetitions": 8, "rest_seconds": 75, "notes": "Controlado"})
        self.assertEqual(edited["load_value"], 10)
        self.assertEqual(edited["repetitions"], 8)
        workouts.remove_set(self.conn, self.user_id, new_set["id"])
        self.assertEqual([r[0] for r in self.conn.execute("SELECT set_number FROM workout_set WHERE workout_exercise_id=? ORDER BY set_number", (first["id"],))], [1, 2, 3])
        workouts.reorder_exercises(self.conn, self.user_id, monday["id"], [second["id"], first["id"]])
        self.assertEqual([r[0] for r in self.conn.execute("SELECT id FROM workout_exercise WHERE day_id=? ORDER BY position", (monday["id"],))], [second["id"], first["id"]])
        duplicate = workouts.duplicate_exercise(self.conn, self.user_id, first["id"])
        self.assertEqual(duplicate["position"], 3)
        workouts.remove_exercise(self.conn, self.user_id, second["id"])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM workout_exercise WHERE day_id=?", (monday["id"],)).fetchone()[0], 2)
        self.conn.close()
        self.conn = connect(self.db_path)
        loaded = workouts.get_plan(self.conn, plan["id"], self.user_id)
        self.assertEqual(loaded["name"], "Força")
        self.assertEqual(loaded["days"][1]["title"], "Pernas + caminhada")
        self.assertEqual(len(loaded["days"][0]["exercises"]), 2)
        self.assertEqual(loaded["days"][0]["exercises"][0]["identification_status"], "pending")
        self.assertIsNotNone(loaded["days"][0]["exercises"][0]["media_id"])

    def test_display_translation_keeps_original_and_history_snapshots(self):
        plan = workouts.create_plan(self.conn, self.user_id, "Nomes")
        day = plan["days"][0]
        exercise_id = self.conn.execute("SELECT id FROM exercise ORDER BY id LIMIT 1").fetchone()[0]
        original_name = "Dumbbell Alternate Shoulder Press (female) Shoulders.gif"
        self.conn.execute("UPDATE exercise SET provisional_name_raw=? WHERE id=?", (original_name, exercise_id))
        workout_exercise = workouts.add_exercise(self.conn, self.user_id, day["id"], exercise_id)
        loaded_day = workouts.get_plan(self.conn, plan["id"], self.user_id)["days"][0]
        loaded_exercise = loaded_day["exercises"][0]
        self.assertEqual(loaded_exercise["display_name"], "Desenvolvimento alternado com halteres")
        self.assertEqual(loaded_exercise["original_name"], "Dumbbell Alternate Shoulder Press (female) Shoulders")
        self.assertEqual(loaded_exercise["exercise_id"], exercise_id)

        old_session = workouts.record_session(self.conn, self.user_id, day["id"], 60, [{
            "workout_exercise_id": workout_exercise["id"], "display_name": "Dumbbell Alternate Shoulder Press (female) Shoulders",
            "sets": [{"repetitions": 12, "rest_seconds": 90}],
        }])
        new_session = workouts.record_session(self.conn, self.user_id, day["id"], 60, [{
            "workout_exercise_id": workout_exercise["id"], "display_name": loaded_exercise["display_name"],
            "sets": [{"repetitions": 12, "rest_seconds": 90}],
        }])
        old_detail = workouts.get_session(self.conn, old_session["id"], self.user_id)
        new_detail = workouts.get_session(self.conn, new_session["id"], self.user_id)
        self.assertEqual(old_detail["exercises"][0]["exercise_name_snapshot"], "Dumbbell Alternate Shoulder Press (female) Shoulders")
        self.assertEqual(new_detail["exercises"][0]["exercise_name_snapshot"], "Desenvolvimento alternado com halteres")
        self.assertEqual(new_detail["exercises"][0]["workout_exercise_id_snapshot"], workout_exercise["id"])
        self.assertEqual(self.conn.execute("SELECT provisional_name_raw FROM exercise WHERE id=?", (exercise_id,)).fetchone()[0], original_name)

    def test_invalid_reorder_rejected_and_empty_day_is_rest(self):
        plan = workouts.create_plan(self.conn, self.user_id, "Teste")
        day = plan["days"][0]
        exercise_id = self.conn.execute("SELECT id FROM exercise LIMIT 1").fetchone()[0]
        item = workouts.add_exercise(self.conn, self.user_id, day["id"], exercise_id)
        with self.assertRaises(workouts.WorkoutError):
            workouts.reorder_exercises(self.conn, self.user_id, day["id"], [])
        workouts.remove_exercise(self.conn, self.user_id, item["id"])
        self.assertEqual(self.conn.execute("SELECT is_rest FROM workout_day WHERE id=?", (day["id"],)).fetchone()[0], 1)

    def test_users_are_selectable_and_plans_are_isolated(self):
        second_user = users.create_user(self.conn, "Outra pessoa")
        self.assertEqual(users.require_user(self.conn, second_user["id"]), second_user["id"])
        first_plan = workouts.create_plan(self.conn, self.user_id, "Privado A")
        second_plan = workouts.create_plan(self.conn, second_user["id"], "Privado B")
        self.assertEqual([p["id"] for p in workouts.list_plans(self.conn, self.user_id)], [first_plan["id"]])
        self.assertEqual([p["id"] for p in workouts.list_plans(self.conn, second_user["id"])], [second_plan["id"]])
        with self.assertRaises(LookupError):
            workouts.get_plan(self.conn, first_plan["id"], second_user["id"])
        with self.assertRaises(LookupError):
            workouts.rename_plan(self.conn, second_user["id"], first_plan["id"], "Acessar indevidamente")
        first_day = first_plan["days"][0]
        exercise_id = self.conn.execute("SELECT id FROM exercise LIMIT 1").fetchone()[0]
        workouts.add_exercise(self.conn, self.user_id, first_day["id"], exercise_id)
        workouts.record_session(self.conn, self.user_id, first_day["id"], 900)
        self.assertEqual(len(workouts.list_sessions(self.conn, self.user_id)), 1)
        self.assertEqual(workouts.list_sessions(self.conn, second_user["id"]), [])
        with self.assertRaises(LookupError):
            workouts.record_session(self.conn, second_user["id"], first_day["id"], 900)

    def test_completed_session_details_are_snapshotted_and_user_scoped(self):
        plan = workouts.create_plan(self.conn, self.user_id, "Plano original")
        day = plan["days"][0]
        exercise_ids = [row[0] for row in self.conn.execute("SELECT id FROM exercise ORDER BY id")]
        first = workouts.add_exercise(self.conn, self.user_id, day["id"], exercise_ids[0])
        second = workouts.add_exercise(self.conn, self.user_id, day["id"], exercise_ids[1])
        snapshot = [
            {"workout_exercise_id": first["id"], "display_name": "Agachamento realizado", "sets": [{"set_number": 1, "repetitions": 8, "load_value": 20, "load_unit": "kg", "rest_seconds": 60, "notes": "Controlado"}]},
            {"workout_exercise_id": second["id"], "display_name": "Corrida realizada", "sets": [{"set_number": 1, "repetitions": None, "load_value": None, "load_unit": "none", "rest_seconds": 0, "notes": ""}]},
        ]
        session = workouts.record_session(self.conn, self.user_id, day["id"], 900, snapshot)
        second_session = workouts.record_session(self.conn, self.user_id, day["id"], 240, [
            {"display_name": "Exercício adicional", "sets": [{"set_number": 1, "repetitions": 10, "load_value": 5, "load_unit": "kg", "rest_seconds": 30, "notes": ""}]}
        ])
        workouts.remove_exercise(self.conn, self.user_id, second["id"])
        workouts.remove_exercise(self.conn, self.user_id, first["id"])
        workouts.rename_plan(self.conn, self.user_id, plan["id"], "Plano alterado depois")

        detail = workouts.get_session(self.conn, session["id"], self.user_id)
        self.assertEqual(detail["exercise_count"], 2)
        self.assertTrue(detail["snapshot_available"])
        self.assertEqual([item["exercise_name_snapshot"] for item in detail["exercises"]], ["Agachamento realizado", "Corrida realizada"])
        self.assertEqual(detail["exercises"][0]["sets"][0]["repetitions"], 8)
        self.assertEqual(detail["exercises"][0]["sets"][0]["load_value"], 20)
        self.assertEqual(detail["exercises"][0]["workout_exercise_id_snapshot"], first["id"])
        self.assertEqual(len(workouts.list_sessions(self.conn, self.user_id)), 2)
        self.assertEqual(workouts.get_session(self.conn, second_session["id"], self.user_id)["exercises"][0]["exercise_name_snapshot"], "Exercício adicional")
        with self.assertRaises(LookupError):
            workouts.get_session(self.conn, session["id"], users.create_user(self.conn, "Outra")['id'])

    def test_reset_plan_user_and_application_preserves_dataset_library(self):
        other = users.create_user(self.conn, "Outra")
        plan = workouts.create_plan(self.conn, self.user_id, "Apagar plano")
        other_plan = workouts.create_plan(self.conn, other["id"], "Preservar até reset global")
        library_before = tuple(self.conn.execute(
            "SELECT (SELECT COUNT(*) FROM dataset),(SELECT COUNT(*) FROM source_archive),"
            "(SELECT COUNT(*) FROM original_path),(SELECT COUNT(*) FROM exercise),"
            "(SELECT COUNT(*) FROM media_asset),(SELECT COUNT(*) FROM exercise_media)"
        ).fetchone())
        users.reset_plan(self.conn, self.user_id, plan["id"])
        self.assertEqual([p["id"] for p in workouts.list_plans(self.conn, self.user_id)], [plan["id"]])
        self.assertTrue(all(not day["exercises"] and day["is_rest"] for day in workouts.get_plan(self.conn, plan["id"], self.user_id)["days"]))
        self.assertEqual([p["id"] for p in workouts.list_plans(self.conn, other["id"])], [other_plan["id"]])
        own_plan = workouts.create_plan(self.conn, self.user_id, "Reset usuário")
        users.reset_user(self.conn, self.user_id)
        self.assertEqual(users.get_user(self.conn, self.user_id)["name"], "Usuário padrão")
        self.assertEqual(workouts.list_plans(self.conn, self.user_id), [])
        self.assertEqual([p["id"] for p in workouts.list_plans(self.conn, other["id"])], [other_plan["id"]])
        default = users.reset_app(self.conn)
        self.assertEqual(default["name"], "Usuário padrão")
        self.assertEqual(workouts.list_plans(self.conn, default["id"]), [])
        library_after = tuple(self.conn.execute(
            "SELECT (SELECT COUNT(*) FROM dataset),(SELECT COUNT(*) FROM source_archive),"
            "(SELECT COUNT(*) FROM original_path),(SELECT COUNT(*) FROM exercise),"
            "(SELECT COUNT(*) FROM media_asset),(SELECT COUNT(*) FROM exercise_media)"
        ).fetchone())
        self.assertEqual(library_after, library_before)


class UserMigrationTests(unittest.TestCase):
    def test_existing_plans_are_assigned_to_default_user_without_data_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old.sqlite3"
            old = sqlite3.connect(path)
            old.executescript("""
              CREATE TABLE workout_plan(id INTEGER PRIMARY KEY,name TEXT NOT NULL,is_active INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
              CREATE TABLE workout_day(id INTEGER PRIMARY KEY,plan_id INTEGER NOT NULL REFERENCES workout_plan(id) ON DELETE CASCADE,weekday INTEGER NOT NULL,title TEXT NOT NULL DEFAULT '',is_rest INTEGER NOT NULL DEFAULT 1,UNIQUE(plan_id,weekday));
              INSERT INTO workout_plan(id,name) VALUES (41,'Plano antigo');
              INSERT INTO workout_day(id,plan_id,weekday,title,is_rest) VALUES (51,41,1,'Treino preservado',0);
            """)
            old.close()
            conn = connect(path)
            try:
                user_id = users.require_user(conn, None)
                plan = workouts.get_plan(conn, 41, user_id)
                self.assertEqual(plan["name"], "Plano antigo")
                self.assertEqual(plan["days"][0]["title"], "Treino preservado")
                self.assertEqual(conn.execute("SELECT user_id FROM workout_plan WHERE id=41").fetchone()[0], user_id)
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute("INSERT INTO workout_plan(user_id,name) VALUES (NULL,'Sem proprietário')")
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
