from decimal import Decimal
from core.models import Product, Dealer
from core.assistant.vector_store import search_parts_vector
from core.assistant.guardrails import format_grounded_part
from core.services.order_service import create_draft_order
from core.exceptions import ContractAPIException

# Groq / OpenAI compatible Tool Schemas
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_parts",
            "description": (
                "Search the product catalogue for motorcycle and car spare parts using natural language, "
                "vehicle model, category, brand, or SKU code. Returns matching parts with live prices and stock."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language search query, e.g. 'brake pads', 'clutch plate', 'oil filter'.",
                    },
                    "vehicle": {
                        "type": "string",
                        "description": "Vehicle make and model if specified, e.g. 'Bajaj Pulsar 150', 'KTM Duke 390'.",
                    },
                    "category": {
                        "type": "string",
                        "description": "Product category if known, e.g. 'Brakes', 'Filters', 'Lighting & Electrical'.",
                    },
                    "brand": {
                        "type": "string",
                        "description": "Brand filter, e.g. 'Endurance', 'Brembo', 'Bosch'.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "Check current available stock quantity and live catalogue price in PostgreSQL for a specific SKU.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sku": {
                        "type": "string",
                        "description": "The exact product SKU code, e.g. 'BRK-1044'.",
                    },
                },
                "required": ["sku"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_draft_order",
            "description": (
                "Create a new DRAFT order for a dealer. Never confirms the order. "
                "Validates dealer id, SKUs, and quantities."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dealer_id": {
                        "type": "integer",
                        "description": "The numeric ID of the dealer placing the order.",
                    },
                    "items": {
                        "type": "array",
                        "description": "List of line items to order.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "sku": {"type": "string", "description": "Product SKU code."},
                                "quantity": {"type": "integer", "description": "Quantity to order (minimum 1)."},
                            },
                            "required": ["sku", "quantity"],
                        },
                    },
                },
                "required": ["dealer_id", "items"],
            },
        },
    },
]


def execute_tool(name: str, arguments: dict, current_dealer_id: int = None) -> tuple[dict, dict | None]:
    """
    Executes an approved tool by name.
    Returns (tool_result_dict, action_or_none).
    """
    if name == "search_parts":
        query = arguments.get("query", "")
        vehicle = arguments.get("vehicle")
        category = arguments.get("category")
        brand = arguments.get("brand")

        if not query or not isinstance(query, str):
            return {"error": "Missing required string 'query' parameter."}, None

        matches = search_parts_vector(
            query=query,
            vehicle=vehicle,
            category=category,
            brand=brand,
            top_k=5,
        )

        if not matches:
            return {
                "results": [],
                "message": f"No matching parts found for query '{query}'. Ask the dealer for clarification or vehicle details.",
            }, None

        formatted = [format_grounded_part(m) for m in matches]
        return {
            "results_count": len(matches),
            "parts_xml": "\n".join(formatted),
            "skus_found": [m["sku"] for m in matches],
        }, None

    elif name == "check_stock":
        sku = arguments.get("sku", "")
        if not sku or not isinstance(sku, str):
            return {"error": "Missing required 'sku' parameter."}, None

        sku_clean = sku.strip()
        product = Product.objects.filter(sku__iexact=sku_clean).first()
        if not product:
            return {"error": f"Product with SKU '{sku_clean}' does not exist in catalogue."}, None

        return {
            "sku": product.sku,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "vehicle_fitment": product.vehicle_fitment,
            "available_stock": product.stock,
            "current_price": f"₹{product.price}",
            "unit_price_raw": str(product.price),
        }, None

    elif name == "create_draft_order":
        dealer_id = arguments.get("dealer_id") or current_dealer_id
        items = arguments.get("items", [])

        if not dealer_id:
            return {"error": "dealer_id is required to create a draft order."}, None
        if not items or not isinstance(items, list):
            return {"error": "items must be a non-empty list of items."}, None

        try:
            order, created = create_draft_order(dealer_id=int(dealer_id), items_data=items)
            action = {
                "type": "draft_order_created",
                "order_number": order.order_number,
            }
            return {
                "status": "success",
                "order_number": order.order_number,
                "order_status": order.status,
                "subtotal": f"₹{order.subtotal}",
                "tax_total": f"₹{order.tax_total}",
                "grand_total": f"₹{order.grand_total}",
                "items_count": order.items.count(),
                "message": f"Draft order {order.order_number} created successfully.",
            }, action
        except ContractAPIException as e:
            return {"error": f"Failed to create order: {e.message}", "details": e.details}, None
        except Exception as e:
            return {"error": f"Failed to create draft order: {str(e)}"}, None

    else:
        return {"error": f"Unknown tool name: {name}"}, None
