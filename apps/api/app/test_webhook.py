import hmac
import base64
import time
import uuid
import json
import urllib.request

# The official test secret from Whatnot docs (raw base64, no 'wn_wh_' prefix)
SECRET_B64 = "AQIDBAUGBwgJCgsMDQ4PEBESExQVFhcYGRobHB0eHyA="
SECRET_BYTES = base64.b64decode(SECRET_B64)

# 1. Create a fake Whatnot payload
payload = {
    "type": "orders.created",
    "timestamp": "2026-11-11T12:00:00.000Z",
    "data": {
        "order_id": f"ord_test_{uuid.uuid4().hex[:8]}", # ✅ NOW UNIQUE EVERY TIME!
        "buyer": {"username": "twinturnaders"}
    },
    "version": "v2",
    "seller_id": "seller_123"
}
# Must be compact JSON (no spaces) for signature to match
payload_json = json.dumps(payload, separators=(',', ':'))

# 2. Generate required headers
webhook_id = str(uuid.uuid4())
webhook_timestamp = str(int(time.time()))

# 3. Sign the payload: HMAC-SHA256 of "{id}.{timestamp}.{body}"
msg = f"{webhook_id}.{webhook_timestamp}.{payload_json}".encode('utf-8')
signature = base64.b64encode(hmac.new(SECRET_BYTES, msg, 'sha256').digest()).decode('utf-8')

# 4. Send the POST request to your running server
req = urllib.request.Request(
    "http://127.0.0.1:8000/webhooks/whatnot",
    data=payload_json.encode('utf-8'),
    headers={
        "Content-Type": "application/json",
        "webhook-id": webhook_id,
        "webhook-timestamp": webhook_timestamp,
        "webhook-signature": f"v1,{signature}"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req) as response:
        print(f"✅ SUCCESS! Status: {response.status}")
        print(f"Response: {response.read().decode('utf-8')}")
except urllib.error.HTTPError as e:
    print(f"❌ FAILED! Status: {e.code}")
    print(f"Response: {e.read().decode('utf-8')}")