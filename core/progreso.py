"""Lectura del informe de finalización de actividades (progress CSV/XLSX)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd

from . import seguimiento as se


def _guardar_temp(uploaded_file) -> Path:
    sufijo = Path(uploaded_file.name).suffix or ".csv"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=sufijo)
    tmp.write(uploaded_file.getvalue())
    tmp.close()
    return Path(tmp.name)


def leer_progreso(uploaded_file) -> tuple[list[str], pd.DataFrame]:
    """Devuelve (nombres de actividades, dataframe de alumnos)."""
    path = _guardar_temp(uploaded_file)
    try:
        return se.parse_progress(path)
    finally:
        path.unlink(missing_ok=True)
