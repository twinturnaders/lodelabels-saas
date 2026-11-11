import json
from fastapi import FastAPI, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from standardwebhooks import Webhook

from app.db import engine, get_db, Base
from app.config import settings
from app.models.webhook_event import WebhookEvent


# Create tables on startup (for MVP speed. Use Alembic for production later)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="LodeLabels API")

# Strip the 'wn_wh_' prefix because standardwebhooks expects the raw base64 key
webhook_secret = settings.whatnot_webhook_secret.replace("wn_wh_", "")
wh = Webhook(webhook_secret)

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
        id=f"evt_{webhook_id}", # Or use UUID
        webhook_id=webhook_id,
        topic=topic,
        seller_id=seller_id,
        payload=payload
    )
    db.add(new_event)
    db.commit()

    print(f"✅ Successfully stored {topic} for seller {seller_id}")

    # 7. TODO: Trigger background worker to process the order and print label
    
    return {"status": "success"}

@app.get("/")
def health_check():
    return {"status": "LodeLabels API is alive"}