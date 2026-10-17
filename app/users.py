from __future__ import annotations

import sqlite3

from . import workouts


def list_users(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT id,name,created_at,updated_at FROM app_user ORDER BY id")]


def create_user(conn: sqlite3.Connection, name: str) -> dict:
    name = name.strip()
    if not name:
        raise workouts.WorkoutError("Informe um nome para o usuário")
    with conn:
        cursor = conn.execute("INSERT INTO app_user(name) VALUES (?)", (name,))
    return dict(conn.execute("SELECT id,name,created_at,updated_at FROM app_user WHERE id=?", (cursor.lastrowid,)).fetchone())


def get_user(conn: sqlite3.Connection, user_id: int) -> dict:
    row = conn.execute("SELECT id,name,created_at,updated_at FROM app_user WHERE id=?", (user_id,)).fetchone()
    if row is None:
        raise LookupError("Usuário não encontrado")
    return dict(row)


def require_user(conn: sqlite3.Connection, user_id: int | None) -> int:
    if user_id is None:
        row = conn.execute("SELECT id FROM app_user ORDER BY id LIMIT 1").fetchone()
        if row is None:
            raise LookupError("Nenhum usuário cadastrado")
        return row["id"]
    get_user(conn, user_id)
    return user_id


def reset_user_data(conn: sqlite3.Connection, user_id: int) -> dict:
    user = get_user(conn, user_id)
    with conn:
        conn.execute("DELETE FROM workout_plan WHERE user_id=?", (user_id,))
    return user


def reset_application_data(conn: sqlite3.Connection) -> dict:
    """Delete app-owned accounts and plans only; all imported library tables remain intact."""
    with conn:
        conn.execute("DELETE FROM workout_plan")
        conn.execute("DELETE FROM app_user")
        cursor = conn.execute("INSERT INTO app_user(name) VALUES ('Usuário padrão')")
    return get_user(conn, cursor.lastrowid)


def reset_plan(conn: sqlite3.Connection, user_id: int, plan_id: int) -> None:
    plan = conn.execute("SELECT 1 FROM workout_plan WHERE id=? AND user_id=?", (plan_id, user_id)).fetchone()
    if plan is None:
        raise LookupError("Plano não encontrado para o usuário selecionado")
    with conn:
        conn.execute("DELETE FROM workout_exercise WHERE day_id IN (SELECT id FROM workout_day WHERE plan_id=?)", (plan_id,))
        conn.execute("UPDATE workout_day SET title='',is_rest=1 WHERE plan_id=?", (plan_id,))


def reset_user(conn: sqlite3.Connection, user_id: int) -> dict:
    return reset_user_data(conn, user_id)


def reset_app(conn: sqlite3.Connection) -> dict:
    return reset_application_data(conn)
