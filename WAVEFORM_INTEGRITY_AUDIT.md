# MERMAID Waveform-Integrity Audit

**Repository:** `mermaid-buffer`  
**Audit date:** 2026-08-18  
**Scope:** Read-only scientific and waveform-forensics audit of the tracked repository, including source, tests, documentation, packaging, selected Git history, and isolated temporary round-trip experiments. No tracked code or data was modified during the audit.

## Audit status and priority register

Use these checkboxes as the disposition record for follow-up work. A finding is unchecked until it has been independently assessed and either remediated or explicitly accepted with documented scientific justification.

- [ ] **CRITICAL — Output-path collision can silently lose a waveform.** Two distinct accepted inputs with the same timestamp basename produce the same flat output pathname. The later conversion overwrites the earlier one.
- [ ] **HIGH — SNCL fields can be silently truncated in miniSEED headers.** Network, station, and location are not constrained to their miniSEED field widths, so the filename can disagree with the emitted header.
- [ ] **HIGH — Default STEIM2 serialization rejects some valid int32 series.** A sufficiently large adjacent sample difference aborts the complete run.
- [ ] **HIGH (conditional) — Literal circular buffers are not reconstructed.** If source files are wrapped rings rather than already chronological sample streams, the converter cannot produce scientifically valid ordering.
- [ ] **MEDIUM — The encoded miniSEED sampling rate differs from 40.01406 Hz.** Current serialization produces a small but measurable long-duration timing discrepancy.
- [ ] **MEDIUM — Headerless, four-byte-aligned corruption is accepted as data.** The stated input format makes such corruption indistinguishable from valid int32 samples.
- [ ] **INFORMATIONAL — Confirm the intended station/SNCL convention.** This repository documents `P0023` as an example but contains no authoritative mapping, zero-padding rule, or legacy/released-name transition.
- [ ] **INFORMATIONAL — Obtain authoritative firmware/layout fixtures.** No tracked real MERMAID waveform or circular-buffer fixture exists.

## Executive conclusion

For the narrow documented input contract—an already-linear, headerless, little-endian signed-int32 file whose basename is the first-sample UTC timestamp—the converter preserves ordinary, representable sample arrays exactly and applies no intentional time correction.

That is not evidence that the output is faithful to a physical MERMAID circular buffer. The repository does not contain a ring-buffer layout, index, valid-count, wrap, reset, or firmware decoder. It assumes those issues have already been resolved before bytes reach this project.

The principal production risks are silent output overwrite on timestamp collisions, silent fixed-width SNCL truncation, and failure of the implicit STEIM2 encoder for otherwise valid int32 sequences.

## Evidence and verification environment

The source was inspected at the repository `main` revision during the audit. Relevant history began with commit `e77a3d1` (`Add initial raw buffer-to-mseed converter`) and shows direct headerless `<i4` pass-through from the first implementation; no circular-buffer decoder was subsequently removed.

Verification used the repository virtual environment:

```text
ObsPy 1.5.0
NumPy 2.4.6
63 passed
```

All generated inputs and miniSEED outputs were created beneath isolated `/private/tmp` directories. The repository has no tracked real waveform fixtures; all exercised waveforms were synthetic.

## Conversion pipeline

```text
filename + raw bytes
  -> parsed SegmentInfo(starttime, npts)
  -> NumPy <i4 sample array
  -> ObsPy Trace with supplied metadata
  -> ObsPy miniSEED writer
```

