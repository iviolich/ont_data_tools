# Nanopore Sequencing Pipeline

Data processing pipeline for Oxford Nanopore sequencing: basecalling with Dorado, summary statistics, and archival utilities.

## Prerequisites

- [Dorado](https://github.com/nanoporetech/dorado) (basecaller)
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) with Python 3, pandas, numpy
- [samtools](http://www.htslib.org/)
- GNU coreutils (parallel, gzip, tar)

## Directory Structure

The pipeline expects a standard layout at `/data/user_scripts/`:

```
/data/user_scripts/
├── scripts/        # This repo — pipeline scripts
├── tools/          # External tools (dorado, miniconda3, samtools)
└── ref_files/      # Reference genomes
```

## Scripts

### Basecalling (Tower)

- **`run_dorado_local_dirs.sh`** — Tower basecalling. Processes a list of directories containing pod5 files sequentially with Dorado. Supports DNA/RNA models, modification calling, alignment, and dry-run mode.

### Basecalling (SLURM Cluster)

- **`run_dorado_slurm.sh`** — SLURM array job basecalling. Each task processes one pod5 path from a list. Supports S3 downloads, tar extraction, fast5-to-pod5 conversion, and duplex mode. Edit `BASE_DIR` at the top for your cluster paths.

### Summary Statistics

- **`calculate_summary_stats_v3.py`** — Compute coverage, N50, and read length distribution for DNA sequencing runs (standard UL bins: 100kb–1Mb+).
- **`calculate_summary_stats_v3_under_100kb.py`** — Same metrics with finer bins for shorter reads (20kb–100kb+).
- **`calculate_summary_stats_rna.py`** — RNA-specific metrics: total reads (millions), quality score bins (Q5–Q25).

### Archival

- **`tar_flowcells.sh`** — Tar flowcell directories in parallel for transfer.
- **`tar_cleanup.sh`** — Verify tar archives against source directories and clean up originals.
- **`tar_report.sh`** — Generate a CSV report comparing tar archives to source data.

### Utilities

- **`cleanup.sh`** — Verify archived data against a remote destination and optionally delete local copies.
- **`organize.sh`** — Sort files into an organized upload folder structure by sample ID.

## Deployment

1. Clone this repo into `/data/user_scripts/scripts/`
2. Append the contents of `.bashrc` to your `~/.bashrc` (or copy the conda init block and alias functions)
3. Install Dorado and miniconda into `/data/user_scripts/tools/`
4. Install Python dependencies: `conda install pandas numpy`

## Usage

### Basecalling (Tower)

```bash
# DNA basecalling with modifications
./run_dorado_local_dirs.sh \
  --dirlist dna_dirs.txt \
  --model sup@v5.0.0 \
  --mod 5mCG_5hmCG,6mA \
  --output ./dna_output

# RNA basecalling with poly-A estimation
./run_dorado_local_dirs.sh \
  --dirlist rna_dirs.txt \
  --model rna004_130bps_sup@v5.1.0 \
  --estimate-poly-a \
  --output ./rna_output

# Dry run (print commands without executing)
./run_dorado_local_dirs.sh \
  --dirlist dirs.txt \
  --model sup@v5.0.0 \
  --dryrun
```

### Basecalling (SLURM cluster)

```bash
# Submit array job for 10 pod5 paths, 2 at a time
sbatch -J dorado_SAMPLE --array=1-10%2 run_dorado_slurm.sh \
  --pod5list paths.list \
  --model sup@v5.0.0 \
  --mod 5mCG_5hmCG,6mA \
  --project /private/nanopore/basecalled/MyProject/
```

### Summary Statistics

```bash
# DNA stats for all runs matching a pattern
pullstats_dna_ul --size 3.3 --dir "/data/run_*"

# DNA stats with finer bins (HMW / under-100kb focus)
pullstats_dna_hmw --size 3.3 --dir "/data/run_*"

# RNA stats
pullstats_rna --dir "/data/rna_run_*"
```

The `pullstats_*` shell functions (defined in `.bashrc`) activate conda and call the appropriate Python script.
