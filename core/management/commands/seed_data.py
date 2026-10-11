import csv
import os
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Product, Dealer


class Command(BaseCommand):
    help = "Load catalogue.csv and dealers.csv into PostgreSQL. Idempotent and safe to run multiple times."

    def handle(self, *args, **options):
        data_dir = settings.DATA_DIR
        catalogue_path = os.path.join(data_dir, "catalogue.csv")
        dealers_path = os.path.join(data_dir, "dealers.csv")

        if not os.path.exists(catalogue_path):
            self.stdout.write(self.style.ERROR(f"Catalogue file not found at {catalogue_path}"))
            return

        if not os.path.exists(dealers_path):
            self.stdout.write(self.style.ERROR(f"Dealers file not found at {dealers_path}"))
            return

        self.stdout.write(f"Seeding catalogue from {catalogue_path}...")
        self.seed_catalogue(catalogue_path)

        self.stdout.write(f"Seeding dealers from {dealers_path}...")
        self.seed_dealers(dealers_path)

        self.stdout.write("Syncing product vector index in ChromaDB...")
        try:
            from core.assistant.vector_store import index_all_products
            res = index_all_products()
            self.stdout.write(f"Vector index synced: {res['indexed']} indexed, {res['pruned']} pruned.")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Vector indexing skipped/deferred: {e}"))

        self.stdout.write(self.style.SUCCESS("Data seeding completed successfully."))

    def seed_catalogue(self, path):
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            created_count = 0
            updated_count = 0

            with transaction.atomic():
                for row in reader:
                    sku = row["sku"].strip()
                    price = Decimal(str(row["price"].strip()))
                    stock = int(row["stock"].strip())

                    product, created = Product.objects.get_or_create(
                        sku=sku,
                        defaults={
                            "name": row["name"].strip(),
                            "category": row["category"].strip(),
                            "brand": row["brand"].strip(),
                            "vehicle_fitment": row["vehicle_fitment"].strip(),
                            "price": price,
                            "stock": stock,
                            "description": row["description"].strip(),
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        # Update metadata fields, preserve live stock
                        product.name = row["name"].strip()
                        product.category = row["category"].strip()
                        product.brand = row["brand"].strip()
                        product.vehicle_fitment = row["vehicle_fitment"].strip()
                        product.price = price
                        product.description = row["description"].strip()
                        product.save(update_fields=[
                            "name", "category", "brand", "vehicle_fitment", "price", "description"
                        ])
                        updated_count += 1

        self.stdout.write(
            f"Catalogue: {created_count} created, {updated_count} updated. Total in DB: {Product.objects.count()}"
        )

    def seed_dealers(self, path):
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            created_count = 0
            updated_count = 0

            with transaction.atomic():
                for row in reader:
                    dealer_code = row["dealer_code"].strip()
                    credit_limit = Decimal(str(row["credit_limit"].strip()))

                    dealer, created = Dealer.objects.get_or_create(
                        dealer_code=dealer_code,
                        defaults={
                            "name": row["name"].strip(),
                            "city": row.get("city", "").strip(),
                            "phone": row.get("phone", "").strip(),
                            "email": row.get("email", "").strip(),
                            "gstin": row.get("gstin", "").strip(),
                            "credit_limit": credit_limit,
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        dealer.name = row["name"].strip()
                        dealer.city = row.get("city", "").strip()
                        dealer.phone = row.get("phone", "").strip()
                        dealer.email = row.get("email", "").strip()
                        dealer.gstin = row.get("gstin", "").strip()
                        dealer.credit_limit = credit_limit
                        dealer.save(update_fields=[
                            "name", "city", "phone", "email", "gstin", "credit_limit"
                        ])
                        updated_count += 1

        self.stdout.write(
            f"Dealers: {created_count} created, {updated_count} updated. Total in DB: {Dealer.objects.count()}"
        )
