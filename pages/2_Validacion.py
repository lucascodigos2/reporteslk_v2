"""Validación del mapa actividad del progreso ↔ examen del calendario."""

from __future__ import annotations

import streamlit as st

from core import db, progreso, validacion

st.set_page_config(page_title="Validación", page_icon="▪", layout="wide")

st.title("Validación de pruebas")
st.caption(
    "Confirma qué actividad del informe de progreso corresponde a cada examen "
    "del calendario, y cuáles no deben contar como prueba calificable."
)

# ---------------------------------------------------------------------------
# Selección de curso
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

etiquetas = {f"{c['codigo']} — {c.get('nombre') or 'sin nombre'}": c for c in cursos}
elegido = st.selectbox("Curso", list(etiquetas))
curso = etiquetas[elegido]

examenes = db.examenes_de_curso(curso["id"])
del_calendario = [e for e in examenes if e.get("pub_date")]

if db.curso_validado(curso["id"]):
    st.success("Este curso ya está validado. Puedes volver a validarlo subiendo el informe de nuevo.")
    with st.expander("Ver mapa actual"):
        st.dataframe(
            [
                {
                    "Prueba": e["nombre"],
                    "Actividad del progreso": e.get("actividad_progreso") or "—",
                    "Publicación": e.get("pub_date") or "—",
                    "Límite": e.get("deadline") or "—",
                    "Cuenta para nota": e["cuenta_para_nota"],
                }
                for e in examenes
            ],
            use_container_width=True,
            hide_index=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Subida del informe de progreso
# ---------------------------------------------------------------------------
st.subheader("Informe de finalización de actividades")
archivo = st.file_uploader("Informe de progreso (.csv o .xlsx)", type=["csv", "xlsx"])

if archivo is None:
    st.stop()

try:
    actividades, _alumnos = progreso.leer_progreso(archivo)
except Exception as e:  # noqa: BLE001
    st.error("No se ha podido leer el informe de progreso.")
    with st.expander("Detalle técnico"):
        st.code(str(e))
    st.stop()

st.write(
    f"Detectadas **{len(actividades)}** actividades y "
    f"**{len(del_calendario)}** exámenes en el calendario del curso."
)

# ---------------------------------------------------------------------------
# Tabla editable de validación
# ---------------------------------------------------------------------------
opciones = [validacion.SIN_ASIGNAR] + [
    validacion.etiqueta_examen(e) for e in del_calendario
]
etiqueta_a_id = {
    validacion.etiqueta_examen(e): e["id"] for e in del_calendario
}
id_a_etiqueta = {v: k for k, v in etiqueta_a_id.items()}

propuesta = validacion.proponer_mapa(actividades, del_calendario)

filas = [
    {
        "Actividad del progreso": p["actividad"],
        "Examen del calendario": id_a_etiqueta.get(p["examen_id"], validacion.SIN_ASIGNAR),
        "Cuenta para nota": p["cuenta_para_nota"],
    }
    for p in propuesta
]

sin_asignar = sum(1 for f in filas if f["Examen del calendario"] == validacion.SIN_ASIGNAR)
if sin_asignar:
    st.warning(
        f"{sin_asignar} actividad(es) no se han podido asociar a un examen del "
        "calendario. Revísalas: si son pruebas no calificables (p. ej. la proba "
        "inicial), déjalas sin asignar y desmarca «Cuenta para nota»."
    )

st.caption(
    "Revisa cada fila. Las actividades sin examen asignado no tendrán plazo y no "
    "influirán en el estado global del alumno."
)

editado = st.data_editor(
    filas,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "Actividad del progreso": st.column_config.TextColumn(disabled=True),
        "Examen del calendario": st.column_config.SelectboxColumn(
            options=opciones, required=True, width="large"
        ),
        "Cuenta para nota": st.column_config.CheckboxColumn(
            help="Desmarca las pruebas no calificables (no cuentan para APTO)."
        ),
    },
    key="editor_validacion",
)

# ---------------------------------------------------------------------------
# Validaciones previas al guardado
# ---------------------------------------------------------------------------
asignados = [f["Examen del calendario"] for f in editado if f["Examen del calendario"] != validacion.SIN_ASIGNAR]
duplicados = {x for x in asignados if asignados.count(x) > 1}

if duplicados:
    st.error(
        "Hay exámenes asignados a más de una actividad: "
        + ", ".join(sorted(duplicados))
        + ". Cada examen del calendario debe corresponder como mucho a una actividad."
    )
    st.stop()

sin_cubrir = [e for e in del_calendario if id_a_etiqueta[e["id"]] not in asignados]
if sin_cubrir:
    st.info(
        "Exámenes del calendario sin actividad asociada (no se seguirán): "
        + ", ".join(e["nombre"] for e in sin_cubrir)
    )

# ---------------------------------------------------------------------------
# Guardado
# ---------------------------------------------------------------------------
if st.button("Guardar validación", type="primary"):
    try:
        # Limpiar pruebas sin calendario de una validación anterior
        db.borrar_examenes_sin_calendario(curso["id"])

        # Reiniciar el mapeo de los exámenes del calendario
        for e in del_calendario:
            db.actualizar_examen(
                e["id"],
                {"actividad_progreso": None, "validado": False},
            )

        for orden, fila in enumerate(editado):
            etiqueta = fila["Examen del calendario"]
            cuenta = bool(fila["Cuenta para nota"])
            actividad = fila["Actividad del progreso"]

            if etiqueta == validacion.SIN_ASIGNAR:
                # Prueba sin plazo (no calificable): se guarda para dejar constancia
                db.crear_examen(
                    curso["id"],
                    {
                        "clave": None,
                        "nombre": actividad,
                        "actividad_progreso": actividad,
                        "pub_date": None,
                        "deadline": None,
                        "cuenta_para_nota": cuenta,
                        "orden": orden,
                        "validado": True,
                    },
                )
            else:
                db.actualizar_examen(
                    etiqueta_a_id[etiqueta],
                    {
                        "actividad_progreso": actividad,
                        "cuenta_para_nota": cuenta,
                        "orden": orden,
                        "validado": True,
                    },
                )
    except Exception as e:  # noqa: BLE001
        st.error("No se ha podido guardar la validación.")
        with st.expander("Detalle técnico"):
            st.code(str(e))
    else:
        st.success("Validación guardada. El mapa se reutilizará en las próximas subidas.")
        st.rerun()
