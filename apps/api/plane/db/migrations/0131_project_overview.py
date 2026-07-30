# What the Project Overview reports on. Additive throughout: four nullable/defaulted columns
# on `projects` and two new tables, so a rollback is a drop and existing rows are untouched.
# See docs/architecture/decisions/0005-project-overview-attributes-and-updates.md.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0130_project_view_axes_on_by_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='priority',
            field=models.CharField(choices=[('urgent', 'Urgent'), ('high', 'High'), ('medium', 'Medium'), ('low', 'Low'), ('none', 'None')], default='none', max_length=30),
        ),
        migrations.AddField(
            model_name='project',
            name='start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='project',
            name='state',
            field=models.CharField(blank=True, choices=[('planned', 'Planned'), ('in_progress', 'In progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], max_length=32, null=True),
        ),
        migrations.AddField(
            model_name='project',
            name='target_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ProjectLink',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('url', models.URLField()),
                ('metadata', models.JSONField(default=dict)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_%(class)s', to='db.project')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workspace_%(class)s', to='db.workspace')),
            ],
            options={
                'verbose_name': 'Project Link',
                'verbose_name_plural': 'Project Links',
                'db_table': 'project_links',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='EntityUpdate',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('entity_name', models.CharField(choices=[('project', 'Project'), ('work_item', 'Work item')], max_length=30)),
                ('entity_identifier', models.UUIDField()),
                ('status', models.CharField(choices=[('on_track', 'On track'), ('at_risk', 'At risk'), ('off_track', 'Off track')], default='on_track', max_length=30)),
                ('description', models.TextField(blank=True)),
                ('actor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='entity_updates', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='replies', to='db.entityupdate')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_%(class)s', to='db.project')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workspace_%(class)s', to='db.workspace')),
            ],
            options={
                'verbose_name': 'Entity Update',
                'verbose_name_plural': 'Entity Updates',
                'db_table': 'entity_updates',
                'ordering': ('-created_at',),
                'indexes': [models.Index(fields=['entity_name', 'entity_identifier'], name='entity_update_target_idx')],
            },
        ),
    ]
