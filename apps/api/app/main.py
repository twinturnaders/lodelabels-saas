import json
import os
import asyncio
import traceback
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from standardwebhooks import Webhook

from app.db import engine, get_db, Base
from app.config import settings
from app.models.webhook_event import WebhookEvent
from app.models.print_job import PrintJob

# Create tables on startup (for MVP speed. Use Alembic for production later)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="LodeLabels API")

# Strip the 'wn_wh_' prefix because standardwebhooks expects the raw base64 key
raw_secret = settings.whatnot_webhook_secret
webhook_secret = raw_secret.replace("wn_wh_", "") if raw_secret.startswith("wn_wh_") else raw_secret
wh = Webhook(webhook_secret)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, seller_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[seller_id] = websocket

    def disconnect(self, seller_id: str):
        if seller_id in self.active_connections:
            del self.active_connections[seller_id]

    async def send_print_job(self, seller_id: str, message: dict):
        if seller_id in self.active_connections:
            await self.active_connections[seller_id].send_json(message)

manager = ConnectionManager()

# ✅ TEMPORARY DEBUG ROUTE - DELETE AFTER TESTING
@app.api_route("/debug-webhook", methods=["GET", "POST"])
async def debug_webhook(request: Request):
    body = await request.body()
    headers = dict(request.headers)
    return {
        "method": request.method,
        "path": request.url.path,
        "headers": headers,
        "body_length": len(body),
        "client_ip": request.client.host if request.client else None
    }

# ✅ FIXED: Accepts both GET (Whatnot ping) and POST (real events)
@app.api_route("/webhooks/whatnot", methods=["GET", "POST"])
async def receive_whatnot_webhook(request: Request, db: Session = Depends(get_db)):
    # Respond to Whatnot's connectivity ping
    if request.method == "GET":
        return {"status": "ok"}
    
    # 1. Read raw body (Required for signature verification)
    raw_body = await request.body()
    
    # 2. Extract headers (Standard Webhooks uses lowercase)
    headers = {
        "webhook-id": request.headers.get("webhook-id"),
        "webhook-timestamp": request.headers.get("webhook-timestamp"),
        "webhook-signature": request.headers.get("webhook-signature"),
    }

    # 3. Verify the signature
    # try:
    #     event_data = wh.verify(raw_body, headers)
    # except Exception as e:
    #     print(f"❌ Webhook verification failed: {e}")
    #     raise HTTPException(status_code=400, detail="Invalid signature")

    # 🚨 TEMPORARILY DISABLED TO TEST PIPELINE 🚨
    event_data = json.loads(raw_body)

    # 4. Parse the verified payload
    payload = json.loads(raw_body)
    webhook_id = headers["webhook-id"]
    topic = payload.get("type")
    seller_id = payload.get("seller_id")

    # 5. DEDUPLICATION
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.webhook_id == webhook_id).first()
    if existing_event:
        print(f"⚠️ Duplicate webhook ignored: {webhook_id}")
        return {"status": "duplicate_ignored"}

    # 6. Save to database
    new_event = WebhookEvent(
        id=f"evt_{webhook_id}",
        webhook_id=webhook_id,
        topic=topic,
        seller_id=seller_id,
        payload=payload
    )
    db.add(new_event)
    db.commit()

    print(f"✅ Successfully stored {topic} for seller {seller_id}")

    # 7. Trigger background worker
    if topic == "orders.created":
        asyncio.create_task(process_order_background(new_event.id))

    return {"status": "success"}

@app.get("/labels/{label_id}/file")
async def get_label_file(label_id: str, db: Session = Depends(get_db)):
    from app.models.order import Sale_Label
    sale_label = db.query(Sale_Label).filter(Sale_Label.id == label_id).first()
    if not sale_label or not os.path.exists(sale_label.file_path):
        raise HTTPException(status_code=404, detail="Label not found")
    return FileResponse(sale_label.file_path, media_type="image/png")

@app.websocket("/agent/ws/{seller_id}")
async def websocket_endpoint(websocket: WebSocket, seller_id: str):
    await manager.connect(seller_id, websocket)
    print(f"🔌 Agent connected for seller: {seller_id}")
    try:
        while True:
            data = await websocket.receive_text()
            print(f"📨 Received from agent: {data}")
    except WebSocketDisconnect:
        manager.disconnect(seller_id)
        print(f"❌ Agent disconnected for seller: {seller_id}")

@app.get("/")
def health_check():
    return {"status": "LodeLabels API is alive"}

async def process_order_background(event_id: str):
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        from app.services.order_service import process_order_created
        process_order_created(event_id, db)
        print(f"✅ Order processed successfully for event {event_id}")
    except Exception as e:
        print(f"❌ Error processing order {event_id}: {e}")
        traceback.print_exc()
    finally:
        db.close()