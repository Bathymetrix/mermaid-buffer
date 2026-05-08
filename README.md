# mermaid-buffer

`mermaid-buffer` is a small, standalone v1 converter for semi-continuous raw
MERMAID circular-buffer waveform data. The `buffer2mseed` command reads raw
little-endian signed int32 waveform files and writes one miniSEED `.mseed` file
per accepted input file.

## What It Converts

Input files must contain only raw little-endian signed 32-bit integer samples:

```text
NumPy dtype: <i4
```

There is no file header, and no extension is required. The filename is the UTC
start time of the first sample. Supported filename timestamp forms are exactly:

```text
YYYY-MM-DDTHH_MM_SS
YYYY-MM-DDTHH_MM_SS.ffffff
```

Examples:

```text
2018-11-03T10_53_50
2018-12-06T03_06_14.450000
```

Unsupported or malformed timestamp filenames are skipped and logged. Files whose
byte counts are not valid raw int32 sample data are also skipped and logged.

Directory layout can already be organized by time. The converter discovers files
recursively:

```text
2018-09/2018-09-13/2018-09-13T19_25_10.925000
2018-12/2018-12-06/2018-12-06T03_06_14.450000
```

Dot files are skipped and logged. Hidden directories are pruned during recursive
discovery and logged once; their contents are not traversed.

## What It Does Not Do

`mermaid-buffer` does not do time correction, event analysis, DET/REQ logic,
interpolation, gap filling, merging, or continuity forcing. It also does not
import from or imitate [`mermaid-records`](https://github.com/Bathymetrix/mermaid-records)
parsing/normalization architecture, and it does not add switches or special
cases to [`automaid`](https://github.com/earthscopeoceans/automaid).

## Install

```bash
python -m pip install .
```

For development:

```bash
python -m pip install -e ".[dev]"
```

## Usage

The direct CLI contract is:

```bash
buffer2mseed -i INPUT_ROOT -o OUTPUT_ROOT -s STATION
```

Long option form:

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

Full option form with defaults shown explicitly:

```bash
buffer2mseed \
  --input-root /path/to/raw/files \
  --output-root /path/to/mseed/output \
  --station P0023 \
  --network MH \
  --location 20 \
  --channel BDH \
  --sampling-frequency 40.01406 \
  --data_quality R
```

CLI help and version:

```bash
buffer2mseed --help
buffer2mseed --version
```

## CLI Options

`-i, --input-root INPUT_ROOT`

Root directory to search recursively for raw binary input files. Every
discovered regular file is checked as one raw `<i4` waveform file whose filename
is its UTC start time. Dot files are skipped, hidden directories are pruned, and
files that do not match the input contract are skipped and logged.

`-o, --output-root OUTPUT_ROOT`

Directory where output `.mseed` files, the transition JSONL log, and the
skipped-file JSONL log are written. Output waveform files are written flat into
this directory.

`-s, --station STATION`

Required station code, for example `P0023`. This is written to
`trace.stats.station` and included in the output filename.

`-fs, --sampling-frequency HZ`

Sampling frequency in Hz. Default: `40.01406`. This is written to
`trace.stats.sampling_rate` and used for transition timing, adjacency tolerance,
and channel band-code validation. The converter does not use `40 Hz` as a
default or fallback.

`-n, --network NETWORK`

Network code. Default: `MH`. This is written to `trace.stats.network` and
included in the output filename.

`-l, --location LOCATION`

Location code. Default: `20`. This is written to `trace.stats.location` and
included in the output filename.

`-c, --channel CHANNEL`

Channel code. Default: `BDH`. This is written to `trace.stats.channel` and
included in the output filename. The channel code must be exactly three
alphanumeric characters. Its first letter is validated as a SEED waveform band
code for the selected sampling frequency. At the default `40.01406 Hz`, `B` and
`S` are valid while a channel such as `MHZ` is rejected.

`--data_quality INDICATOR`

miniSEED data quality indicator. Default: `R`. The value is normalized to
uppercase and must be one of `D`, `R`, `Q`, or `M`. This is written to
`trace.stats.mseed.dataquality`.

The raw input files have no header or metadata, so `--network`, `--station`,
`--location`, `--channel`, and `--data_quality` do not select data from the
input. They label every output trace produced by that run.

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

`buffer2mseed` is stateless. Each invocation is a full-input run over the
current `--input-root`; it does not keep a manifest, compare against a previous
run, or incrementally decide what changed.

Reruns rewrite same-name `.mseed` outputs. Reruns also rewrite both JSONL logs:

```text
buffer2mseed_transition_records.jsonl
buffer2mseed_skipped_files.jsonl
```

The tool does not prune stale, incorrect, or outdated output files. It does not
audit the output directory or warn about additional files already present there.
The caller is responsible for choosing appropriate input and output directories;
the CLI does not enforce that they are separate.

## Output Files

Each accepted input binary file produces exactly one output `.mseed` file.
Output filenames use SNCL plus the original source timestamp string:

```text
NETWORK.STATION.LOCATION.CHANNEL.SOURCE_TIMESTAMP.mseed
```

Default example:

```text
MH.P0023.20.BDH.2018-12-06T03_06_14.450000.mseed
```

miniSEED metadata is written with ObsPy. The selected sampling frequency is
written to `trace.stats.sampling_rate`, and the data quality indicator is set
explicitly from `--data_quality`.

The CLI prints one progress line as each output is written, followed by a
concise run summary:

```text
[1/12] 2018-11-03T10_53_50 -> MH.P0023.20.BDH.2018-11-03T10_53_50.mseed
Processed 12 file(s); skipped 2 file(s).
```

## Skipped-File Log

Skipped inputs and hidden directories pruned during discovery are recorded in:

```text
buffer2mseed_skipped_files.jsonl
```

Each record includes the skipped path and reason.

## Transition Log

Even though waveform files are written one-to-one, the converter sorts accepted
input files by parsed start time and logs every transition between consecutive
segments:

```text
buffer2mseed_transition_records.jsonl
```

Each record includes the previous file, next file, start times, sample counts,
expected next start time, delta in seconds and samples, and a transition kind:

```text
adjacent | gap | overlap
```

Expected next start is:

```text
previous_starttime + previous_npts / sampling_frequency_hz
```

Adjacency uses a tolerance of half a sample:

```text
0.5 / sampling_frequency_hz seconds
```

## Public API

The package root exposes only the small validation API intended for v1 support:

```python
from mermaid_buffer import (
    DEFAULT_SAMPLING_FREQUENCY_HZ,
    band_codes_for_sample_rate,
    validate_channel_code,
)
```

The bundled `seed_codes.py` module exists to validate miniSEED metadata for this
converter. It should not be treated as a general-purpose SEED/FDSN utility
library.

## Development

Run tests with:

```bash
python -m pytest
```
