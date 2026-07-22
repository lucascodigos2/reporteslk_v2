"""Envío del resumen diario de avisos por correo (relay SMTP de Mailjet).

Credenciales en st.secrets["mailjet"]: api_key, secret_key, remitente. En Mailjet
el usuario y la contraseña de SMTP son la API key y la secret key, no las de la
cuenta. Los destinatarios NO van aquí: se configuran por curso en la base de datos.
"""

from __future__ import annotations

import html
import re
import smtplib
from email.message import EmailMessage
from typing import Any

import streamlit as st

SERVIDOR = "in-v3.mailjet.com"
PUERTO = 587
TIMEOUT = 30

_RE_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ErrorCorreo(RuntimeError):
    """Fallo controlado al enviar el resumen."""


def normalizar_destinatarios(texto: str) -> tuple[list[str], list[str]]:
    """Parte un texto libre en (correos válidos, líneas descartadas).

    Acepta un correo por línea o separados por comas. Quita duplicados
    conservando el orden. Un error aquí pasaría desapercibido dentro del envío
    automático, así que se valida al guardar.
    """
    validos: list[str] = []
    invalidos: list[str] = []
    for trozo in re.split(r"[\n,;]+", texto or ""):
        c = trozo.strip()
        if not c:
            continue
        if _RE_CORREO.match(c):
            if c.lower() not in {v.lower() for v in validos}:
                validos.append(c)
        else:
            invalidos.append(c)
    return validos, invalidos


def _cfg() -> dict[str, str]:
    try:
        cfg = st.secrets["mailjet"]
    except (KeyError, FileNotFoundError):
        raise ErrorCorreo(
            "No hay configuración de correo. Añade una sección [mailjet] con "
            "api_key, secret_key y remitente en los secrets."
        ) from None
    faltan = [k for k in ("api_key", "secret_key", "remitente") if not cfg.get(k)]
    if faltan:
        raise ErrorCorreo(f"Faltan claves en [mailjet]: {', '.join(faltan)}.")
    return cfg


def hay_configuracion() -> bool:
    try:
        _cfg()
    except ErrorCorreo:
        return False
    return True


def _cuerpo(curso: dict[str, Any], resultado: dict[str, Any]) -> tuple[str, str]:
    """Devuelve (texto plano, html) del resumen."""
    recordatorios = resultado["recordatorios"]
    r = resultado["resumen"]
    fecha = resultado["as_of"].strftime("%d/%m/%Y")
    codigo = curso["codigo"]

    cabecera = (
        f"Seguimiento del curso {codigo} a {fecha}.\n"
        f"{r['alumnos']} alumnos: {r['al_dia']} al día, {r['a_recordar']} a avisar, "
        f"{r['retrasados']} retrasados, {r['sin_empezar']} sin empezar.\n"
    )

    if recordatorios:
        filas = "\n".join(
            f"  {x['alumno']} — {x['actividad']} — límite {x['limite'].strftime('%d/%m/%Y')} "
            f"({x['dias_restantes']} día{'s' if x['dias_restantes'] != 1 else ''} lectivo"
            f"{'s' if x['dias_restantes'] != 1 else ''})"
            for x in recordatorios
        )
        texto = f"{cabecera}\nAlumnos a avisar hoy:\n{filas}\n"
    else:
        texto = f"{cabecera}\nHoy no hay alumnos con pruebas pendientes en plazo.\n"

    texto += "\nSe adjunta el informe completo en Excel.\n"

    # HTML: escapar todo, que los nombres vienen del informe del LMS
    def esc(v: Any) -> str:
        return html.escape(str(v))

    if recordatorios:
        celdas = "".join(
            "<tr>"
            f"<td style='padding:4px 10px;border-bottom:1px solid #eee'>{esc(x['alumno'])}</td>"
            f"<td style='padding:4px 10px;border-bottom:1px solid #eee'>{esc(x['email'])}</td>"
            f"<td style='padding:4px 10px;border-bottom:1px solid #eee'>{esc(x['actividad'])}</td>"
            f"<td style='padding:4px 10px;border-bottom:1px solid #eee'>{esc(x['limite'].strftime('%d/%m/%Y'))}</td>"
            f"<td style='padding:4px 10px;border-bottom:1px solid #eee;text-align:right'>{esc(x['dias_restantes'])}</td>"
            "</tr>"
            for x in recordatorios
        )
        tabla = (
            "<table style='border-collapse:collapse;font-size:14px'>"
            "<tr style='text-align:left'>"
            "<th style='padding:4px 10px'>Alumno</th><th style='padding:4px 10px'>Correo</th>"
            "<th style='padding:4px 10px'>Prueba</th><th style='padding:4px 10px'>Límite</th>"
            "<th style='padding:4px 10px'>Días</th></tr>"
            f"{celdas}</table>"
        )
    else:
        tabla = "<p>Hoy no hay alumnos con pruebas pendientes en plazo.</p>"

    cuerpo_html = (
        "<div style='font-family:system-ui,sans-serif;color:#222'>"
        f"<h2 style='font-size:17px;margin:0 0 4px'>Seguimiento {esc(codigo)}</h2>"
        f"<p style='color:#666;margin:0 0 16px;font-size:13px'>Datos a {esc(fecha)}</p>"
        f"<p style='font-size:14px'>{r['alumnos']} alumnos · {r['al_dia']} al día · "
        f"<strong>{r['a_recordar']} a avisar</strong> · {r['retrasados']} retrasados · "
        f"{r['sin_empezar']} sin empezar</p>"
        f"{tabla}"
        "<p style='color:#666;font-size:13px;margin-top:16px'>"
        "Se adjunta el informe completo en Excel.</p></div>"
    )
    return texto, cuerpo_html


