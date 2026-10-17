from __future__ import annotations

import sqlite3

from .exercise_names import display_name_from_filename

class WorkoutError(ValueError):
    pass


def _plan(conn: sqlite3.Connection, plan_id: int, user_id: int) -> dict:
    plan = conn.execute("SELECT * FROM workout_plan WHERE id=? AND user_id=?", (plan_id, user_id)).fetchone()
    if plan is None:
        raise LookupError("Plano não encontrado")
    result = dict(plan)
    result["days"] = []
    days = conn.execute("SELECT * FROM workout_day WHERE plan_id=? ORDER BY weekday", (plan_id,)).fetchall()
    for day in days:
        day_data = dict(day)
        day_data["exercises"] = []
        exercises = conn.execute(
            """SELECT we.id, we.day_id, we.exercise_id, we.position, we.execution_type,
                      ex.provisional_name_raw AS display_name, ex.identification_status,
                      em.id AS occurrence_id, ma.id AS media_id, op.path_raw AS original_path,
                      op.gender_folder_raw AS gender_origin, op.area_folder_raw AS area_origin,
                      op.category_path_raw AS category_origin, sa.archive_name AS source_archive
               FROM workout_exercise we JOIN exercise ex ON ex.id=we.exercise_id
               LEFT JOIN exercise_media em ON em.exercise_id=ex.id
               LEFT JOIN media_asset ma ON ma.id=em.media_asset_id
               LEFT JOIN original_path op ON op.id=em.original_path_id
               LEFT JOIN source_archive sa ON sa.id=op.source_archive_id
               WHERE we.day_id=? ORDER BY we.position, we.id""", (day["id"],)
        ).fetchall()
        for exercise in exercises:
            exercise_data = dict(exercise)
            exercise_data["display_name"] = display_name_from_filename(exercise_data["display_name"])
            exercise_data["sets"] = [dict(row) for row in conn.execute(
                "SELECT * FROM workout_set WHERE workout_exercise_id=? ORDER BY set_number",
                (exercise["id"],),
            )]
            day_data["exercises"].append(exercise_data)
        result["days"].append(day_data)
    return result


def list_plans(conn: sqlite3.Connection, user_id: int) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM workout_plan WHERE user_id=? ORDER BY is_active DESC, updated_at DESC, id DESC", (user_id,))]


def get_plan(conn: sqlite3.Connection, plan_id: int, user_id: int) -> dict:
    return _plan(conn, plan_id, user_id)


def create_plan(conn: sqlite3.Connection, user_id: int, name: str) -> dict:
    name = name.strip()
    if not name:
        raise WorkoutError("Informe um nome para o plano")
    with conn:
        cursor = conn.execute("INSERT INTO workout_plan(user_id,name) VALUES (?,?)", (user_id, name))
        plan_id = cursor.lastrowid
        conn.executemany("INSERT INTO workout_day(plan_id,weekday) VALUES (?,?)",
                         [(plan_id, i) for i in range(1, 8)])
    return _plan(conn, plan_id, user_id)


def rename_plan(conn: sqlite3.Connection, user_id: int, plan_id: int, name: str) -> dict:
    name = name.strip()
    if not name:
        raise WorkoutError("Informe um nome para o plano")
    with conn:
        if not conn.execute("UPDATE workout_plan SET name=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?", (name, plan_id, user_id)).rowcount:
            raise LookupError("Plano não encontrado")
    return _plan(conn, plan_id, user_id)


def _owned_day(conn: sqlite3.Connection, day_id: int, user_id: int) -> None:
    if conn.execute("SELECT 1 FROM workout_day d JOIN workout_plan p ON p.id=d.plan_id WHERE d.id=? AND p.user_id=?", (day_id, user_id)).fetchone() is None:
        raise LookupError("Dia não encontrado para o usuário selecionado")


