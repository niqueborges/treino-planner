from __future__ import annotations

import json
import sqlite3
import unicodedata
import zipfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .db import DEFAULT_DB, ROOT, connect
from .exercise_names import display_name_from_filename
from . import workouts
from . import users as app_users


def _normalize_search_term(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return " ".join("".join(char for char in normalized if not unicodedata.combining(char)).split())


_PORTUGUESE_SEARCH_ALIASES = {
    "supino": ("bench press",),
    "agachamento": ("squat",),
    "puxada": ("lat pulldown",),
    "remada": ("row",),
    "rosca biceps": ("biceps curl",),
    "biceps": ("biceps",),
    "triceps": ("triceps",),
    "extensora": ("leg extension",),
    "flexora": ("leg curl",),
    "panturrilha": ("calf raise",),
    "elevacao lateral": ("lateral raise",),
    "desenvolvimento": ("shoulder press",),
    "abdominal": ("abdominal", "crunch"),
    "prancha": ("plank",),
    "gluteo": ("glute",),
    "ponte de gluteos": ("glute bridge",),
}


def _library_search_terms(search: str) -> list[str]:
    """Keep the user query and add only explicitly reviewed exact-term aliases."""
    terms = [search]
    aliases = _PORTUGUESE_SEARCH_ALIASES.get(_normalize_search_term(search), ())
    for alias in aliases:
        if alias.casefold() not in {term.casefold() for term in terms}:
            terms.append(alias)
    return terms


class LibraryHandler(SimpleHTTPRequestHandler):
    server_version = "TreinoPlanner/0.1"

    def __init__(self, *args, db_path: str | Path = DEFAULT_DB, **kwargs):
        self.db_path = Path(db_path)
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        super().log_message(fmt, *args)

    def _json(self, value: object, status: int = 200) -> None:
        raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    @staticmethod
    def _one(query: dict[str, list[str]], key: str, default: str = "") -> str:
        return query.get(key, [default])[0].strip()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/library":
            self._library(query)
        elif parsed.path == "/api/facets":
            self._facets(query)
        elif parsed.path == "/api/summary":
            self._summary()
        elif parsed.path == "/api/users":
            conn = connect(self.db_path)
            try: self._json(app_users.list_users(conn))
            finally: conn.close()
        elif parsed.path == "/api/history":
            conn = connect(self.db_path)
            try: self._json(workouts.list_sessions(conn, self._active_user(conn)))
            except LookupError as exc: self._json({"error": str(exc)}, 404)
            except ValueError as exc: self._json({"error": str(exc)}, 400)
            finally: conn.close()
        elif parsed.path.startswith("/api/media/"):
            self._media(parsed.path.rsplit("/", 1)[-1])
        elif parsed.path == "/api/plans":
            conn = connect(self.db_path)
            try:
                user_id = self._active_user(conn)
                self._json(workouts.list_plans(conn, user_id))
            except (ValueError, LookupError) as exc: self._json({"error": str(exc)}, 400)
            finally: conn.close()
        elif parsed.path.startswith("/api/plans/"):
            try: plan_id = int(parsed.path.rsplit("/", 1)[-1])
            except ValueError: self._json({"error": "Plano inválido"}, 400); return
            conn = connect(self.db_path)
            try: self._json(workouts.get_plan(conn, plan_id, self._active_user(conn)))
            except LookupError as exc: self._json({"error": str(exc)}, 404)
            except ValueError as exc: self._json({"error": str(exc)}, 400)
            finally: conn.close()
        else:
            super().do_GET()

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        value = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(value, dict): raise workouts.WorkoutError("Envie um objeto JSON")
        return value

    def _active_user(self, conn: sqlite3.Connection) -> int:
        raw = self.headers.get("X-User-Id")
        try: user_id = int(raw) if raw else None
        except ValueError as exc: raise ValueError("Usuário ativo inválido") from exc
        return app_users.require_user(conn, user_id)

    def _dispatch_mutation(self) -> None:
        parsed = urlparse(self.path); path = parsed.path
        try:
            body = self._body() if self.command != "DELETE" else {}
            conn = connect(self.db_path)
            try:
                if path == "/api/reset/application" and self.command == "POST":
                    result = app_users.reset_app(conn); status = 200
                    self._json({"user": result}); return
                if path == "/api/users" and self.command == "POST":
                    result = app_users.create_user(conn, str(body.get("name", ""))); status = 201
                    self._json(result, status); return
                user_id = self._active_user(conn)
                if path == "/api/workout-sessions" and self.command == "POST":
                    result = workouts.record_session(conn,user_id,int(body["day_id"]),body["duration_seconds"])
                    self._json(result,201); return
                if path.startswith("/api/users/") and path.endswith("/reset") and self.command == "POST":
                    target_user = int(path.split("/")[3])
                    if target_user != user_id: raise LookupError("Só é possível resetar o usuário selecionado")
                    result = app_users.reset_user(conn, user_id); self._json(result); return
                elif path.startswith("/api/plans/") and path.endswith("/reset") and self.command == "POST":
                    plan_id = int(path.split("/")[3]); app_users.reset_plan(conn, user_id, plan_id); self._json({"ok": True}); return
                if path == "/api/plans" and self.command == "POST":
                    result = workouts.create_plan(conn, user_id, str(body.get("name", ""))); status = 201
                elif path.startswith("/api/plans/") and self.command == "PATCH":
                    result = workouts.rename_plan(conn, user_id, int(path.rsplit("/",1)[1]), str(body.get("name", ""))); status = 200
                elif path.startswith("/api/workout-days/") and path.endswith("/exercises") and self.command == "POST":
                    day_id = int(path.split("/")[3]); result = workouts.add_exercise(conn, user_id, day_id, int(body["exercise_id"])); status = 201
                elif path.startswith("/api/workout-days/") and path.endswith("/reorder") and self.command == "POST":
                    day_id = int(path.split("/")[3]); workouts.reorder_exercises(conn, user_id, day_id, [int(x) for x in body["exercise_ids"]]); result = {"ok": True}; status = 200
                elif path.startswith("/api/workout-days/") and self.command == "PATCH":
                    workouts.update_day(conn, user_id, int(path.rsplit("/",1)[1]), body.get("title"), body.get("is_rest")); result = {"ok": True}; status = 200
                elif path.startswith("/api/workout-exercises/") and path.endswith("/sets") and self.command == "POST":
                    result = workouts.add_set(conn, user_id, int(path.split("/")[3])); status = 201
                elif path.startswith("/api/workout-exercises/") and path.endswith("/duplicate") and self.command == "POST":
                    result = workouts.duplicate_exercise(conn, user_id, int(path.split("/")[3])); status = 201
                elif path.startswith("/api/workout-exercises/") and self.command == "DELETE":
                    workouts.remove_exercise(conn, user_id, int(path.rsplit("/",1)[1])); result = {"ok": True}; status = 200
                elif path.startswith("/api/workout-sets/") and self.command == "PATCH":
                    result = workouts.update_set(conn, user_id, int(path.rsplit("/",1)[1]), body); status = 200
                elif path.startswith("/api/workout-sets/") and self.command == "DELETE":
                    workouts.remove_set(conn, user_id, int(path.rsplit("/",1)[1])); result = {"ok": True}; status = 200
                else:
                    self._json({"error": "Rota não encontrada"}, 404); return
            finally: conn.close()
            self._json(result, status)
        except LookupError as exc: self._json({"error": str(exc)}, 404)
        except (workouts.WorkoutError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc: self._json({"error": str(exc)}, 400)

    def do_POST(self) -> None: self._dispatch_mutation()
    def do_PATCH(self) -> None: self._dispatch_mutation()
    def do_DELETE(self) -> None: self._dispatch_mutation()

    def _library(self, query: dict[str, list[str]]) -> None:
        search = self._one(query, "search")[:200]
        gender = self._one(query, "gender")
        area = self._one(query, "area")
        category = self._one(query, "category")
        try:
            page = max(1, int(self._one(query, "page", "1")))
            page_size = min(60, max(1, int(self._one(query, "page_size", "24"))))
        except ValueError:
            self._json({"error": "page and page_size must be integers"}, 400)
            return

        where = ["op.entry_type='file'", "op.extension_raw='.gif'", "ex.identification_status='pending'"]
        params: list[object] = []
        for column, value in (("op.gender_folder_raw", gender), ("op.area_folder_raw", area)):
            if value:
                where.append(f"{column}=?")
                params.append(value)
        if category == "__direct__":
            where.append("op.category_path_raw=''")
        elif category:
            where.append("op.category_path_raw=?")
            params.append(category)
        if search:
            search_clauses = []
            for term in _library_search_terms(search):
                search_clauses.append("(lower(op.basename_raw) LIKE lower(?) OR lower(op.path_raw) LIKE lower(?))")
                # Filenames commonly separate English words with hyphens/underscores.
                needle = "%" + "%".join(term.split()) + "%"
                params.extend((needle, needle))
            where.append("(" + " OR ".join(search_clauses) + ")")
        where_sql = " AND ".join(where)
        base = """
          FROM exercise_media em
          JOIN exercise ex ON ex.id=em.exercise_id
          JOIN media_asset ma ON ma.id=em.media_asset_id
          JOIN original_path op ON op.id=em.original_path_id
          JOIN source_archive sa ON sa.id=op.source_archive_id
        """
        conn = connect(self.db_path)
        try:
            total = int(conn.execute(f"SELECT COUNT(*) {base} WHERE {where_sql}", params).fetchone()[0])
            rows = conn.execute(
                f"""SELECT em.id AS occurrence_id, ex.id AS exercise_id,
                           ex.provisional_name_raw AS display_name,
                           ex.identification_status, ma.id AS media_id, ma.sha256,
                           ma.size_bytes, op.path_raw AS original_path,
                           op.gender_folder_raw AS gender_origin,
                           op.area_folder_raw AS area_origin,
                           op.category_path_raw AS category_origin,
                           sa.archive_name AS source_archive
                    {base} WHERE {where_sql}
                    ORDER BY op.basename_raw COLLATE NOCASE, op.path_raw
                    LIMIT ? OFFSET ?""",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        finally:
            conn.close()
        items = [dict(row) for row in rows]
        for item in items:
            item["display_name"] = display_name_from_filename(item["display_name"])
        self._json({"items": items, "page": page,
                    "page_size": page_size, "total": total,
                    "pages": (total + page_size - 1) // page_size})

    def _facets(self, query: dict[str, list[str]]) -> None:
        gender = self._one(query, "gender")
        area = self._one(query, "area")
        conn = connect(self.db_path)
        try:
            where = "op.entry_type='file' AND op.extension_raw='.gif'"
            params: list[object] = []
            if gender:
                where += " AND op.gender_folder_raw=?"
                params.append(gender)
            if area:
                where += " AND op.area_folder_raw=?"
                params.append(area)
            genders = [r[0] for r in conn.execute(
                "SELECT DISTINCT gender_folder_raw FROM original_path WHERE entry_type='file' AND extension_raw='.gif' "
                "AND gender_folder_raw IS NOT NULL ORDER BY gender_folder_raw")]
            areas = [r[0] for r in conn.execute(
                f"SELECT DISTINCT area_folder_raw FROM original_path op WHERE {where} "
                "AND area_folder_raw IS NOT NULL ORDER BY area_folder_raw", params)]
            categories = [r[0] for r in conn.execute(
                f"SELECT DISTINCT category_path_raw FROM original_path op WHERE {where} "
                "ORDER BY category_path_raw", params)]
        finally:
            conn.close()
        self._json({"genders": genders, "areas": areas, "categories": categories})

    def _summary(self) -> None:
        conn = connect(self.db_path)
        try:
            counts = {
                "archives": conn.execute("SELECT COUNT(*) FROM source_archive").fetchone()[0],
                "gif_occurrences": conn.execute("SELECT COUNT(*) FROM original_path WHERE entry_type='file' AND extension_raw='.gif'").fetchone()[0],
                "unique_media": conn.execute("SELECT COUNT(*) FROM media_asset").fetchone()[0],
                "pending_exercises": conn.execute("SELECT COUNT(*) FROM exercise WHERE identification_status='pending'").fetchone()[0],
            }
        finally:
            conn.close()
        self._json(counts)

    def _media(self, media_id_raw: str) -> None:
        try:
            media_id = int(media_id_raw)
        except ValueError:
            self.send_error(404)
            return
        conn = connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT ma.size_bytes, ma.mime_type, op.path_raw, op.entry_index, sa.archive_path "
                "FROM media_asset ma JOIN original_path op ON op.id=ma.representative_original_path_id "
                "JOIN source_archive sa ON sa.id=op.source_archive_id WHERE ma.id=?", (media_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            self.send_error(404)
            return
        try:
            with zipfile.ZipFile(row["archive_path"]) as archive:
                entry = archive.infolist()[row["entry_index"]]
                if entry.filename != row["path_raw"]:
                    raise KeyError("The original ZIP entry no longer matches its imported index")
                stream = archive.open(entry, "r")
                self.send_response(200)
                self.send_header("Content-Type", row["mime_type"])
                self.send_header("Content-Length", str(row["size_bytes"]))
                self.send_header("Cache-Control", "public, max-age=86400, immutable")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                while chunk := stream.read(1024 * 1024):
                    self.wfile.write(chunk)
                stream.close()
        except (OSError, KeyError, zipfile.BadZipFile) as exc:
            if not self.wfile.closed:
                try:
                    self.send_error(404, f"Media source unavailable: {exc}")
                except (BrokenPipeError, ConnectionResetError):
                    pass


def _local_ips() -> list[str]:
    """Return non-loopback IPv4 addresses available on this machine."""
    import socket
    ips: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addr = info[4][0]
            if not addr.startswith("127."):
                ips.append(addr)
    except OSError:
        pass
    # Fallback: connect to a public IP to discover the default route address.
    if not ips:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ips.append(s.getsockname()[0])
        except OSError:
            pass
    return sorted(set(ips))


def serve(host: str = "0.0.0.0", port: int = 8000, db_path: str | Path = DEFAULT_DB) -> None:
    handler = lambda *args, **kwargs: LibraryHandler(*args, db_path=db_path, **kwargs)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Treino Planner: http://{host}:{port}/ (Ctrl+C para encerrar)", flush=True)
    if host == "0.0.0.0":
        for ip in _local_ips():
            print(f"  Rede local: http://{ip}:{port}/", flush=True)
        if not _local_ips():
            print("  Nenhum IP de rede local detectado.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

