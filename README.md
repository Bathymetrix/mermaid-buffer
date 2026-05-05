# buffmaid

MERMAID BUFFer autoMAID: a small converter for semi-continuous raw MERMAID circular-buffer waveform data.

`buffmaid` converts raw binary waveform files containing only little-endian signed int32 samples (`<i4`) into MiniSEED2 files with ObsPy. It does not apply time correction, interpolation, event logic, gap filling, trace merging, or continuity forcing. One input file produces exactly one output `.mseed` file.

The sampling rate is fixed for all data:

```text
40.01406 Hz
```

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

Optional metadata fields:

```bash
buffmaid convert \
  --input-root /path/to/raw/files \
  --output-root /path/to/mseed/output \
  --station P0023 \
  --network MH \
  --location 10 \
  --channel BHZ
```

Input files are discovered recursively under `--input-root`. Each filename is interpreted as the UTC start time of the first sample, for example:

```text
2018-09/2018-09-13/2018-09-13T19_25_10.925000
2018-12/2018-12-06/2018-12-06T03_06_14.450000
2018-11/2018-11-03/2018-11-03T10_53_50
```

Output files are written flat into `--output-root` using SNCL plus the original source timestamp string:

```text
MH.P0023.10.BHZ.2018-12-06T03_06_14.450000.mseed
```

`buffmaid` also writes a transition log to:

```text
buffmaid_transition_records.jsonl
```

Each JSONL record describes the transition between consecutive input files sorted by parsed start time and marks it as `adjacent`, `gap`, or `overlap`.
