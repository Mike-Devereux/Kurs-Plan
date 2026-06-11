from django.db import migrations

CHECKER_SUBTITLE = (
    "Choose your target specialization, pick the courses you plan to take, "
    "then submit to see whether they satisfy the specialization's "
    "requirements."
)


def seed_checker_subtitle(apps, schema_editor):
    SiteText = apps.get_model('planner', 'SiteText')
    SiteText.objects.get_or_create(
        key='checker_subtitle',
        defaults={'content': CHECKER_SUBTITLE},
    )


def remove_checker_subtitle(apps, schema_editor):
    SiteText = apps.get_model('planner', 'SiteText')
    SiteText.objects.filter(key='checker_subtitle').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed_checker_subtitle, remove_checker_subtitle),
    ]
