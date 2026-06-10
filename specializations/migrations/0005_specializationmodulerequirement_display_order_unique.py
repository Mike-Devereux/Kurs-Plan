from django.db import migrations, models


def dedupe_display_orders(apps, schema_editor):
    SpecializationModuleRequirement = apps.get_model(
        'specializations', 'SpecializationModuleRequirement',
    )
    spec_ids = (
        SpecializationModuleRequirement.objects
        .values_list('specialization_id', flat=True)
        .distinct()
    )
    for spec_id in spec_ids:
        used: set[int] = set()
        for requirement in (
            SpecializationModuleRequirement.objects
            .filter(specialization_id=spec_id)
            .order_by('id')
        ):
            order = requirement.display_order
            while order in used:
                order += 1
            if order != requirement.display_order:
                requirement.display_order = order
                requirement.save(update_fields=['display_order'])
            used.add(order)


class Migration(migrations.Migration):

    dependencies = [
        ('specializations', '0004_additionalrequirementrule_modules_included'),
    ]

    operations = [
        migrations.RunPython(dedupe_display_orders, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='specializationmodulerequirement',
            constraint=models.UniqueConstraint(
                fields=('specialization', 'display_order'),
                name='unique_specialization_module_display_order',
            ),
        ),
    ]
