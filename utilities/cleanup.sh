#!/bin/bash
set -euo pipefail

#
# Example:
#   ./check_and_delete.sh \
#     --dest s3://my-bucket/backup-folder \
#     --dirlist /path/to/local_dirs.txt \
#     [--dryrun]
#

usage() {
    echo "Usage: $0 --dest <destination> --dirlist <dirlist_file> [--dryrun]"
    exit 1
}

# Default value for dry run flag
DRYRUN=0

# Parse named arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dest)
            DEST="$2"
            shift 2
            ;;
        --dirlist)
            DIRLIST="$2"
            shift 2
            ;;
        --dryrun)
            DRYRUN=1
            shift
            ;;
        *)
            echo "Unknown parameter passed: $1"
            usage
            ;;
    esac
done

# must have both
if [ -z "${DEST:-}" ] || [ -z "${DIRLIST:-}" ]; then
    usage
fi

echo "Starting interactive deletion process..."
echo

# 1 GB in bytes
GB=1073741824

while IFS= read -r dir; do
    # skip non‐directories
    if [ ! -d "$dir" ]; then
        echo "[WARN] '$dir' is not a directory; skipping."
        continue
    fi

    echo "================================================================"
    echo "Checking directory: $dir"
    echo "----------------------------------------------------------------"

    # find every regular file under $dir
    find "$dir" -type f | while IFS= read -r file; do
        filename="$(basename "$file")"
        destfile="$DEST/$filename"            # adjust if DEST mirrors subdirs

        if [ ! -f "$destfile" ]; then
            echo "[MISSING]   $filename → not found in $DEST"
            continue
        fi

        # get sizes
        orig_size=$(stat -c%s "$file")
        dest_size=$(stat -c%s "$destfile")
        orig_gb=$(awk -v s="$orig_size" -v g="$GB" 'BEGIN{printf "%.2f", s/g}')
        dest_gb=$(awk -v s="$dest_size" -v g="$GB" 'BEGIN{printf "%.2f", s/g}')

        # print a little table row
        printf " %-20s  %10d bytes (%5s GB)  →  %10d bytes (%5s GB)" \
            "$filename" "$orig_size" "$orig_gb" "$dest_size" "$dest_gb"
        if [ "$orig_size" -eq "$dest_size" ]; then
            echo "  [OK]"
        else
            echo "  [DIFF]"
        fi
    done

    echo "================================================================"
    # prompt for directory deletion
    read -p "Delete entire directory '$dir'? (yes/no): " answer < /dev/tty

    if [ "$answer" = "yes" ]; then
        if [ "$DRYRUN" -eq 1 ]; then
            echo "[DRY RUN] would delete: $dir"
        else
            echo "Deleting: $dir"
            rm -rf "$dir"
            echo "[DELETED] $dir"
        fi
    else
        echo "[SKIPPED] not deleting $dir"
    fi
    echo
done < "$DIRLIST"

echo "All done."
