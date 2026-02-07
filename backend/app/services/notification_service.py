import os
import json
from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session
from app.models.finance import PushSubscription

# VAPID keys should be in .env. 
# If not present, we will log a warning.
VAPID_PRIVATE = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {
    "sub": "mailto:christian.zv@cerebro.com"
}

def send_push_notification(subscription_info, data_dict):
    """
    Sends a push notification to a specific subscription.
    """
    if not VAPID_PRIVATE or not VAPID_PUBLIC:
        print("ERROR: VAPID keys not configured. skipping notification.")
        return False

    try:
        response = webpush(
            subscription_info=subscription_info,
            data=json.dumps(data_dict),
            vapid_private_key=VAPID_PRIVATE,
            vapid_claims=VAPID_CLAIMS
        )
        return response.ok
    except WebPushException as ex:
        print(f"Push error: {ex}")
        return False
    except Exception as e:
        print(f"Unexpected push error: {e}")
        return False

def notify_user_new_expense(db: Session, user_id: int, amount: int, concept: str):
    """
    Finds all subscriptions for a user and sends a notification.
    """
    print(f"DEBUG [PUSH] Starting notification for User ID {user_id}...")
    subscriptions = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    
    if not subscriptions:
        print(f"DEBUG [PUSH] ❌ No subscriptions found for user {user_id}")
        return

    print(f"DEBUG [PUSH] Found {len(subscriptions)} subscriptions.")

    payload = {
        "title": "¡Nuevo Gasto Detectado! 💸",
        "body": f"Se detectó un gasto de ${amount:,} en {concept}. Toca para categorizar con Lúcio.",
        "icon": "/icon-512.png",
        "tag": "new-expense",
        "data": {
            "url": "/?view=agent", # Or wherever the agent is
            "type": "gmail_pending"
        }
    }

    for i, sub in enumerate(subscriptions):
        print(f"DEBUG [PUSH] Sending to subscription #{i+1} (ID: {sub.id})...")
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        success = send_push_notification(sub_info, payload)
        if success:
            print(f"DEBUG [PUSH] ✅ Notification sent successfully to {sub.endpoint[:30]}...")
        else:
            print(f"DEBUG [PUSH] ❌ Failed to send to {sub.endpoint[:30]}...")
            # Optional: Delete invalid subscription?
            # db.delete(sub)
            # db.commit()
