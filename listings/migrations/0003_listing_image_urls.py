from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0002_listing_image_url"),
    ]

    operations = [
        migrations.RenameField(
            model_name="listing",
            old_name="image_url",
            new_name="image_url_170x135",
        ),
        migrations.AddField(
            model_name="listing",
            name="image_url_75x75",
            field=models.URLField(blank=True, default=""),
        ),
    ]
