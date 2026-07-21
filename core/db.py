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


def actualizar_examen(examen_id: str, campos: dict[str, Any]) -> None:
    get_client().table("examenes").update(campos).eq("id", examen_id).execute()


def crear_examen(curso_id: str, campos: dict[str, Any]) -> dict[str, Any]:
    res = get_client().table("examenes").insert({**campos, "curso_id": curso_id}).execute()
    return res.data[0]


def borrar_examenes_sin_calendario(curso_id: str) -> None:
    """Borra las pruebas creadas en validación (las que no vienen del calendario).

    Se identifican por no tener fecha de publicación. Permite re-validar un curso
    sin duplicar filas ni tocar los exámenes reales del INF_30.
    """
    (
        get_client()
        .table("examenes")
        .delete()
        .eq("curso_id", curso_id)
        .is_("pub_date", "null")
        .execute()
    )


# ---------------------------------------------------------------------------
# Instantáneas de seguimiento
# ---------------------------------------------------------------------------

def crear_subida(
    curso_id: str,
    fecha_referencia: Any,
    n_alumnos: int,
    resumen: dict[str, Any],
    detalle: list[dict[str, Any]],
) -> dict[str, Any]:
    """Guarda una instantánea del seguimiento (cabecera + detalle por alumno)."""
    client = get_client()
    res = (
        client.table("subidas")
        .insert(
            {
                "curso_id": curso_id,
                "fecha_referencia": str(fecha_referencia),
                "n_alumnos": n_alumnos,
                "resumen": resumen,
            }
        )
        .execute()
    )
    subida = res.data[0]

    if detalle:
        filas = [{**d, "subida_id": subida["id"]} for d in detalle]
        # insertar por lotes para no exceder el tamaño de petición
        for i in range(0, len(filas), 500):
            client.table("seguimiento").insert(filas[i : i + 500]).execute()

    return subida


def subidas_de_curso(curso_id: str) -> list[dict[str, Any]]:
    res = (
        get_client()
        .table("subidas")
        .select("*")
        .eq("curso_id", curso_id)
        .order("fecha_referencia", desc=True)
        .execute()
    )
    return res.data or []


def borrar_subida(subida_id: str) -> None:
    get_client().table("subidas").delete().eq("id", subida_id).execute()


def curso_validado(curso_id: str) -> bool:
    res = (
        get_client()
        .table("examenes")
        .select("id")
        .eq("curso_id", curso_id)
        .eq("validado", True)
        .limit(1)
        .execute()
    )
    return bool(res.data)
