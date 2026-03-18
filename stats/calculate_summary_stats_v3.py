#!/usr/bin/env python
"""
calculate_summary_stats_v3.py

Based on the original script by Miten Jain, this version:
  1. Requires a --size option (in gigabases) to set the genome size.
  2. Adds a --dir option which accepts a directory or wildcard pattern. When provided,
     the script will expand the pattern, search each matching directory recursively for
     files starting with "sequencing_summary" OR ending with "_summary.txt.gz",
     process each file individually, and output a CSV table.
  3. Adds a --nameby option (default "filename") controlling how the "File" label is derived:
       filename  — basename of the summary file (good for cluster flat output dirs where the
                   BAM name is baked into the filename, e.g. Sample_fast_summary.txt.gz)
       dirname   — basename of the matched --dir directory (good for local PromethION runs
                   where summary files are deep inside per-sample directories)
       path      — full file path
  4. Adds a --append option to append an underscore and a string to the label.
     If you don't want anything appended, use --no-append to override --append.
  5. Uses the **first field of each read's pod5 filename** (split on _) as "flowcell_id".
  6. Now supports both regular summary files (with "filename" column) and live basecalling
     summary files (with "filename_pod5" column).

Usage Examples:
  Aggregated mode:
    python calculate_summary_stats_v3.py --size 3.3 file1.txt file2.txt

  Directory mode, label by matched directory name (local PromethION):
    python calculate_summary_stats_v3.py --size 3.3 --dir "*EnTEX*" --nameby dirname

  Directory mode, label by filename (cluster flat output dir):
    python calculate_summary_stats_v3.py --size 3.3 --dir "/project/out" --nameby filename

  To run without appending any string:
    python calculate_summary_stats_v3.py --size 3.3 --no-append --dir "*EnTEX*"
"""

from __future__ import print_function
import os
import sys
import time
import gzip
import glob
import csv
from optparse import OptionParser

def get_label(filepath, dirpath, nameby):
    """
    Return the sample label for a summary file.

    filepath : path to the summary file (may be comma-joined in aggregated mode)
    dirpath  : the directory matched by --dir glob (None in aggregated/file-list mode)
    nameby   : 'filename', 'dirname', or 'path'

    dirname falls back to filename when dirpath is None (aggregated mode).
    """
    if nameby == "path":
        return filepath
    if nameby == "dirname" and dirpath is not None:
        return os.path.basename(dirpath)
    # filename (or dirname fallback)
    if "," in filepath:
        return ",".join(os.path.basename(p) for p in filepath.split(","))
    return os.path.basename(filepath)

