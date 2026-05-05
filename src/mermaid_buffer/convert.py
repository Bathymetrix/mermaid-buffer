"""Raw MERMAID circular-buffer waveform conversion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import numpy as np
from obspy import Trace, UTCDateTime

SAMPLING_RATE_HZ = 40.01406
RAW_DTYPE = np.dtype("<i4")
ADJACENCY_TOLERANCE_SECONDS = 0.5 / SAMPLING_RATE_HZ

DEFAULT_NETWORK = "MH"
DEFAULT_LOCATION = "10"
DEFAULT_CHANNEL = "BHZ"
DEFAULT_TRANSITION_LOG_NAME = "buffer2mseed_transition_records.jsonl"


@dataclass(frozen=True)
class SegmentInfo:
    """Parsed metadata for one raw waveform segment."""

    path: Path
    source_timestamp: str
    starttime: UTCDateTime
    npts: int


@dataclass(frozen=True)
class ConversionResult:
    """Summary of a conversion run."""

    input_root: Path
    output_root: Path
    output_paths: list[Path]
    transition_log_path: Path


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


def discover_segments(input_root: str | Path) -> list[SegmentInfo]:
    """Recursively discover input files and sort them by parsed UTC start time."""

    root = Path(input_root)
    segments = [
        SegmentInfo(
            path=path,
            source_timestamp=path.name,
            starttime=parse_starttime_from_filename(path),
            npts=count_raw_samples(path),
        )
        for path in root.rglob("*")
        if path.is_file()
    ]
    return sorted(segments, key=lambda segment: (segment.starttime.timestamp, str(segment.path)))


def make_output_path(
    input_path: str | Path,
    output_root: str | Path,
    station: str,
    network: str = DEFAULT_NETWORK,
    location: str = DEFAULT_LOCATION,
    channel: str = DEFAULT_CHANNEL,
) -> Path:
    """Build the flat miniSEED output path for one source file."""

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
) -> Trace:
    """Create an ObsPy Trace with miniSEED metadata."""

    trace = Trace(data=np.asarray(samples, dtype=RAW_DTYPE))
    trace.stats.network = network
    trace.stats.station = station
    trace.stats.location = location
    trace.stats.channel = channel
    trace.stats.starttime = starttime
    trace.stats.sampling_rate = SAMPLING_RATE_HZ
    trace.stats.mseed = {"dataquality": "R"}
    return trace


def convert_segment(
    segment: SegmentInfo,
    output_root: str | Path,
    station: str,
    network: str = DEFAULT_NETWORK,
    location: str = DEFAULT_LOCATION,
    channel: str = DEFAULT_CHANNEL,
) -> Path:
    """Convert one raw waveform segment to one miniSEED file."""

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
    )
    outpath = make_output_path(
        input_path=segment.path,
        output_root=output_root,
        station=station,
        network=network,
        location=location,
        channel=channel,
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
) -> ConversionResult:
    """Convert every discovered raw waveform file under an input root."""

    input_root = Path(input_root)
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    segments = discover_segments(input_root)
    transition_log_path = write_transition_log(segments, output_root)
    output_paths = [
        convert_segment(
            segment=segment,
            output_root=output_root,
            station=station,
            network=network,
            location=location,
            channel=channel,
        )
        for segment in segments
    ]

    return ConversionResult(
        input_root=input_root,
        output_root=output_root,
        output_paths=output_paths,
        transition_log_path=transition_log_path,
    )


def classify_transition(delta_seconds: float) -> str:
    """Classify a transition delta as adjacent, gap, or overlap."""

    if abs(delta_seconds) <= ADJACENCY_TOLERANCE_SECONDS:
        return "adjacent"
    if delta_seconds > 0:
        return "gap"
    return "overlap"


def transition_record(previous: SegmentInfo, next_segment: SegmentInfo) -> dict[str, object]:
    """Build one JSON-serializable transition record."""

    expected_next_starttime = previous.starttime + previous.npts / SAMPLING_RATE_HZ
    delta_seconds = float(next_segment.starttime - expected_next_starttime)
    previous_endtime = _last_sample_time(previous)

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
        "delta_samples": delta_seconds * SAMPLING_RATE_HZ,
        "kind": classify_transition(delta_seconds),
    }


def transition_records(segments: Iterable[SegmentInfo]) -> list[dict[str, object]]:
    """Build transition records for consecutive sorted segments."""

    ordered = list(segments)
    return [
        transition_record(previous, next_segment)
        for previous, next_segment in zip(ordered, ordered[1:])
    ]


def write_transition_log(
    segments: Iterable[SegmentInfo],
    output_root: str | Path,
    filename: str = DEFAULT_TRANSITION_LOG_NAME,
) -> Path:
    """Write canonical JSONL transition records to the output root."""

    outpath = Path(output_root) / filename
    outpath.parent.mkdir(parents=True, exist_ok=True)
    with outpath.open("w", encoding="utf-8") as handle:
        for record in transition_records(segments):
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")
    return outpath


def _last_sample_time(segment: SegmentInfo) -> UTCDateTime:
    if segment.npts <= 0:
        return segment.starttime
    return segment.starttime + (segment.npts - 1) / SAMPLING_RATE_HZ


def _format_utc(value: UTCDateTime) -> str:
    return value.datetime.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