def _owned_exercise(conn: sqlite3.Connection, workout_exercise_id: int, user_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT we.*,d.plan_id,p.user_id FROM workout_exercise we JOIN workout_day d ON d.id=we.day_id JOIN workout_plan p ON p.id=d.plan_id WHERE we.id=? AND p.user_id=?", (workout_exercise_id, user_id)).fetchone()
    if row is None:
        raise LookupError("Exercício do treino não encontrado para o usuário selecionado")
    return row


def _owned_set(conn: sqlite3.Connection, set_id: int, user_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT ws.*,we.day_id,p.user_id FROM workout_set ws JOIN workout_exercise we ON we.id=ws.workout_exercise_id JOIN workout_day d ON d.id=we.day_id JOIN workout_plan p ON p.id=d.plan_id WHERE ws.id=? AND p.user_id=?", (set_id, user_id)).fetchone()
    if row is None:
        raise LookupError("Série não encontrada para o usuário selecionado")
    return row


def update_day(conn: sqlite3.Connection, user_id: int, day_id: int, title: str | None = None, is_rest: bool | None = None) -> None:
    _owned_day(conn, day_id, user_id)
    fields, values = [], []
    if title is not None:
        fields.append("title=?"); values.append(title.strip())
    if is_rest is not None:
        fields.append("is_rest=?"); values.append(int(is_rest))
    if not fields:
        return
    values.append(day_id)
    with conn:
        if not conn.execute(f"UPDATE workout_day SET {','.join(fields)} WHERE id=?", values).rowcount:
            raise LookupError("Dia não encontrado")


def add_exercise(conn: sqlite3.Connection, user_id: int, day_id: int, exercise_id: int) -> dict:
    with conn:
        _owned_day(conn, day_id, user_id)
        if conn.execute("SELECT 1 FROM exercise WHERE id=?", (exercise_id,)).fetchone() is None:
            raise LookupError("Exercício da biblioteca não encontrado")
        position = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM workout_exercise WHERE day_id=?", (day_id,)).fetchone()[0]
        cursor = conn.execute("INSERT INTO workout_exercise(day_id,exercise_id,position) VALUES (?,?,?)", (day_id, exercise_id, position))
        workout_exercise_id = cursor.lastrowid
        conn.executemany("INSERT INTO workout_set(workout_exercise_id,set_number,repetitions,load_unit,rest_seconds) VALUES (?,?,12,'kg',90)",
                         [(workout_exercise_id, i) for i in range(1, 4)])
        conn.execute("UPDATE workout_day SET is_rest=0 WHERE id=?", (day_id,))
    return dict(conn.execute("SELECT * FROM workout_exercise WHERE id=?", (workout_exercise_id,)).fetchone())


def add_set(conn: sqlite3.Connection, user_id: int, workout_exercise_id: int) -> dict:
    with conn:
        _owned_exercise(conn, workout_exercise_id, user_id)
        number = conn.execute("SELECT COALESCE(MAX(set_number),0)+1 FROM workout_set WHERE workout_exercise_id=?", (workout_exercise_id,)).fetchone()[0]
        cursor = conn.execute("INSERT INTO workout_set(workout_exercise_id,set_number,repetitions,load_unit,rest_seconds) VALUES (?,?,12,'kg',90)", (workout_exercise_id, number))
    return dict(conn.execute("SELECT * FROM workout_set WHERE id=?", (cursor.lastrowid,)).fetchone())


def update_set(conn: sqlite3.Connection, user_id: int, set_id: int, payload: dict) -> dict:
    allowed = {"repetitions", "load_value", "load_unit", "rest_seconds", "notes"}
    values = {key: payload[key] for key in allowed if key in payload}
    if not values:
        raise WorkoutError("Nenhum campo de série para atualizar")
    if values.get("load_unit", "kg") not in ("kg", "lb", "none"):
        raise WorkoutError("Unidade de carga inválida")
    for key in ("repetitions", "rest_seconds"):
        if key in values and values[key] is not None:
            try: values[key] = int(values[key])
            except (TypeError, ValueError): raise WorkoutError(f"{key} deve ser inteiro")
    if values.get("repetitions", 1) is not None and values.get("repetitions", 1) < 1:
        raise WorkoutError("Repetições deve ser maior que zero")
    if values.get("rest_seconds", 0) is not None and values.get("rest_seconds", 0) < 0:
        raise WorkoutError("Descanso não pode ser negativo")
    if "load_value" in values and values["load_value"] is not None:
        try: values["load_value"] = float(values["load_value"])
        except (TypeError, ValueError): raise WorkoutError("Carga inválida")
        if values["load_value"] < 0: raise WorkoutError("Carga não pode ser negativa")
    if "notes" in values: values["notes"] = str(values["notes"])
    _owned_set(conn, set_id, user_id)
    with conn:
        cur = conn.execute(f"UPDATE workout_set SET {','.join(f'{k}=?' for k in values)} WHERE id=?", (*values.values(), set_id))
        if not cur.rowcount: raise LookupError("Série não encontrada")
    return dict(conn.execute("SELECT * FROM workout_set WHERE id=?", (set_id,)).fetchone())


def remove_set(conn: sqlite3.Connection, user_id: int, set_id: int) -> None:
    row = _owned_set(conn, set_id, user_id)
    workout_exercise_id = row["workout_exercise_id"]
    with conn:
        count = conn.execute("SELECT COUNT(*) FROM workout_set WHERE workout_exercise_id=?", (workout_exercise_id,)).fetchone()[0]
        if count <= 1: raise WorkoutError("Cada exercício precisa ter ao menos uma série")
        conn.execute("DELETE FROM workout_set WHERE id=?", (set_id,))
        rows = conn.execute("SELECT id FROM workout_set WHERE workout_exercise_id=? ORDER BY set_number,id", (workout_exercise_id,)).fetchall()
        # Shift to a high temporary range to preserve the positive-number check and uniqueness.
        conn.executemany("UPDATE workout_set SET set_number=? WHERE id=?", [(1000000 + i, item["id"]) for i, item in enumerate(rows, 1)])
        conn.executemany("UPDATE workout_set SET set_number=? WHERE id=?", [(i, item["id"]) for i, item in enumerate(rows, 1)])


def _resequence(conn: sqlite3.Connection, day_id: int) -> None:
    ids = [r[0] for r in conn.execute("SELECT id FROM workout_exercise WHERE day_id=? ORDER BY position,id", (day_id,))]
    conn.executemany("UPDATE workout_exercise SET position=? WHERE id=?", [(i, identity) for i, identity in enumerate(ids, 1)])
    conn.execute("UPDATE workout_day SET is_rest=? WHERE id=?", (int(not ids), day_id))


def reorder_exercises(conn: sqlite3.Connection, user_id: int, day_id: int, exercise_ids: list[int]) -> None:
    _owned_day(conn, day_id, user_id)
    actual = [r[0] for r in conn.execute("SELECT id FROM workout_exercise WHERE day_id=?", (day_id,))]
    if len(actual) != len(exercise_ids) or set(actual) != set(exercise_ids):
        raise WorkoutError("A ordem deve conter cada exercício do dia exatamente uma vez")
    with conn:
        conn.executemany("UPDATE workout_exercise SET position=? WHERE id=?", [(i, identity) for i, identity in enumerate(exercise_ids, 1)])


def remove_exercise(conn: sqlite3.Connection, user_id: int, workout_exercise_id: int) -> None:
    row = _owned_exercise(conn, workout_exercise_id, user_id)
    with conn:
        conn.execute("DELETE FROM workout_exercise WHERE id=?", (workout_exercise_id,))
        _resequence(conn, row["day_id"])


def duplicate_exercise(conn: sqlite3.Connection, user_id: int, workout_exercise_id: int) -> dict:
    row = _owned_exercise(conn, workout_exercise_id, user_id)
    with conn:
        position = conn.execute("SELECT COALESCE(MAX(position),0)+1 FROM workout_exercise WHERE day_id=?", (row["day_id"],)).fetchone()[0]
        cursor = conn.execute("INSERT INTO workout_exercise(day_id,exercise_id,position,execution_type) VALUES (?,?,?,?)",
                              (row["day_id"], row["exercise_id"], position, row["execution_type"]))
        conn.execute("INSERT INTO workout_set(workout_exercise_id,set_number,repetitions,load_value,load_unit,rest_seconds,notes) SELECT ?,set_number,repetitions,load_value,load_unit,rest_seconds,notes FROM workout_set WHERE workout_exercise_id=?", (cursor.lastrowid, workout_exercise_id))
        conn.execute("UPDATE workout_day SET is_rest=0 WHERE id=?", (row["day_id"],))
    return dict(conn.execute("SELECT * FROM workout_exercise WHERE id=?", (cursor.lastrowid,)).fetchone())


def list_sessions(conn: sqlite3.Connection, user_id: int, limit: int = 100) -> list[dict]:
    return [dict(row) for row in conn.execute(
        "SELECT id,user_id,plan_id,workout_day_id,plan_name_snapshot,day_title_snapshot,exercise_count,duration_seconds,completed_at "
        "FROM workout_session WHERE user_id=? ORDER BY completed_at DESC,id DESC LIMIT ?", (user_id, limit)
    )]


def record_session(conn: sqlite3.Connection, user_id: int, day_id: int, duration_seconds: int) -> dict:
    _owned_day(conn, day_id, user_id)
    try: duration_seconds = int(duration_seconds)
    except (TypeError, ValueError) as exc: raise WorkoutError("Duração inválida") from exc
    if duration_seconds < 0:
        raise WorkoutError("Duração não pode ser negativa")
    row = conn.execute(
        """SELECT p.id AS plan_id,p.name AS plan_name,d.title AS day_title,
                  COUNT(we.id) AS exercise_count
           FROM workout_day d JOIN workout_plan p ON p.id=d.plan_id
           LEFT JOIN workout_exercise we ON we.day_id=d.id
           WHERE d.id=? AND p.user_id=? GROUP BY d.id""", (day_id, user_id)
    ).fetchone()
    if row is None: raise LookupError("Dia não encontrado para o usuário selecionado")
    if row["exercise_count"] == 0: raise WorkoutError("Não é possível registrar um dia sem exercícios")
    with conn:
        cursor = conn.execute(
            """INSERT INTO workout_session(user_id,plan_id,workout_day_id,plan_name_snapshot,
                       day_title_snapshot,exercise_count,duration_seconds)
               VALUES (?,?,?,?,?,?,?)""",
            (user_id,row["plan_id"],day_id,row["plan_name"],row["day_title"],row["exercise_count"],duration_seconds),
        )
    return dict(conn.execute("SELECT * FROM workout_session WHERE id=?", (cursor.lastrowid,)).fetchone())
