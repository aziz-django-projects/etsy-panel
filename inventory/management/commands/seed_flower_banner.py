from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from inventory.services import seed_flower_banner


class Command(BaseCommand):
    help = "Seed inventory buckets and recipes for the Flower Banner listing."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--listing-id", type=int, required=True)
        parser.add_argument("--product-name", type=str, default="Flower Banner")

    def handle(self, *args, **options):
        user_id = options["user_id"]
        listing_id = options["listing_id"]
        product_name = options["product_name"]

        User = get_user_model()
        try:
            owner = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            raise CommandError(f"User not found: {user_id}") from exc

        seed_flower_banner(owner, listing_id, product_name=product_name)
        self.stdout.write(self.style.SUCCESS(f"{product_name} inventory seeded."))
