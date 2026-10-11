from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")
TAX_RATE = Decimal("0.18")


def round_money(val: Decimal) -> Decimal:
    return val.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def calculate_line(unit_price: Decimal, quantity: int) -> dict:
    unit_price = round_money(Decimal(str(unit_price)))
    line_subtotal = round_money(unit_price * quantity)
    line_tax = round_money(line_subtotal * TAX_RATE)
    line_total = round_money(line_subtotal + line_tax)
    return {
        "unit_price": unit_price,
        "quantity": quantity,
        "line_subtotal": line_subtotal,
        "line_tax": line_tax,
        "line_total": line_total,
    }


def calculate_order_totals(lines: list[dict]) -> dict:
    subtotal = sum((line["line_subtotal"] for line in lines), Decimal("0.00"))
    tax_total = sum((line["line_tax"] for line in lines), Decimal("0.00"))
    grand_total = round_money(subtotal + tax_total)
    return {
        "subtotal": round_money(subtotal),
        "tax_total": round_money(tax_total),
        "grand_total": grand_total,
    }
