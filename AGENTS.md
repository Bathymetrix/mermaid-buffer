# AGENTS.md

Guidance for coding agents working in this repository.

## Collaboration Rules

- The user handles staging and git-mutating commands. Do not run `git add`, `git commit`, `git branch`, `git checkout`, `git push`, or other git-mutating commands unless the user explicitly asks.
- When a coherent work unit is complete, tell the user it is a good commit point and suggest a concise commit message.
- When the thread has accumulated enough context that a fresh thread would be cleaner, tell the user it is a good new-thread point and provide a compact handoff summary.
- Before changing files, briefly explain what will be edited and why.
- Keep generated artifacts out of the repo. Remove accidental `__pycache__`, `.pytest_cache`, build output, and egg-info artifacts when they are produced during verification.

## Naming Rules

- Repository directory: `mermaid-buffer`.
- Distribution/project name: `mermaid-buffer`.
- Python import package: `mermaid_buffer`.
- Console command: `buffer2mseed`.
- Remove user-facing and source mentions of the previous package name.
- Use lowercase `miniSEED` and `.mseed` in prose. Use `format="MSEED"` only when referring to the ObsPy API value.

## CLI Contract

- The CLI is direct, with no `convert` subcommand.
- Supported command shape:

```bash
buffer2mseed -i INPUT_ROOT -o OUTPUT_ROOT -fs SAMPLING_FREQUENCY_HZ -s STATION
```

- Long options must also work:

```bash
buffer2mseed --input-root INPUT_ROOT --output-root OUTPUT_ROOT --sampling-frequency SAMPLING_FREQUENCY_HZ --station STATION
```

- Metadata option aliases:
  - `-s`, `--station`
  - `-n`, `--network`
  - `-c`, `--channel`
  - `-l`, `--location`
- Data quality option:
  - `--data_quality`
- Sampling frequency option aliases:
  - `-fs`, `--sampling-frequency`

- Defaults:
  - network: `MH`
  - location: `20`
  - channel: `BHZ`
  - data quality: `R`
  - sampling frequency: `40.01406`
- Channel codes are supplied by the user or defaulted. They must be exactly three alphanumeric characters.
- Sampling frequency is supplied by the user or defaulted. It must be a positive value in Hz.
- Data quality is supplied by the user or defaulted. It must be one of the miniSEED data quality indicators `D`, `R`, `Q`, or `M`.
- Validate the first channel letter as a SEED waveform band code for the selected sampling frequency before conversion. At the default `40.01406 Hz`, `B` and `S` are valid; reject a code like `MHZ` with a useful error.
- Keep band-code/channel validation importable from the package root, for example `from mermaid_buffer import band_codes_for_sample_rate`.

## Conversion Rules

- Convert raw MERMAID circular-buffer waveform files to one `.mseed` file per input file.
- Raw inputs are little-endian signed int32 samples only, NumPy dtype `<i4`.
- Raw inputs have no header and no required extension.
- The filename is the UTC start time of the first sample.
- Support timestamps with and without fractional seconds, for example:
  - `2018-12-06T03_06_14.450000`
  - `2018-11-03T10_53_50`
- Recursively discover files under `--input-root`.
- Skip dot files instead of treating them as raw inputs.
- Skip discovered files that cannot be parsed as raw inputs instead of crashing.
- Log skipped files with the path and reason.
- Use the default sampling frequency constant `40.01406`. Do not use `40` as a default or fallback.
- Do not add time correction, event analysis, DET/REQ logic, interpolation, gap filling, merging, or continuity forcing.
- Use ObsPy `Trace` and write with `trace.write(outpath, format="MSEED")`.
- Write the selected sampling frequency to `trace.stats.sampling_rate`.
- Set miniSEED data quality explicitly with `trace.stats.mseed = {"dataquality": DATA_QUALITY}`.

## Output Rules

- One input file produces exactly one output `.mseed`.
- Conversion is stateless. Every run discovers the full current input tree.
- Re-run conversion rewrites same-name output files and JSONL logs.
- Do not check output directories for extra incorrect or outdated files, and do not prune them.
- Do not enforce input/output directory separation.
- Output filenames use:

```text
NETWORK.STATION.LOCATION.CHANNEL.SOURCE_TIMESTAMP.mseed
```

- Default example:

```text
MH.P0023.20.BHZ.2018-12-06T03_06_14.450000.mseed
```

- Transition log filename:

```text
buffer2mseed_transition_records.jsonl
```

- Skipped-file log filename:

```text
buffer2mseed_skipped_files.jsonl
```

- Skipped-file records include the skipped file path and reason.
- Transition records sort discovered inputs by parsed start time and log every consecutive transition as `adjacent`, `gap`, or `overlap`.
- Expected next start is `previous_starttime + previous_npts / sampling_frequency_hz`.
- Adjacency tolerance is `0.5 / sampling_frequency_hz` seconds.
- During conversion, the CLI prints one `[X/Y] INPUT_BASENAME -> OUTPUT_BASENAME.mseed` line per written file.
- The CLI prints a concise processed/skipped file count.

## Verification

- Prefer the repo virtual environment when available:

```bash
.venv/bin/python -m pytest
.venv/bin/buffer2mseed --help
```

- If the outer repo directory has recently been renamed, verify that `.venv` does not contain stale absolute paths before relying on installed console scripts.
