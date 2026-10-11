import re
from core.models import Product

SKU_PATTERN = re.compile(r"\b[A-Z]{3}-\d{4}\b")
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"NOTE\s+FOR\s+AI(\s+ASSISTANTS?)?:?", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+)?(previous\s+)?instructions?", re.IGNORECASE),
    re.compile(r"\[system\]\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+admin\s+mode", re.IGNORECASE),
    re.compile(r"VIKMO-FREE-\d+", re.IGNORECASE),
    re.compile(r"90%\s+off", re.IGNORECASE),
]


def sanitize_untrusted_text(text: str) -> str:
    """
    Strips known prompt injection phrases from product descriptions
    before injecting them into the LLM context.
    """
    if not text:
        return ""
    sanitized = text
    for pattern in PROMPT_INJECTION_PATTERNS:
        sanitized = pattern.sub("[REDACTED UNTRUSTED CONTENT]", sanitized)
    return sanitized.strip()


def format_grounded_part(part: dict) -> str:
    """
    Formats a part dictionary into a secure, bounded XML-like tag.
    Ensures that price and stock are prominently presented as ground truth.
    """
    desc = sanitize_untrusted_text(part.get("description", ""))
    return (
        f'<part_item sku="{part["sku"]}">'
        f'<name>{part["name"]}</name>'
        f'<brand>{part["brand"]}</brand>'
        f'<category>{part["category"]}</category>'
        f'<fitment>{part["vehicle_fitment"]}</fitment>'
        f'<live_stock>{part["stock"]}</live_stock>'
        f'<live_price>₹{part["price"]}</live_price>'
        f'<description>{desc}</description>'
        f'</part_item>'
    )


def extract_and_validate_cited_skus(text: str, candidates: list[str] = None) -> list[str]:
    """
    Finds all SKU patterns in the assistant reply and verifies against PostgreSQL.
    Every returned SKU is guaranteed to exist in the database.
    """
    found_matches = set(SKU_PATTERN.findall(text or ""))
    if candidates:
        found_matches.update(candidates)

    if not found_matches:
        return []

    # Verify each SKU exists in Product table
    valid_skus = set(
        Product.objects.filter(sku__in=found_matches).values_list("sku", flat=True)
    )

    # Return in order of first appearance in the reply text (or sorted if candidates)
    ordered = []
    for token in text.split():
        cleaned = re.sub(r"[^\w-]", "", token)
        if cleaned in valid_skus and cleaned not in ordered:
            ordered.append(cleaned)

    for sku in valid_skus:
        if sku not in ordered:
            ordered.append(sku)

    return ordered


def post_process_reply(reply: str) -> str:
    """
    Verifies that the reply does not parrot known injection phrases or unauthorized codes.
    """
    cleaned = reply
    if "VIKMO-FREE-90" in cleaned or "90% off" in cleaned.lower():
        cleaned = re.sub(r"VIKMO-FREE-90", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"90%\s+off", "standard catalogue price", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()
