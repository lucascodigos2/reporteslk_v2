# Plataforma de seguimiento de cursos

Aplicación en Streamlit para dar de alta cursos (a partir del informe de días
lectivos INF_30) y llevar el seguimiento de finalización de actividades de
varios cursos a la vez, con los datos persistidos en Supabase.

> Estado: **Fase 1** — alta y gestión de cursos. Pendiente: pantalla de
> validación de exámenes, cruce con el informe de progreso y multiusuario.

## Estructura

```
app.py                 # página principal (lista de cursos)
pages/1_Cursos.py      # alta y borrado de cursos
core/
  db.py                # acceso a Supabase
  calendario.py        # detección de exámenes desde el INF_30
  seguimiento.py       # lógica de clasificación/Excel (del proyecto original)
schema.sql             # tablas de la base de datos
requirements.txt
.streamlit/
  config.toml          # tema visual
  secrets.toml         # credenciales (NO se sube al repo)
```

## Puesta en marcha (local)

1. **Crear las tablas**: en Supabase → *SQL Editor* → pega el contenido de
   `schema.sql` y ejecútalo.
2. **Credenciales**: en Supabase → *Project Settings → API*, copia la
   `service_role` key y pégala en `.streamlit/secrets.toml` (campo
   `service_key`). Ese fichero está en `.gitignore` y no se sube.
3. **Instalar y arrancar**:
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```

## Despliegue en Streamlit Cloud

1. Sube este repo a GitHub (ver abajo).
2. En share.streamlit.io crea la app apuntando a `app.py`.
3. En *Settings → Secrets* pega el mismo contenido de `secrets.toml`
   (con la `service_key` real).

## Subir a un repo nuevo

Desde esta carpeta:

```
git init
git add .
git commit -m "Fase 1: alta y gestión de cursos"
git branch -M main
git remote add origin <URL-de-tu-repo-nuevo>
git push -u origin main
```

`secrets.toml` no se subirá gracias a `.gitignore`. Verifícalo con
`git status` antes del primer push.
