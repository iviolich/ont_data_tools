#!/usr/bin/env python
"""
calculate_summary_stats_v3.py

Based on the original script by Miten Jain, this version:
  1. Requires a --size option (in gigabases) to set the genome size.
  2. Adds a --dir option which accepts a directory or wildcard pattern. When provided,
     the script will expand the pattern, search each matching directory recursively for
     files starting with "sequencing_summary" OR ending with "_summary.txt.gz", 
     process each file individually, and output a CSV table.
  3. Adds a --shortname option that accepts "yes" (default) or "no". If "yes", the "File" field is replaced
     by the second field of the file path (delimited by '/'); if "no", the full file path is used.
  4. Adds a --append option (default "fast") to append an underscore and a string to the file name.
     If you don't want anything appended, use --no-append to override --append.
  5. Uses the **first field of each read's "filename" or "filename_pod5"** (split on `_`) as "flowcell_id".  

Usage Examples:
  Aggregated mode (default behavior, with shortname and appended "fast"):
    python calculate_summary_stats_v3.py --size 3.3 file1.txt file2.txt

  Directory mode (with default --shortname and appended "_fast"):
    python calculate_summary_stats_v3.py --size 3.3 --dir "*EnTEX*"

  To run without shortening the file name:
    python calculate_summary_stats_v3.py --size 3.3 --shortname no --dir "*EnTEX*"

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

def transform_file_field(file_field, shortname_option):
    if shortname_option != "yes":
        return file_field

    if "," in file_field:
        files_list = file_field.split(",")
        new_list = []
        for item in files_list:
            parts = item.split("/")
            new_list.append(parts[1] if len(parts) >= 2 else item)
        return ",".join(new_list)
    else:
        parts = file_field.split("/")
        return parts[1] if len(parts) >= 2 else file_field

def extract_flowcell_id(header, parts):
    try:
        idx = header.index("filename_pod5")
    except ValueError:
        try:
            idx = header.index("filename")
        except ValueError:
            return ""

    if len(parts) > idx:
        return parts[idx].split("_")[0]
    return ""

def process_single_file(inFile, actual_genome_size):
    read_lengths = []
    bases = 0
    flowcell_id = None

    try:
        f = gzip.open(inFile, 'rt') if inFile.endswith('.gz') else open(inFile, 'r')
    except Exception as e:
        sys.stderr.write("Error opening file %s: %s\n" % (inFile, str(e)))
        return None

    header = f.readline().strip().split()
    try:
        length_index = header.index("sequence_length_template")
    except ValueError:
        sys.stderr.write("Error: 'sequence_length_template' not found in header of %s\n" % inFile)
        f.close()
        return None

    for line in f:
        if 'filename' in line and 'read_id' in line:
            continue

        parts = line.strip().split()
        if len(parts) <= length_index:
            continue

        if flowcell_id is None:
            flowcell_id = extract_flowcell_id(header, parts)

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
    lt20 = round(sum(i for i in read_lengths if i >= 20000) / actual_genome_size, 2)
    lt40 = round(sum(i for i in read_lengths if i >= 40000) / actual_genome_size, 2)
    lt60 = round(sum(i for i in read_lengths if i >= 60000) / actual_genome_size, 2)
    lt80 = round(sum(i for i in read_lengths if i >= 80000) / actual_genome_size, 2)
    lt100 = round(sum(i for i in read_lengths if i >= 100000) / actual_genome_size, 2)
    num1000 = len([i for i in read_lengths if i >= 1000000])

    return {
        'File': inFile,
        'flowcell_id': flowcell_id or "",
        'read_N50': n50_val,
        'Gb': total_gigabases,
        'coverage': coverage,
        '20kb+': lt20,
        '40kb+': lt40,
        '60kb+': lt60,
        '80kb+': lt80,
        '100kb+': lt100,
        'whales': num1000
    }

def process_aggregated_files(files, actual_genome_size):
    read_lengths = []
    bases = 0
    flowcell_ids = set()
    file_names = []

    for inFile in files:
        try:
            f = gzip.open(inFile, 'rt') if inFile.endswith('.gz') else open(inFile, 'r')
        except Exception as e:
            sys.stderr.write("Error opening file %s: %s\n" % (inFile, str(e)))
            continue

        file_names.append(inFile)
        header = f.readline().strip().split()
        try:
            length_index = header.index("sequence_length_template")
        except ValueError:
            sys.stderr.write("Error: 'sequence_length_template' not found in header of %s\n" % inFile)
            f.close()
            continue

        for line in f:
            if 'filename' in line and 'read_id' in line:
                continue

            parts = line.strip().split()
            if len(parts) <= length_index:
                continue

            flowcell_id = extract_flowcell_id(header, parts)
            if flowcell_id:
                flowcell_ids.add(flowcell_id)

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
    lt20 = round(sum(i for i in read_lengths if i >= 20000) / actual_genome_size, 2)
    lt40 = round(sum(i for i in read_lengths if i >= 40000) / actual_genome_size, 2)
    lt60 = round(sum(i for i in read_lengths if i >= 60000) / actual_genome_size, 2)
    lt80 = round(sum(i for i in read_lengths if i >= 80000) / actual_genome_size, 2)
    lt100 = round(sum(i for i in read_lengths if i >= 100000) / actual_genome_size, 2)
    num1000 = len([i for i in read_lengths if i >= 100000])

    return {
        'File': ",".join(file_names),
        'flowcell_id': ",".join(sorted(flowcell_ids)),
        'read_N50': n50_val,
        'Gb': total_gigabases,
        'coverage': coverage,
        '20kb+': lt20,
        '40kb+': lt40,
        '60kb+': lt60,
        '80kb+': lt80,
        '100kb+': lt100,
        'whales': num1000
    }
    
def main(myCommandLine=None):
    t0 = time.time()

    usageStr = "python %prog [options] sequencing_summary.txt [sequencing_summary2.txt ...]"
    parser = OptionParser(usage=usageStr, version="%prog 0.0.3")
    parser.add_option("--size", dest="genome_size", type="float",
                      help="Genome size in gigabases for coverage calculations (REQUIRED)")
    parser.add_option("--dir", dest="directory", type="string", default=None,
                      help="Directory or wildcard pattern to search for directories containing files starting with 'sequencing_summary' or ending with '_summary.txt.gz'")
    parser.add_option("--shortname", dest="shortname", type="choice", choices=["yes", "no"], default="yes",
                      help="If 'yes' (default), output only the second field from the file path; if 'no', output the full file path.")
    parser.add_option("--append", dest="append_str", type="string", default="fast",
                      help="Optional string to append to the file name (default: fast)")
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
        '20kb+',
        '40kb+',
        '60kb+',
        '80kb+',
        '100kb+',
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

                # Shorten "File" if requested
                stats["File"] = transform_file_field(stats["File"], options.shortname)

                # Append string if provided
                if options.append_str:
                    stats["File"] = stats["File"] + "_" + options.append_str

                # Write out all columns
                row = [str(stats[col]) for col in header]
                writer.writerow(row)

    # Aggregated mode (explicit file list on command line)
    elif args:
        stats = process_aggregated_files(args, actual_genome_size)
        if stats:
            stats["File"] = transform_file_field(stats["File"], options.shortname)
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