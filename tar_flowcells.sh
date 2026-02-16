#!/bin/bash
set -euo pipefail

usage() {
    echo "Usage: $0 --dest <destination> --dirlist <dirlist_file> [--dryrun]"
    exit 1
}

# Default value for dry run flag
DRYRUN=0
MAX_JOBS=5 # Maximum number of concurrent jobs

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

# Check that required variables are set
if [ -z "${DEST:-}" ] || [ -z "${DIRLIST:-}" ]; then
    usage
fi

# Export variables so they're available in subshells (e.g., in parallel)
export DEST DRYRUN

# Ensure the destination directory exists or create it
if [ ! -d "$DEST" ]; then
    if [ "$DRYRUN" -eq 1 ]; then
        echo "Dry run: Destination directory '$DEST' does not exist. It would be created."
    else
        echo "Destination directory '$DEST' does not exist. Creating it..."
        mkdir -p "$DEST"
    fi
fi

# Ensure write permission on the destination directory
if [ ! -w "$DEST" ]; then
    echo "Error: No write permission on the destination directory '$DEST'."
    exit 1
fi

echo "Calculating total required space..."
total_required=0
while IFS= read -r dir; do
    if [ -d "$dir" ]; then
        size=$(du -sb "$dir" | cut -f1)
        total_required=$((total_required + size))
    else
        echo "Warning: Directory '$dir' does not exist and will be skipped."
    fi
done < "$DIRLIST"

# Get available free space (in bytes) on the drive containing DEST
free_space=$(df --output=avail -B1 "$DEST" | tail -n 1)

# Ensure free_space and total_required are valid numbers
if ! [[ "$free_space" =~ ^[0-9]+$ ]]; then
    echo "Error: free_space is not a valid number"
    exit 1
fi

if ! [[ "$total_required" =~ ^[0-9]+$ ]]; then
    echo "Error: total_required is not a valid number"
    exit 1
fi

# Convert bytes to TB (1 TB = 1024^4 bytes = 1099511627776)
conv=1099511627776
total_required_tb=$(awk -v tot="$total_required" -v conv="$conv" 'BEGIN { printf "%.2f", tot/conv }')
free_space_tb=$(awk -v free="$free_space" -v conv="$conv" 'BEGIN { printf "%.2f", free/conv }')

echo "Total required space: $total_required bytes (${total_required_tb} TB)"
echo "Available free space on destination drive: $free_space bytes (${free_space_tb} TB)"

if (( free_space < total_required )); then
    echo "Error: Not enough free space on destination drive. Aborting. Clear space or consider splitting your input into two runs."
    exit 1
fi

if [ "$DRYRUN" -eq 1 ]; then
    echo "Dry run: Sufficient space available. The following actions would be taken:"
fi

# Function to archive a directory
archive_dir() {
    dir="$1"
    if [ ! -d "$dir" ]; then
        echo "Skipping non-existent directory: $dir"
        return
    fi

    subdir=$(basename "$dir")
    parent=$(dirname "$dir")
    tarfile="$DEST/${subdir}.pod5.tar"

    if [ "$DRYRUN" -eq 1 ]; then
        echo "Dry run: Would archive '$dir' to '$tarfile' (using '$parent' as base directory)."
    else
        echo "Archiving '$dir' to '$tarfile'..."
        # Use the -C option so that tarfile is created relative to your original working directory
        tar -cf "$tarfile" -C "$parent" "$subdir" && echo "Archive created successfully: $tarfile"
    fi
}

export -f archive_dir

# Run the archiving process in parallel, limiting the number of concurrent jobs to MAX_JOBS
#cat "$DIRLIST" | parallel --progress -j "$MAX_JOBS" archive_dir
cat "$DIRLIST" | parallel --eta -j "$MAX_JOBS" archive_dir

if [ "$DRYRUN" -eq 1 ]; then
    echo "Dry run complete. No archives were created."
else
    echo "Archiving process complete."
fi
