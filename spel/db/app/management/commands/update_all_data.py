"""Load a `spel export` directory as a snapshot: manage.py update_all_data DIR [--replace]."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...models import Snapshot
from ..loaders import SnapshotLoader


class Command(BaseCommand):
    help = "Load the CSVs written by `spel export` into the database as one snapshot"

    def add_arguments(self, parser):
        parser.add_argument("directory", help="Export directory (holds snapshot.json and the CSVs)")
        parser.add_argument("--label", default=None, help="Snapshot label (default: snapshot.json's)")
        parser.add_argument("--replace", action="store_true", help="Replace a snapshot with the same label")
        parser.add_argument("--batch", type=int, default=2000, help="bulk_create batch size")
        parser.add_argument("--list", action="store_true", help="List loaded snapshots and exit")

    def handle(self, *args, **opts):
        if opts["list"]:
            for s in Snapshot.objects.order_by("-loaded_at"):
                self.stdout.write(f"{s.label:40s} {s.e3sm_branch}@{s.e3sm_commit[:8]}  loaded {s.loaded_at:%Y-%m-%d %H:%M}")
            return
        directory = Path(opts["directory"])
        if not (directory / "snapshot.json").is_file():
            raise CommandError(f"{directory} has no snapshot.json (run `spel export` first)")
        loader = SnapshotLoader(directory, label=opts["label"], replace=opts["replace"],
                                batch_size=opts["batch"], log=self.stdout.write)
        try:
            snap = loader.load()
        except ValueError as err:
            raise CommandError(str(err))
        total = sum(loader.counts.values())
        self.stdout.write(self.style.SUCCESS(f"Loaded snapshot '{snap.label}' ({total} rows)"))
