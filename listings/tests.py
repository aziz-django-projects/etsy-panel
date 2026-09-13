from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from etsy.models import EtsyAccount
from inventory.models import (
    InventoryProduct,
    InventoryRecipeItem,
    InventoryVariation,
    StockBucket,
    StockMovement,
)
from inventory.services import apply_stock_for_order_transition
from orders.models import Order, OrderItem
from .models import Listing, ListingVariation
from .services import sync_active_listings


class ListingSyncTests(TestCase):
    @patch("listings.services.EtsyClient")
    def test_batch_sync_updates_listings_and_keeps_missing_variation_history(self, client_class):
        user = get_user_model().objects.create_user(username="seller", password="test")
        EtsyAccount.objects.create(user=user, shop_id=42)
        listing = Listing.objects.create(owner=user, etsy_listing_id=11)
        ListingVariation.objects.create(listing=listing, etsy_product_id=100, label="Old")

        client = client_class.return_value
        client.get_active_listings.return_value = {
            "count": 2,
            "results": [
                {"listing_id": 11, "title": "First", "quantity": 3},
                {"listing_id": 22, "title": "Second", "quantity": 4},
            ],
        }
        client.get_listings_with_images.return_value = {
            "results": [
                {"listing_id": 11, "images": [{"url_170x135": "https://example.com/first.jpg"}]},
                {"listing_id": 22, "images": []},
            ]
        }
        client.get_listings_inventory_batch.return_value = {
            "results": [
                {"listing_id": 11, "inventory": {"products": [
                    {"product_id": 101, "property_values": [{"values": ["Blue"], "value_ids": [7]}]},
                ]}},
                {"listing_id": 22, "inventory": None},
            ]
        }

        result = sync_active_listings(user)

        self.assertEqual(result, {
            "listings_synced": 2,
            "variation_sync_ok": 2,
            "variation_sync_failed": 0,
        })
        client.get_active_listings.assert_called_once_with(shop_id=42, limit=50, offset=0)
        client.get_listings_with_images.assert_called_once_with([11, 22])
        client.get_listings_inventory_batch.assert_called_once_with([11, 22])
        listing.refresh_from_db()
        self.assertEqual(listing.image_url_170x135, "https://example.com/first.jpg")
        self.assertEqual(
            list(
                listing.variations.filter(is_deleted=False).values_list(
                    "etsy_product_id", "label"
                )
            ),
            [(101, "Blue")],
        )
        self.assertTrue(
            listing.variations.get(etsy_product_id=100).is_deleted
        )
        self.assertTrue(Listing.objects.filter(etsy_listing_id=22).exists())


