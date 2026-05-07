"""Raw MERMAID circular-buffer waveform conversion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import isfinite
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from obspy import Trace, UTCDateTime

from mermaid_buffer.seed_codes import validate_channel_code

SAMPLING_RATE_HZ = 40.01406
RAW_DTYPE = np.dtype("<i4")

DEFAULT_NETWORK = "MH"
DEFAULT_LOCATION = "20"
DEFAULT_CHANNEL = "BHZ"
DEFAULT_DATA_QUALITY = "R"
DEFAULT_TRANSITION_LOG_NAME = "buffer2mseed_transition_records.jsonl"
DEFAULT_SKIPPED_LOG_NAME = "buffer2mseed_skipped_files.jsonl"
MINISEED_DATA_QUALITY_INDICATORS = ("D", "R", "Q", "M")


@dataclass(frozen=True)
class SegmentInfo:
    """Parsed metadata for one raw waveform segment."""

    path: Path
    source_timestamp: str
    starttime: UTCDateTime
    npts: int


@dataclass(frozen=True)
class SkippedFile:
    """A discovered file that was not accepted as a raw waveform segment."""

    path: Path
    reason: str


@dataclass(frozen=True)
class DiscoveryResult:
    """Accepted and skipped files from recursive input discovery."""

    segments: list[SegmentInfo]
    skipped_files: list[SkippedFile]


@dataclass(frozen=True)
class ConversionResult:
    """Summary of a conversion run."""

    input_root: Path
    output_root: Path
    output_paths: list[Path]
    transition_log_path: Path
    skipped_log_path: Path
    skipped_files: list[SkippedFile]


def parse_starttime_from_filename(path: str | Path) -> UTCDateTime:
    """Parse a UTC start time from a raw MERMAID filename."""

    source_timestamp = Path(path).name
    if "T" not in source_timestamp:
        raise ValueError(f"Filename does not contain a timestamp separator: {source_timestamp}")

    date_part, time_part = source_timestamp.split("T", maxsplit=1)
    normalized = f"{date_part}T{time_part.replace('_', ':')}"
    try:
        return UTCDateTime(normalized)
    except Exception as exc:
        raise ValueError(f"Could not parse UTC timestamp from filename: {source_timestamp}") from exc


def read_raw_samples(path: str | Path) -> np.ndarray:
    """Read one raw waveform file as little-endian signed int32 samples."""

    return np.fromfile(path, dtype=RAW_DTYPE)


def count_raw_samples(path: str | Path) -> int:
    """Count int32 samples in a raw waveform file without loading it."""

    file_size = Path(path).stat().st_size
    item_size = RAW_DTYPE.itemsize
    if file_size % item_size:
        raise ValueError(f"Raw file size is not divisible by {item_size} bytes: {path}")
    return file_size // item_size


def validate_sampling_frequency_hz(sampling_frequency_hz: float) -> float:
    """Return a positive sampling frequency in Hz or raise ValueError."""

    try:
        frequency = float(sampling_frequency_hz)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"sampling_frequency_hz must be a positive finite value; got {sampling_frequency_hz!r}"
        ) from exc
    if not isfinite(frequency) or frequency <= 0:
        raise ValueError(
            f"sampling_frequency_hz must be a positive finite value; got {sampling_frequency_hz!r}"
        )
    return frequency


def validate_data_quality_indicator(data_quality: str) -> str:
    """Return a normalized miniSEED data quality indicator or raise ValueError."""

    normalized = data_quality.strip().upper()
    if normalized not in MINISEED_DATA_QUALITY_INDICATORS:
        allowed = ", ".join(MINISEED_DATA_QUALITY_INDICATORS)
        raise ValueError(
            "data_quality must be one of the miniSEED data quality indicators "
            f"{allowed}; got {data_quality!r}"
        )
    return normalized


def discover_segments(input_root: str | Path) -> list[SegmentInfo]:
    """Recursively discover input files and sort them by parsed UTC start time."""

    return discover_input_files(input_root).segments


def discover_input_files(input_root: str | Path) -> DiscoveryResult:
    """Recursively discover raw segments and collect skipped-file reasons."""

    root = Path(input_root)
    segments: list[SegmentInfo] = []
    skipped_files: list[SkippedFile] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            skipped_files.append(SkippedFile(path=path, reason="Dot file is skipped"))
            continue
        try:
            starttime = parse_starttime_from_filename(path)
            npts = count_raw_samples(path)
        except (OSError, ValueError) as exc:
            skipped_files.append(SkippedFile(path=path, reason=str(exc)))
            continue
        segments.append(
            SegmentInfo(
                path=path,
                source_timestamp=path.name,
                starttime=starttime,
                npts=npts,
            )
        )

    return DiscoveryResult(
        segments=sorted(
            segments,
            key=lambda segment: (segment.starttime.timestamp, str(segment.path)),
        ),
        skipped_files=sorted(skipped_files, key=lambda skipped: str(skipped.path)),
    )


def make_output_path(
    input_path: str | Path,
    output_root: str | Path,
    station: str,
    network: str = DEFAULT_NETWORK,
    location: str = DEFAULT_LOCATION,
    channel: str = DEFAULT_CHANNEL,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
) -> Path:
    """Build the flat miniSEED output path for one source file."""

    frequency = validate_sampling_frequency_hz(sampling_frequency_hz)
    channel = validate_channel_code(channel, frequency)
    source_timestamp = Path(input_path).name
    filename = f"{network}.{station}.{location}.{channel}.{source_timestamp}.mseed"
    return Path(output_root) / filename


def build_trace(
    samples: np.ndarray,
    starttime: UTCDateTime,
    station: str,
    network: str = DEFAULT_NETWORK,
    location: str = DEFAULT_LOCATION,
    channel: str = DEFAULT_CHANNEL,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
    data_quality: str = DEFAULT_DATA_QUALITY,
) -> Trace:
    """Create an ObsPy Trace with miniSEED metadata."""

    frequency = validate_sampling_frequency_hz(sampling_frequency_hz)
    channel = validate_channel_code(channel, frequency)
    data_quality = validate_data_quality_indicator(data_quality)
    trace = Trace(data=np.asarray(samples, dtype=RAW_DTYPE))
    trace.stats.network = network
    trace.stats.station = station
    trace.stats.location = location
    trace.stats.channel = channel
    trace.stats.starttime = starttime
    trace.stats.sampling_rate = frequency
    trace.stats.mseed = {"dataquality": data_quality}
    return trace


def convert_segment(
    segment: SegmentInfo,
    output_root: str | Path,
    station: str,
    network: str = DEFAULT_NETWORK,
    location: str = DEFAULT_LOCATION,
    channel: str = DEFAULT_CHANNEL,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
    data_quality: str = DEFAULT_DATA_QUALITY,
) -> Path:
    """Convert one raw waveform segment to one miniSEED file."""

    frequency = validate_sampling_frequency_hz(sampling_frequency_hz)
    channel = validate_channel_code(channel, frequency)
    data_quality = validate_data_quality_indicator(data_quality)
    samples = read_raw_samples(segment.path)
    if len(samples) != segment.npts:
        raise ValueError(f"Sample count changed while converting: {segment.path}")

    trace = build_trace(
        samples=samples,
        starttime=segment.starttime,
        station=station,
        network=network,
        location=location,
        channel=channel,
        sampling_frequency_hz=frequency,
        data_quality=data_quality,
    )
    outpath = make_output_path(
        input_path=segment.path,
        output_root=output_root,
        station=station,
        network=network,
        location=location,
        channel=channel,
        sampling_frequency_hz=frequency,
    )
    outpath.parent.mkdir(parents=True, exist_ok=True)
    trace.write(str(outpath), format="MSEED")
    return outpath


def convert_tree(
    input_root: str | Path,
    output_root: str | Path,
    station: str,
    network: str = DEFAULT_NETWORK,
    location: str = DEFAULT_LOCATION,
    channel: str = DEFAULT_CHANNEL,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
    data_quality: str = DEFAULT_DATA_QUALITY,
    *,
    progress_callback: Callable[[int, int, SegmentInfo, Path], None] | None = None,
) -> ConversionResult:
    """Convert every discovered raw waveform file under an input root."""

    input_root = Path(input_root)
    output_root = Path(output_root)
    frequency = validate_sampling_frequency_hz(sampling_frequency_hz)
    channel = validate_channel_code(channel, frequency)
    data_quality = validate_data_quality_indicator(data_quality)
    output_root.mkdir(parents=True, exist_ok=True)

    discovery = discover_input_files(input_root)
    segments = discovery.segments
    transition_log_path = write_transition_log(
        segments,
        output_root,
        sampling_frequency_hz=frequency,
    )
    skipped_log_path = write_skipped_log(discovery.skipped_files, output_root)
    output_paths: list[Path] = []
    total_segments = len(segments)
    for segment_number, segment in enumerate(segments, start=1):
        output_path = convert_segment(
            segment=segment,
            output_root=output_root,
            station=station,
            network=network,
            location=location,
            channel=channel,
            sampling_frequency_hz=frequency,
            data_quality=data_quality,
        )
        output_paths.append(output_path)
        if progress_callback is not None:
            progress_callback(segment_number, total_segments, segment, output_path)

    return ConversionResult(
        input_root=input_root,
        output_root=output_root,
        output_paths=output_paths,
        transition_log_path=transition_log_path,
        skipped_log_path=skipped_log_path,
        skipped_files=discovery.skipped_files,
    )


def classify_transition(
    delta_seconds: float,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
) -> str:
    """Classify a transition delta as adjacent, gap, or overlap."""

    tolerance_seconds = 0.5 / validate_sampling_frequency_hz(sampling_frequency_hz)
    if abs(delta_seconds) <= tolerance_seconds:
        return "adjacent"
    if delta_seconds > 0:
        return "gap"
    return "overlap"


def transition_record(
    previous: SegmentInfo,
    next_segment: SegmentInfo,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
) -> dict[str, object]:
    """Build one JSON-serializable transition record."""

    frequency = validate_sampling_frequency_hz(sampling_frequency_hz)
    expected_next_starttime = previous.starttime + previous.npts / frequency
    delta_seconds = float(next_segment.starttime - expected_next_starttime)
    previous_endtime = _last_sample_time(previous, frequency)

    return {
        "previous_file": str(previous.path),
        "next_file": str(next_segment.path),
        "previous_starttime": _format_utc(previous.starttime),
        "previous_endtime": _format_utc(previous_endtime),
        "previous_npts": previous.npts,
        "next_starttime": _format_utc(next_segment.starttime),
        "next_npts": next_segment.npts,
        "expected_next_starttime": _format_utc(expected_next_starttime),
        "delta_seconds": delta_seconds,
        "delta_samples": delta_seconds * frequency,
        "kind": classify_transition(delta_seconds, frequency),
    }


def transition_records(
    segments: Iterable[SegmentInfo],
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
) -> list[dict[str, object]]:
    """Build transition records for consecutive sorted segments."""

    frequency = validate_sampling_frequency_hz(sampling_frequency_hz)
    ordered = list(segments)
    return [
        transition_record(previous, next_segment, frequency)
        for previous, next_segment in zip(ordered, ordered[1:])
    ]


def write_transition_log(
    segments: Iterable[SegmentInfo],
    output_root: str | Path,
    filename: str = DEFAULT_TRANSITION_LOG_NAME,
    *,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
) -> Path:
    """Write canonical JSONL transition records to the output root."""

    outpath = Path(output_root) / filename
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open("w", encoding="utf-8") as handle:
        for record in transition_records(segments, sampling_frequency_hz):
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    return outpath


def write_skipped_log(
    skipped_files: Iterable[SkippedFile],
    output_root: str | Path,
    filename: str = DEFAULT_SKIPPED_LOG_NAME,
) -> Path:
    """Write JSONL records for files skipped during discovery."""

    outpath = Path(output_root) / filename
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open("w", encoding="utf-8") as handle:
        for skipped_file in skipped_files:
            record = {
                "file": str(skipped_file.path),
                "reason": skipped_file.reason,
            }
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    return outpath


def _last_sample_time(
    segment: SegmentInfo,
    sampling_frequency_hz: float = SAMPLING_RATE_HZ,
) -> UTCDateTime:
    if segment.npts <= 0:
        return segment.starttime
    frequency = validate_sampling_frequency_hz(sampling_frequency_hz)
    return segment.starttime + (segment.npts - 1) / frequency


def _format_utc(value: UTCDateTime) -> str:
    return value.datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
