from django.conf import settings
from django.db import models
from django.utils import timezone

class EtsyAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    etsy_user_id = models.BigIntegerField(null=True, blank=True)  # token prefix'inden gelecek
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.TextField(blank=True)
    last_connected_at = models.DateTimeField(null=True, blank=True)
    shop_id = models.BigIntegerField(null=True, blank=True)
    shop_name = models.CharField(max_length=255, blank=True)


    def is_access_token_valid(self):
        return self.expires_at and self.expires_at > timezone.now()