def process_single_file(inFile, actual_genome_size):
    """
    Process a single sequencing_summary file and compute statistics.
    Extracts the first '_'‐delimited field from the pod5 filename column
    (either 'filename', 'filename_pod5', or 'input_filename') of the first data line
    and calls that 'flowcell_id'. Returns a dictionary of stats or None.
    """
    read_lengths = []
    bases = 0
    flowcell_id = None

    # Open (possibly gzipped)
    try:
        if inFile.endswith('.gz'):
            f = gzip.open(inFile, 'rt')
        else:
            f = open(inFile, 'r')
    except Exception as e:
        sys.stderr.write("Error opening file %s: %s\n" % (inFile, str(e)))
        return None

    # Read header to find the index of "sequence_length_template" and filename column
    header = f.readline().strip().split()
    try:
        length_index = header.index("sequence_length_template")
    except ValueError:
        sys.stderr.write("Error: 'sequence_length_template' not found in header of %s\n" % inFile)
        f.close()
        return None

    # Look for filename column - try filename variants
    filename_index = None
    for possible_name in ["filename", "filename_pod5", "input_filename"]:
        try:
            filename_index = header.index(possible_name)
            break
        except ValueError:
            continue

    if filename_index is None:
        sys.stderr.write("Warning: Neither 'filename', 'filename_pod5', nor 'input_filename' found in header of %s\n" % inFile)

    # Iterate through every data line
    for line in f:
        # Skip repeated header lines, if any
        if ('filename' in line or 'input_filename' in line) and 'read_id' in line:
            continue

        parts = line.strip().split()
        if len(parts) <= length_index:
            continue

        # On the very first valid data row, grab the pod‐filename (parts[filename_index]),
        # split on '_', and take the first field as flowcell_id.
        if flowcell_id is None and filename_index is not None and len(parts) > filename_index:
            pod_filename = parts[filename_index]        # e.g. "PBE83079_skip_15726cb4_58deb308_0.pod5"
            flowcell_id = pod_filename.split("_")[0]    # e.g. "PBE83079"

        # Collect read length
        try:
            length = int(parts[length_index])
        except ValueError:
            continue

        read_lengths.append(length)
        bases += length

    f.close()

    if not read_lengths:
        return None

    # Sort descending
    read_lengths.sort(reverse=True)
    total_bases = bases
    total_gigabases = round(total_bases / 1e9, 2)
    target = total_bases / 2.0

    cumulative = 0
    n50_val = 0
    for x in read_lengths:
        cumulative += x
        if cumulative >= target:
            n50_val = x
            break

    coverage = round(total_bases / actual_genome_size, 2)
    lt100 = round(sum(i for i in read_lengths if i >= 100000) / actual_genome_size, 2)
    lt200 = round(sum(i for i in read_lengths if i >= 200000) / actual_genome_size, 2)
    lt300 = round(sum(i for i in read_lengths if i >= 300000) / actual_genome_size, 2)
    lt400 = round(sum(i for i in read_lengths if i >= 400000) / actual_genome_size, 2)
    lt500 = round(sum(i for i in read_lengths if i >= 500000) / actual_genome_size, 2)
    lt1000 = round(sum(i for i in read_lengths if i >= 1000000) / actual_genome_size, 2)
    num1000 = len([i for i in read_lengths if i >= 1000000])

    return {
        'File'        : inFile,
        'flowcell_id' : flowcell_id or "",
        'read_N50'    : n50_val,
        'Gb'          : total_gigabases,
        'coverage'    : coverage,
        '100kb+'      : lt100,
        '200kb+'      : lt200,
        '300kb+'      : lt300,
        '400kb+'      : lt400,
        '500kb+'      : lt500,
        '1Mb+'        : lt1000,
        'whales'      : num1000
    }

def process_aggregated_files(inFile_list, actual_genome_size):
    """
    Process multiple sequencing_summary files as a single aggregated group.
    Extracts the first '_'‐delimited field from the pod5 filename column
    (either 'filename', 'filename_pod5', or 'input_filename') of the first data line
    in each file, collects them in a set, and joins with semicolons.
    Returns a stats dictionary or None.
    """
    read_lengths = []
    bases = 0
    flowcell_ids = set()

    for inFile in inFile_list:
        try:
            if inFile.endswith('.gz'):
                f = gzip.open(inFile, 'rt')
            else:
                f = open(inFile, 'r')
        except Exception as e:
            sys.stderr.write("Error opening file %s: %s\n" % (inFile, str(e)))
            continue

        header = f.readline().strip().split()
        try:
            length_index = header.index("sequence_length_template")
        except ValueError:
            sys.stderr.write("Error: 'sequence_length_template' not found in header of %s\n" % inFile)
            f.close()
            continue

        # Look for filename column - try filename variants
        filename_index = None
        for possible_name in ["filename", "filename_pod5", "input_filename"]:
            try:
                filename_index = header.index(possible_name)
                break
            except ValueError:
                continue

        first_data_line = True
        for line in f:
            if ('filename' in line or 'input_filename' in line) and 'read_id' in line:
                continue

            parts = line.strip().split()
            if len(parts) <= length_index:
                continue

            # On the very first valid data row of this file, capture the pod filename's prefix
            if first_data_line and filename_index is not None and len(parts) > filename_index:
                pod_filename = parts[filename_index]
                prefix = pod_filename.split("_")[0]
                flowcell_ids.add(prefix)
                first_data_line = False

            try:
                length = int(parts[length_index])
            except ValueError:
                continue

            read_lengths.append(length)
            bases += length

        f.close()

    if not read_lengths:
        return None

    read_lengths.sort(reverse=True)
    total_bases = bases
    total_gigabases = round(total_bases / 1e9, 2)
    target = total_bases / 2.0

    cumulative = 0
    n50_val = 0
    for x in read_lengths:
        cumulative += x
        if cumulative >= target:
            n50_val = x
            break

    coverage = round(total_bases / actual_genome_size, 2)
    lt100 = round(sum(i for i in read_lengths if i >= 100000) / actual_genome_size, 2)
    lt200 = round(sum(i for i in read_lengths if i >= 200000) / actual_genome_size, 2)
    lt300 = round(sum(i for i in read_lengths if i >= 300000) / actual_genome_size, 2)
    lt400 = round(sum(i for i in read_lengths if i >= 400000) / actual_genome_size, 2)
    lt500 = round(sum(i for i in read_lengths if i >= 500000) / actual_genome_size, 2)
    lt1000 = round(sum(i for i in read_lengths if i >= 1000000) / actual_genome_size, 2)
    num1000 = len([i for i in read_lengths if i >= 1000000])

    # Join all unique prefixes (should usually all be the same) with semicolons
    flowcell_str = ";".join(sorted(flowcell_ids)) if flowcell_ids else ""

    return {
        'File'        : ",".join(inFile_list),
        'flowcell_id' : flowcell_str,
        'read_N50'    : n50_val,
        'Gb'          : total_gigabases,
        'coverage'    : coverage,
        '100kb+'      : lt100,
        '200kb+'      : lt200,
        '300kb+'      : lt300,
        '400kb+'      : lt400,
        '500kb+'      : lt500,
        '1Mb+'        : lt1000,
        'whales'      : num1000
    }

