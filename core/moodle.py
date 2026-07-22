"""Descarga del informe de finalización de actividades desde Moodle.

Credenciales en st.secrets["moodle"]: url (informe de referencia), usuario,
password. Nunca deben estar en el repositorio.
"""

from __future__ import annotations

import html
import re
from urllib.parse import parse_qs, urlparse

import requests
import streamlit as st

TIMEOUT = 60


class ErrorMoodle(RuntimeError):
    """Fallo controlado al hablar con Moodle (login, curso o descarga)."""


def _cfg() -> dict[str, str]:
    try:
        cfg = st.secrets["moodle"]
    except (KeyError, FileNotFoundError):
        raise ErrorMoodle(
            "No hay configuración de Moodle. Añade una sección [moodle] con "
            "url, usuario y password en los secrets."
        ) from None
    faltan = [k for k in ("url", "usuario", "password") if not cfg.get(k)]
    if faltan:
        raise ErrorMoodle(f"Faltan claves en [moodle]: {', '.join(faltan)}.")
    return cfg


def base_url() -> str:
    """Raíz de la instalación de Moodle, deducida de la URL del informe."""
    return _cfg()["url"].split("/report/", 1)[0]


def curso_id_por_defecto() -> str | None:
    """El `course=` de la URL de ejemplo, útil como sugerencia en el alta."""
    qs = parse_qs(urlparse(_cfg()["url"]).query)
    return (qs.get("course") or [None])[0]


def url_informe(course_id: str | int) -> str:
    """URL de la página del informe de progreso de un curso."""
    return (
        f"{base_url()}/report/progress/index.php"
        f"?course={course_id}"
        "&activityinclude=quiz"
        "&activityorder=orderincourse"
        "&activitysection=-1"
    )


def _expediente(codigo: str) -> str:
    """Parte numérica del expediente: '2026/001653' -> '001653'."""
    return codigo.strip().split("/")[-1].strip()


def buscar_curso(codigo: str, sesion: requests.Session | None = None) -> list[dict[str, str]]:
    """Cursos de Moodle cuyo nombre empieza por el expediente del curso.

    Los cursos de la Xunta/SEPE se llaman '2026/001653_IFCT0019_...', es decir,
    el prefijo coincide con el `codigo` que guardamos al leer el INF_30. Filtrar
    por ese prefijo descarta tanto los enlaces internos de otros cursos como las
    coincidencias por código de certificado (que no son únicas).
    """
    s = sesion or abrir_sesion()

    try:
        r = s.get(
            f"{base_url()}/course/search.php",
            params={"search": _expediente(codigo), "perpage": 100},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise ErrorMoodle(f"No se ha podido buscar el curso en Moodle: {e}") from e

    prefijo = codigo.strip()
    encontrados: dict[str, str] = {}
    for cid, etiqueta in re.findall(
        r'course/view\.php\?id=(\d+)[^>]*>(.{0,200}?)</a>', r.text, re.S
    ):
        nombre = html.unescape(re.sub(r"<[^>]+>", "", etiqueta)).strip()
        if nombre.startswith(prefijo):
            encontrados.setdefault(cid, nombre)

    return [{"id": cid, "nombre": n} for cid, n in encontrados.items()]


def abrir_sesion() -> requests.Session:
    """Inicia sesión y devuelve la sesión autenticada (cookie MoodleSession)."""
    cfg = _cfg()
    login = f"{base_url()}/login/index.php"

    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (compatible; seguimiento-cursos)"

    try:
        # El logintoken (CSRF) solo existe en algunas versiones/configuraciones.
        r = s.get(login, timeout=TIMEOUT)
        r.raise_for_status()
        datos = {"username": cfg["usuario"], "password": cfg["password"]}
        m = re.search(r'name="logintoken"\s+value="([^"]+)"', r.text)
        if m:
            datos["logintoken"] = m.group(1)

        r = s.post(login, data=datos, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        raise ErrorMoodle(f"No se ha podido contactar con Moodle: {e}") from e

    if "MoodleSession" not in s.cookies or "/login/index.php" in r.url:
        raise ErrorMoodle(
            "Moodle ha rechazado el acceso. Revisa el usuario y la contraseña "
            "en los secrets (puede haber caducado)."
        )
    return s


def descargar_informe(
    course_id: str | int,
    sesion: requests.Session | None = None,
    codigo_esperado: str | None = None,
):
    """Descarga el informe en CSV. Devuelve (nombre de fichero, contenido).

    El enlace de descarga lleva un `sesskey` que cambia en cada sesión, así que
    se extrae de la página del informe en cada ejecución en vez de guardarse.

    Si se pasa `codigo_esperado`, se comprueba que el expediente aparece en el
    nombre del fichero devuelto por Moodle. Un id equivocado descargaría datos
    personales de alumnos de otro curso sin que nada lo delatase.
    """
    s = sesion or abrir_sesion()

    try:
        r = s.get(url_informe(course_id), timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        raise ErrorMoodle(f"No se ha podido abrir el informe del curso {course_id}: {e}") from e

    # excelcsv = UTF-16 con tabuladores, el mismo formato que se subía a mano
    # y el que espera seguimiento.parse_progress. No usar format=csv (UTF-8/comas).
    m = re.search(r'href="([^"]*format=excelcsv[^"]*)"', r.text)
    if not m:
        raise ErrorMoodle(
            f"El curso {course_id} no ha devuelto un informe descargable. "
            "Comprueba que el id es correcto y que la cuenta tiene acceso al curso."
        )

    try:
        csv = s.get(html.unescape(m.group(1)), timeout=TIMEOUT * 2)
        csv.raise_for_status()
    except requests.RequestException as e:
        raise ErrorMoodle(f"Falló la descarga del CSV: {e}") from e

    if "csv" not in csv.headers.get("content-type", ""):
        raise ErrorMoodle("Moodle no ha devuelto un CSV; puede que la sesión haya expirado.")

    disposicion = csv.headers.get("content-disposition", "")
    m_nombre = re.search(r"filename=([^;]+)", disposicion)
    nombre = m_nombre.group(1).strip() if m_nombre else f"progress_{course_id}.csv"

    if codigo_esperado:
        # En el nombre el expediente va como '2026_001653'
        esperado = codigo_esperado.strip().replace("/", "_")
        if esperado not in nombre:
            raise ErrorMoodle(
                f"El curso {course_id} de Moodle no corresponde al expediente "
                f"{codigo_esperado} (el informe descargado es «{nombre}»). "
                "Corrige el id de Moodle en la página Cursos."
            )

    return nombre, csv.content


class FicheroDescargado:
    """Envoltorio con la interfaz mínima que espera progreso.leer_progreso."""

    def __init__(self, nombre: str, contenido: bytes) -> None:
        self.name = nombre
        self._contenido = contenido

    def getvalue(self) -> bytes:
        return self._contenido
