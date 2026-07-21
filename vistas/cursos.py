"""Alta y gestión de cursos."""

from __future__ import annotations

import streamlit as st

from core import calendario, db, ui

ui.cabecera(
    "Cursos",
    "Da de alta un curso subiendo su informe de días lectivos (INF_30). "
    "Se detectarán automáticamente sus exámenes y plazos.",
)

try:
    cursos = db.listar_cursos()
except Exception as e:  # noqa: BLE001
    st.error(
        "No se ha podido conectar con la base de datos. Revisa las credenciales "
        "de Supabase y que el esquema (`schema.sql`) esté creado."
    )
    with st.expander("Detalle técnico"):
        st.code(str(e))
    st.stop()

# ---------------------------------------------------------------------------
# Alta de curso
# ---------------------------------------------------------------------------
with st.expander("Dar de alta un curso nuevo", expanded=not cursos):
    archivo = st.file_uploader(
        "Informe de días lectivos (.xlsx)", type=["xlsx"], key="alta_calendario"
    )

    if archivo is not None:
        try:
            info = calendario.analizar_calendario(archivo)
        except Exception as e:  # noqa: BLE001
            st.error("No se ha podido leer el informe de días lectivos.")
            with st.expander("Detalle técnico"):
                st.code(str(e))
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Curso", info["codigo"])
            c2.metric("Exámenes detectados", len(info["examenes"]))
            c3.metric("Días lectivos", len(info["fechas_lectivas"]))

            st.dataframe(
                [
                    {
                        "Prueba": e["nombre"],
                        "Publicación": e["pub_date"],
                        "Límite": e["deadline"],
                        "Módulo": e["cod_mf"],
                        "Final": "Sí" if e["es_final"] else "",
                        "Igualdad": "Sí" if e["es_igualdad"] else "",
                    }
                    for e in info["examenes"]
                ],
                use_container_width=True,
                hide_index=True,
            )

            if db.curso_por_codigo(info["codigo"]):
                st.warning(
                    f"Ya existe un curso con código **{info['codigo']}**. "
                    "Bórralo abajo si quieres volver a darlo de alta."
                )
            elif st.button("Guardar curso", type="primary"):
                curso = db.crear_curso(
                    info["codigo"], info["nombre"], info["fechas_lectivas"]
                )
                db.guardar_examenes(curso["id"], info["examenes"])
                st.success("Curso guardado.")
                st.rerun()

# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------
if not cursos:
    st.info("Todavía no hay cursos dados de alta.")
    st.stop()

st.markdown(f"##### {len(cursos)} curso(s)")

for c in cursos:
    examenes = db.examenes_de_curso(c["id"])
    validado = db.curso_validado(c["id"])
    n_subidas = len(db.subidas_de_curso(c["id"]))

    with st.container(border=True):
        izq, der = st.columns([6, 1])

        with izq:
            estado = (
                ui.chip("Validado", "ok")
                if validado
                else ui.chip("Pendiente de validar", "warn")
            )
            st.markdown(f"**{c['codigo']}** &nbsp; {estado}", unsafe_allow_html=True)
            st.caption(
                f"{c.get('nombre') or 'sin nombre'}  ·  {len(examenes)} pruebas  ·  "
                f"{n_subidas} subida(s)  ·  alta {c['creado_en'][:10]}"
            )
            if not validado:
                st.caption(
                    "Ve a **Validación** para asociar las actividades del informe "
                    "de progreso a cada examen."
                )

        with der:
            if st.button("Borrar", key=f"del_{c['id']}", use_container_width=True):
                st.session_state[f"confirmar_{c['id']}"] = True

        # Confirmación: el borrado es destructivo y arrastra exámenes e histórico
        if st.session_state.get(f"confirmar_{c['id']}"):
            st.warning(
                f"¿Borrar **{c['codigo']}**? Se eliminarán también sus "
                f"{len(examenes)} pruebas y sus {n_subidas} subida(s) del histórico. "
                "No se puede deshacer."
            )
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Sí, borrar", key=f"si_{c['id']}", type="primary"):
                db.borrar_curso(c["id"])
                st.session_state.pop(f"confirmar_{c['id']}", None)
                st.rerun()
            if b2.button("Cancelar", key=f"no_{c['id']}"):
                st.session_state.pop(f"confirmar_{c['id']}", None)
                st.rerun()
