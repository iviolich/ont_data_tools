#!/usr/bin/env python
"""
calculate_summary_stats_rna.py

Computes RNA sequencing metrics (in millions of reads rather than genome coverage).
Reports total gigabases, N50, total reads, and read counts at q5/q10/q15/q20/q25 thresholds.

Options:
  --dir        : Directory or wildcard pattern to search for files starting with "sequencing_summary"
                 or ending with "_summary.txt.gz".
                 (If provided, the script processes each matching file individually.)
  --nameby     : How to label each row (default: "filename"):
                   filename  — basename of the summary file (good for cluster flat output dirs
                               where the BAM name is baked into the filename)
                   dirname   — basename of the matched --dir directory (good for local PromethION
                               runs where summary files are deep inside per-sample directories)
                   path      — full file path
  --append     : A string to append (with an underscore) to the sample name (default: none).
  --no-append  : Overrides --append and does not append any string.
  -n/--name    : Override the sample name (aggregated mode only).

Usage Examples:
  Aggregated mode:
    python calculate_summary_stats_rna.py file1.txt file2.txt

  Aggregated mode with explicit sample name:
    python calculate_summary_stats_rna.py -n MySample file1.txt file2.txt

  Directory mode, label by matched directory name (local PromethION):
    python calculate_summary_stats_rna.py --dir "*RNA*" --nameby dirname

  Directory mode, label by filename (cluster flat output dir):
    python calculate_summary_stats_rna.py --dir "/project/out" --nameby filename
"""

import os, sys, time, gzip, glob, csv
import argparse


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


def _open_file(inFile):
    if inFile.endswith('.gz'):
        return gzip.open(inFile, 'rt')
    return open(inFile, 'r')


def _parse_file(inFile):
    """
    Generator that yields (length, qscore) for each read in a summary file.
    Reads line-by-line to avoid loading the full file into memory.
    """
    try:
        f = _open_file(inFile)
    except Exception as e:
        sys.stderr.write("Error opening file %s: %s\n" % (inFile, str(e)))
        return

    try:
        header = f.readline().strip().split()
    except Exception as e:
        sys.stderr.write("Error reading header of %s: %s\n" % (inFile, str(e)))
        f.close()
        return

    try:
        length_index = header.index("sequence_length_template")
    except ValueError:
        sys.stderr.write("Error: 'sequence_length_template' not found in header of %s\n" % inFile)
        f.close()
        return

    try:
        qscore_index = header.index("mean_qscore_template")
    except ValueError:
        sys.stderr.write("Error: 'mean_qscore_template' not found in header of %s\n" % inFile)
        f.close()
        return

    for line in f:
        parts = line.strip().split()
        if len(parts) <= max(length_index, qscore_index):
            continue
        try:
            length = int(parts[length_index])
            qscore = float(parts[qscore_index])
        except ValueError:
            continue
        yield length, qscore

    f.close()


def process_rna_file(inFile):
    """
    Processes a single RNA sequencing summary file.
    Returns a dictionary with the computed metrics.
    """
    total_reads = 0
    total_bases = 0
    count_q5 = count_q10 = count_q15 = count_q20 = count_q25 = 0
    read_lengths = []

    for length, qscore in _parse_file(inFile):
        total_reads += 1
        total_bases += length
        read_lengths.append(length)
        if qscore >= 5:  count_q5  += 1
        if qscore >= 10: count_q10 += 1
        if qscore >= 15: count_q15 += 1
        if qscore >= 20: count_q20 += 1
        if qscore >= 25: count_q25 += 1

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

    return {
        'Sample': inFile,  # will be transformed below
        'total_Gbp': round(total_bases / 1E9, 2),
        'N50': N50,
        'total_reads_M': total_reads / 1E6,
        'q5_reads_M':  round(count_q5  / 1E6, 2),
        'q10_reads_M': round(count_q10 / 1E6, 2),
        'q15_reads_M': round(count_q15 / 1E6, 2),
        'q20_reads_M': round(count_q20 / 1E6, 2),
        'q25_reads_M': round(count_q25 / 1E6, 2),
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
        for length, qscore in _parse_file(inFile):
            total_reads += 1
            total_bases += length
            read_lengths.append(length)
            if qscore >= 5:  count_q5  += 1
            if qscore >= 10: count_q10 += 1
            if qscore >= 15: count_q15 += 1
            if qscore >= 20: count_q20 += 1
            if qscore >= 25: count_q25 += 1

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

    return {
        'Sample': ",".join(file_list),
        'total_Gbp': round(total_bases / 1E9, 2),
        'N50': N50,
        'total_reads_M': total_reads / 1E6,
        'q5_reads_M':  round(count_q5  / 1E6, 2),
        'q10_reads_M': round(count_q10 / 1E6, 2),
        'q15_reads_M': round(count_q15 / 1E6, 2),
        'q20_reads_M': round(count_q20 / 1E6, 2),
        'q25_reads_M': round(count_q25 / 1E6, 2),
    }


def main(myCommandLine=None):
    t0 = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument('nfile', nargs='*', help="Input RNA sequencing summary files")
    parser.add_argument("-n", "--name", help="The sample name")
    parser.add_argument("--dir", dest="directory", type=str, default=None,
                        help="Directory or wildcard pattern to search for files starting with 'sequencing_summary' or ending with '_summary.txt.gz'")
    parser.add_argument("--nameby", dest="nameby", choices=["filename", "dirname", "path"], default="filename",
                        help="How to label each row: 'filename' (default) uses the summary file's basename; 'dirname' uses the matched --dir directory name; 'path' uses the full file path.")
    parser.add_argument("--append", dest="append_str", type=str, default="",
                        help="Optional string to append to the sample name (default: none)")
    parser.add_argument("--no-append", dest="append_str", action="store_const", const="",
                        help="Do not append any string to the sample name (overrides --append)")
    args = parser.parse_args()

    if not args.nfile and not args.directory:
        parser.print_help()
        sys.exit(0)

    header = ['Sample','total_Gbp','N50','total_reads_M','q5_reads_M','q10_reads_M','q15_reads_M','q20_reads_M','q25_reads_M']

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
            seq_summary_files = glob.glob(os.path.join(d, "**", "sequencing_summary*"), recursive=True)
            summary_files     = glob.glob(os.path.join(d, "**", "*_summary.txt.gz"), recursive=True)
            files = seq_summary_files + summary_files
            if not files:
                sys.stderr.write("Warning: No sequencing_summary files found in directory %s\n" % d)
                continue
            for f in files:
                res = process_rna_file(f)
                if res is not None:
                    res["Sample"] = get_label(f, d, args.nameby)
                    if args.append_str:
                        res["Sample"] = res["Sample"] + "_" + args.append_str
                    results.append(res)
        for res in results:
            writer.writerow([str(res[col]) for col in header])
    else:
        res = process_aggregated_rna_files(args.nfile)
        if res is None:
            sys.stderr.write("No data processed.\n")
            sys.exit(1)
        if args.name:
            res["Sample"] = args.name
        else:
            res["Sample"] = get_label(res["Sample"], None, args.nameby)
        if args.append_str:
            res["Sample"] = res["Sample"] + "_" + args.append_str
        writer.writerow([str(res[col]) for col in header])

    sys.stderr.write("Total time for the program: %.3f seconds\n" % (time.time() - t0))


if __name__ == '__main__':
    main()
