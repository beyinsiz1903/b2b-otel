from app.db import db


async def ensure_indexes():
    """Performans indekslerini oluştur.

    Kritik unique indeksler (`matches.request_id`, `password_reset_tokens.token_hash`)
    sessizce yutulmaz — yaratılamazsa açıkça raise eder. Diğer indeksler best-effort.
    """
    await db.matches.create_index("request_id", unique=True)
    await db.password_reset_tokens.create_index("token_hash", unique=True)
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)

    try:
        await db.hotels.create_index("email", unique=True)
        await db.hotels.create_index("region")
        await db.hotels.create_index("approval_status")

        await db.availability_listings.create_index("hotel_id")
        await db.availability_listings.create_index("region")
        await db.availability_listings.create_index("room_type")
        await db.availability_listings.create_index("date_end")
        await db.availability_listings.create_index("availability_status")
        await db.availability_listings.create_index("created_at")
        await db.availability_listings.create_index([("region", 1), ("date_end", -1)])
        await db.availability_listings.create_index([("hotel_id", 1), ("created_at", -1)])

        await db.requests.create_index("from_hotel_id")
        await db.requests.create_index("to_hotel_id")
        await db.requests.create_index("listing_id")
        await db.requests.create_index("status")
        await db.requests.create_index([("from_hotel_id", 1), ("created_at", -1)])
        await db.requests.create_index([("to_hotel_id", 1), ("created_at", -1)])

        await db.matches.create_index("hotel_a_id")
        await db.matches.create_index("hotel_b_id")
        await db.matches.create_index([("hotel_a_id", 1), ("hotel_b_id", 1)])
        await db.matches.create_index("accepted_at")
        await db.matches.create_index("status")

        await db.password_reset_tokens.create_index("hotel_id")

        await db.pms_integrations.create_index("hotel_id", unique=True)
        await db.pms_integrations.create_index("api_key_hash")
        await db.pms_availability_snapshots.create_index("hotel_id")
        await db.pms_availability_snapshots.create_index([("hotel_id", 1), ("received_at", -1)])
        await db.pms_reservation_events.create_index("hotel_id")
        await db.pms_reservation_events.create_index([("hotel_id", 1), ("received_at", -1)])
        await db.availability_listings.create_index([("hotel_id", 1), ("pms_external_ref", 1)], unique=True, sparse=True)

        await db.inventory.create_index("hotel_id")
        await db.inventory.create_index([("hotel_id", 1), ("room_type", 1)])

        await db.daily_availability.create_index("inventory_id")
        await db.daily_availability.create_index("hotel_id")
        await db.daily_availability.create_index("date")
        await db.daily_availability.create_index([("inventory_id", 1), ("date", 1)], unique=True)

        await db.pricing_rules.create_index("hotel_id")
        await db.pricing_rules.create_index([("hotel_id", 1), ("is_active", 1), ("priority", -1)])

        await db.activity_logs.create_index("actor_hotel_id")
        await db.activity_logs.create_index("created_at")

        await db.room_templates.create_index("hotel_id")

        await db.payments.create_index("hotel_id")
        await db.payments.create_index("match_id")
        await db.payments.create_index([("hotel_id", 1), ("status", 1)])

        await db.invoices.create_index("hotel_id")
        await db.invoices.create_index("payment_id")
        await db.invoices.create_index("invoice_number", unique=True)

        await db.subscriptions.create_index("hotel_id")
        await db.subscriptions.create_index([("hotel_id", 1), ("status", 1)])

        await db.notifications.create_index("hotel_id")
        await db.notifications.create_index([("hotel_id", 1), ("is_read", 1)])
        await db.notifications.create_index([("hotel_id", 1), ("created_at", -1)])

        await db.kvkk_requests.create_index("hotel_id")

        await db.pms_outbound_events.create_index("hotel_id")
        await db.pms_outbound_events.create_index([("hotel_id", 1), ("created_at", -1)])
        await db.pms_outbound_events.create_index("status")

    except Exception as e:
        print(f"Index creation warning: {e}")
