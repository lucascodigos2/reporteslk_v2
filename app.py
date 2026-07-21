"""Plataforma de seguimiento de cursos — página principal."""

from __future__ import annotations

import streamlit as st

from core import auth, db

st.set_page_config(
    page_title="Seguimiento de cursos",
    page_icon="▪",
    layout="wide",
)

auth.exigir_login()

st.title("Seguimiento de cursos")
st.caption(
    "Da de alta tus cursos con el informe de días lectivos y lleva el "
    "seguimiento de varios a la vez."
)

try:
    cursos = db.listar_cursos()
except Exception as e:  # noqa: BLE001
    st.error(
        "No se ha podido conectar con la base de datos. Revisa las credenciales "
        "de Supabase en los *secrets* y que el esquema (`schema.sql`) esté creado."
    )
    with st.expander("Detalle técnico"):
        st.code(str(e))
    st.stop()

if not cursos:
    st.info(
        "Todavía no hay cursos. Ve a **Cursos** (menú de la izquierda) para dar "
        "de alta el primero subiendo su informe de días lectivos (INF_30)."
    )
else:
    st.subheader(f"{len(cursos)} curso(s) dado(s) de alta")
    for c in cursos:
        with st.container(border=True):
            st.markdown(f"**{c['codigo']}** — {c.get('nombre') or 'sin nombre'}")
            st.caption(f"Alta: {c['creado_en'][:10]}")
