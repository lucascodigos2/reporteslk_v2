"""Acceso a datos sobre Supabase (Postgres).

Lee las credenciales de st.secrets["supabase"]. Usa la service_role key si está
disponible (backend, protege el PII); si no, cae a la publishable key.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import streamlit as st
from supabase import Client, create_client


@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    cfg = st.secrets["supabase"]
    key = cfg.get("service_key") or cfg.get("publishable_key")
    if not key:
        raise RuntimeError(
            "Falta la clave de Supabase en secrets.toml "
            "(service_key o publishable_key)."
        )
    return create_client(cfg["url"], key)


# ---------------------------------------------------------------------------
# Cursos
# ---------------------------------------------------------------------------

def listar_cursos() -> list[dict[str, Any]]:
    res = get_client().table("cursos").select("*").order("creado_en", desc=True).execute()
    return res.data or []


def curso_por_codigo(codigo: str) -> dict[str, Any] | None:
    res = get_client().table("cursos").select("*").eq("codigo", codigo).limit(1).execute()
    return (res.data or [None])[0]


def crear_curso(codigo: str, nombre: str, fechas_lectivas: list[date]) -> dict[str, Any]:
    payload = {
        "codigo": codigo,
        "nombre": nombre,
        "fechas_lectivas": [d.isoformat() for d in fechas_lectivas],
    }
    res = get_client().table("cursos").insert(payload).execute()
    return res.data[0]


def borrar_curso(curso_id: str) -> None:
    # examenes se borra en cascada (ON DELETE CASCADE)
    get_client().table("cursos").delete().eq("id", curso_id).execute()


# ---------------------------------------------------------------------------
# Exámenes
# ---------------------------------------------------------------------------

def examenes_de_curso(curso_id: str) -> list[dict[str, Any]]:
    res = (
        get_client()
        .table("examenes")
        .select("*")
        .eq("curso_id", curso_id)
        .order("orden")
        .execute()
    )
    return res.data or []


def guardar_examenes(curso_id: str, examenes: list[dict[str, Any]]) -> None:
    """Reemplaza los exámenes del curso por la lista dada."""
    client = get_client()
    client.table("examenes").delete().eq("curso_id", curso_id).execute()
    if examenes:
        rows = [{**e, "curso_id": curso_id} for e in examenes]
        client.table("examenes").insert(rows).execute()
