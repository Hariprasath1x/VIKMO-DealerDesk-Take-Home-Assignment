import zoneinfo
from django.db import transaction
from django.utils import timezone
from core.models import OrderDailySequence


def get_next_order_number() -> str:
    kolkata_tz = zoneinfo.ZoneInfo("Asia/Kolkata")
    now_ist = timezone.now().astimezone(kolkata_tz)
    date_val = now_ist.date()
    date_str = date_val.strftime("%Y%m%d")

    with transaction.atomic():
        seq_obj, _ = OrderDailySequence.objects.select_for_update().get_or_create(
            date=date_val,
            defaults={"last_sequence": 0},
        )
        seq_obj.last_sequence += 1
        seq_obj.save(update_fields=["last_sequence"])
        seq_num = seq_obj.last_sequence

    return f"ORD-{date_str}-{seq_num:04d}"
