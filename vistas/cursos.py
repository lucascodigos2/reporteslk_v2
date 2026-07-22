"""Alta y gestión de cursos."""

from __future__ import annotations

import html

import streamlit as st

from core import calendario, db, moodle, ui

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

                # Vincular con Moodle por expediente. Que Moodle falle no debe
                # impedir dar de alta el curso.
                # El aviso se guarda porque el rerun de abajo limpiaría la pantalla.
                try:
                    encontrados = moodle.buscar_curso(info["codigo"])
                except moodle.ErrorMoodle as e:
                    aviso = ("warning", f"No se pudo consultar Moodle: {e}")
                else:
                    if len(encontrados) == 1:
                        db.actualizar_curso(
                            curso["id"], {"moodle_course_id": encontrados[0]["id"]}
                        )
                        aviso = (
                            "info",
                            f"Vinculado con Moodle (curso {encontrados[0]['id']}): "
                            f"{encontrados[0]['nombre']}",
                        )
                    else:
                        aviso = (
                            "warning",
                            "No se ha podido identificar el curso en Moodle "
                            f"({len(encontrados)} coincidencias). Añade el id a "
                            "mano para poder descargar el informe.",
                        )

                st.session_state["aviso_alta"] = aviso
                st.rerun()

# ---------------------------------------------------------------------------
# Listado
# ---------------------------------------------------------------------------
aviso = st.session_state.pop("aviso_alta", None)
if aviso:
    st.success("Curso guardado.")
    getattr(st, aviso[0])(aviso[1])

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
            # El código viene de un Excel subido: escapar antes de inyectarlo como HTML.
            st.markdown(
                f"**{html.escape(str(c['codigo']))}** &nbsp; {estado}",
                unsafe_allow_html=True,
            )
            st.caption(
                f"{c.get('nombre') or 'sin nombre'}  ·  {len(examenes)} pruebas  ·  "
                f"{n_subidas} subida(s)  ·  alta {c['creado_en'][:10]}"
            )
            if not validado:
                st.caption(
                    "Ve a **Validación** para asociar las actividades del informe "
                    "de progreso a cada examen."
                )

            # Id de Moodle: habilita la descarga automática del informe
            with st.expander(
                "Moodle: " + (f"curso {c['moodle_course_id']}" if c.get("moodle_course_id")
                              else "sin vincular")
            ):
                nuevo = st.text_input(
                    "Id del curso en Moodle",
                    value=c.get("moodle_course_id") or "",
                    key=f"moodle_{c['id']}",
                    help="El número que aparece como `course=` en la URL del "
                         "informe de progreso de este curso en Moodle.",
                )
                b1, b2 = st.columns(2)
                if b1.button("Guardar id", key=f"gm_{c['id']}"):
                    db.actualizar_curso(
                        c["id"], {"moodle_course_id": nuevo.strip() or None}
                    )
                    st.rerun()

                if b2.button("Buscar en Moodle", key=f"bm_{c['id']}"):
                    try:
                        st.session_state[f"hits_{c['id']}"] = moodle.buscar_curso(
                            c["codigo"]
                        )
                    except moodle.ErrorMoodle as e:
                        st.error(str(e))

                hits = st.session_state.get(f"hits_{c['id']}")
                if hits is not None:
                    if not hits:
                        st.warning(
                            f"Ningún curso de Moodle empieza por «{c['codigo']}». "
                            "Introduce el id a mano."
                        )
                    else:
                        etiquetas = {f"{h['id']} — {h['nombre']}": h["id"] for h in hits}
                        elegido = st.selectbox(
                            "Coincidencias", list(etiquetas), key=f"sel_{c['id']}"
                        )
                        if st.button("Vincular", key=f"vc_{c['id']}", type="primary"):
                            db.actualizar_curso(
                                c["id"], {"moodle_course_id": etiquetas[elegido]}
                            )
                            st.session_state.pop(f"hits_{c['id']}", None)
                            st.rerun()

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
