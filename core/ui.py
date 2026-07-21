"""Piezas de interfaz reutilizables entre vistas."""

from __future__ import annotations

import streamlit as st


def cabecera(titulo: str, subtitulo: str = "") -> None:
    """Cabecera consistente para todas las páginas."""
    st.markdown(f'<p class="titulo-pagina">{titulo}</p>', unsafe_allow_html=True)
    if subtitulo:
        st.markdown(f'<p class="subtitulo-pagina">{subtitulo}</p>', unsafe_allow_html=True)


def chip(texto: str, tipo: str = "ok") -> str:
    """Devuelve el HTML de una etiqueta de estado ('ok' o 'warn')."""
    return f'<span class="chip chip-{tipo}">{texto}</span>'


def selector_curso(cursos: list[dict], clave: str) -> dict:
    """Desplegable de curso común a las vistas."""
    etiquetas = {
        f"{c['codigo']} — {c.get('nombre') or 'sin nombre'}": c for c in cursos
    }
    return etiquetas[st.selectbox("Curso", list(etiquetas), key=clave)]
