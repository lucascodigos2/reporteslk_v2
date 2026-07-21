"""Generación del seguimiento a partir del mapa validado en base de datos.

A diferencia del script original, los plazos NO se recalculan del calendario en
cada ejecución: se leen de la tabla `examenes`, tal como quedaron validados.
"""

from __future__ import annotations

import io
from collections import Counter
from datetime import date, datetime
from typing import Any

import pandas as pd

from . import seguimiento as se


def _a_fecha(valor: Any) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date):
        return valor
    return date.fromisoformat(str(valor)[:10])


def examdefs_desde_db(examenes: list[dict[str, Any]]) -> list[tuple[str, se.ExamDef]]:
    """Convierte las filas validadas de `examenes` en pares (actividad, ExamDef)."""
    matched: list[tuple[str, se.ExamDef]] = []
    for e in sorted(examenes, key=lambda x: (x.get("orden") is None, x.get("orden") or 0)):
        actividad = e.get("actividad_progreso")
        if not actividad:
            continue  # examen del calendario sin actividad asociada: no se sigue
        pub = _a_fecha(e.get("pub_date"))
        dl = _a_fecha(e.get("deadline"))
        matched.append(
            (
                actividad,
                se.ExamDef(
                    key=e.get("clave") or "",
                    name=actividad,
                    pub_date=pub,
                    deadline=dl,
                    cod_mf=e.get("cod_mf"),
                    is_final=bool(e.get("es_final")),
                    is_equality=bool(e.get("es_igualdad")),
                    has_calendar=bool(pub and dl),
                    counts_for_grade=bool(e.get("cuenta_para_nota", True)),
                ),
            )
        )
    return matched


def generar(
    curso: dict[str, Any],
    examenes: list[dict[str, Any]],
    actividades: list[str],
    alumnos: pd.DataFrame,
    as_of: date,
) -> dict[str, Any]:
    """Calcula estados, KPIs y el Excel del curso para la fecha dada."""
    matched_todos = examdefs_desde_db(examenes)

    # Solo las actividades que existen realmente en el informe subido
    matched = [(a, e) for a, e in matched_todos if a in actividades]
    faltantes = [a for a, _ in matched_todos if a not in actividades]
    nuevas = [
        a
        for a in actividades
        if a not in {act for act, _ in matched_todos}
    ]

    if not matched:
        raise ValueError(
            "Ninguna actividad del informe coincide con el mapa validado. "
            "¿Es el informe del curso correcto? Puedes volver a validarlo."
        )

    dias_lectivos = [
        d for d in (_a_fecha(x) for x in (curso.get("fechas_lectivas") or [])) if d
    ]

    # Matriz alumno × actividad
    matrix: dict[str, dict[str, se.StudentExam]] = {}
    for _, stu in alumnos.iterrows():
        nombre = stu["alumno"]
        matrix[nombre] = {}
        for act, exam in matched:
            raw = str(stu.get(f"status::{act}", "") or "")
            completado = se.parse_completion_date(str(stu.get(f"date::{act}", "") or ""))
            estado = se.classify_exam(raw, completado, exam, as_of)
            matrix[nombre][act] = se.StudentExam(
                status=estado, completed_at=completado, raw_status=raw
            )

    # Estados globales
    globales = Counter()
    for nombre in matrix:
        globales[se.global_student_status(se.calendar_statuses(matrix[nombre], matched))] += 1

    n_recordar = globales["RECORDAR"] + globales["RETRASADO + RECORDAR"]
    n_retrasado = globales["RETRASADO"] + globales["RETRASADO + RECORDAR"]
    resumen = {
        "alumnos": len(matrix),
        "al_dia": globales["AL DÍA"],
        "a_recordar": n_recordar,
        "retrasados": n_retrasado,
        "sin_empezar": globales["SIN EMPEZAR"],
    }

    # Lista de avisos de hoy, ordenada por urgencia
    recordatorios = []
    for nombre, fila in matrix.items():
        for act, exam in matched:
            if fila[act].status != se.STATUS_RECORDAR or not exam.deadline:
                continue
            restantes = se.lective_days_remaining(as_of, exam.deadline, dias_lectivos)
            recordatorios.append(
                {
                    "alumno": nombre,
                    "email": next(
                        (
                            s["email"]
                            for _, s in alumnos.iterrows()
                            if s["alumno"] == nombre
                        ),
                        "",
                    ),
                    "actividad": act,
                    "limite": exam.deadline,
                    "dias_restantes": restantes,
                }
            )
    recordatorios.sort(key=lambda r: (r["dias_restantes"], r["limite"], r["alumno"]))

    # Excel completo (reutiliza el generador del script original)
    wb = se.build_workbook(
        alumnos, matched, matrix, [], as_of, curso["codigo"], dias_lectivos
    )
    buffer = io.BytesIO()
    wb.save(buffer)

    return {
        "matched": matched,
        "matrix": matrix,
        "resumen": resumen,
        "recordatorios": recordatorios,
        "excel": buffer.getvalue(),
        "actividades_faltantes": faltantes,
        "actividades_nuevas": nuevas,
        "as_of": as_of,
    }


def filas_seguimiento(
    resultado: dict[str, Any],
    examenes: list[dict[str, Any]],
    alumnos: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Aplana la matriz para guardarla como detalle de la instantánea."""
    id_por_actividad = {
        e["actividad_progreso"]: e["id"] for e in examenes if e.get("actividad_progreso")
    }
    email_por_alumno = {s["alumno"]: s["email"] for _, s in alumnos.iterrows()}

    filas = []
    for nombre, fila in resultado["matrix"].items():
        for act, _ in resultado["matched"]:
            se_item = fila[act]
            filas.append(
                {
                    "alumno": nombre,
                    "email": email_por_alumno.get(nombre, ""),
                    "actividad": act,
                    "examen_id": id_por_actividad.get(act),
                    "estado": se_item.status,
                    "completado_en": (
                        se_item.completed_at.isoformat()
                        if isinstance(se_item.completed_at, datetime)
                        else None
                    ),
                }
            )
    return filas
