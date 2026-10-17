from __future__ import annotations

import argparse
from pathlib import Path

from .db import DEFAULT_DB, connect
from .importer import import_dataset
from .web import serve


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    importer = commands.add_parser("import-dataset", help="Index ZIP files without extracting them")
    importer.add_argument("archives", nargs="+", help="ZIP files or directories containing ZIP files")
    importer.add_argument("--db", type=Path, default=DEFAULT_DB, help=f"SQLite database (default: {DEFAULT_DB})")

    server = commands.add_parser("serve", help="Run the local app and media library API")
    server.add_argument("--db", type=Path, default=DEFAULT_DB)
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if args.command == "import-dataset":
        def report(result):
            state = "unchanged; skipped" if result["skipped"] else (
                f"{result['gif_occurrences']} GIF occurrences, {result['new_media']} new SHA-256 media records, "
                f"{result['new_paths']} original paths"
            )
            print(f"{result['archive']}: {state}")
        import_dataset(args.archives, args.db, progress=report)
        conn = connect(args.db)
        try:
            totals = conn.execute("SELECT (SELECT COUNT(*) FROM source_archive), "
                                  "(SELECT COUNT(*) FROM exercise_media), "
                                  "(SELECT COUNT(*) FROM media_asset)").fetchone()
        finally:
            conn.close()
        print(f"Library totals: {totals[1]} GIF occurrences / {totals[2]} unique media / {totals[0]} archive snapshots")
        print(f"Database: {args.db}")
        return 0
    if args.command == "serve":
        serve(args.host, args.port, args.db)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
