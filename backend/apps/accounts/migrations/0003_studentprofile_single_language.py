# Один язык ученика вместо пары «язык обучения / язык объяснений».
# Значение берётся из explanation_language (им уже определялись интерфейс и объяснения);
# instruction_language служил только подсказкой распознавания и удаляется.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_parental_controls"),
    ]

    operations = [
        migrations.RenameField(
            model_name="studentprofile",
            old_name="explanation_language",
            new_name="language",
        ),
        migrations.RemoveField(
            model_name="studentprofile",
            name="instruction_language",
        ),
        migrations.AlterField(
            model_name="studentprofile",
            name="language",
            field=models.CharField(
                choices=[("ru", "Русский"), ("ky", "Кыргызча")],
                default="ru",
                help_text="Единый язык ученика: интерфейс, объяснения и подсказка распознавания",
                max_length=2,
            ),
        ),
    ]
