"""
Database export: one CSV per table of the Django app (spel/db) from an
analysis (`spel analyze`'s cache, or a case pickle), plus `snapshot.json`.

    from spel.scripts.db_export.snapshot import export_snapshot

`schema.TABLES` is the contract shared with the loader
(spel/db/app/management/loaders.py): CSV name -> ordered columns.
"""
