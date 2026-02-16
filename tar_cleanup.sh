#!/bin/bash
set -euo pipefail

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

if [ -z "${DEST:-}" ] || [ -z "${DIRLIST:-}" ]; then
    usage
fi

echo "Starting interactive deletion process..."

# Define conversion factor: 1 GB = 1073741824 bytes
GB=1073741824

while IFS= read -r dir; do
    if [ ! -d "$dir" ]; then
        echo "Directory '$dir' does not exist. Skipping..."
        continue
    fi

    subdir=$(basename "$dir")
    tarfile="$DEST/${subdir}.pod5.tar"

    if [ ! -f "$tarfile" ]; then
        echo "Tar file '$tarfile' for directory '$dir' does not exist. Skipping..."
        continue
    fi

    orig_size=$(du -sb "$dir" | cut -f1)
    tar_size=$(stat -c%s "$tarfile")
    orig_size_gb=$(awk -v size="$orig_size" -v gb="$GB" 'BEGIN { printf "%.2f", size/gb }')
    tar_size_gb=$(awk -v size="$tar_size" -v gb="$GB" 'BEGIN { printf "%.2f", size/gb }')
    orig_files=$(find "$dir" | wc -l)
    tar_files=$(tar -tf "$tarfile" | wc -l)

    echo "---------------------------------------------------------"
    echo "Directory:           $dir"
    echo "Tar file:            $tarfile"
    echo "Original size:       $orig_size bytes (${orig_size_gb} GB)"
    echo "Tar file size:       $tar_size bytes (${tar_size_gb} GB)"
    diff_bytes=$((orig_size - tar_size))
    diff_gb=$(awk -v diff="$diff_bytes" -v gb="$GB" 'BEGIN { printf "%.2f", diff/gb }')
    if [ $diff_bytes -lt 0 ]; then
        abs_diff_gb=$(awk -v diff="$diff_bytes" -v gb="$GB" 'BEGIN { printf "%.2f", (-1*diff)/gb }')
        echo "Tar file is larger than original by $abs_diff_gb GB."
    else
        echo "Original is larger than tar file by $diff_gb GB."
    fi
    echo "Original file count: $orig_files"
    echo "Tar file count:      $tar_files"
    echo "Top-level entries in tar file:"
    tar -tf "$tarfile" | cut -d/ -f1 | sort | uniq
    echo "---------------------------------------------------------"
    echo "Please verify that the above details match as expected."

    # Corrected prompt: read input from the terminal
    read -p "Do you want to delete the original directory '$dir'? (yes/no): " answer < /dev/tty

    if [ "$answer" = "yes" ]; then
        if [ "$DRYRUN" -eq 1 ]; then
            echo "Dry run: Would delete directory '$dir'."
        else
            echo "Deleting directory '$dir'..."
            rm -rf "$dir"
            echo "Directory '$dir' deleted."
        fi
    else
        echo "Skipping deletion of '$dir'."
    fi
    echo
done < "$DIRLIST"

echo "Interactive deletion process complete."
