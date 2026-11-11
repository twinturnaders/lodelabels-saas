import json
import os
import asyncio
import traceback
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import FileResponse
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
webhook_secret = settings.whatnot_webhook_secret.replace("wn_wh_", "")
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

@app.post("/webhooks/whatnot")
async def receive_whatnot_webhook(request: Request, db: Session = Depends(get_db)):
    # 1. Read raw body (Required for signature verification)
    raw_body = await request.body()
    
    # 2. Extract headers
    headers = {
        "webhook-id": request.headers.get("webhook-id"),
        "webhook-timestamp": request.headers.get("webhook-timestamp"),
        "webhook-signature": request.headers.get("webhook-signature"),
    }

    # 3. Verify the signature (Rejects if fake or tampered)
    try:
        event_data = wh.verify(raw_body, headers)
    except Exception as e:
        print(f"Webhook verification failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # 4. Parse the verified payload
    payload = json.loads(raw_body)
    webhook_id = headers["webhook-id"]
    topic = payload.get("type")
    seller_id = payload.get("seller_id")

    # 5. DEDUPLICATION: Check if we already processed this exact webhook ID
    existing_event = db.query(WebhookEvent).filter(WebhookEvent.webhook_id == webhook_id).first()
    if existing_event:
        print(f"Duplicate webhook ignored: {webhook_id}")
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

    # 7. Trigger background worker to process the order and print label
    if topic == "orders.created":
        asyncio.create_task(process_order_background(new_event.id))

    return {"status": "success"}

@app.get("/labels/{label_id}/file")
async def get_label_file(label_id: str, db: Session = Depends(get_db)):
    from app.models.order import SaleLabel
    sale_label = db.query(SaleLabel).filter(SaleLabel.id == label_id).first()
    if not sale_label or not os.path.exists(sale_label.file_path):
        raise HTTPException(status_code=404, detail="Label not found")
    return FileResponse(sale_label.file_path, media_type="image/png")

@app.websocket("/agent/ws/{seller_id}")
async def websocket_endpoint(websocket: WebSocket, seller_id: str):
    await manager.connect(seller_id, websocket)
    print(f"🔌 Agent connected for seller: {seller_id}")
    try:
        while True:
            # Keep the connection alive and listen for acks
            data = await websocket.receive_text()
            print(f"Received from agent: {data}")
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
    except Exception as e:
        print(f"❌ Error processing order: {e}")
        traceback.print_exc()
    finally:
        db.close()