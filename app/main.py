import hashlib
import hmac

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from . import config
from .pipeline import process_message

app = FastAPI()


def verify_signature(body: bytes, signature: str) -> bool:
    expected = hmac.new(
        config.KAPSO_WEBHOOK_SECRET.encode(),
        body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()
    sig = request.headers.get("X-Webhook-Signature", "")

    if not verify_signature(body, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-Webhook-Event", "")
    if event != "whatsapp.message.received":
        return {"status": "ignored"}

    payload = await request.json()
    msg = payload.get("message", {})

    if msg.get("type") != "text":
        return {"status": "ignored"}

    text = msg["text"]["body"]
    phone_number = payload["conversation"]["phone_number"]
    phone_number_id = payload["phone_number_id"]

    background_tasks.add_task(process_message, text, phone_number, phone_number_id)
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}