def enviar_resumen(
    curso: dict[str, Any],
    resultado: dict[str, Any],
    destinatarios: list[str] | None = None,
) -> list[str]:
    """Envía el resumen de avisos del curso. Devuelve los destinatarios usados.

    Se envía también cuando no hay nadie a quien avisar: si solo llegara correo
    los días con avisos, un fallo del proceso sería indistinguible de un día
    tranquilo.
    """
    cfg = _cfg()
    destinos = destinatarios if destinatarios is not None else (curso.get("destinatarios") or [])
    if not destinos:
        raise ErrorCorreo(
            f"El curso {curso['codigo']} no tiene destinatarios configurados. "
            "Añádelos en la página Cursos."
        )

    n = resultado["resumen"]["a_recordar"]
    asunto = (
        f"Seguimiento {curso['codigo']} — "
        + (f"{n} alumno{'s' if n != 1 else ''} a avisar" if n else "sin avisos")
    )

    texto, cuerpo_html = _cuerpo(curso, resultado)

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = cfg["remitente"]
    msg["To"] = ", ".join(destinos)
    msg.set_content(texto)
    msg.add_alternative(cuerpo_html, subtype="html")

    excel = resultado.get("excel")
    if excel:
        msg.add_attachment(
            excel,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=f"seguimiento_{curso['codigo'].replace('/', '-')}_"
            f"{resultado['as_of'].strftime('%Y%m%d')}.xlsx",
        )

    try:
        with smtplib.SMTP(SERVIDOR, PUERTO, timeout=TIMEOUT) as smtp:
            smtp.starttls()
            smtp.login(cfg["api_key"], cfg["secret_key"])
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError as e:
        raise ErrorCorreo(
            "Mailjet ha rechazado las credenciales. Recuerda que el usuario y la "
            "contraseña SMTP son la API key y la secret key, no las de tu cuenta."
        ) from e
    except smtplib.SMTPRecipientsRefused as e:
        raise ErrorCorreo(f"Destinatarios rechazados: {e.recipients}") from e
    except smtplib.SMTPSenderRefused as e:
        raise ErrorCorreo(
            f"Mailjet ha rechazado el remitente «{cfg['remitente']}». "
            "Tiene que estar validado en Senders & Domains."
        ) from e
    except (smtplib.SMTPException, OSError) as e:
        raise ErrorCorreo(f"No se ha podido enviar el correo: {e}") from e

    return destinos
