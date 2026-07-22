"""Seguimiento del curso: estados, avisos del día e informe Excel."""

from __future__ import annotations

from datetime import date

import streamlit as st

from core import correo, db, informe, moodle, progreso, ui

ui.cabecera(
    "Seguimiento",
    "Sube el informe de finalización de actividades para ver quién va al día, "
    "a quién hay que avisar hoy y descargar el informe completo.",
)

# ---------------------------------------------------------------------------
# Curso
# ---------------------------------------------------------------------------
try:
    cursos = db.listar_cursos()
except Exception as e:  # noqa: BLE001
    st.error("No se ha podido conectar con la base de datos.")
    with st.expander("Detalle técnico"):
        st.code(str(e))
    st.stop()

if not cursos:
    st.info("Primero da de alta un curso en la página **Cursos**.")
    st.stop()

curso = ui.selector_curso(cursos, "curso_seguimiento")

examenes = db.examenes_de_curso(curso["id"])
if not db.curso_validado(curso["id"]):
    st.warning(
        "Este curso todavía no está validado. Ve a **Validación** y confirma qué "
        "actividad corresponde a cada examen antes de generar el seguimiento."
    )
    st.stop()

origen = st.radio(
    "Origen del informe",
    ["Descargar de Moodle", "Subir un fichero"],
    horizontal=True,
    label_visibility="collapsed",
)

col_a, col_b = st.columns([2, 1])
with col_a:
    if origen == "Subir un fichero":
        archivo = st.file_uploader("Informe de progreso (.csv o .xlsx)", type=["csv", "xlsx"])
    else:
        archivo = None
        if curso.get("moodle_course_id"):
            st.caption(f"Curso {curso['moodle_course_id']} en Moodle.")
        else:
            st.warning(
                "Este curso no tiene id de Moodle. Añádelo en la página "
                "**Cursos** para poder descargar el informe automáticamente."
            )
with col_b:
    fecha_ref = st.date_input("Fecha de referencia", value=date.today(), format="DD/MM/YYYY")

guardar = st.checkbox(
    "Guardar esta subida en el histórico", value=True,
    help="Permite ver después la evolución del curso en el tiempo.",
)

if origen == "Descargar de Moodle":
    listo = bool(curso.get("moodle_course_id"))
    etiqueta = "Descargar de Moodle y generar seguimiento"
else:
    listo = archivo is not None
    etiqueta = "Generar seguimiento"

if listo and st.button(etiqueta, type="primary"):
    try:
        if origen == "Descargar de Moodle":
            with st.spinner("Descargando el informe de Moodle…"):
                nombre, contenido = moodle.descargar_informe(
                    curso["moodle_course_id"], codigo_esperado=curso["codigo"]
                )
            archivo = moodle.FicheroDescargado(nombre, contenido)
            st.caption(f"Descargado: {nombre}")
        actividades, alumnos = progreso.leer_progreso(archivo)
        resultado = informe.generar(curso, examenes, actividades, alumnos, fecha_ref)
    except moodle.ErrorMoodle as e:
        st.error(str(e))
    except Exception as e:  # noqa: BLE001
        st.error(f"No se ha podido generar el seguimiento. {e}")
        with st.expander("Detalle técnico"):
            st.code(str(e))
    else:
        if guardar:
            try:
                db.crear_subida(
                    curso["id"],
                    fecha_ref,
                    resultado["resumen"]["alumnos"],
                    resultado["resumen"],
                    informe.filas_seguimiento(resultado, examenes, alumnos),
                )
            except Exception as e:  # noqa: BLE001
                st.warning(f"El informe se ha generado, pero no se pudo guardar en el histórico: {e}")
        st.session_state["resultado"] = resultado

# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------
resultado = st.session_state.get("resultado")
if resultado:
    st.divider()

    if resultado["actividades_faltantes"]:
        st.warning(
            "Actividades validadas que no aparecen en este informe: "
            + ", ".join(resultado["actividades_faltantes"])
        )
    if resultado["actividades_nuevas"]:
        st.warning(
            "Actividades del informe que no están en el mapa validado (se ignoran): "
            + ", ".join(resultado["actividades_nuevas"])
            + ". Vuelve a **Validación** si quieres incluirlas."
        )

    r = resultado["resumen"]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Alumnos", r["alumnos"])
    c2.metric("Al día", r["al_dia"])
    c3.metric("A avisar hoy", r["a_recordar"])
    c4.metric("Retrasados", r["retrasados"])
    c5.metric("Sin empezar", r["sin_empezar"])

    st.subheader("A avisar hoy")
    recordatorios = resultado["recordatorios"]
    if recordatorios:
        st.caption("Alumnos con una prueba abierta y sin finalizar, por urgencia.")
        st.dataframe(
            [
                {
                    "Alumno": x["alumno"],
                    "Email": x["email"],
                    "Prueba": x["actividad"],
                    "Límite": x["limite"].strftime("%d/%m/%Y"),
                    "Días lectivos restantes": x["dias_restantes"],
                }
                for x in recordatorios
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("Nadie tiene pruebas en plazo pendientes hoy.")

    d1, d2 = st.columns([1, 1])
    d1.download_button(
        "Descargar informe completo (.xlsx)",
        data=resultado["excel"],
        file_name=f"seguimiento_{curso['codigo'].replace('/', '-')}_"
        f"{resultado['as_of'].strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    destinatarios = curso.get("destinatarios") or []
    if d2.button(
        "Enviar resumen por correo",
        use_container_width=True,
        disabled=not destinatarios,
        help="Configura los destinatarios en la página Cursos."
        if not destinatarios
        else "Envía a: " + ", ".join(destinatarios),
    ):
        try:
            enviados = correo.enviar_resumen(curso, resultado)
        except correo.ErrorCorreo as e:
            st.error(str(e))
        else:
            st.success("Resumen enviado a " + ", ".join(enviados))

# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Histórico del curso")

subidas = db.subidas_de_curso(curso["id"])
if not subidas:
    st.caption("Todavía no hay subidas guardadas para este curso.")
else:
    tabla = [
        {
            "Fecha referencia": s["fecha_referencia"],
            "Alumnos": (s.get("resumen") or {}).get("alumnos"),
            "Al día": (s.get("resumen") or {}).get("al_dia"),
            "A avisar": (s.get("resumen") or {}).get("a_recordar"),
            "Retrasados": (s.get("resumen") or {}).get("retrasados"),
            "Guardado": s["subido_en"][:16].replace("T", " "),
        }
        for s in subidas
    ]
    st.dataframe(tabla, use_container_width=True, hide_index=True)

    evolucion = {
        s["fecha_referencia"]: (s.get("resumen") or {}).get("al_dia", 0)
        for s in reversed(subidas)
    }
    if len(evolucion) > 1:
        st.caption("Evolución de alumnos al día")
        st.line_chart(evolucion)
