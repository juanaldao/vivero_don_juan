import csv
import json
import os
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
BATCH_SIZE = 50


def load_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def insert_batches(client, table, rows):
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        client.table(table).insert(batch).execute()
        print(f"  {table}: inserted rows {i + 1}–{i + len(batch)}")


def main():
    client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # --- descripcion ---
    print("Loading descripcion...")
    desc_rows = load_csv("descripcion.csv")
    if not desc_rows[0].get("embedding"):
        raise SystemExit("Run generate_embeddings.py first — embedding column is empty.")

    desc_insert = []
    for r in desc_rows:
        desc_insert.append({
            "plant_id":          int(r["plant_id"]),
            "nombre_cientifico": r["nombre_cientifico"],
            "nombre_comun":      r["nombre_comun"],
            "categoria":         r["categoria"] or None,
            "exposicion_solar":  r["exposicion_solar"] or None,
            "riego":             r["riego"] or None,
            "crecimiento":       r["crecimiento"] or None,
            "facilidad_cultivo": r["facilidad_cultivo"] or None,
            "uso_recomendado":   r["uso_recomendado"] or None,
            "resistencia_frio":  r["resistencia_frio"] or None,
            "descripcion":       r["descripcion"] or None,
            "embedding":         json.loads(r["embedding"]),  # list[float]
            "created_at":        r["created_at"] or None,
        })

    insert_batches(client, "descripcion", desc_insert)

    # --- catalogo ---
    print("Loading catalogo...")
    cat_rows = load_csv("catalogo.csv")

    cat_insert = []
    for r in cat_rows:
        cat_insert.append({
            "variante_id":       int(r["variante_id"]),
            "plant_id":          int(r["plant_id"]),
            "nombre_comun":      r["nombre_comun"] or None,
            "nombre_cientifico": r["nombre_cientifico"] or None,
            "tamano_envase_lts": float(r["tamano_envase_lts"]) if r["tamano_envase_lts"] else None,
            "precio":            float(r["precio"]) if r["precio"] else None,
            "stock":             int(r["stock"]) if r["stock"] else None,
            "elegibilidad":      int(r["elegibilidad"]) if r["elegibilidad"] else None,
        })

    insert_batches(client, "catalogo", cat_insert)
    print("Done.")


if __name__ == "__main__":
    main()
