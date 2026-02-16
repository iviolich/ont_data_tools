#!/usr/bin/env python
"""
pullstats_rna.py

This script computes RNA sequencing metrics (in millions of reads rather than coverage).
It calculates total gigabases, N50, total reads (in millions), and counts (in millions)
for various quality bins.

Additional options:
  --dir        : Directory or wildcard pattern to search for files starting with "sequencing_summary".
                 (If provided, the script processes each matching file individually.)
  --shortname  : If "yes" (default), the sample name is derived by taking the second field (delimited by '/')
                 from the file path. If "no", the full file path is used.
  --append     : A string to append (with an underscore) to the sample name (default: "fast").
  --no-append  : Overrides --append and does not append any string.

Positional arguments (nfile) are used in aggregated mode.
An optional sample name can be provided with -n/--name.
"""

import os, sys, time, gzip, glob, csv
import numpy as np
import pandas as pd
import argparse

def transform_file_field(file_field, shortname_option):
    """
    Transforms the file_field based on the shortname_option.
    If shortname_option is "yes", then:
      - For a comma‐separated list (aggregated mode), it transforms each component by splitting on "/" 
        and using the second field.
      - Otherwise, it does the same for a single file path.
    If shortname_option is "no", the original file_field is returned.
    """
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

def process_rna_file(inFile):
    """
    Processes a single RNA sequencing summary file.
    Returns a dictionary with the computed metrics.
    """
    total_reads = 0
    total_bases = 0
    count_q5 = count_q10 = count_q15 = count_q20 = count_q25 = 0
    read_lengths = []

    try:
        if inFile.endswith('.gz'):
            f = gzip.open(inFile, 'rt')
        else:
            f = open(inFile, 'r')
    except Exception as e:
        sys.stderr.write("Error opening file %s: %s\n" % (inFile, str(e)))
        return None

    try:
        # Use a raw string literal for the regex pattern to avoid invalid escape sequence warnings
        df = pd.read_csv(f, sep=r'\s+')
    except Exception as e:
        sys.stderr.write("Error reading file %s: %s\n" % (inFile, str(e)))
        f.close()
        return None
    f.close()

    # Drop columns that are not needed (ignore errors if some columns are missing)
    df = df.drop(columns=['filename', 'read_id', 'run_id', 'channel', 'mux', 
                           'start_time', 'duration', 'template_start', 'template_duration'], 
                 errors='ignore')

    # Create quality bins based on mean_qscore_template
    q5 = df[df['mean_qscore_template'] >= 5]
    q10 = df[df['mean_qscore_template'] >= 10]
    q15 = df[df['mean_qscore_template'] >= 15]
    q20 = df[df['mean_qscore_template'] >= 20]
    q25 = df[df['mean_qscore_template'] >= 25]

    count_q5 = len(q5)
    count_q10 = len(q10)
    count_q15 = len(q15)
    count_q20 = len(q20)
    count_q25 = len(q25)

    bases = df['sequence_length_template']
    total_bases = np.sum(bases)
    total_reads = len(df)
    read_lengths = list(bases)

    # Calculate N50
    read_lengths.sort(reverse=True)
    cumulative_bases = 0
    N50 = 0
    target = total_bases / 2.0
    for length in read_lengths:
        cumulative_bases += length
        if cumulative_bases >= target:
            N50 = length
            break

    total_Gbp = round(total_bases / 1E9, 2)
    total_reads_M = total_reads / 1E6
    count_q5_M = count_q5 / 1E6
    count_q10_M = count_q10 / 1E6
    count_q15_M = count_q15 / 1E6
    count_q20_M = count_q20 / 1E6
    count_q25_M = count_q25 / 1E6

    return {
        'Sample': inFile,  # will be transformed below
        'total_Gbp': total_Gbp,
        'N50': N50,
        'total_reads_M': total_reads_M,
        'q5_reads_M': round(count_q5_M, 2),
        'q10_reads_M': round(count_q10_M, 2),
        'q15_reads_M': round(count_q15_M, 2),
        'q20_reads_M': round(count_q20_M, 2),
        'q25_reads_M': round(count_q25_M, 2)
    }

