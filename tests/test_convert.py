from pathlib import Path

import numpy as np
from obspy import UTCDateTime, read

from buffmaid.convert import (
    SAMPLING_RATE_HZ,
    SegmentInfo,
    build_trace,
    make_output_path,
    parse_starttime_from_filename,
    read_raw_samples,
    transition_record,
)


def test_parse_starttime_with_fractional_seconds():
    starttime = parse_starttime_from_filename("2018-12-06T03_06_14.450000")

    assert starttime == UTCDateTime(2018, 12, 6, 3, 6, 14, 450000)


def test_parse_starttime_without_fractional_seconds():
    starttime = parse_starttime_from_filename("2018-11-03T10_53_50")

    assert starttime == UTCDateTime(2018, 11, 3, 10, 53, 50)


def test_output_filename_generation(tmp_path):
    outpath = make_output_path(
        input_path=Path("2018-12-06T03_06_14.450000"),
        output_root=tmp_path,
        station="P0023",
    )

    assert outpath == tmp_path / "MH.P0023.10.BHZ.2018-12-06T03_06_14.450000.mseed"


def test_reading_little_endian_int32_binary_data(tmp_path):
    raw_path = tmp_path / "2018-11-03T10_53_50"
    expected = np.array([-7, 0, 42, 2_147_483_647], dtype="<i4")
    expected.tofile(raw_path)

    samples = read_raw_samples(raw_path)

    assert samples.dtype == np.dtype("<i4")
    np.testing.assert_array_equal(samples, expected)


def test_fixed_sampling_rate_constant():
    assert SAMPLING_RATE_HZ == 40.01406


def test_transition_classification_adjacent_gap_overlap():
    start = UTCDateTime(2018, 12, 6, 3, 6, 14, 450000)
    previous = _segment("previous", start, 10)
    expected_next = start + 10 / SAMPLING_RATE_HZ

    adjacent = transition_record(previous, _segment("adjacent", expected_next, 5))
    gap = transition_record(previous, _segment("gap", expected_next + 1 / SAMPLING_RATE_HZ, 5))
    overlap = transition_record(previous, _segment("overlap", expected_next - 1 / SAMPLING_RATE_HZ, 5))

    assert adjacent["kind"] == "adjacent"
    assert gap["kind"] == "gap"
    assert overlap["kind"] == "overlap"


def test_mseed_metadata_includes_dataquality_r(tmp_path):
    trace = build_trace(
        samples=np.array([1, 2, 3], dtype="<i4"),
        starttime=UTCDateTime(2018, 12, 6, 3, 6, 14, 450000),
        station="P0023",
    )
    outpath = tmp_path / "metadata.mseed"

    trace.write(str(outpath), format="MSEED")
    written = read(str(outpath))[0]

    assert written.stats.mseed.dataquality == "R"
    assert written.stats.network == "MH"
    assert written.stats.station == "P0023"
    assert written.stats.location == "10"
    assert written.stats.channel == "BHZ"


def _segment(name: str, starttime: UTCDateTime, npts: int) -> SegmentInfo:
    return SegmentInfo(
        path=Path(name),
        source_timestamp=name,
        starttime=starttime,
        npts=npts,
    )
