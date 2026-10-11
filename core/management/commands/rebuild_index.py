from django.core.management.base import BaseCommand
from core.assistant.vector_store import index_all_products


class Command(BaseCommand):
    help = "Rebuild or update the ChromaDB vector index from PostgreSQL catalogue products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=100,
            help="Number of products to embed and upsert per batch (default: 100).",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        self.stdout.write(f"Indexing products into ChromaDB with batch size {batch_size}...")
        res = index_all_products(batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                f"Vector index updated successfully: {res['indexed']} products indexed, "
                f"{res['pruned']} stale vectors pruned."
            )
        )
