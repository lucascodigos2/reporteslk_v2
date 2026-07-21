"""Alta y gestión de cursos."""

from __future__ import annotations

import streamlit as st

from core import auth, calendario, db

st.set_page_config(page_title="Cursos", page_icon="▪", layout="wide")

auth.exigir_login()

st.title("Cursos")

# ---------------------------------------------------------------------------
# Alta de curso nuevo
# ---------------------------------------------------------------------------
st.subheader("Dar de alta un curso")
st.caption(
    "Sube el informe de días lectivos (INF_30). Se detectarán automáticamente "
    "los exámenes y sus fechas de plazo."
)

archivo = st.file_uploader("Informe de días lectivos (.xlsx)", type=["xlsx"])

if archivo is not None:
    try:
        info = calendario.analizar_calendario(archivo)
    except Exception as e:  # noqa: BLE001
        st.error("No se ha podido leer el informe de días lectivos.")
        with st.expander("Detalle técnico"):
            st.code(str(e))
    else:
        st.success(
            f"Curso detectado: **{info['codigo']}** — "
            f"{len(info['examenes'])} exámenes, "
            f"{len(info['fechas_lectivas'])} días lectivos."
        )
        st.dataframe(
            [
                {
                    "Examen": e["nombre"],
                    "Publicación": e["pub_date"],
                    "Límite": e["deadline"],
                    "Módulo": e["cod_mf"],
                    "Final": e["es_final"],
                    "Igualdad": e["es_igualdad"],
                }
                for e in info["examenes"]
            ],
            use_container_width=True,
            hide_index=True,
        )

        existente = db.curso_por_codigo(info["codigo"])
        if existente:
            st.warning(
                f"Ya existe un curso con código {info['codigo']}. "
                "Bórralo abajo si quieres volver a darlo de alta."
            )
        elif st.button("Guardar curso", type="primary"):
            curso = db.crear_curso(
                info["codigo"], info["nombre"], info["fechas_lectivas"]
            )
            db.guardar_examenes(curso["id"], info["examenes"])
            st.success("Curso guardado.")
            st.rerun()

st.divider()

# ---------------------------------------------------------------------------
# Cursos existentes
# ---------------------------------------------------------------------------
st.subheader("Cursos dados de alta")

try:
    cursos = db.listar_cursos()
except Exception as e:  # noqa: BLE001
    st.error("No se ha podido conectar con la base de datos.")
    with st.expander("Detalle técnico"):
        st.code(str(e))
    st.stop()

if not cursos:
    st.info("Todavía no hay cursos.")
else:
    for c in cursos:
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"**{c['codigo']}** — {c.get('nombre') or 'sin nombre'}")
                exs = db.examenes_de_curso(c["id"])
                st.caption(
                    f"{len(exs)} exámenes · alta {c['creado_en'][:10]}"
                )
            with col2:
                if st.button("Borrar", key=f"del_{c['id']}"):
                    db.borrar_curso(c["id"])
                    st.rerun()