def main(myCommandLine=None):
    t0 = time.time()

    usageStr = "python %prog [options] sequencing_summary.txt [sequencing_summary2.txt ...]"
    parser = OptionParser(usage=usageStr, version="%prog 0.0.3")
    parser.add_option("--size", dest="genome_size", type="float",
                      help="Genome size in gigabases for coverage calculations (REQUIRED)")
    parser.add_option("--dir", dest="directory", type="string", default=None,
                      help="Directory or wildcard pattern to search for directories containing files starting with 'sequencing_summary' or ending with '_summary.txt.gz'")
    parser.add_option("--nameby", dest="nameby", type="choice", choices=["filename", "dirname", "path"], default="filename",
                      help="How to label each row: 'filename' (default) uses the summary file's basename; 'dirname' uses the matched --dir directory name; 'path' uses the full file path.")
    parser.add_option("--append", dest="append_str", type="string", default="",
                      help="Optional string to append to the file name (default: none)")
    parser.add_option("--no-append", dest="append_str", action="store_const", const="",
                      help="Do not append any string to the file name (overrides --append)")
    (options, args) = parser.parse_args()

    # Ensure genome size was given
    if options.genome_size is None:
        parser.error("--size option is required. Please specify a genome size in gigabases.")

    # Convert genome size from Gb to bases
    actual_genome_size = options.genome_size * 1e9

    # New header: File, flowcell_id, then the original metrics
    header = [
        'File',
        'flowcell_id',
        'read_N50',
        'Gb',
        'coverage',
        '100kb+',
        '200kb+',
        '300kb+',
        '400kb+',
        '500kb+',
        '1Mb+',
        'whales'
    ]

    # Prepare CSV writer
    writer = csv.writer(sys.stdout)
    writer.writerow(header)

    # Directory‐mode
    if options.directory:
        dirs = glob.glob(options.directory)
        if not dirs:
            sys.stderr.write("No directories match the pattern: %s\n" % options.directory)
            sys.exit(1)

        for d in dirs:
            if not os.path.isdir(d):
                continue

            seq_summary_files = glob.glob(os.path.join(d, "**", "sequencing_summary*"), recursive=True)
            summary_files     = glob.glob(os.path.join(d, "**", "*_summary.txt.gz"), recursive=True)
            files = seq_summary_files + summary_files

            if not files:
                sys.stderr.write("Warning: No sequencing summary files found in directory %s\n" % d)
                continue

            for f in files:
                stats = process_single_file(f, actual_genome_size)
                if stats is None:
                    continue

                stats["File"] = get_label(f, d, options.nameby)

                if options.append_str:
                    stats["File"] = stats["File"] + "_" + options.append_str

                row = [str(stats[col]) for col in header]
                writer.writerow(row)

    # Aggregated mode (explicit file list on command line)
    elif args:
        stats = process_aggregated_files(args, actual_genome_size)
        if stats:
            stats["File"] = get_label(stats["File"], None, options.nameby)
            if options.append_str:
                stats["File"] = stats["File"] + "_" + options.append_str
            row = [str(stats[col]) for col in header]
            writer.writerow(row)

    else:
        parser.print_help()
        sys.exit(0)

    sys.stderr.write("Total time for the program: %.3f seconds\n" % (time.time() - t0))

if __name__ == '__main__':
    main()
