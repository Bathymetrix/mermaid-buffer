# mermaid-buffer

These instructions supplement:

- the global Codex AGENTS (`~/.codex/AGENTS.md`)
- the shared MERMAID AGENTS (`$MERMAID/AGENTS.md`)

The shared MERMAID AGENTS are considered part of this repository's
instructions.

If they cannot be located or read for any reason, stop and notify the user
before making changes.

If instructions conflict, this file takes precedence.

## Repository Scope

`mermaid-buffer` converts raw MERMAID circular-buffer waveform files into
miniSEED.

This repository owns:

- raw waveform decoding;
- metadata assignment required for miniSEED;
- conversion logging;
- transition analysis between adjacent waveform files.

It does **not** own:

- waveform processing;
- event detection;
- timeline construction;
- scientific interpretation;
- acquisition inference;
- catalog generation.

## Naming

Use the following canonical names throughout the repository:

- repository: `mermaid-buffer`
- Python package: `mermaid_buffer`
- console command: `mermaid-buffer`

Use lowercase `miniSEED` and `.mseed` in prose.

Use `format="MSEED"` only when referring to the ObsPy API.

## CLI Contract

The supported command is:

```text
mermaid-buffer convert
```

Supported options:

- `-i`, `--input-root`
- `-o`, `--output-root`
- `-f`, `--sampling-frequency`
- `-s`, `--station`
- `-n`, `--network`
- `-l`, `--location`
- `-c`, `--channel`
- `-q`, `--data-quality`

Defaults:

- network: `MH`
- location: `20`
- channel: `BDH`
- data quality: `R`
- sampling frequency: `40.01406`

Validate:

- channel codes are exactly three alphanumeric characters;
- the first channel letter is compatible with the selected sampling
  frequency;
- sampling frequency is positive;
- miniSEED data quality is one of `D`, `R`, `Q`, or `M`.

Treat the CLI and generated files as the primary public interface.

Keep the package's Python API intentionally minimal.

## Conversion Rules

Convert one raw waveform file into one `.mseed` file.

Raw inputs are:

- little-endian signed int32 (`<i4`);
- headerless;
- recursively discovered beneath the input root.

The filename represents the UTC start time of the first sample.

Support timestamps both with and without fractional seconds.

Skip:

- dot files;
- files that cannot be parsed as valid waveform inputs.

Log every skipped file together with the reason.

Always use the requested sampling frequency (default `40.01406 Hz`).

Do not introduce:

- time correction;
- interpolation;
- gap filling;
- merging;
- continuity forcing;
- event analysis;
- DET/REQ logic.

Use ObsPy `Trace` objects and write output with:

```python
trace.write(..., format="MSEED")
```

Populate:

- `trace.stats.sampling_rate`
- `trace.stats.mseed["dataquality"]`

## Output Rules

One input file always produces exactly one output `.mseed`.

Conversion is stateless.

Every run discovers the complete input tree and rewrites outputs having the
same filename.

Do not prune existing output directories.

Do not require input and output directories to differ.

Output filenames use:

```text
NETWORK.STATION.LOCATION.CHANNEL.SOURCE_TIMESTAMP.mseed
```

Transition log:

```text
buffer2mseed_transition_records.jsonl
```

Skipped-file log:

```text
buffer2mseed_skipped_files.jsonl
```

Transition records compare adjacent waveform files ordered by parsed start
time.

Classify transitions only as:

- `adjacent`
- `gap`
- `overlap`

Expected continuity is computed from:

- previous start time;
- previous sample count;
- sampling frequency.

Adjacency tolerance is:

```text
0.5 / sampling_frequency_hz
```

The CLI should report concise conversion progress together with processed and
skipped file totals.

## Public API

The package root intentionally exports only:

- `__version__`

Avoid exposing internal helpers, modules, or classes as stable public API.

## Verification

Prefer the repository virtual environment when available.

Typical verification includes:

```bash
.venv/bin/python -m pytest
.venv/bin/mermaid-buffer --help
.venv/bin/mermaid-buffer convert --help
```

If verifying CI status, prefer GitHub CLI when available and report relevant
workflow and matrix results.
