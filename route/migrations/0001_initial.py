from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='RouteLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(choices=[('search', 'Search'), ('error', 'Error'), ('info', 'Info')], max_length=20)),
                ('source', models.CharField(choices=[('route_api', 'Route API'), ('map_view', 'Map View'), ('manual', 'Manual')], default='manual', max_length=20)),
                ('message', models.CharField(max_length=255)),
                ('start_location', models.CharField(blank=True, max_length=200)),
                ('finish_location', models.CharField(blank=True, max_length=200)),
                ('status_code', models.PositiveIntegerField(blank=True, null=True)),
                ('details', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={
                'ordering': ['-created_at', '-id'],
            },
        ),
    ]
