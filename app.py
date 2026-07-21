"""Plataforma de seguimiento de cursos — enrutado y sesión."""

from __future__ import annotations

import streamlit as st

from core import auth

st.set_page_config(
    page_title="Seguimiento de cursos",
    page_icon="▪",
    layout="wide",
    initial_sidebar_state="auto",
)

ESTILO = """
<style>
/* Ocultar cromo sobrante de Streamlit */
#MainMenu, footer, [data-testid="stDecoration"] {visibility: hidden; height: 0;}

.block-container {padding-top: 3rem; max-width: 1150px;}

/* Cabecera de página */
.titulo-pagina {
  font-size: 1.6rem;
  font-weight: 600;
  margin: 0 0 .2rem 0;
}
.subtitulo-pagina {
  color: #9a9a9a;
  font-size: .92rem;
  margin: 0 0 1.6rem 0;
}

/* Pantalla de acceso */
.marca {
  font-size: 1.7rem;
  font-weight: 600;
  margin-top: 3.5rem;
  border-top: 2px solid #BC3A2B;
  padding-top: 1.1rem;
}
.marca-sub {color: #9a9a9a; font-size: .92rem; margin-bottom: 1.8rem;}

/* Etiquetas de estado */
.chip {
  display: inline-block;
  font-size: .72rem;
  padding: .14rem .55rem;
  border-radius: 999px;
  font-weight: 600;
  letter-spacing: .02em;
}
.chip-ok   {background: rgba(60,160,90,.18);  color: #7ddba1;}
.chip-warn {background: rgba(230,160,30,.18); color: #ecc06a;}
</style>
"""
st.markdown(ESTILO, unsafe_allow_html=True)


if not auth.usuario_actual():
    # Sin sesión: solo la pantalla de acceso, sin menú lateral.
    st.markdown(
        "<style>[data-testid='stSidebar']{display:none;}</style>",
        unsafe_allow_html=True,
    )
    st.navigation(
        [st.Page(auth.pagina_login, title="Entrar")], position="hidden"
    ).run()
else:
    navegacion = st.navigation(
        [
            st.Page("vistas/cursos.py", title="Cursos", icon=":material/school:", default=True),
            st.Page("vistas/validacion.py", title="Validación", icon=":material/fact_check:"),
            st.Page("vistas/seguimiento.py", title="Seguimiento", icon=":material/monitoring:"),
        ]
    )
    auth.barra_usuario()
    navegacion.run()
