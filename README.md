# buffmaid

`buffmaid` means **MERMAID BUFFer autoMAID**.

It is a small, standalone converter for semi-continuous raw MERMAID circular-buffer waveform data. The job is intentionally narrow: read raw binary waveform files and write one miniSEED file per input file.

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

Directory layout can already be organized by time. `buffmaid` discovers files recursively:

```text
2018-09/2018-09-13/2018-09-13T19_25_10.925000
2018-12/2018-12-06/2018-12-06T03_06_14.450000
```

The sampling rate is fixed for all data:

```text
40.01406 Hz
```

`buffmaid` does not use `40 Hz` as a default or fallback.

## What It Does Not Do

`buffmaid` does not do time correction, event analysis, DET/REQ logic, interpolation, gap filling, trace merging, or continuity forcing. It also does not import from or imitate `mermaid-records` parsing/normalization architecture, and it does not add switches or special cases to `automaid`.

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
buffmaid convert \
  --input-root /path/to/raw/files \
  --output-root /path/to/mseed/output \
  --station P0023
```

Full option form:

```bash
buffmaid convert \
  --input-root /path/to/raw/files \
  --output-root /path/to/mseed/output \
  --station P0023 \
  --network MH \
  --location 10 \
  --channel BHZ
```

CLI help:

```bash
buffmaid convert --help
```

## CLI Options

`--input-root INPUT_ROOT`

Root directory to search recursively for raw binary input files. Every discovered regular file is interpreted as one raw `<i4` waveform file whose filename is its UTC start time.

`--output-root OUTPUT_ROOT`

Directory where output `.mseed` files and the transition JSONL log are written. Output waveform files are written flat into this directory.

`--station STATION`

Required station code, for example `P0023`. This is written to `trace.stats.station` and included in the output filename.

`--network NETWORK`

Network code. Default: `MH`. This is written to `trace.stats.network` and included in the output filename.

`--location LOCATION`

Location code. Default: `10`. This is written to `trace.stats.location` and included in the output filename.

`--channel CHANNEL`

Channel code. Default: `BHZ`. This is written to `trace.stats.channel` and included in the output filename.

The raw input files have no header or metadata, so `--network`, `--station`, `--location`, and `--channel` do not select data from the input. They label every output trace produced by that run.

For example:

```bash
buffmaid convert \
  --input-root raw \
  --output-root mseed \
  --station P0023 \
  --channel BDF
```

writes traces with `trace.stats.channel = "BDF"` and filenames like:

```text
MH.P0023.10.BDF.2018-12-06T03_06_14.450000.mseed
```

## Output Files

Each input binary file produces exactly one output `.mseed` file. Output filenames use SNCL plus the original source timestamp string:

```text
MH.P0023.10.BHZ.2018-12-06T03_06_14.450000.mseed
```

miniSEED metadata is written with ObsPy. The data quality indicator is set explicitly to `R`.

## Transition Log

Even though waveform files are written one-to-one, `buffmaid` sorts discovered input files by parsed start time and logs every transition between consecutive segments:

```text
buffmaid_transition_records.jsonl
```

Each record includes the previous file, next file, start times, sample counts, expected next start time, delta in seconds and samples, and a transition kind:

```text
adjacent | gap | overlap
```

Adjacency uses a tolerance of half a sample:

```text
0.5 / 40.01406 seconds
```

## Development

Run tests with:

```bash
python -m pytest
```
