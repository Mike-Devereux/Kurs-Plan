from django.db import migrations, models


def dedupe_display_orders(apps, schema_editor):
    CourseCategory = apps.get_model('courses', 'CourseCategory')
    used: set[int] = set()
    for category in CourseCategory.objects.order_by('id'):
        order = category.display_order
        while order in used:
            order += 1
        if order != category.display_order:
            category.display_order = order
            category.save(update_fields=['display_order'])
        used.add(order)


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0003_course'),
    ]

    operations = [
        migrations.RunPython(dedupe_display_orders, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='coursecategory',
            constraint=models.UniqueConstraint(
                fields=('display_order',),
                name='unique_course_category_display_order',
            ),
        ),
    ]
