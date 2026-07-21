"""Detección de exámenes a partir del informe de días lectivos (INF_30).

Envuelve la lógica de core/seguimiento.py para devolver estructuras listas
para guardar en la base de datos.
"""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from . import seguimiento as se


def _guardar_temp(uploaded_file) -> Path:
    sufijo = Path(uploaded_file.name).suffix or ".xlsx"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
    tmp.write(uploaded_file.getvalue())
    tmp.close()
    return Path(tmp.name)


def analizar_calendario(uploaded_file) -> dict[str, Any]:
    """Devuelve código de curso, días lectivos y exámenes detectados."""
    path = _guardar_temp(uploaded_file)
    try:
        base, lective_days = se.load_calendar(path)
        schedule = se.build_exam_schedule(base, lective_days)
    finally:
        path.unlink(missing_ok=True)

    codigo = str(base["Cod. Curso"].iloc[0]) if len(base) else path.stem
    nombre = str(base["Desc. MF"].iloc[0]) if "Desc. MF" in base.columns and len(base) else ""

    examenes: list[dict[str, Any]] = []
    for i, ex in enumerate(schedule):
        examenes.append(
            {
                "clave": ex.key,
                "nombre": ex.name,
                "actividad_progreso": None,
                "pub_date": ex.pub_date.isoformat() if ex.pub_date else None,
                "deadline": ex.deadline.isoformat() if ex.deadline else None,
                "cod_mf": ex.cod_mf,
                "es_final": ex.is_final,
                "es_igualdad": ex.is_equality,
                "cuenta_para_nota": True,
                "orden": i,
                "validado": False,
            }
        )

    return {
        "codigo": codigo,
        "nombre": nombre,
        "fechas_lectivas": lective_days,
        "examenes": examenes,
    }