def process_aggregated_rna_files(file_list):
    """
    Processes multiple RNA files in aggregated mode.
    Returns a dictionary with aggregated metrics.
    """
    total_reads = 0
    total_bases = 0
    count_q5 = count_q10 = count_q15 = count_q20 = count_q25 = 0
    read_lengths = []

    for inFile in file_list:
        try:
            if inFile.endswith('.gz'):
                f = gzip.open(inFile, 'rt')
            else:
                f = open(inFile, 'r')
        except Exception as e:
            sys.stderr.write("Error opening file %s: %s\n" % (inFile, str(e)))
            continue

        try:
            df = pd.read_csv(f, sep=r'\s+')
        except Exception as e:
            sys.stderr.write("Error reading file %s: %s\n" % (inFile, str(e)))
            f.close()
            continue
        f.close()

        df = df.drop(columns=['filename', 'read_id', 'run_id', 'channel', 'mux', 
                               'start_time', 'duration', 'template_start', 'template_duration'], 
                     errors='ignore')

        q5 = df[df['mean_qscore_template'] >= 5]
        q10 = df[df['mean_qscore_template'] >= 10]
        q15 = df[df['mean_qscore_template'] >= 15]
        q20 = df[df['mean_qscore_template'] >= 20]
        q25 = df[df['mean_qscore_template'] >= 25]

        count_q5 += len(q5)
        count_q10 += len(q10)
        count_q15 += len(q15)
        count_q20 += len(q20)
        count_q25 += len(q25)

        bases = df['sequence_length_template']
        total_bases += np.sum(bases)
        total_reads += len(df)
        read_lengths.extend(list(bases))

    if total_reads == 0:
        return None

    read_lengths.sort(reverse=True)
    cumulative_bases = 0
    N50 = 0
    target = total_bases / 2.0
    for length in read_lengths:
        cumulative_bases += length
        if cumulative_bases >= target:
            N50 = length
            break

    total_Gbp = round(total_bases / 1E9, 2)
    total_reads_M = total_reads / 1E6
    count_q5_M = count_q5 / 1E6
    count_q10_M = count_q10 / 1E6
    count_q15_M = count_q15 / 1E6
    count_q20_M = count_q20 / 1E6
    count_q25_M = count_q25 / 1E6

    sample_field = ",".join(file_list)

    return {
        'Sample': sample_field,
        'total_Gbp': total_Gbp,
        'N50': N50,
        'total_reads_M': total_reads_M,
        'q5_reads_M': round(count_q5_M, 2),
        'q10_reads_M': round(count_q10_M, 2),
        'q15_reads_M': round(count_q15_M, 2),
        'q20_reads_M': round(count_q20_M, 2),
        'q25_reads_M': round(count_q25_M, 2)
    }

def main(myCommandLine=None):
    t0 = time.time()
    parser = argparse.ArgumentParser()
    # Positional argument for RNA files (aggregated mode)
    parser.add_argument('nfile', nargs='*', help="Input RNA sequencing summary files")
    # Optional sample name
    parser.add_argument("-n", "--name", help="The sample name")
    # --dir option for directory mode
    parser.add_argument("--dir", dest="directory", type=str, default=None,
                        help="Directory or wildcard pattern to search for files starting with 'sequencing_summary'")
    # --shortname option (choice yes/no, default yes)
    parser.add_argument("--shortname", dest="shortname", choices=["yes", "no"], default="yes",
                        help="If 'yes' (default), output only the second field from the file path; if 'no', output the full file path.")
    # --append option (default "fast")
    parser.add_argument("--append", dest="append_str", type=str, default="fast",
                        help="Optional string to append to the sample name (default: fast)")
    # --no-append option to override --append (store constant empty string)
    parser.add_argument("--no-append", dest="append_str", action="store_const", const="",
                        help="Do not append any string to the sample name (overrides --append)")
    args = parser.parse_args()

    if not args.nfile and not args.directory:
        parser.print_help()
        sys.exit(0)

    header = ['Sample','total_Gbp','N50','total_reads_M','q5_reads_M','q10_reads_M','q15_reads_M','q20_reads_M','q25_reads_M']

    # Set up a CSV writer to output comma-delimited rows
    writer = csv.writer(sys.stdout)
    writer.writerow(header)

    if args.directory:
        dirs = glob.glob(args.directory)
        if not dirs:
            sys.stderr.write("No directories match the pattern: %s\n" % args.directory)
            sys.exit(1)
        results = []
        for d in dirs:
            if not os.path.isdir(d):
                continue
            files = glob.glob(os.path.join(d, "**", "sequencing_summary*"), recursive=True)
            if not files:
                sys.stderr.write("Warning: No sequencing_summary files found in directory %s\n" % d)
                continue
            for f in files:
                res = process_rna_file(f)
                if res is not None:
                    results.append(res)
        for res in results:
            res["Sample"] = transform_file_field(res["Sample"], args.shortname)
            if args.append_str:
                res["Sample"] = res["Sample"] + "_" + args.append_str
            row = [str(res[col]) for col in header]
            writer.writerow(row)
    else:
        res = process_aggregated_rna_files(args.nfile)
        if res is None:
            sys.stderr.write("No data processed.\n")
            sys.exit(1)
        sample_field = args.name if args.name else res["Sample"]
        res["Sample"] = sample_field
        res["Sample"] = transform_file_field(res["Sample"], args.shortname)
        if args.append_str:
            res["Sample"] = res["Sample"] + "_" + args.append_str
        row = [str(res[col]) for col in header]
        writer.writerow(row)

    sys.stderr.write("Total time for the program: %.3f seconds\n" % (time.time() - t0))

if __name__ == '__main__':
    main()
