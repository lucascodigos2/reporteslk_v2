"""Autenticación con Supabase Auth (email + contraseña).

Las cuentas se dan de alta desde el panel de Supabase (Authentication → Users);
la app no permite registro libre, para que solo entre quien deba.

Nota de seguridad: el cliente de autenticación se crea nuevo en cada intento de
login y NO se cachea. Un cliente compartido entre sesiones guardaría la sesión
del último usuario autenticado y podría filtrarse a otro navegador.
"""

from __future__ import annotations

from typing import Any

import streamlit as st
from supabase import create_client


def _cliente_auth():
    cfg = st.secrets["supabase"]
    key = cfg.get("publishable_key")
    if not key:
        raise RuntimeError(
            "Falta 'publishable_key' en los secrets: es la clave que debe usarse "
            "para autenticar usuarios."
        )
    return create_client(cfg["url"], key)


def usuario_actual() -> dict[str, Any] | None:
    return st.session_state.get("usuario")


def cerrar_sesion() -> None:
    st.session_state.pop("usuario", None)


def _intentar_login(email: str, password: str) -> str | None:
    """Devuelve None si el login fue bien, o un mensaje de error."""
    try:
        res = _cliente_auth().auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
    except Exception as e:  # noqa: BLE001
        texto = str(e).lower()
        if "invalid" in texto or "credentials" in texto:
            return "Email o contraseña incorrectos."
        if "email not confirmed" in texto:
            return (
                "La cuenta existe pero el email no está confirmado. "
                "Confírmalo desde el panel de Supabase."
            )
        return f"No se ha podido iniciar sesión: {e}"

    if not res or not res.user:
        return "Email o contraseña incorrectos."

    st.session_state["usuario"] = {"id": res.user.id, "email": res.user.email}
    return None


def _pantalla_login() -> None:
    st.title("Seguimiento de cursos")
    st.caption("Introduce tus credenciales para acceder.")

    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        enviar = st.form_submit_button("Entrar", type="primary")

    if enviar:
        if not email or not password:
            st.error("Rellena email y contraseña.")
        else:
            error = _intentar_login(email, password)
            if error:
                st.error(error)
            else:
                st.rerun()

    st.caption(
        "¿No tienes acceso? Las cuentas las crea el administrador desde Supabase."
    )


def _barra_usuario() -> None:
    usuario = usuario_actual()
    with st.sidebar:
        st.caption(f"Sesión: **{usuario['email']}**")
        if st.button("Cerrar sesión"):
            cerrar_sesion()
            st.rerun()


def exigir_login() -> None:
    """Bloquea la página si no hay sesión iniciada. Llamar al principio de cada página."""
    if usuario_actual():
        _barra_usuario()
        return
    _pantalla_login()
    st.stop()
