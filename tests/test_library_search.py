from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.parse
import urllib.request
import zipfile
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.importer import import_dataset
from app.web import LibraryHandler


class LibrarySearchAliasTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "library.sqlite3"
        archive_path = self.root / "fixtures.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            names = ("Bench-Press.gif", "Incline-Bench-Press.gif", "Squat.gif", "Cable-Row.gif", "Plank.gif",
                     "Dumbbell-Alternate-Shoulder-Press-(female)-Shoulders.gif",
                     "Dumbbell-Front-Squat-(female)-Thighs.gif",
                     "4-Punches-Side-Squat-(female)-Plyometrics.gif",
                     "Bodyweight-Half-Squat-(male)-Thighs.gif",
                     "Band-Low-Chest-Press-(female)-Chest.gif")
            for index, name in enumerate(names, 1):
                archive.writestr(f"Dataset/FEMININO/ACADEMIA/{name}", f"GIF fixture {index}".encode())
        import_dataset([archive_path], self.db_path)

        handler = partial(LibraryHandler, db_path=self.db_path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def search(self, term: str = "", **params: int) -> dict:
        query = {"search": term, **params}
        url = f"{self.base_url}/api/library?{urllib.parse.urlencode(query)}"
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.load(response)

    def test_supino_finds_bench_press_and_keeps_alias_results_paginated(self) -> None:
        first = self.search("supino", page_size=1)
        self.assertEqual(first["total"], 2)
        self.assertEqual(first["pages"], 2)
        self.assertEqual(len(first["items"]), 1)
        second = self.search("supino", page=2, page_size=1)
        self.assertEqual(second["total"], 2)
        self.assertEqual(len(second["items"]), 1)

    def test_agachamento_finds_squat(self) -> None:
        result = self.search("agachamento")
        self.assertEqual(result["total"], 4)
        names = {item["display_name"] for item in result["items"]}
        self.assertIn("Squat", names)
        self.assertIn("Agachamento frontal com halteres", names)
        self.assertIn("Agachamento lateral com 4 socos", names)
        self.assertIn("Meio agachamento com peso corporal", names)

    def test_term_without_alias_keeps_existing_filename_search(self) -> None:
        result = self.search("Cable")
        self.assertEqual(result["total"], 1)
        self.assertIn("Cable", result["items"][0]["display_name"])

    def test_translated_exercise_is_found_by_original_and_portuguese_name(self) -> None:
        english = self.search("Dumbbell Alternate Shoulder Press")
        portuguese = self.search("Desenvolvimento alternado com halteres")
        self.assertEqual(english["total"], 1)
        self.assertEqual(portuguese["total"], 1)
        self.assertEqual(english["items"][0]["exercise_id"], portuguese["items"][0]["exercise_id"])
        self.assertEqual(english["items"][0]["display_name"], "Desenvolvimento alternado com halteres")
        self.assertIn("Dumbbell Alternate Shoulder Press", english["items"][0]["original_name"])
        self.assertEqual(english["items"][0]["original_name"], portuguese["items"][0]["original_name"])

    def test_recent_translations_are_searchable_in_both_languages(self) -> None:
        translations = {
            "Dumbbell Front Squat (female) Thighs": "Agachamento frontal com halteres",
            "4 Punches Side Squat (female) Plyometrics": "Agachamento lateral com 4 socos",
            "Bodyweight Half Squat (male) Thighs": "Meio agachamento com peso corporal",
            "Band Low Chest Press (female) Chest": "Supino baixo com faixa elástica",
        }
        for original_name, translated_name in translations.items():
            with self.subTest(original_name=original_name):
                english = self.search(original_name)
                portuguese = self.search(translated_name)
                self.assertEqual(english["total"], 1)
                self.assertEqual(portuguese["total"], 1)
                self.assertEqual(english["items"][0]["exercise_id"], portuguese["items"][0]["exercise_id"])
                self.assertEqual(english["items"][0]["display_name"], translated_name)
                self.assertEqual(english["items"][0]["original_name"], portuguese["items"][0]["original_name"])

    def test_empty_search_returns_all_and_counts_match_items(self) -> None:
        result = self.search(page_size=2)
        self.assertEqual(result["total"], 10)
        self.assertEqual(result["pages"], 5)
        self.assertEqual(len(result["items"]), 2)


class LibraryFacetsAndCategoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db_path = self.root / "library.sqlite3"
        archive_path = self.root / "categorized.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
            entries = (
                ("Dataset/MASCULINO/ACADEMIA/EXERCÍCIOS COM BARRAS/COSTAS/Barbell-Row.gif", b"gif1"),
                ("Dataset/MASCULINO/ACADEMIA/EXERCÍCIOS COM HALTERES/COSTAS/Dumbbell-Row.gif", b"gif2"),
                ("Dataset/MASCULINO/ACADEMIA/EXERCÍCIOS COM BARRAS/PEITO/Bench-Press.gif", b"gif3"),
                ("Dataset/MASCULINO/ACADEMIA/EXERCÍCIOS COM BARRAS/PERNA/Barbell-Squat.gif", b"gif4"),
                ("Dataset/MASCULINO/ACADEMIA/CARDIO/Treadmill-Run.gif", b"gif5"),
                ("Dataset/FEMININO/FUNCIONAL/ABDOMINAIS/Crunch.gif", b"gif6"),
                ("Dataset/FEMININO/FUNCIONAL/PESO CORPORAL/COSTAS/Inverted-Row.gif", b"gif7"),
                ("Dataset/FEMININO/FUNCIONAL/TRX/TRX-Chest-Press.gif", b"gif8"),
            )
            for path, data in entries:
                archive.writestr(path, data)
        import_dataset([archive_path], self.db_path)

        handler = partial(LibraryHandler, db_path=self.db_path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def get_json(self, path: str, **params: object) -> dict:
        query_str = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{self.base_url}{path}" + (f"?{query_str}" if query_str else "")
        with urllib.request.urlopen(url, timeout=3) as response:
            return json.load(response)

    def test_facets_returns_modalities_and_available_groups(self) -> None:
        data = self.get_json("/api/facets")
        self.assertIn("ACADEMIA", data["areas"])
        self.assertIn("FUNCIONAL", data["areas"])
        self.assertIn("groups", data)
        group_ids = [g["id"] for g in data["groups"]]
        self.assertIn("costas", group_ids)
        self.assertIn("peito", group_ids)
        self.assertIn("perna", group_ids)
        self.assertIn("cardio", group_ids)
        self.assertIn("trx", group_ids)

    def test_facets_by_area_filters_groups(self) -> None:
        acad = self.get_json("/api/facets", area="ACADEMIA")
        acad_group_ids = [g["id"] for g in acad["groups"]]
        self.assertIn("costas", acad_group_ids)
        self.assertIn("perna", acad_group_ids)
        self.assertNotIn("trx", acad_group_ids)

        func = self.get_json("/api/facets", area="FUNCIONAL")
        func_group_ids = [g["id"] for g in func["groups"]]
        self.assertIn("trx", func_group_ids)
        self.assertIn("costas", func_group_ids)
        self.assertNotIn("biceps", func_group_ids)

    def test_filter_by_group_finds_all_matching_exercises(self) -> None:
        all_costas = self.get_json("/api/library", category="costas")
        self.assertEqual(all_costas["total"], 3)
        names = {item["original_name"] for item in all_costas["items"]}
        self.assertIn("Barbell Row", names)
        self.assertIn("Dumbbell Row", names)
        self.assertIn("Inverted Row", names)

    def test_filter_by_group_and_area_narrows_scope(self) -> None:
        acad_costas = self.get_json("/api/library", area="ACADEMIA", category="costas")
        self.assertEqual(acad_costas["total"], 2)

        func_costas = self.get_json("/api/library", area="FUNCIONAL", category="costas")
        self.assertEqual(func_costas["total"], 1)
        self.assertEqual(func_costas["items"][0]["original_name"], "Inverted Row")

    def test_filter_combining_modality_group_and_text_search(self) -> None:
        result = self.get_json("/api/library", area="ACADEMIA", category="costas", search="Dumbbell")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["original_name"], "Dumbbell Row")

    def test_raw_functional_tool_category(self) -> None:
        trx = self.get_json("/api/library", category="trx")
        self.assertEqual(trx["total"], 1)
        self.assertEqual(trx["items"][0]["original_name"], "TRX Chest Press")

    def test_nonexistent_category_returns_zero_results(self) -> None:
        result = self.get_json("/api/library", category="inexistente")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["items"], [])


if __name__ == "__main__":
    unittest.main()
