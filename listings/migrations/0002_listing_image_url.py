from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("listings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="listing",
            name="image_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