@override_settings(INVENTORY_CATALOG_SYNC_ENABLED=True)
class InventoryCatalogSyncTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="seller", password="test"
        )
        EtsyAccount.objects.create(user=self.user, shop_id=42)

    def set_etsy_response(self, client, *, title="Pennant", products=None, inventory=True):
        client.get_active_listings.return_value = {
            "count": 1,
            "results": [{"listing_id": 11, "title": title}],
        }
        client.get_listings_with_images.return_value = {"results": []}
        client.get_listings_inventory_batch.return_value = {
            "results": [
                {
                    "listing_id": 11,
                    "inventory": {"products": products or []} if inventory else None,
                }
            ]
        }

    @patch("listings.services.EtsyClient")
    def test_new_variation_is_pending_and_repeated_sync_is_idempotent(self, client_class):
        client = client_class.return_value
        self.set_etsy_response(client, products=[{
            "product_id": 101,
            "property_values": [{
                "property_id": 1,
                "values": ["Blue"],
                "value_ids": [7],
            }],
        }])

        sync_active_listings(self.user)
        sync_active_listings(self.user)

        product = InventoryProduct.objects.get(owner=self.user, etsy_listing_id=11)
        variation = product.variations.get(etsy_product_id=101)
        self.assertEqual(product.name, "Pennant")
        self.assertEqual(variation.name, "Blue")
        self.assertEqual(variation.etsy_property_ids, [1])
        self.assertEqual(variation.etsy_value_ids, [7])
        self.assertEqual(InventoryProduct.objects.count(), 1)
        self.assertEqual(InventoryVariation.objects.count(), 1)
        self.assertEqual(StockBucket.objects.count(), 0)
        self.assertEqual(InventoryRecipeItem.objects.count(), 0)

        self.client.force_login(self.user)
        response = self.client.get("/inventory/")
        self.assertContains(response, "Stok reçetesi bekleyen varyasyonlar")
        self.assertContains(response, "Blue")

        order = Order.objects.create(
            owner=self.user, etsy_order_id=89, status=Order.Status.SHIPPED
        )
        OrderItem.objects.create(
            order=order, etsy_listing_id=11, quantity=1,
            variation_raw=[{"property_id": 1, "value_id": 7}],
        )
        apply_stock_for_order_transition(order, Order.Status.RECEIVED, False)
        self.assertEqual(StockMovement.objects.count(), 0)

    @patch("listings.services.EtsyClient")
    def test_legacy_name_match_preserves_locally_disabled_variation(self, client_class):
        product = InventoryProduct.objects.create(
            owner=self.user, etsy_listing_id=11, name="Old title", is_active=False
        )
        variation = InventoryVariation.objects.create(
            product=product, name="Blue", is_active=False
        )
        self.set_etsy_response(client_class.return_value, products=[{
            "product_id": 101,
            "property_values": [{"values": ["Blue"], "value_ids": [7]}],
        }])

        sync_active_listings(self.user)

        product.refresh_from_db()
        variation.refresh_from_db()
        self.assertEqual(product.name, "Pennant")
        self.assertFalse(product.is_active)
        self.assertFalse(variation.is_active)
        self.assertEqual(variation.etsy_product_id, 101)
        self.assertEqual(InventoryVariation.objects.count(), 1)

    @patch("listings.services.EtsyClient")
    def test_rename_preserves_recipe_stock_and_order_matching(self, client_class):
        product = InventoryProduct.objects.create(
            owner=self.user, etsy_listing_id=11, name="Old title"
        )
        bucket = StockBucket.objects.create(
            owner=self.user, product=product, name="Small", quantity=12
        )
        variation = InventoryVariation.objects.create(
            product=product,
            name="Blue",
            etsy_value_ids=[7],
        )
        recipe = InventoryRecipeItem.objects.create(
            variation=variation, bucket=bucket, quantity=2
        )

        client = client_class.return_value
        self.set_etsy_response(client, title="New title", products=[{
            "product_id": 101,
            "property_values": [{
                "property_id": 1,
                "values": ["Navy"],
                "value_ids": [7],
            }],
        }])
        sync_active_listings(self.user)
        sync_active_listings(self.user)

        product.refresh_from_db()
        variation.refresh_from_db()
        bucket.refresh_from_db()
        self.assertEqual(product.name, "New title")
        self.assertEqual(variation.name, "Navy")
        self.assertEqual(variation.etsy_product_id, 101)
        self.assertEqual(variation.etsy_property_ids, [1])
        self.assertEqual(InventoryVariation.objects.count(), 1)
        self.assertTrue(InventoryRecipeItem.objects.filter(pk=recipe.pk).exists())
        self.assertEqual(bucket.quantity, 12)

        order = Order.objects.create(
            owner=self.user, etsy_order_id=88, status=Order.Status.SHIPPED
        )
        OrderItem.objects.create(
            order=order,
            etsy_listing_id=11,
            quantity=2,
            variation_label="Blue",
            variation_raw=[{"property_id": 1, "value_id": 7}],
        )
        apply_stock_for_order_transition(order, Order.Status.RECEIVED, False)
        bucket.refresh_from_db()
        self.assertEqual(bucket.quantity, 8)

        self.set_etsy_response(client, products=[])
        sync_active_listings(self.user)
        variation.refresh_from_db()
        self.assertFalse(variation.etsy_available)
        self.assertTrue(variation.is_active)
        self.assertTrue(InventoryRecipeItem.objects.filter(pk=recipe.pk).exists())

        order.canceled = True
        order.save(update_fields=["canceled"])
        apply_stock_for_order_transition(order, Order.Status.SHIPPED, False)
        bucket.refresh_from_db()
        self.assertEqual(bucket.quantity, 12)
        self.assertEqual(StockMovement.objects.count(), 2)

    @patch("listings.services.EtsyClient")
    def test_null_inventory_does_not_remove_existing_variations(self, client_class):
        listing = Listing.objects.create(owner=self.user, etsy_listing_id=11)
        ListingVariation.objects.create(
            listing=listing, etsy_product_id=101, label="Blue"
        )
        product = InventoryProduct.objects.create(
            owner=self.user, etsy_listing_id=11, name="Old title"
        )
        variation = InventoryVariation.objects.create(
            product=product, name="Blue", etsy_product_id=101
        )
        self.set_etsy_response(client_class.return_value, inventory=False)

        sync_active_listings(self.user)

        product.refresh_from_db()
        variation.refresh_from_db()
        self.assertEqual(product.name, "Pennant")
        self.assertTrue(variation.etsy_available)
        self.assertFalse(
            ListingVariation.objects.get(etsy_product_id=101).is_deleted
        )

    def test_ambiguous_variation_ids_do_not_deduct_stock(self):
        product = InventoryProduct.objects.create(
            owner=self.user, etsy_listing_id=11, name="Pennant"
        )
        for index, name in enumerate(("Blue", "Azure"), start=1):
            variation = InventoryVariation.objects.create(
                product=product, name=name,
                etsy_property_ids=[1], etsy_value_ids=[7],
            )
            bucket = StockBucket.objects.create(
                owner=self.user, product=product,
                name=f"Bucket {index}", quantity=10,
            )
            InventoryRecipeItem.objects.create(
                variation=variation, bucket=bucket, quantity=1
            )
        order = Order.objects.create(
            owner=self.user, etsy_order_id=90, status=Order.Status.SHIPPED
        )
        OrderItem.objects.create(
            order=order, etsy_listing_id=11, quantity=1,
            variation_raw=[{"property_id": 1, "value_id": 7}],
        )

        apply_stock_for_order_transition(order, Order.Status.RECEIVED, False)

        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertTrue(all(
            quantity == 10 for quantity in StockBucket.objects.values_list(
                "quantity", flat=True
            )
        ))


