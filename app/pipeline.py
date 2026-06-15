import asyncio
import httpx
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from supabase import create_client
from . import config

openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
anthropic_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

SYSTEM_PROMPT = """\
Sos el asistente virtual del Vivero Don Juan. Ayudás a los clientes con:
- Información sobre plantas: cuidados, riego, exposición solar, crecimiento, usos.
- Precios y disponibilidad de stock.
- Presupuestos (presupuestos): listá las plantas pedidas con tamaño de envase, precio y stock.

Usá únicamente el contexto de plantas provisto. Si no hay información suficiente, decilo claramente.
Respondé siempre en español, de forma amable y concisa. No uses markdown en las respuestas.\
"""


async def get_embedding(text: str) -> list[float]:
    resp = await openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return resp.data[0].embedding


async def search_plants(embedding: list[float]) -> list[dict]:
    result = await asyncio.to_thread(
        lambda: supabase.rpc(
            "search_plants",
            {"query_embedding": embedding, "match_count": 3},
        ).execute()
    )
    return result.data or []


async def get_catalog(plant_ids: list[int]) -> list[dict]:
    result = await asyncio.to_thread(
        lambda: supabase.table("catalogo")
        .select("*")
        .in_("plant_id", plant_ids)
        .execute()
    )
    return result.data or []


def build_context(plants: list[dict], catalog: list[dict]) -> str:
    if not plants:
        return "No se encontraron plantas relevantes en el catálogo."

    catalog_by_plant: dict[int, list[dict]] = {}
    for item in catalog:
        catalog_by_plant.setdefault(item["plant_id"], []).append(item)

    lines = []
    for p in plants:
        lines.append(f"{p['nombre_comun']} ({p['nombre_cientifico']})")
        lines.append(f"  Categoría: {p['categoria']} | Solar: {p['exposicion_solar']} | Riego: {p['riego']}")
        lines.append(f"  Crecimiento: {p['crecimiento']} | Dificultad: {p['facilidad_cultivo']}")
        lines.append(f"  Uso: {p['uso_recomendado']} | Resistencia al frío: {p['resistencia_frio']}")
        lines.append(f"  {p['descripcion']}")

        variants = catalog_by_plant.get(p["plant_id"], [])
        if variants:
            lines.append("  Variantes:")
            for v in sorted(variants, key=lambda x: x["tamano_envase_lts"]):
                lines.append(
                    f"    - Envase {v['tamano_envase_lts']}L: ${v['precio']:,.0f} "
                    f"(stock: {v['stock']})"
                )
        lines.append("")

    return "\n".join(lines)


async def send_whatsapp(phone_number_id: str, to: str, text: str) -> None:
    # Kapso expects E.164 without leading +
    to = to.lstrip("+")
    url = f"{config.KAPSO_API_BASE_URL}/meta/whatsapp/v24.0/{phone_number_id}/messages"
    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            headers={"X-API-Key": config.KAPSO_API_KEY},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
            timeout=10,
        )


async def process_message(text: str, phone_number: str, phone_number_id: str) -> None:
    embedding = await get_embedding(text)
    plants = await search_plants(embedding)
    plant_ids = [p["plant_id"] for p in plants]
    catalog = await get_catalog(plant_ids) if plant_ids else []
    context = build_context(plants, catalog)

    response = await anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Contexto de plantas relevantes:\n{context}\n\nConsulta: {text}",
            }
        ],
    )
    reply = response.content[0].text
    await send_whatsapp(phone_number_id, phone_number, reply)
