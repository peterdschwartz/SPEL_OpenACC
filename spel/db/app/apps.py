from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _sqlite_pragmas(sender, connection, **kwargs):
    """WAL lets readers proceed while a request writes; a busy timeout waits instead of failing."""
    if connection.vendor == "sqlite":
        with connection.cursor() as cur:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA busy_timeout=30000")


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "db.app"
    label = "app"

    def ready(self):
        connection_created.connect(_sqlite_pragmas, dispatch_uid="spel-sqlite-pragmas")
