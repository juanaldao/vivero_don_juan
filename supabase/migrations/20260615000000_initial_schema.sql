-- Enable pgvector for semantic search
create extension if not exists vector;

-- Plant master data
create table descripcion (
    plant_id          integer primary key,
    nombre_cientifico text not null,
    nombre_comun      text not null,
    categoria         text,
    exposicion_solar  text,
    riego             text,
    crecimiento       text,
    facilidad_cultivo text,
    uso_recomendado   text,
    resistencia_frio  text,
    descripcion       text,
    embedding         vector(1536),
    created_at        timestamptz default now()
);

-- Vector similarity index (cosine distance)
create index on descripcion using hnsw (embedding vector_cosine_ops);

-- Product variants / catalog
create table catalogo (
    variante_id       integer primary key,
    plant_id          integer references descripcion(plant_id),
    nombre_comun      text,
    nombre_cientifico text,
    tamano_envase_lts numeric,
    precio            numeric,
    stock             integer,
    elegibilidad      integer
);

create index on catalogo (plant_id);
