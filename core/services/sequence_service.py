import zoneinfo
from django.db import transaction, connection
from django.utils import timezone
from core.models import OrderDailySequence


def get_next_order_number() -> str:
    kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = timezone.now().astimezone(kolkata_tz)
    date_val = now_ist.date()
    date_str = date_val.strftime("%Y%m%d")

    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"seq_{date_str}"])

        seq_obj = OrderDailySequence.objects.select_for_update().filter(date=date_val).first()
        if not seq_obj:
            seq_obj, _ = OrderDailySequence.objects.get_or_create(
                date=date_val,
                defaults={"last_sequence": 0},
            )
            seq_obj = OrderDailySequence.objects.select_for_update().get(date=date_val)

        seq_obj.last_sequence += 1
        seq_obj.save(update_fields=["last_sequence"])
        seq_num = seq_obj.last_sequence

    return f"ORD-{date_str}-{seq_num:04d}"
