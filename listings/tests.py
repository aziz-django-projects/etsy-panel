from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from etsy.models import EtsyAccount
from .models import Listing, ListingVariation
from .services import sync_active_listings


class ListingSyncTests(TestCase):
    @patch("listings.services.EtsyClient")
    def test_batch_sync_updates_listings_and_removes_missing_variations(self, client_class):
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
            list(listing.variations.values_list("etsy_product_id", "label")),
            [(101, "Blue")],
        )
        self.assertTrue(Listing.objects.filter(etsy_listing_id=22).exists())
