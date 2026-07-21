"""Propuesta de emparejamiento actividad del progreso ↔ examen del calendario.

A diferencia del script original (que emparejaba por posición), aquí se propone
por identidad: se extrae el número/tipo de prueba del nombre de la actividad y se
busca el examen correspondiente. La propuesta es solo una sugerencia: el usuario
la confirma o corrige en la pantalla de validación, y el resultado se persiste.
"""

from __future__ import annotations

import re
from typing import Any

SIN_ASIGNAR = "— No calificable / sin plazo —"


def _clave_sugerida(actividad: str) -> str | None:
    """Deduce la clave de examen a partir del nombre de la actividad."""
    txt = actividad.upper().strip()

    # Pruebas del módulo de igualdad: "Test 1: FCOXXX22", "Test final: FCOXXX22"
    if txt.startswith("TEST") or "IGUALDAD" in txt or "FCO" in txt:
        if "FINAL" in txt:
            return "TEST_FINAL_IGUALDAD"
        m = re.search(r"TEST\s*(\d+)", txt)
        return f"TEST_{m.group(1)}_IGUALDAD" if m else None

    # Prueba inicial / diagnóstica: no es examen calificable
    if "INICIAL" in txt:
        return None

    # Examen final de especialidad
    if "FINAL" in txt and ("EXAME" in txt or "EXAMEN" in txt):
        return "EXAME_FINAL"

    # Exámenes numerados: "EXAME 7: TEMA 4"
    m = re.search(r"EXAM[EN]*\s*(\d+)", txt)
    if m:
        return f"EXAME_{m.group(1)}"

    return None


def proponer_mapa(
    actividades: list[str], examenes: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Para cada actividad, propone el examen del calendario que le corresponde.

    Devuelve filas listas para la tabla editable de validación.
    """
    por_clave = {e["clave"]: e for e in examenes if e.get("clave")}
    ya_usados: set[str] = set()
    filas: list[dict[str, Any]] = []

    for actividad in actividades:
        clave = _clave_sugerida(actividad)
        examen = por_clave.get(clave) if clave else None
        # No asignar dos actividades al mismo examen
        if examen and examen["id"] in ya_usados:
            examen = None
        if examen:
            ya_usados.add(examen["id"])

        filas.append(
            {
                "actividad": actividad,
                "examen_id": examen["id"] if examen else None,
                "cuenta_para_nota": examen is not None,
            }
        )

    return filas


def etiqueta_examen(examen: dict[str, Any]) -> str:
    """Texto mostrado en el desplegable de la tabla de validación."""
    pub = examen.get("pub_date") or "?"
    dl = examen.get("deadline") or "?"
    return f"{examen['nombre']}  ({pub} → {dl})"
