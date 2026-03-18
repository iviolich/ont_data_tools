# ONT Data Tools

Tools for Oxford Nanopore sequencing data: basecalling with Dorado, demultiplexing, alignment with minimap2, summary statistics, and archival/data management.

For detailed workflow documentation, see the [Workflow Overview](https://ucsc-cgl.atlassian.net/wiki/spaces/~63c888081d7734b550c2052b/pages/2553348107/Workflow+Overview#).

## Prerequisites

- [Dorado](https://github.com/nanoporetech/dorado) (basecaller and demultiplexer)
- [minimap2](https://github.com/lh3/minimap2) (aligner)
- [Miniconda](https://docs.conda.io/en/latest/miniconda.html) with Python 3, pandas, numpy
- [samtools](http://www.htslib.org/)
- GNU coreutils (parallel, gzip, tar)

## Directory Structure

The tools expect a standard layout at `/data/user_scripts/`:

```
/data/user_scripts/
├── scripts/            # This repo
│   ├── basecalling/
│   │   ├── run_dorado_local_dirs.sh
│   │   └── run_dorado_slurm.sh
│   ├── stats/
│   │   ├── calculate_summary_stats_v3.py
│   │   ├── calculate_summary_stats_v3_under_100kb.py
│   │   ├── calculate_summary_stats_rna.py
│   │   └── run_stats_slurm.sh
│   ├── archival/
│   │   ├── tar_flowcells.sh
│   │   ├── tar_cleanup.sh
│   │   └── tar_report.sh
│   ├── demultiplexing/
│   │   ├── demux_dorado_slurm.sh
│   │   └── demux_dorado_local.sh
│   ├── alignment/
│   │   ├── align_minimap_slurm.sh
│   │   └── align_minimap_local.sh
│   ├── summary/
│   │   └── summary_dorado_slurm.sh
│   ├── utilities/
│   │   ├── cleanup.sh
│   │   └── organize.sh
│   └── bashrc_additions.sh
├── tools/              # External tools (dorado, miniconda3, samtools)
└── ref_files/          # Reference genomes
```

## Scripts

### Basecalling

- **`basecalling/run_dorado_local_dirs.sh`** — Tower basecalling. Processes a list of directories containing pod5 files sequentially with Dorado. Supports DNA/RNA models, modification calling, and dry-run mode.
- **`basecalling/run_dorado_slurm.sh`** — SLURM cluster basecalling. Runs as an array job — each task processes one pod5 path from a list. Supports S3 downloads, tar extraction, and fast5-to-pod5 conversion. Edit `BASE_DIR` at the top for your cluster paths.

### Demultiplexing

- **`demultiplexing/demux_dorado_slurm.sh`** — SLURM cluster demultiplexing. Runs as an array job — each task demultiplexes one BAM using `dorado demux`. Supports re-classification or splitting pre-tagged reads from basecalling (`--no_classify`). Edit `BASE_DIR` at the top for your cluster paths.
- **`demultiplexing/demux_dorado_local.sh`** — Local machine demultiplexing. Processes all BAMs in a list sequentially. Same options as the SLURM version.

### Alignment

- **`alignment/align_minimap_slurm.sh`** — SLURM cluster alignment. Runs as an array job — each task aligns one input file (BAM, FASTQ, or FASTQ.gz) to a reference genome using minimap2. Outputs a sorted, indexed BAM. Edit `BASE_DIR` at the top for your cluster paths.
- **`alignment/align_minimap_local.sh`** — Local machine alignment. Processes all inputs in a list sequentially. Defaults to 48 threads (or `nproc` if fewer available), overridable with `--threads`.

### Dorado Summary

- **`summary/summary_dorado_slurm.sh`** — SLURM array job to run `dorado summary` on a list of BAMs, one per task. Outputs a gzipped TSV per BAM.

### Summary Statistics

- **`stats/calculate_summary_stats_v3.py`** — Coverage, N50, and read length distribution for DNA runs (UL bins: 100kb–1Mb+).
- **`stats/calculate_summary_stats_v3_under_100kb.py`** — Same metrics with finer bins for shorter reads (20kb–100kb+).
- **`stats/calculate_summary_stats_rna.py`** — RNA-specific metrics: total reads (millions), quality score bins (Q5–Q25).
- **`stats/run_stats_slurm.sh`** — Generic SLURM wrapper to run any stats script on the cluster, capturing stdout to a file for Google Sheets import.

### Archival

- **`archival/tar_flowcells.sh`** — Tar flowcell directories in parallel for transfer.
- **`archival/tar_cleanup.sh`** — Verify tar archives against source directories and clean up originals.
- **`archival/tar_report.sh`** — Generate a CSV report comparing tar archives to source data.

### Utilities

- **`utilities/cleanup.sh`** — Verify archived data against a remote destination and optionally delete local copies.
- **`utilities/organize.sh`** — Sort files into an organized upload folder structure by sample ID.

## Deployment

1. Clone this repo as `scripts` under `/data/user_scripts/`:
   ```bash
   git clone <repo_url> /data/user_scripts/scripts
   ```
2. Append the contents of `bashrc_additions.sh` to your `~/.bashrc`
3. Install Dorado and miniconda into `/data/user_scripts/tools/`
4. Create a `current` symlink pointing to the active Dorado version:
   ```bash
   ln -sfn /data/user_scripts/tools/dorado/dorado-1.3.0-linux-x64 \
           /data/user_scripts/tools/dorado/current
   ```
   Update the symlink when upgrading Dorado — the basecalling scripts use it by default.
5. Install Python dependencies: `conda install pandas numpy`

## Usage

### Basecalling (Tower)

```bash
# DNA basecalling with modifications
run_dorado_local_dirs.sh \
  --dirlist dna_dirs.txt \
  --model sup@v5.0.0 \
  --mod 5mCG_5hmCG,6mA \
  --output ./dna_output

# RNA basecalling with poly-A estimation
run_dorado_local_dirs.sh \
  --dirlist rna_dirs.txt \
  --model rna004_130bps_sup@v5.1.0 \
  --drd_opts "--estimate-poly-a" \
  --output ./rna_output

# Dry run (print commands without executing)
run_dorado_local_dirs.sh \
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

# RNA basecalling with poly-A estimation
sbatch -J dorado_RNA --array=1-4%2 run_dorado_slurm.sh \
  --pod5list rna_paths.list \
  --model rna004_130bps_sup@v5.1.0 \
  --drd_opts "--estimate-poly-a" \
  --project /private/nanopore/basecalled/MyRNAProject/
```

### Demultiplexing (SLURM cluster)

```bash
# Demultiplex, classifying reads during demux (kit not used at basecalling)
sbatch -J demux_SAMPLE --array=1-4 demux_dorado_slurm.sh \
  --bamlist bams.list \
  --kit SQK-NBD114-24 \
  --project /private/nanopore/demultiplexed/MyProject/

# Split pre-tagged reads (kit was passed to dorado basecaller)
sbatch -J demux_SAMPLE --array=1-4 demux_dorado_slurm.sh \
  --bamlist bams.list \
  --kit SQK-NBD114-24 \
  --no_classify \
  --project /private/nanopore/demultiplexed/MyProject/
```

### Demultiplexing (local)

```bash
bash demux_dorado_local.sh \
  --bamlist bams.list \
  --kit SQK-NBD114-24 \
  --project /data/demultiplexed/MyProject/
```

### Alignment (SLURM cluster)

```bash
# DNA alignment (default map-ont preset)
sbatch -J align_SAMPLE --array=1-4 align_minimap_slurm.sh \
  --inputlist reads.list \
  --reference /private/nanopore/references/genome.fa \
  --project /private/nanopore/aligned/MyProject/

# RNA/cDNA alignment (splice-aware)
sbatch -J align_SAMPLE --array=1-4 align_minimap_slurm.sh \
  --inputlist reads.list \
  --reference /private/nanopore/references/genome.fa \
  --preset splice \
  --mm2_opts "--secondary=no -s 40 -G 350k" \
  --project /private/nanopore/aligned/MyProject/
```

### Alignment (local)

```bash
bash align_minimap_local.sh \
  --inputlist reads.list \
  --reference /data/references/genome.fa \
  --project /data/aligned/MyProject/
```

### Dorado Summary (SLURM cluster)

```bash
sbatch -J summary_SAMPLE --array=1-4 summary_dorado_slurm.sh \
  --bamlist bams.list \
  --project /private/nanopore/summaries/MyProject/
```

### Summary Statistics

The `--nameby` option controls how each row is labelled:
- `dirname` — use the name of the directory matched by `--dir` (recommended locally, where summary files are deep inside per-sample directories)
- `filename` — use the basename of the summary file itself (recommended on the cluster, where BAM-named summaries are in a flat output directory)
- `path` — use the full file path

```bash
# DNA stats — local PromethION, label by matched directory name
pullstats_dna_ul --size 3.3 --dir "*DogT2T*" --nameby dirname

# DNA stats — cluster flat output dir, label by filename
pullstats_dna_ul --size 3.3 --dir "/private/nanopore/basecalled/MyProject" --nameby filename

# RNA stats — local PromethION
pullstats_rna --dir "*RNA*" --nameby dirname

# Any stats script on SLURM (avoids running on login node)
sbatch -J stats_SAMPLE run_stats_slurm.sh \
  --script /path/to/calculate_summary_stats_v3.py \
  --out results.csv \
  --args "--size 3.3 --no-append --nameby filename --dir /private/nanopore/basecalled/MyProject"
```

The `pullstats_*` shell functions (defined in `bashrc_additions.sh`) activate conda and call the appropriate Python script.
