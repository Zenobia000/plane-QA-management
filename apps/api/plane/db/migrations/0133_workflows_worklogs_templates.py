# Three Phase D families in one migration: workflow transitions, worklogs and templates.
# All additive -- four new tables and no change to an existing one, so a project that never
# writes a transition has no workflow and every state change stays legal.

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0132_estimate_time_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='StateTransition',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('requires_approval', models.BooleanField(default=False)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('from_state', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transitions_out', to='db.state')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_%(class)s', to='db.project')),
                ('to_state', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='transitions_in', to='db.state')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workspace_%(class)s', to='db.workspace')),
            ],
            options={
                'verbose_name': 'State Transition',
                'verbose_name_plural': 'State Transitions',
                'db_table': 'state_transitions',
                'ordering': ('from_state', 'to_state'),
            },
        ),
        migrations.CreateModel(
            name='StateTransitionApprover',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('member', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='state_transition_approvals', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_%(class)s', to='db.project')),
                ('transition', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='approvers', to='db.statetransition')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workspace_%(class)s', to='db.workspace')),
            ],
            options={
                'verbose_name': 'State Transition Approver',
                'verbose_name_plural': 'State Transition Approvers',
                'db_table': 'state_transition_approvers',
            },
        ),
        migrations.CreateModel(
            name='Template',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('kind', models.CharField(choices=[('work_item', 'Work item'), ('project', 'Project')], max_length=30)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('payload', models.JSONField(default=dict)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('project', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='templates', to='db.project')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='templates', to='db.workspace')),
            ],
            options={
                'verbose_name': 'Template',
                'verbose_name_plural': 'Templates',
                'db_table': 'templates',
                'ordering': ('kind', 'name'),
            },
        ),
        migrations.CreateModel(
            name='Worklog',
            fields=[
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Last Modified At')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Deleted At')),
                ('id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True)),
                ('duration', models.PositiveIntegerField(help_text='Whole minutes.')),
                ('description', models.TextField(blank=True)),
                ('logged_at', models.DateField()),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created_by', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('issue', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='worklogs', to='db.issue')),
                ('logged_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='worklogs', to=settings.AUTH_USER_MODEL)),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='project_%(class)s', to='db.project')),
                ('updated_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated_by', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('workspace', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='workspace_%(class)s', to='db.workspace')),
            ],
            options={
                'verbose_name': 'Worklog',
                'verbose_name_plural': 'Worklogs',
                'db_table': 'worklogs',
                'ordering': ('-logged_at', '-created_at'),
            },
        ),
        migrations.AddConstraint(
            model_name='statetransition',
            constraint=models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True)), fields=('project', 'from_state', 'to_state'), name='state_transition_unique_edge_when_active'),
        ),
        migrations.AddConstraint(
            model_name='statetransitionapprover',
            constraint=models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True)), fields=('transition', 'member'), name='state_transition_approver_unique_when_active'),
        ),
        migrations.AddConstraint(
            model_name='template',
            constraint=models.UniqueConstraint(condition=models.Q(('deleted_at__isnull', True)), fields=('workspace', 'kind', 'name'), name='template_unique_name_per_kind_when_active'),
        ),
        migrations.AddIndex(
            model_name='worklog',
            index=models.Index(fields=['issue', 'logged_at'], name='worklog_issue_date_idx'),
        ),
    ]
