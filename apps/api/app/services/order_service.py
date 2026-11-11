from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.order import Order, SaleLabel, ShowCounter, BuyerNumber
from app.models.webhook_event import WebhookEvent
from app.services.label_service import create_text_label, LABELS_DIR

def process_order_created(event_id: str, db: Session):
    # 1. Fetch the event
    event = db.get(WebhookEvent, event_id)
    if not event or event.processed:
        return

    payload = event.payload
    seller_id = payload.get("seller_id")
    order_data = payload.get("data", {})
    
    # Extract buyer username (fallback to "unknown" if API structure changes)
    buyer = order_data.get("buyer", {})
    username = buyer.get("username") or buyer.get("display_name", "unknown").replace("@", "")
    whatnot_order_id = order_data.get("order_id", "unknown")

    # 2. Check for duplicate order
    existing_order = db.query(Order).filter(Order.whatnot_order_id == whatnot_order_id).first()
    if existing_order:
        print(f"⚠️ Order {whatnot_order_id} already processed. Skipping to prevent duplicate labels.")
        event.processed = True
        db.commit()
        return

    # 3. Save the normalized Order
    order = Order(
        id=f"ord_{whatnot_order_id}",
        seller_id=seller_id,
        whatnot_order_id=whatnot_order_id,
        buyer_username=username,
        raw_payload=payload
    )
    db.add(order)
    db.flush() # Get the order.id

    # 4. Get or Create Buyer Number (with upsert logic)
    buyer_record = db.get(BuyerNumber, (seller_id, username))
    if not buyer_record:
        # Get current counter
        counter = db.get(ShowCounter, seller_id)
        if not counter:
            counter = ShowCounter(seller_id=seller_id, next_item_number=1, next_buyer_number=1)
            db.add(counter)
            db.flush()
        
        new_buyer_num = counter.next_buyer_number
        counter.next_buyer_number += 1
        
        buyer_record = BuyerNumber(
            seller_id=seller_id,
            buyer_username=username,
            buyer_number=new_buyer_num
        )
        db.add(buyer_record)
    
    current_buyer_number = buyer_record.buyer_number

    # 5. Get Next Item Number
    counter = db.get(ShowCounter, seller_id)
    if not counter:
        counter = ShowCounter(seller_id=seller_id, next_item_number=1, next_buyer_number=1)
        db.add(counter)
        db.flush()
    
    current_item_number = counter.next_item_number
    counter.next_item_number += 1

    # 6. Generate the Label PNG
    safe_username = username.replace("/", "_").replace("\\", "_")
    file_name = f"item_{current_item_number:03d}_buyer_{current_buyer_number:02d}_{safe_username}.png"
    output_path = LABELS_DIR / file_name

    create_text_label(
        top_text=f"ITEM {current_item_number:03d}",
        buyer_number=current_buyer_number,
        username=username,
        output_path=output_path
    )

    # 7. Save the SaleLabel Record
    sale_label = SaleLabel(
        id=f"lbl_{current_item_number}_{current_buyer_number}_{safe_username}",
        order_id=order.id,
        seller_id=seller_id,
        item_number=current_item_number,
        buyer_number=current_buyer_number,
        buyer_username=username,
        file_path=str(output_path),
        status="generated"
    )
    db.add(sale_label)
    db.flush() # Get the sale_label.id

    # 8. Create the Print Job
    from app.models.print_job import PrintJob
    print_job = PrintJob(
        id=f"job_{sale_label.id}",
        label_id=sale_label.id,
        seller_id=seller_id,
        status="queued"
    )
    db.add(print_job)

    # 9. Mark event as processed
    event.processed = True
    db.commit()

    # 10. Push to WebSocket!
    import asyncio
    from app.main import manager
    asyncio.create_task(
        manager.send_print_job(seller_id, {
            "type": "print_job",
            "job_id": print_job.id,
            "label_id": sale_label.id,
            "image_url": f"http://127.0.0.1:8000/labels/{sale_label.id}/file",
            "username": username,
            "item_number": current_item_number
        })
    )
    print(f"✅ Generated Label and queued print job for @{username}")