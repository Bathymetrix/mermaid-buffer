# mermaid-buffer

`mermaid-buffer` is a small, standalone converter for semi-continuous raw MERMAID circular-buffer waveform data. The v0 command reads raw binary waveform files and writes one miniSEED file per input file.

## What It Converts

Input files must contain only little-endian signed 32-bit integer samples:

```text
NumPy dtype: <i4
```

There is no file header, and no extension is required. The filename is the UTC start time of the first sample:

```text
2018-12-06T03_06_14.450000
2018-11-03T10_53_50
```

Directory layout can already be organized by time. The converter discovers files recursively:

```text
2018-09/2018-09-13/2018-09-13T19_25_10.925000
2018-12/2018-12-06/2018-12-06T03_06_14.450000
```

Dot files and files that cannot be parsed as raw inputs are skipped instead of stopping the run. Each skipped file is recorded with a reason in `buffer2mseed_skipped_files.jsonl`.

The sampling frequency defaults to:

```text
40.01406 Hz
```

Pass `-fs` or `--sampling-frequency` to use a different positive value in Hz. The converter does not use `40 Hz` as a default or fallback.

## What It Does Not Do

`mermaid-buffer` does not do time correction, event analysis, DET/REQ logic, interpolation, gap filling, trace merging, or continuity forcing. It also does not import from or imitate `mermaid-records` parsing/normalization architecture, and it does not add switches or special cases to `automaid`.

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Usage

```bash
buffer2mseed \
  --input-root /path/to/raw/files \
  --output-root /path/to/mseed/output \
  --station P0023
```

Short option form:

```bash
buffer2mseed \
  -i /path/to/raw/files \
  -o /path/to/mseed/output \
  -s P0023
```

Full option form:

```bash
buffer2mseed \
  --input-root /path/to/raw/files \
  --output-root /path/to/mseed/output \
  --sampling-frequency 40.01406 \
  --station P0023 \
  --network MH \
  --channel BHZ \
  --location 20
```

CLI help:

```bash
buffer2mseed --help
```

## CLI Options

`-i, --input-root INPUT_ROOT`

Root directory to search recursively for raw binary input files. Every discovered regular file is checked as one raw `<i4` waveform file whose filename is its UTC start time. Dot files and files that do not match are skipped and logged.

`-o, --output-root OUTPUT_ROOT`

Directory where output `.mseed` files, the transition JSONL log, and the skipped-file JSONL log are written. Output waveform files are written flat into this directory.

`-fs, --sampling-frequency HZ`

Sampling frequency in Hz. Default: `40.01406`. This is written to `trace.stats.sampling_rate` and used for transition timing, adjacency tolerance, and channel band-code validation.

`-s, --station STATION`

Required station code, for example `P0023`. This is written to `trace.stats.station` and included in the output filename.

`-n, --network NETWORK`

Network code. Default: `MH`. This is written to `trace.stats.network` and included in the output filename.

`-c, --channel CHANNEL`

Channel code. Default: `BHZ`. This is written to `trace.stats.channel` and included in the output filename.
The channel code must be exactly three alphanumeric characters. Its first letter
is validated as a SEED band code for the selected sampling frequency. At the
default `40.01406 Hz`, `B` and `S` are valid while a channel such as `MHZ` is
rejected.

`-l, --location LOCATION`

Location code. Default: `20`. This is written to `trace.stats.location` and included in the output filename.

The SEED band-code helpers are importable for later reuse:

```python
from mermaid_buffer import band_codes_for_sample_rate, validate_channel_code
```

The raw input files have no header or metadata, so `--network`, `--station`, `--location`, and `--channel` do not select data from the input. They label every output trace produced by that run.

For example:

```bash
buffer2mseed \
  --input-root raw \
  --output-root mseed \
  --station P0023 \
  --channel BDF
```

writes traces with `trace.stats.channel = "BDF"` and filenames like:

```text
MH.P0023.20.BDF.2018-12-06T03_06_14.450000.mseed
```

## Run Model

`buffer2mseed` is stateless. Each invocation is a full-input run over the current `--input-root`; it does not keep a manifest, compare against a previous run, or incrementally decide what changed.

The converter rewrites the output files it owns when the same output filename already exists, including the JSONL logs. It does not audit the output directory, delete extra files, or warn about additional incorrect or outdated files already present there. The caller is responsible for choosing appropriate input and output directories; the CLI does not enforce that they are separate.

## Output Files

Each accepted input binary file produces exactly one output `.mseed` file. Output filenames use SNCL plus the original source timestamp string:

```text
MH.P0023.20.BHZ.2018-12-06T03_06_14.450000.mseed
```

miniSEED metadata is written with ObsPy. The data quality indicator is set explicitly to `R`.

The CLI prints one progress line as each output is written, followed by a concise run summary:

```text
[1/12] 2018-11-03T10_53_50 -> MH.P0023.20.BHZ.2018-11-03T10_53_50.mseed
Processed 12 file(s); skipped 2 file(s).
```

## Skipped-File Log

Discovered dot files, files whose names cannot be parsed as UTC start times, or files whose byte counts are not valid little-endian int32 sample data, are skipped and logged:

```text
buffer2mseed_skipped_files.jsonl
```

Each record includes the file path and skip reason.

## Transition Log

Even though waveform files are written one-to-one, the converter sorts discovered input files by parsed start time and logs every transition between consecutive segments:

```text
buffer2mseed_transition_records.jsonl
```

Each record includes the previous file, next file, start times, sample counts, expected next start time, delta in seconds and samples, and a transition kind:

```text
adjacent | gap | overlap
```

Adjacency uses a tolerance of half a sample:

```text
0.5 / sampling_frequency_hz seconds
```

## Development

Run tests with:

```bash
python -m pytest
```