@override_settings(INVENTORY_CATALOG_SYNC_ENABLED=False)
class DisabledInventoryCatalogSyncTests(TestCase):
    @patch("listings.services.EtsyClient")
    def test_sync_does_not_change_inventory_when_switch_is_off(self, client_class):
        user = get_user_model().objects.create_user(username="seller", password="test")
        EtsyAccount.objects.create(user=user, shop_id=42)
        client = client_class.return_value
        client.get_active_listings.return_value = {
            "count": 1, "results": [{"listing_id": 11, "title": "Pennant"}]
        }
        client.get_listings_with_images.return_value = {"results": []}
        client.get_listings_inventory_batch.return_value = {"results": [{
            "listing_id": 11, "inventory": {"products": [{
                "product_id": 101,
                "property_values": [{"values": ["Blue"], "value_ids": [7]}],
            }]},
        }]}

        sync_active_listings(user)

        self.assertEqual(InventoryProduct.objects.count(), 0)
        self.assertEqual(InventoryVariation.objects.count(), 0)

    @patch("listings.services.EtsyClient")
    def test_switch_off_preserves_existing_inventory_names(self, client_class):
        user = get_user_model().objects.create_user(username="seller", password="test")
        EtsyAccount.objects.create(user=user, shop_id=42)
        product = InventoryProduct.objects.create(
            owner=user, etsy_listing_id=11, name="Existing name"
        )
        client = client_class.return_value
        client.get_active_listings.return_value = {
            "count": 1, "results": [{"listing_id": 11, "title": "New Etsy name"}]
        }
        client.get_listings_with_images.return_value = {"results": []}
        client.get_listings_inventory_batch.return_value = {
            "results": [{"listing_id": 11, "inventory": None}]
        }

        sync_active_listings(user)

        product.refresh_from_db()
        self.assertEqual(product.name, "Existing name")
