"""Repair installations where the initial communications migration was faked.

Some existing databases contain the migration records for 0001/0002 and the
announcement tables, but not the chat tables that were later added to those
initial migration files.  This migration only creates a missing table, so it
is a no-op for correctly migrated environments.
"""

from django.db import migrations

CHAT_MODELS = (
    "Conversation",
    "ConversationParticipant",
    "Message",
)


def create_missing_chat_tables(apps, schema_editor):
    """Create chat tables absent from an already-recorded initial migration."""
    existing_tables = set(schema_editor.connection.introspection.table_names())

    for model_name in CHAT_MODELS:
        model = apps.get_model("communications", model_name)
        if model._meta.db_table not in existing_tables:  # noqa: SLF001
            schema_editor.create_model(model)
            existing_tables.add(model._meta.db_table)  # noqa: SLF001


class Migration(migrations.Migration):

    dependencies = [
        ("communications", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(create_missing_chat_tables, migrations.RunPython.noop),
    ]
