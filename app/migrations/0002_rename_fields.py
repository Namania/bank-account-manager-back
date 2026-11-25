from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(model_name='account', old_name='isActive', new_name='is_active'),
        migrations.RenameField(model_name='account', old_name='create_at', new_name='created_at'),
        migrations.RenameField(model_name='transaction', old_name='create_at', new_name='created_at'),
    ]
