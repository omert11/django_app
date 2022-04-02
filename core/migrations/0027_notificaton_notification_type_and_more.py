# Generated by Django 4.0.3 on 2022-03-29 09:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_alter_friendrequest_from_user_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='notificaton',
            name='notification_type',
            field=models.CharField(choices=[('follow', 'follow'), ('friend_req', 'friend_req'), ('notification', 'notification')], default='notification', max_length=20),
        ),
        migrations.AlterField(
            model_name='notificaton',
            name='to_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='to_user_notfy', to='core.profile'),
        ),
    ]