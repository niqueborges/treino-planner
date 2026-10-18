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
            names = ("Bench-Press.gif", "Incline-Bench-Press.gif", "Squat.gif", "Cable-Row.gif", "Plank.gif")
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
        self.assertEqual(result["total"], 1)
        self.assertIn("Squat", result["items"][0]["display_name"])

    def test_term_without_alias_keeps_existing_filename_search(self) -> None:
        result = self.search("Cable")
        self.assertEqual(result["total"], 1)
        self.assertIn("Cable", result["items"][0]["display_name"])

    def test_empty_search_returns_all_and_counts_match_items(self) -> None:
        result = self.search(page_size=2)
        self.assertEqual(result["total"], 5)
        self.assertEqual(result["pages"], 3)
        self.assertEqual(len(result["items"]), 2)


if __name__ == "__main__":
    unittest.main()