1. Discovery recursively examines non-hidden regular files. A file is accepted if its basename is a supported timestamp and its nonzero byte length is a multiple of four. See `discover_input_files()` in [`convert.py`](src/mermaid_buffer/convert.py#L121-L166).
2. `parse_starttime_from_filename()` accepts only `YYYY-MM-DDTHH_MM_SS` and `YYYY-MM-DDTHH_MM_SS.ffffff`, replaces underscores with colons, and constructs `UTCDateTime`. See [`convert.py`](src/mermaid_buffer/convert.py#L79-L94).
3. `read_raw_samples()` performs `np.fromfile(..., dtype=np.dtype("<i4"))`. See [`convert.py`](src/mermaid_buffer/convert.py#L97-L100).
4. `build_trace()` applies `np.asarray(samples, dtype=RAW_DTYPE)`, then assigns network, station, location, channel, starttime, sampling rate, and data quality. See [`convert.py`](src/mermaid_buffer/convert.py#L187-L210).
5. `convert_segment()` calls `trace.write(..., format="MSEED")` with no explicit encoding, byte order, or record length. See [`convert.py`](src/mermaid_buffer/convert.py#L213-L253).

### Transformations applied

| Property | Transformation | Scientific consequence |
| --- | --- | --- |
| Samples | File bytes interpreted as little-endian signed int32 | Requires input to truly be `<i4` chronological samples. |
| Sample order | None | Bytes remain in file order; no circular unwrapping occurs. |
| Sample count | Bytes / 4; zero-size files rejected | Count is exact for a valid raw file. |
| Start time | Parsed from filename, not sample content | Limited to whole microseconds in accepted filenames. |
| Sampling rate | User float, default `40.01406` | miniSEED serialization quantizes it; see below. |
| SNCL and quality | User/default metadata | Raw input has no metadata; values label every output. |
| Data encoding | ObsPy default in the tested environment: STEIM2 | Exact for representable differences, but not universally writable. |

No code performs scaling, offset removal, normalization, interpolation, gap filling, merging, sample sorting, or intentional clock correction.

## Sample-integrity audit

`RAW_DTYPE` is explicitly `np.dtype("<i4")`; this is little-endian signed int32. See [`convert.py`](src/mermaid_buffer/convert.py#L26-L27). The raw conversion path supplies this same dtype to `Trace`, so it does not implicitly pass raw samples through a floating-point representation.

For successful writes, read-back samples were native `int32` and exactly equal to the source arrays. The exercised cases included a nine-sample signed sequence, 10,000 sequential samples, a single `-2147483648` sample, and the order-sensitive sequence `[3, 4, 5, 1, 2]`.

There is no raw-input NaN representation in int32 data. A direct caller of the internal `build_trace()` helper could pass floating-point data and trigger NumPy integer coercion, but that is outside the CLI raw-file conversion path.

### STEIM2 representability failure

The default writer selected STEIM2 in the tested environment. A two-sample array `[0, 536870911]` wrote and round-tripped exactly, but `[0, 536870912]` failed with:

```text
Unable to represent difference in <= 30 bits
```

Larger ordinary signed differences also failed. The exception is raised from the writer rather than producing altered samples, but `convert_tree()` does not catch it per segment; it terminates the complete run. Because the raw contract permits all int32 values, this is a real mismatch between accepted input representation and guaranteed output representability.

## Circular-buffer ordering audit

There is no code that interprets an input as a ring. In particular, the repository has no fields or logic for buffer capacity, current write index, valid sample count before first wrap, oldest/newest index determination, wraparound reordering, reboot/reset detection, or malformed index/state metadata.

The simple synthetic sequence `[3, 4, 5, 1, 2]` remained exactly that sequence after conversion. This demonstrates direct pass-through. It does **not** validate a wrapped physical buffer: if chronology were instead `[1, 2, 3, 4, 5]`, the converter would emit the wrong order.

**Scientific interpretation:** the current contract can be valid only if an upstream export has already emitted files in chronological sample order and has assigned their start-time filenames correctly. That upstream step is not represented, documented, or testable in this repository.

## Timing audit

### Start-time semantics

Start time is obtained solely from the source filename. The parser accepts only zero or six fractional decimal digits, and uses `UTCDateTime`; it does not consult local timezone settings. See [`convert.py`](src/mermaid_buffer/convert.py#L79-L94).

No source code applies a start-time correction or drift adjustment. Tested miniSEED records had `time_correction = 0` and zero activity flags.

### End-time semantics

The implementation correctly distinguishes the two relevant formulas:

```text
last sample time             = start + (npts - 1) / fs
expected next segment start  = start + npts / fs
```

`_last_sample_time()` uses the former. See [`convert.py`](src/mermaid_buffer/convert.py#L405-L412). Transition records use the latter. See [`convert.py`](src/mermaid_buffer/convert.py#L326-L350).

Independent calculations confirmed the expected last-sample time for short round-trip records. A 10,000-sample test differed by `+2 microseconds` from the last-sample time calculated with requested `40.01406 Hz`; that difference comes from the miniSEED encoded-rate quantization, not an `npts / fs` off-by-one error.

## Sampling-rate precision analysis

The project default is `40.01406 Hz`. See [`convert.py`](src/mermaid_buffer/convert.py#L26). Git history shows it began as a fixed project rate and was later exposed as a configurable option; no firmware-specific historical rates are identified in repository materials.

With the tested ObsPy/libmseed stack, requested `40.01406` was encoded using factor/multiplier `22768 / -569` and read back as:

```text
40.01405975395431 Hz
```

This is lower by `0.000000246045694 Hz` (about `6.149 ppb`). Approximate elapsed-time discrepancy for a consumer that follows the encoded rate:

| Elapsed duration | Difference |
| --- | ---: |
| 1 day | 0.531 ms |
| 30 days | 15.94 ms |
| 365.25 days | 194.05 ms |

The transition log uses the requested float rate, while miniSEED readers use the encoded factor/multiplier rate. Thus they use distinct rate models for long individual segments.

## MiniSEED metadata audit

For a valid default invocation, generated headers correctly reported:

```text
Network   MH
Station   P0023
Location  20
Channel   BDH
Quality   R
```

The tested outputs used STEIM2, big-endian data, and 4096-byte records. A multi-record waveform was reconstructed by ObsPy to the full trace sample count; the `npts` in an individual record is necessarily its record-local count, not the total trace count.

Channel and data-quality validation exists. See [`seed_codes.py`](src/mermaid_buffer/seed_codes.py#L66-L96). Network, station, and location receive no equivalent validation before being assigned to the trace. See [`convert.py`](src/mermaid_buffer/convert.py#L202-L209).

Observed serialization behavior:

| Requested CLI value | Header value after read-back | Filename component |
| --- | --- | --- |
| station `P00234` | `P0023` | `P00234` |
| network `ABC` | `AB` | `ABC` |
| location `123` | `12` | `123` |

This silently creates a false correspondence between filename identity and header identity, which is consequential for DMC and catalog workflows.

## One-input / one-output contract

The documentation promises one output per accepted input. The implementation creates a flat filename from SNCL plus the input **basename** only. See [`convert.py`](src/mermaid_buffer/convert.py#L169-L184).

Consequently, distinct files such as:

```text
a/2018-01-01T00_00_00  -> [1, 2, 3]
b/2018-01-01T00_00_00  -> [9, 8, 7]
```

both map to:

```text
MH.P0023.20.BDH.2018-01-01T00_00_00.mseed
```

The audited run reported two output-path entries, both naming that same path, but left one file containing `[9, 8, 7]`. This is silent waveform loss.

Reruns deliberately overwrite same-name expected outputs and transition/skipped logs, while leaving unrelated stale output files. That behavior is documented and covered by a test, but the distinct-input collision is not.

## Malformed and partial input audit

### Explicitly handled

- Empty raw files are skipped.
- Byte lengths not divisible by four are skipped.
- Unsupported or malformed timestamp filenames are skipped.
- Dot files are skipped and hidden directories are pruned.
- Nonpositive, NaN, and infinite sampling frequencies are rejected.
- Invalid channel code/band combinations and quality indicators are rejected.

### Not verifiable under the current raw contract

- Corrupted but four-byte-aligned payloads;
- wrong endian payloads;
- arbitrary unexpected firmware/header layout;
- circular-buffer state/index inconsistencies;
- declared-vs-actual count inconsistencies (there is no declared count);
- unknown station identity; and
- malformed network/station/location field widths.

Every four-byte-aligned payload is a syntactically valid sequence of int32 values. Without a header, checksum, expected size, or external provenance, the converter cannot distinguish corruption from genuine waveform samples.

The count-before-read check detects a size change during conversion only when the count changes. An in-place replacement with the same byte length would not be detected.

## Round-trip verification results

Temporary round-trip conversion and ObsPy read-back established:

| Case | Samples equal | npts | Timing result |
| --- | --- | --- | --- |
| Signed nine-sample sequence | Yes | Exact | Independent end matched at displayed precision. |
| 10,000-sample sequence | Yes | Exact | +2 us versus requested-rate independent end. |
| One-sample `int32` minimum | Yes | 1 | Start equals end exactly. |
| `[3, 4, 5, 1, 2]` | Yes | 5 | Order was unchanged. |
| Adjacent difference `2^29 - 1` | Yes | 2 | Wrote successfully. |
| Adjacent difference `2^29` | No output | N/A | STEIM2 writer error. |

These tests establish successful pass-through fidelity for representable synthetic data only. They cannot validate actual MERMAID buffer extraction.

## Determinism

Two independent conversions of identical valid input bytes and metadata produced byte-identical miniSEED files in the tested environment. No current timestamp is inserted by the conversion code.

This is not a durable cross-version guarantee because writer choices are implicit: the project does not specify encoding, byte order, or record length. ObsPy/libmseed version changes could change byte serialization while retaining scientific equivalence. JSONL transition and skipped-file logs include source paths and therefore differ when input roots differ.

## Cross-repository temporal-contract observations

The related project present in the workspace is `mermaid-timelines`. It does not consume this repository's miniSEED outputs directly; it consumes normalized record JSONL.

Its DET/REQ interval implementation uses the same conceptual final-sample formula, `(sample_count - 1) / sampling_rate`, but does so with `Decimal(str(sampling_rate))` and microsecond rounding. See [`detreq.py`](/Users/jdsimon/programs/mermaid-timelines/src/mermaid_timelines/detreq.py#L163-L168).

The formula agrees with `mermaid-buffer`; precision policy does not:

- timeline: decimal requested rate, microsecond-rounded end time;
- transition log: floating requested rate;
- miniSEED: encoded factor/multiplier rate.

No code in either repository establishes that these rate representations are intentionally interchangeable for long waveform records.

## Existing test coverage and gaps

The current tests cover timestamp parsing, little-endian input reading, ordinary metadata, selected validation, skipped-file logging, transition classification, custom sampling frequency, and expected-output rewrites.

They do not detect:

- output filename collision between distinct source paths;
- silent network/station/location header truncation;
- STEIM2 representability failure;
- broad raw-to-miniSEED exact sample equality;
- independent final-sample time verification;
- encoded sampling-rate error and accumulated timing consequences;
- circular-buffer ordering;
- firmware layout corruption; or
- byte-level determinism under a pinned writer stack.

## Recommended regression and property tests

1. Place two distinct raw files with identical timestamp basenames beneath different subdirectories; require rejection or another explicit, non-lossy collision policy.
2. Parameterize network/station/location boundary lengths and assert that filename and header identities cannot diverge.
3. Exercise adjacent changes of `2^29 - 1`, `2^29`, and representative large signed jumps; define required behavior for full-domain int32 input.
4. Add raw fixtures whose expected array, npts, start time, SNCL, and independently computed final-sample time are checked after read-back.
5. Assert and document the accepted miniSEED encoded-rate approximation, or define a representation that meets the required timing tolerance.
6. Add authoritative firmware-layout fixtures for empty, partial, full, wrapped, reset, and malformed circular buffers if this project is intended to process literal rings.
7. Property-test that every successful raw conversion preserves sample values and order exactly.
8. Test deterministic byte output with a pinned ObsPy/libmseed environment, separately from scientific-equivalence testing.

## Recommended next actions

1. Obtain authoritative raw waveform fixtures and firmware/export documentation before describing this tool as a validated circular-buffer reconstruction path.
2. Decide and implement a collision-safe one-input/one-output rule before batch production use.
3. Define validated SNCL conventions, including field widths and station-name normalization/legacy policy.
4. Define an explicit miniSEED serialization policy that supports the full intended int32 domain, then test it end to end.
5. Decide whether the `40.01406 Hz` miniSEED approximation is scientifically acceptable for the longest expected segment, and document the accepted timing tolerance.
