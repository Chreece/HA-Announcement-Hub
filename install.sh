#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$ROOT_DIR/custom_components/announcement_hub"
HA_CONFIG="${HA_CONFIG:-/home/chreece/homeassistant/config}"
TARGET_PARENT="$HA_CONFIG/custom_components"
TARGET_DIR="$TARGET_PARENT/announcement_hub"
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
  INVOKING_USER="$SUDO_USER"
  INVOKING_HOME="$(getent passwd "$SUDO_USER" | cut -d: -f6)"
else
  INVOKING_USER="$(id -un)"
  INVOKING_HOME="$HOME"
fi
STATE_HOME="${XDG_STATE_HOME:-$INVOKING_HOME/.local/state}"
BACKUP_ROOT="$STATE_HOME/ha-integration-backups/announcement_hub"
STAMP="$(date +%Y%m%d-%H%M%S)"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -d "$SOURCE_DIR" ]] || fail "Component source not found: $SOURCE_DIR"
[[ -d "$HA_CONFIG" ]] || fail "Home Assistant config directory not found: $HA_CONFIG"
command -v python3 >/dev/null 2>&1 || fail "python3 is required for validation"

python3 - "$SOURCE_DIR" <<'PY'
from __future__ import annotations
import ast
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
required = {
    "__init__.py",
    "config_flow.py",
    "const.py",
    "manager.py",
    "manifest.json",
    "message_parts.py",
    "models.py",
    "outputs.py",
    "sensor.py",
    "diagnostics.py",
    "icons.json",
    "services.yaml",
    "strings.json",
}
missing = sorted(name for name in required if not (root / name).is_file())
if missing:
    raise SystemExit(f"Missing component files: {', '.join(missing)}")
for path in root.rglob("*.py"):
    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
for path in [root / "manifest.json", root / "strings.json", root / "icons.json", *sorted((root / "translations").glob("*.json"))]:
    json.loads(path.read_text(encoding="utf-8"))
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
if manifest.get("domain") != "announcement_hub":
    raise SystemExit("Unexpected integration domain")
print(f"Validated Announcement Hub {manifest.get('version', 'unknown')}")
PY

mkdir -p "$TARGET_PARENT" "$BACKUP_ROOT"
if [[ $EUID -eq 0 && -n "$INVOKING_USER" ]]; then
  chown -R "$INVOKING_USER":"$(id -gn "$INVOKING_USER")" "$BACKUP_ROOT"
fi
if [[ -e "$TARGET_DIR" ]]; then
  BACKUP_DIR="$BACKUP_ROOT/$STAMP"
  mkdir -p "$BACKUP_DIR"
  cp -a "$TARGET_DIR" "$BACKUP_DIR/announcement_hub"
  printf 'Backup: %s\n' "$BACKUP_DIR/announcement_hub"
fi

STAGE_DIR="$(mktemp -d "$TARGET_PARENT/.announcement_hub.install.XXXXXX")"
cleanup() {
  rm -rf "$STAGE_DIR"
}
trap cleanup EXIT
cp -a "$SOURCE_DIR/." "$STAGE_DIR/"
if [[ $EUID -eq 0 ]]; then
  if [[ -e "$TARGET_DIR" ]]; then
    INSTALL_OWNER="$(stat -c '%u:%g' "$TARGET_DIR")"
  else
    INSTALL_OWNER="$(stat -c '%u:%g' "$TARGET_PARENT")"
  fi
  chown -R "$INSTALL_OWNER" "$STAGE_DIR"
fi
find "$STAGE_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$STAGE_DIR" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

OLD_DIR=""
if [[ -e "$TARGET_DIR" ]]; then
  OLD_DIR="$TARGET_PARENT/.announcement_hub.old.$STAMP"
  mv "$TARGET_DIR" "$OLD_DIR"
fi
if ! mv "$STAGE_DIR" "$TARGET_DIR"; then
  [[ -n "$OLD_DIR" && -e "$OLD_DIR" ]] && mv "$OLD_DIR" "$TARGET_DIR"
  fail "Could not install the component"
fi
trap - EXIT
[[ -n "$OLD_DIR" ]] && rm -rf "$OLD_DIR"

printf '\nAnnouncement Hub installed at:\n  %s\n' "$TARGET_DIR"
printf 'No Home Assistant script, automation, helper, MPD setting, or Snapserver setting was changed.\n'
printf 'Restart Home Assistant manually, then add Announcement Hub in Settings > Devices & services.\n'
