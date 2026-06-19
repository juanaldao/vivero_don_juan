import asyncio
import traceback
import httpx
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
from supabase import create_client
from . import config
from .quotes import ejecutar_armar_presupuesto

openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
anthropic_client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

# In-memory conversation history keyed by "tg:<chat_id>" or "wa:<phone>"
CONVERSATIONS: dict[str, list] = {}

SYSTEM_PROMPT = """\
Sos el asistente virtual del Vivero Don Juan. Ayudás a los clientes a elegir plantas y armar presupuestos.

Para consultas sobre plantas: usá la herramienta buscar_plantas para buscar disponibilidad, precios y cuidados en el catálogo.

Para presupuestos: primero usá buscar_plantas para confirmar qué productos existen y sus precios. Luego pedile al cliente su nombre completo y número de teléfono. Cuando tengas todo, llamá a armar_presupuesto para generar el PDF.

Información de contacto del vivero:
- Dirección: Av. de las Rosas 123, Tigre, Buenos Aires
- Teléfono: +54 9 11 1234-5678
- Web: www.viverodonjuan.com.ar
- Email: contacto@viverodonjuan.com.ar
- Horario: Lunes a Viernes de 8 a 18hs - Sábados de 9 a 18hs

Respondé siempre en español, de forma amable y concisa. No uses markdown en las respuestas.\
"""

TOOLS = [
    {
        "name": "buscar_plantas",
        "description": (
            "Busca plantas en el catálogo del vivero por nombre o descripción. "
            "Retorna información de cuidados, precios y stock disponible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta de búsqueda"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "armar_presupuesto",
        "description": "Genera un presupuesto PDF con los productos seleccionados y los datos del cliente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "Lista de productos a incluir en el presupuesto",
                    "items": {
                        "type": "object",
                        "properties": {
                            "nombre":     {"type": "string", "description": "Nombre común de la planta"},
                            "envase_lts": {"type": "number", "description": "Tamaño del envase en litros"},
                            "cantidad":   {"type": "integer", "description": "Cantidad deseada"},
                        },
                        "required": ["nombre", "cantidad"],
                    },
                },
                "nombre_cliente":   {"type": "string", "description": "Nombre completo del cliente"},
                "telefono_cliente": {"type": "string", "description": "Teléfono del cliente"},
            },
            "required": ["items", "nombre_cliente", "telefono_cliente"],
        },
    },
]


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


async def ejecutar_buscar_plantas(args: dict) -> str:
    embedding = await get_embedding(args["query"])
    plants = await search_plants(embedding)
    plant_ids = [p["plant_id"] for p in plants]
    catalog = await get_catalog(plant_ids) if plant_ids else []
    return build_context(plants, catalog)


async def chatear(history: list, user_text: str) -> tuple[str, str | None]:
    history.append({"role": "user", "content": user_text})
    pdf_url = None

    for _ in range(10):
        resp = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=history,
        )
        history.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn":
            text = next((b.text for b in resp.content if hasattr(b, "text")), "")
            return text, pdf_url

        if resp.stop_reason == "tool_use":
            tool_results = []
            for b in resp.content:
                if b.type != "tool_use":
                    continue
                try:
                    if b.name == "buscar_plantas":
                        content = await ejecutar_buscar_plantas(b.input)
                    elif b.name == "armar_presupuesto":
                        content, pdf_url = await ejecutar_armar_presupuesto(b.input)
                    else:
                        content = "Herramienta desconocida."
                except Exception as e:
                    traceback.print_exc()
                    content = f"Error al ejecutar {b.name}: {e}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": content,
                })
            history.append({"role": "user", "content": tool_results})

    return "Lo siento, ocurrio un error interno.", pdf_url


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


async def send_telegram(chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        await client.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)


async def send_telegram_document(chat_id: str, document_url: str, caption: str = "") -> None:
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            json={"chat_id": chat_id, "document": document_url, "caption": caption},
            timeout=30,
        )


async def process_message(text: str, phone_number: str, phone_number_id: str) -> None:
    history = CONVERSATIONS.setdefault(f"wa:{phone_number}", [])
    reply, pdf_url = await chatear(history, text)
    if reply:
        await send_whatsapp(phone_number_id, phone_number, reply)
    if pdf_url:
        await send_whatsapp(phone_number_id, phone_number, f"Tu presupuesto: {pdf_url}")


async def process_message_telegram(text: str, chat_id: str) -> None:
    history = CONVERSATIONS.setdefault(f"tg:{chat_id}", [])
    reply, pdf_url = await chatear(history, text)
    if reply:
        await send_telegram(chat_id, reply)
    if pdf_url:
        await send_telegram_document(chat_id, pdf_url, caption="Tu presupuesto esta listo")
