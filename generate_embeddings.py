import csv
import json
import os
import time
from datetime import datetime, timezone
from openai import OpenAI

INPUT_FILE = "descripcion.csv"
OUTPUT_FILE = "descripcion.csv"
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 20  # rows per API call


def build_text(row: dict) -> str:
    return (
        f"Nombre: {row['nombre_comun']} ({row['nombre_cientifico']}). "
        f"Categoría: {row['categoria']}. "
        f"Exposición solar: {row['exposicion_solar']}. "
        f"Riego: {row['riego']}. "
        f"Crecimiento: {row['crecimiento']}. "
        f"Facilidad de cultivo: {row['facilidad_cultivo']}. "
        f"Uso recomendado: {row['uso_recomendado']}. "
        f"Resistencia al frío: {row['resistencia_frio']}. "
        f"Descripción: {row['descripcion']}"
    )


def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY before running this script.")

    client = OpenAI(api_key=api_key)
    now = datetime.now(timezone.utc).isoformat()

    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fieldnames = list(rows[0].keys())

    # Skip rows that already have embeddings
    pending = [r for r in rows if not r.get("embedding")]
    print(f"{len(pending)} rows need embeddings (out of {len(rows)} total)")

    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        texts = [build_text(r) for r in batch]

        response = client.embeddings.create(model=EMBEDDING_MODEL, input=texts)

        for row, emb_obj in zip(batch, response.data):
            row["embedding"] = json.dumps(emb_obj.embedding)
            if not row.get("created_at"):
                row["created_at"] = now

        print(f"  Embedded rows {i + 1}–{i + len(batch)}")
        if i + BATCH_SIZE < len(pending):
            time.sleep(0.5)  # stay well within rate limits

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. {OUTPUT_FILE} updated.")


if __name__ == "__main__":
    main()
