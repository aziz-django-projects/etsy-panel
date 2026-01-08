from django.conf import settings
from django.db import models


class Buyer(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    etsy_buyer_user_id = models.BigIntegerField()
    display_name = models.CharField(max_length=255, blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "etsy_buyer_user_id"], name="uniq_owner_buyer_user_id"
            )
        ]

    def __str__(self):
        label = self.display_name or str(self.etsy_buyer_user_id)
        return f"{label} ({self.etsy_buyer_user_id})"

    @property
    def etsy_messages_url(self) -> str:
        # Etsy web UI URL can change; keep centralized via redirect view.
        return f"https://www.etsy.com/messages?recipient_id={self.etsy_buyer_user_id}"

