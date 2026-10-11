import os
from pathlib import Path
from django.conf import settings
import chromadb
from chromadb.config import Settings

from core.models import Product
from core.assistant.embedding_service import embed_texts, embed_query

COLLECTION_NAME = "dealerdesk_products"
# Relevance threshold: in cosine space (distance = 1 - cosine_similarity),
# 0.0 means identical, values <= 0.60 indicate meaningful semantic relevance.
COSINE_DISTANCE_THRESHOLD = 0.65


def get_chroma_client() -> chromadb.PersistentClient:
    chroma_dir = getattr(settings, "CHROMA_PERSIST_DIR", settings.BASE_DIR / "chroma_db")
    os.makedirs(chroma_dir, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def build_product_document(product: Product) -> str:
    """
    Constructs the canonical text representation for embedding generation.
    Does not include stock or price to avoid stale vector state.
    """
    parts = [
        f"SKU: {product.sku}",
        f"Part Name: {product.name}",
        f"Brand: {product.brand}",
        f"Category: {product.category}",
        f"Vehicle Fitment: {product.vehicle_fitment}",
    ]
    if product.description:
        parts.append(f"Description: {product.description}")
    return "\n".join(parts)


def index_all_products(batch_size: int = 100) -> dict:
    """
    Reads all products from PostgreSQL and upserts into ChromaDB.
    Prunes stale IDs not present in the current database.
    """
    collection = get_collection()
    products = list(Product.objects.all())

    if not products:
        # Empty catalogue: clear existing collection
        existing = collection.get()
        if existing and existing["ids"]:
            collection.delete(ids=existing["ids"])
        return {"indexed": 0, "pruned": len(existing["ids"]) if existing else 0}

    current_skus = {p.sku for p in products}

    # 1. Prune stale vectors
    existing = collection.get()
    stale_ids = [id_ for id_ in existing["ids"] if id_ not in current_skus] if existing else []
    if stale_ids:
        collection.delete(ids=stale_ids)

    # 2. Batch upsert
    total_indexed = 0
    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]
        ids = [p.sku for p in batch]
        documents = [build_product_document(p) for p in batch]
        metadatas = [
            {
                "sku": p.sku,
                "name": p.name,
                "brand": p.brand,
                "category": p.category,
                "vehicle_fitment": p.vehicle_fitment,
            }
            for p in batch
        ]
        embeddings = embed_texts(documents)

        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings,
        )
        total_indexed += len(batch)

    return {"indexed": total_indexed, "pruned": len(stale_ids)}


def search_parts_vector(
    query: str,
    vehicle: str = None,
    category: str = None,
    brand: str = None,
    top_k: int = 6,
    distance_threshold: float = COSINE_DISTANCE_THRESHOLD,
) -> list[dict]:
    """
    Performs dense semantic vector search with metadata filters and relevance thresholding.
    Returns matched products with live PostgreSQL data.
    """
    query_clean = query.strip()
    if not query_clean:
        return []

    # 1. Direct SKU exact match shortcut
    exact_product = Product.objects.filter(sku__iexact=query_clean).first()
    if exact_product:
        return [
            {
                "sku": exact_product.sku,
                "name": exact_product.name,
                "brand": exact_product.brand,
                "category": exact_product.category,
                "vehicle_fitment": exact_product.vehicle_fitment,
                "description": exact_product.description,
                "price": str(exact_product.price),
                "stock": exact_product.stock,
                "score": 1.0,
            }
        ]

    collection = get_collection()
    if collection.count() == 0:
        # If collection is empty, trigger indexing
        index_all_products()

    # Build metadata where filter if provided
    where_filter = {}
    conditions = []
    if category:
        conditions.append({"category": {"$eq": category}})
    if brand:
        conditions.append({"brand": {"$eq": brand}})

    if len(conditions) == 1:
        where_filter = conditions[0]
    elif len(conditions) > 1:
        where_filter = {"$and": conditions}

    query_vec = embed_query(query_clean)

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_k * 2, max(collection.count(), 1)),
        where=where_filter if where_filter else None,
        include=["metadatas", "distances"],
    )

    if not results or not results["ids"] or not results["ids"][0]:
        return []

    candidate_ids = results["ids"][0]
    distances = results["distances"][0]

    # Filter by conservative distance threshold
    filtered_skus = []
    for sku, dist in zip(candidate_ids, distances):
        if dist <= distance_threshold:
            filtered_skus.append((sku, 1.0 - dist))

    if not filtered_skus:
        return []

    # Fetch live records from PostgreSQL
    skus_only = [sku for sku, _ in filtered_skus]
    products_by_sku = {p.sku: p for p in Product.objects.filter(sku__in=skus_only)}

    matched = []
    for sku, score in filtered_skus:
        prod = products_by_sku.get(sku)
        if not prod:
            continue

        # If a vehicle filter was explicitly requested, verify compatibility
        if vehicle:
            v_req = vehicle.lower()
            v_fit = prod.vehicle_fitment.lower()
            if v_req not in v_fit and "universal" not in v_fit:
                # Does not match requested vehicle, skip
                continue

        matched.append(
            {
                "sku": prod.sku,
                "name": prod.name,
                "brand": prod.brand,
                "category": prod.category,
                "vehicle_fitment": prod.vehicle_fitment,
                "description": prod.description,
                "price": str(prod.price),
                "stock": prod.stock,
                "score": round(score, 4),
            }
        )

        if len(matched) >= top_k:
            break

    return matched
