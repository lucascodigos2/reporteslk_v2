# Plataforma de seguimiento de cursos

Aplicación en Streamlit para dar de alta cursos (a partir del informe de días
lectivos INF_30) y llevar el seguimiento de finalización de actividades de
varios cursos a la vez, con los datos persistidos en Supabase.

> Estado: **Fase 4** — acceso con login, alta de cursos, validación de pruebas,
> seguimiento e histórico.

## Flujo de uso

1. **Cursos** — subes el informe de días lectivos (INF_30) y se da de alta el
   curso con sus exámenes y plazos detectados.
2. **Validación** — subes el informe de progreso y confirmas qué actividad
   corresponde a cada examen, marcando las pruebas no calificables (p. ej. la
   proba inicial). El mapa se guarda y se reutiliza.
3. **Seguimiento** — subes el progreso cuando quieras: ves a quién avisar hoy,
   descargas el Excel completo y cada subida queda en el histórico.

## Dar de alta profesores

La app no permite registro libre. Las cuentas se crean desde
**Supabase → Authentication → Users → Add user**, marcando *Auto Confirm User*
para que puedan entrar sin verificar el email.

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
