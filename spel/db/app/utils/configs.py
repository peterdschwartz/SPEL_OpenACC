"""The active snapshot and namelist configuration of a request (session defaults, URL overrides)."""

from __future__ import annotations

from typing import Optional

from ..models import ConfigProfile, PresetConfig, Snapshot
from .helper import compute_config_hash


def active_snapshot(request, label: Optional[str] = None) -> Optional[Snapshot]:
    """The snapshot named by `label` or the session, else the default one, else the most recently loaded."""
    chosen = label  # from the URL; the toolbar picker stores its choice in the session itself
    label = label or request.session.get("active_snapshot")
    snap = Snapshot.objects.filter(label=label).first() if label else None
    if snap is None:
        # remember only a snapshot the visitor chose, so a later change of the default reaches everyone else
        request.session.pop("active_snapshot", None)
        return default_snapshot()
    if chosen and request.session.get("active_snapshot") != snap.label:
        request.session["active_snapshot"] = snap.label
    return snap


def default_snapshot() -> Optional[Snapshot]:
    """The snapshot marked default (`update_all_data --set-default`), else the most recently loaded one."""
    loaded = Snapshot.objects.filter(loaded_at__isnull=False)
    return loaded.filter(is_default=True).first() or loaded.order_by("-loaded_at").first()


def set_default_snapshot(label: str) -> Snapshot:
    """Mark `label` as the default snapshot (and no other). Raises Snapshot.DoesNotExist."""
    snap = Snapshot.objects.get(label=label)
    Snapshot.objects.exclude(pk=snap.pk).filter(is_default=True).update(is_default=False)
    if not snap.is_default:
        snap.is_default = True
        snap.save(update_fields=["is_default"])
    return snap


def config_by_key(key: str) -> Optional[dict]:
    """`preset:<slug>` / `<slug>` / `user:<id>` -> {kind, key, data, label, hash}."""
    if not key:
        return None
    kind, _, ident = key.partition(":")
    if kind == "user":
        cfg = ConfigProfile.objects.filter(id=ident).first()
        if cfg is None:
            return None
        return {"kind": "user", "key": f"user:{cfg.id}", "data": cfg.data or {}, "label": cfg.name, "hash": cfg.user_hash}
    slug = ident if kind == "preset" else key
    preset = PresetConfig.objects.filter(slug=slug).first()
    if preset is None:
        return None
    return {"kind": "preset", "key": preset.slug, "data": preset.data, "label": preset.name, "hash": preset.preset_hash}


def default_config() -> dict:
    preset = PresetConfig.objects.filter(is_default=True).first() or PresetConfig.objects.first()
    if preset is None:
        return {"kind": "none", "key": "", "data": {}, "label": "defaults", "hash": compute_config_hash({})}
    return {"kind": "preset", "key": preset.slug, "data": preset.data, "label": preset.name, "hash": preset.preset_hash}


def active_config(request, key: Optional[str] = None) -> dict:
    """The configuration named by `key` (URL) or the session, else the default preset."""
    sel = key or request.session.get("active_config_key")
    cfg = config_by_key(sel) if sel else None
    if cfg is None:
        cfg = default_config()
    if cfg["key"] and request.session.get("active_config_key") != cfg["key"]:
        request.session["active_config_key"] = cfg["key"]
    return cfg


def all_configs(request) -> list[dict]:
    """Presets plus the user's own configurations, for pickers."""
    out = [{"key": p.slug, "label": p.name, "kind": "preset"} for p in PresetConfig.objects.order_by("name")]
    if request.user.is_authenticated:
        out += [{"key": f"user:{c.id}", "label": c.name, "kind": "user"}
                for c in ConfigProfile.objects.filter(owner=request.user).order_by("name")]
    return out
