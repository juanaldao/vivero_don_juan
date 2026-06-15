create or replace function search_plants(
    query_embedding vector(1536),
    match_count      int     default 3,
    min_similarity   float   default 0.3
)
returns table (
    plant_id         int,
    nombre_comun     text,
    nombre_cientifico text,
    categoria        text,
    exposicion_solar text,
    riego            text,
    crecimiento      text,
    facilidad_cultivo text,
    uso_recomendado  text,
    resistencia_frio text,
    descripcion      text,
    similarity       float
)
language sql stable
as $$
    select
        d.plant_id,
        d.nombre_comun,
        d.nombre_cientifico,
        d.categoria,
        d.exposicion_solar,
        d.riego,
        d.crecimiento,
        d.facilidad_cultivo,
        d.uso_recomendado,
        d.resistencia_frio,
        d.descripcion,
        1 - (d.embedding <=> query_embedding) as similarity
    from descripcion d
    where 1 - (d.embedding <=> query_embedding) > min_similarity
    order by d.embedding <=> query_embedding
    limit match_count;
$$;
