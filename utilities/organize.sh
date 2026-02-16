#!/usr/bin/env bash
# organize.sh — v3
#
# Description:
#   Sort files in the current directory into an organized upload folder:
#     upload/<sample_id>/<pod5|basecalled>/
#   - Files ending in .pod5.tar go to the 'pod5' folder.
#   - All other files go to the 'basecalled' folder (or a custom name).
#
# Configuration (edit these at the top of the script):
#   UPLOAD_ROOT       Top-level upload directory (default: "upload")
#   POD_SUBDIR        Subfolder for .pod5.tar files (default: "pod5")
#   BASECALLED_SUBDIR Subfolder for other files (default: "basecalled")
#   ID_FIELD          Which underscore-delimited field to use as sample ID
#                     (default: 7)
#
# Usage:
#   ./organize.sh [--dryrun] [--basecalled-subdir NAME] [--id-field N]
#
# Options:
#   --dryrun
#       Show what would happen, but do not actually move any files.
#
#   --basecalled-subdir NAME
#       Override the default name for the “basecalled” subfolder.
#
#   --id-field N
#       Pick the Nth field (underscore-delimited) from the filename as sample_id.
#       Must be a positive integer.
#
# Behavior:
#   1. Scans all regular files in the current directory.
#   2. Splits each filename on underscores and picks field $ID_FIELD as sample_id.
#      If that field is empty, the file is skipped with a warning.
#   3. Determines subfolder based on extension:
#        *.pod5.tar → $POD_SUBDIR
#        otherwise   → $BASECALLED_SUBDIR
#   4. Moves (or prints, in dry-run) each file to:
#        $UPLOAD_ROOT/<sample_id>/<subdir>/
#   5. Prints progress messages and a summary at the end.
#
# Examples:
#   # Dry run with all defaults:
#   ./organize.sh --dryrun
#
#   # Real run, but put non-.pod5.tar files into “base” instead of “basecalled”:
#   ./organize.sh --basecalled-subdir base
#
#   # Use the 6th underscore-delimited field as the sample ID:
#   ./organize.sh --id-field 6
#
# Requirements:
#   Bash with ‘shopt -s nullglob’, plus standard coreutils (cut, mkdir, mv, etc.).
# ────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
UPLOAD_ROOT="upload"             # Top-level directory
POD_SUBDIR="pod5"                # Where .pod5.tar files go
BASECALLED_SUBDIR="basecalled"   # Default for all other files
ID_FIELD=7                       # Default underscore-delimited field index for sample_id
# ─── End Configuration ────────────────────────────────────────────────────────

DRYRUN=false

echo "[INFO] Starting organize.sh in $(pwd)"

# ─── Argument Parsing ─────────────────────────────────────────────────────────
usage() {
  echo "Usage: $0 [--dryrun] [--basecalled-subdir NAME] [--id-field N]"
  exit 1
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dryrun)
      DRYRUN=true
      shift
      ;;
    --basecalled-subdir)
      [ $# -ge 2 ] || usage
      BASECALLED_SUBDIR="$2"
      shift 2
      ;;
    --id-field)
      [ $# -ge 2 ] || usage
      ID_FIELD="$2"
      if ! [[ "$ID_FIELD" =~ ^[1-9][0-9]*$ ]]; then
        echo "Error: --id-field requires a positive integer"
        exit 1
      fi
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

echo "[INFO] Dry-run mode: $DRYRUN"
echo "[INFO] upload root: $UPLOAD_ROOT"
echo "[INFO] pod subdir: $POD_SUBDIR"
echo "[INFO] basecalled subdir: $BASECALLED_SUBDIR"
echo "[INFO] sample_id field index: $ID_FIELD"
echo

# ─── Enable nullglob so “*.ext” disappears instead of staying literal ────────
shopt -s nullglob

# ─── Main Loop ───────────────────────────────────────────────────────────────
count=0
for filepath in ./*; do
  # skip if not a regular file
  [ -f "$filepath" ] || continue

  count=$((count + 1))
  fname=$(basename "$filepath")
  echo "[INFO] File #$count: $fname"

  # extract the Nth underscore-delimited field as sample_id
  sample_id=$(echo "$fname" | cut -d'_' -f"$ID_FIELD")
  if [ -z "$sample_id" ]; then
    echo "  [WARN] could not parse sample_id from field $ID_FIELD → skipping"
    continue
  fi

  # choose pod vs basecalled
  case "$fname" in
    *.pod5.tar) subdir="$POD_SUBDIR" ;;
    *)          subdir="$BASECALLED_SUBDIR" ;;
  esac

  dest="$UPLOAD_ROOT/$sample_id/$subdir"
  echo "  → Destination: $dest"

  if [ "$DRYRUN" = "true" ]; then
    echo "  [DRYRUN] mv \"$filepath\" \"$dest/\""
  else
    mkdir -p "$dest"
    mv -- "$filepath" "$dest/"
    echo "  [OK]"
  fi

  echo
done

# ─── Summary ─────────────────────────────────────────────────────────────────
if [ "$count" -eq 0 ]; then
  echo "[INFO] No files found. Are you in the right directory?"
else
  echo "[INFO] Processed $count file(s)."
  if [ "$DRYRUN" = "true" ]; then
    echo "[INFO] Dry run complete; no files were moved."
  else
    echo "[INFO] Done. Files are under '$UPLOAD_ROOT/'."
  fi
fi
