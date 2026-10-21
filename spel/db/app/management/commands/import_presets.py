"""Import namelist presets (.cfg files of `name = value` lines) as PresetConfig rows."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from ...models import IntrinsicGlobals, PresetConfig, Snapshot

DEFAULT_PATH = Path(__file__).resolve().parent / "presets"
DEFAULT_SLUG = "cnprdctcbc"


def parse_cfg(path: Path) -> tuple[dict[str, str], list[str]]:
    """{variable: Fortran literal} from `key = value` lines; returns (data, malformed lines)."""
    data, bad = {}, []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("!", "#", "&", "/")):
            continue
        key, sep, value = line.partition("=")
        if not sep or not key.strip():
            bad.append(line)
            continue
        data[key.strip().lower()] = value.strip()
    return data, bad


class Command(BaseCommand):
    help = "Import/update PresetConfig rows from .cfg files (keyed by namelist variable name)"

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT_PATH), help="Directory with .cfg preset files")
        parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing")
        parser.add_argument("--default", metavar="SLUG", default=None, help="Mark this slug as the default preset")

    @transaction.atomic
    def handle(self, *args, **opts):
        path = Path(opts["path"]).resolve()
        if not path.is_dir():
            raise CommandError(f"Preset path is not a directory: {path}")
        snap = Snapshot.objects.order_by("-loaded_at").first()
        known = set()
        if snap is not None:
            known = set(IntrinsicGlobals.objects.filter(snapshot=snap).exclude(namelist_group="")
                        .values_list("var_name", flat=True))
        n = 0
        for cfg in sorted(path.glob("*.cfg")):
            data, bad = parse_cfg(cfg)
            for line in bad:
                self.stdout.write(self.style.WARNING(f"{cfg.name}: malformed line: {line}"))
            unknown = sorted(set(data) - known) if known else []
            if unknown:
                self.stdout.write(f"{cfg.name}: {len(unknown)} keys unknown to snapshot '{snap.label}': {', '.join(unknown[:8])}{' ...' if len(unknown) > 8 else ''}")
            slug = slugify(cfg.stem)
            if opts["dry_run"]:
                self.stdout.write(f"[DRY] {cfg.name}: {len(data)} keys -> slug={slug}\n{json.dumps(data, indent=2)}")
                continue
            _, created = PresetConfig.objects.update_or_create(slug=slug, defaults={"name": cfg.stem, "data": data})
            n += 1
            self.stdout.write(self.style.SUCCESS(f"{'Created' if created else 'Updated'} preset '{cfg.stem}' ({len(data)} vars)"))
        if opts["dry_run"]:
            return
        default = (opts["default"] or "").lower()
        if not default and not PresetConfig.objects.filter(is_default=True).exists():
            default = DEFAULT_SLUG
        if default:
            PresetConfig.objects.exclude(slug=default).update(is_default=False)
            if PresetConfig.objects.filter(slug=default).update(is_default=True) == 0:
                self.stdout.write(self.style.WARNING(f"Default slug '{default}' not found"))
        self.stdout.write(self.style.NOTICE(f"Processed {n} preset files"))
