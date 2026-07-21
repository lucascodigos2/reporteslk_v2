-- ============================================================================
-- Esquema de la plataforma de seguimiento de cursos
-- Ejecutar en Supabase → SQL Editor → New query → Run
-- ============================================================================
--
-- Seguridad: RLS activado SIN políticas públicas. Solo la clave service_role
-- (que usa el backend de Streamlit desde st.secrets, nunca el navegador) puede
-- leer/escribir. La publishable/anon key NO tiene acceso a estos datos.
-- Cuando se añada login de usuarios (fase posterior) se crearán políticas RLS
-- por usuario.
-- ============================================================================

-- Cursos: se dan de alta subiendo el informe de días lectivos (INF_30)
create table if not exists public.cursos (
    id              uuid primary key default gen_random_uuid(),
    codigo          text not null,
    nombre          text,
    fechas_lectivas jsonb not null default '[]'::jsonb,  -- lista de días lectivos (ISO)
    creado_en       timestamptz not null default now()
);

-- Exámenes/pruebas de cada curso.
-- Se detectan al crear el curso y se CONFIRMAN en la pantalla de validación:
--   - actividad_progreso: nombre exacto de la columna del informe de progreso
--   - cuenta_para_nota:   false para pruebas no calificables (p.ej. proba inicial)
create table if not exists public.examenes (
    id                uuid primary key default gen_random_uuid(),
    curso_id          uuid not null references public.cursos(id) on delete cascade,
    clave             text,          -- EXAME_1, EXAME_FINAL, TEST_1_IGUALDAD...
    nombre            text,          -- nombre mostrado
    actividad_progreso text,         -- columna del progreso a la que se mapea (validación)
    pub_date          date,
    deadline          date,
    cod_mf            text,
    es_final          boolean not null default false,
    es_igualdad       boolean not null default false,
    cuenta_para_nota  boolean not null default true,
    orden             int,
    validado          boolean not null default false,
    creado_en         timestamptz not null default now()
);

create index if not exists examenes_curso_id_idx on public.examenes(curso_id);

-- Activar RLS y no crear políticas: bloquea el acceso público (anon).
alter table public.cursos   enable row level security;
alter table public.examenes enable row level security;
