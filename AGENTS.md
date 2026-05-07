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
buffer2mseed -i INPUT_ROOT -o OUTPUT_ROOT -S STATION
```

- Long options must also work:

```bash
buffer2mseed --input-root INPUT_ROOT --output-root OUTPUT_ROOT --station STATION
```

- Metadata option aliases:
  - `-S`, `--station`
  - `-N`, `--network`
  - `-L`, `--location`
  - `-C`, `--channel`

- Defaults:
  - network: `MH`
  - location: `20`
  - channel: `BHZ`
- Channel codes are supplied by the user or defaulted. They must be exactly three alphanumeric characters.
- Validate the first channel letter as a SEED waveform band code for the fixed `40.01406 Hz` sampling rate before conversion. For this rate, `B` and `S` are valid; reject a code like `MHZ` with a useful error.
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
- Use the fixed sampling rate constant `40.01406`. Do not use `40` as a default or fallback.
- Do not add time correction, event analysis, DET/REQ logic, interpolation, gap filling, merging, or continuity forcing.
- Use ObsPy `Trace` and write with `trace.write(outpath, format="MSEED")`.
- Set miniSEED data quality explicitly with `trace.stats.mseed = {"dataquality": "R"}`.

## Output Rules

- One input file produces exactly one output `.mseed`.
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

- Transition records sort discovered inputs by parsed start time and log every consecutive transition as `adjacent`, `gap`, or `overlap`.
- Expected next start is `previous_starttime + previous_npts / 40.01406`.
- Adjacency tolerance is `0.5 / 40.01406` seconds.

## Verification

- Prefer the repo virtual environment when available:

```bash
.venv/bin/python -m pytest
.venv/bin/buffer2mseed --help
```

- If the outer repo directory has recently been renamed, verify that `.venv` does not contain stale absolute paths before relying on installed console scripts.
