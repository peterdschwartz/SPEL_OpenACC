"""Load a `spel export` directory as a snapshot: manage.py update_all_data DIR [--replace]."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...models import Snapshot
from ...utils.configs import default_snapshot, set_default_snapshot
from ..loaders import SnapshotLoader


class Command(BaseCommand):
    help = "Load the CSVs written by `spel export` into the database as one snapshot"

    def add_arguments(self, parser):
        parser.add_argument("directory", nargs="?", help="Export directory (holds snapshot.json and the CSVs)")
        parser.add_argument("--label", default=None, help="Snapshot label (default: snapshot.json's)")
        parser.add_argument("--replace", action="store_true", help="Replace a snapshot with the same label")
        parser.add_argument("--batch", type=int, default=2000, help="bulk_create batch size")
        parser.add_argument("--list", action="store_true", help="List loaded snapshots and exit")
        parser.add_argument("--set-default", metavar="LABEL", default=None,
                            help="Make LABEL the snapshot visitors see first (with DIRECTORY: after loading it)")

    def handle(self, *args, **opts):
        if opts["list"]:
            default = default_snapshot()
            for s in Snapshot.objects.order_by("-loaded_at"):
                mark = "  (default)" if default is not None and s.pk == default.pk else ""
                loaded = f"{s.loaded_at:%Y-%m-%d %H:%M}" if s.loaded_at else "not loaded"
                self.stdout.write(f"{s.label:40s} {s.e3sm_branch}@{s.e3sm_commit[:8]}  loaded {loaded}{mark}")
            return
        if opts["directory"] is None:
            if opts["set_default"] is None:
                raise CommandError("give an export DIRECTORY to load, --list, or --set-default LABEL")
            self._set_default(opts["set_default"])
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
        if opts["set_default"] is not None:
            self._set_default(opts["set_default"])

    def _set_default(self, label: str) -> None:
        try:
            snap = set_default_snapshot(label)
        except Snapshot.DoesNotExist:
            known = ", ".join(Snapshot.objects.values_list("label", flat=True)) or "none"
            raise CommandError(f"no snapshot '{label}' (loaded: {known})")
        self.stdout.write(self.style.SUCCESS(f"Default snapshot: '{snap.label}'"))
