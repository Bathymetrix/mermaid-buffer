import json
from pathlib import Path

import numpy as np
import pytest
from obspy import UTCDateTime, read

from mermaid_buffer import (
    band_code,
    band_codes_for_sample_rate,
    validate_channel_code,
    validate_sampling_frequency_hz,
)
from mermaid_buffer.cli import build_parser, main
from mermaid_buffer.convert import (
    SAMPLING_RATE_HZ,
    SegmentInfo,
    build_trace,
    convert_tree,
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

    assert outpath == tmp_path / "MH.P0023.20.BHZ.2018-12-06T03_06_14.450000.mseed"


def test_reading_little_endian_int32_binary_data(tmp_path):
    raw_path = tmp_path / "2018-11-03T10_53_50"
    expected = np.array([-7, 0, 42, 2_147_483_647], dtype="<i4")
    expected.tofile(raw_path)

    samples = read_raw_samples(raw_path)

    assert samples.dtype == np.dtype("<i4")
    np.testing.assert_array_equal(samples, expected)


def test_fixed_sampling_rate_constant():
    assert SAMPLING_RATE_HZ == 40.01406


def test_sampling_frequency_validation_rejects_invalid_values():
    assert validate_sampling_frequency_hz("5.0") == 5.0

    with pytest.raises(ValueError, match="sampling_frequency_hz must be a positive finite value"):
        validate_sampling_frequency_hz(0)
    with pytest.raises(ValueError, match="sampling_frequency_hz must be a positive finite value"):
        validate_sampling_frequency_hz("nan")


def test_band_codes_for_mermaid_sampling_rate():
    assert band_codes_for_sample_rate(SAMPLING_RATE_HZ) == ("B", "S")


@pytest.mark.parametrize(
    ("sample_rate_hz", "expected_codes"),
    [
        (0.95, ("L",)),
        (1.0, ("L",)),
        (1.05, ("L",)),
        (0.095, ("V",)),
        (0.1, ("V",)),
        (0.105, ("V",)),
        (0.0095, ("U",)),
        (0.01, ("U",)),
        (0.0105, ("U",)),
    ],
)
def test_nominal_band_codes_allow_five_percent_tolerance(sample_rate_hz, expected_codes):
    assert band_codes_for_sample_rate(sample_rate_hz) == expected_codes


def test_l_band_tolerance_takes_precedence_over_m_band_range():
    assert band_codes_for_sample_rate(1.05) == ("L",)
    assert band_codes_for_sample_rate(1.051) == ("M",)


def test_band_code_uses_corner_period_when_sample_rate_is_ambiguous():
    assert band_code(SAMPLING_RATE_HZ, corner_period_seconds=10) == "B"
    assert band_code(SAMPLING_RATE_HZ, corner_period_seconds=9.999) == "S"

    with pytest.raises(ValueError, match="corner_period_seconds is required"):
        band_code(SAMPLING_RATE_HZ)


def test_channel_code_validation_rejects_invalid_band_code():
    assert validate_channel_code("bhz", SAMPLING_RATE_HZ) == "BHZ"
    assert validate_channel_code("SHZ", SAMPLING_RATE_HZ) == "SHZ"
    assert validate_channel_code("MHZ", 5.0) == "MHZ"

    with pytest.raises(ValueError, match="40.01406 Hz allows B or S"):
        validate_channel_code("MHZ", SAMPLING_RATE_HZ)


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


def test_transition_record_uses_custom_sampling_frequency():
    start = UTCDateTime(2018, 12, 6, 3, 6, 14, 450000)
    previous = _segment("previous", start, 10)
    expected_next = start + 10 / 20.0

    record = transition_record(
        previous,
        _segment("adjacent", expected_next + 0.5 / 20.0, 5),
        sampling_frequency_hz=20.0,
    )

    assert record["kind"] == "adjacent"
    assert record["delta_samples"] == pytest.approx(0.5)


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
    assert written.stats.location == "20"
    assert written.stats.channel == "BHZ"
    assert written.stats.sampling_rate == pytest.approx(SAMPLING_RATE_HZ)


def test_build_trace_accepts_custom_sampling_frequency_and_channel():
    trace = build_trace(
        samples=np.array([1, 2, 3], dtype="<i4"),
        starttime=UTCDateTime(2018, 12, 6, 3, 6, 14, 450000),
        station="P0023",
        channel="MHZ",
        sampling_frequency_hz=5.0,
    )

    assert trace.stats.channel == "MHZ"
    assert trace.stats.sampling_rate == pytest.approx(5.0)


def test_convert_help_lists_metadata_defaults(capsys):
    parser = build_parser()

    try:
        parser.parse_args(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    help_text = capsys.readouterr().out
    assert "-i, --input-root INPUT_ROOT" in help_text
    assert "-o, --output-root OUTPUT_ROOT" in help_text
    assert "-fs, --sampling-frequency HZ" in help_text
    assert "-s, --station STATION" in help_text
    assert "-n, --network NETWORK" in help_text
    assert "-c, --channel CHANNEL" in help_text
    assert "-l, --location LOCATION" in help_text
    assert "(default: MH)" in help_text
    assert "(default: 20)" in help_text
    assert "(default: BHZ)" in help_text
    assert "(default: 40.01406)" in help_text


def test_convert_parser_accepts_short_options(tmp_path):
    parser = build_parser()

    args = parser.parse_args(
        [
            "-i",
            str(tmp_path / "in"),
            "-o",
            str(tmp_path / "out"),
            "-s",
            "P0023",
            "-n",
            "XX",
            "-c",
            "BDF",
            "-l",
            "00",
            "-fs",
            "20.0",
        ]
    )

    assert args.input_root == tmp_path / "in"
    assert args.output_root == tmp_path / "out"
    assert args.station == "P0023"
    assert args.network == "XX"
    assert args.location == "00"
    assert args.channel == "BDF"
    assert args.sampling_frequency == 20.0


def test_convert_tree_uses_custom_sampling_frequency_for_outputs(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    np.array([1, 2, 3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")
    np.array([5, 6], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50.800000")

    result = convert_tree(
        input_root=input_root,
        output_root=output_root,
        station="P0023",
        channel="MHZ",
        sampling_frequency_hz=5.0,
    )

    assert len(result.output_paths) == 2
    written = read(str(result.output_paths[0]))[0]
    assert written.stats.channel == "MHZ"
    assert written.stats.sampling_rate == pytest.approx(5.0)

    transition_record_json = json.loads(result.transition_log_path.read_text(encoding="utf-8"))
    assert transition_record_json["kind"] == "adjacent"
    assert transition_record_json["delta_samples"] == pytest.approx(0.0)


def test_convert_tree_logs_skipped_files_without_crashing(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    docs_root = input_root / "docs"
    docs_root.mkdir(parents=True)
    np.array([1, 2, 3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")
    (input_root / "2018-11-03T10_53_51").write_bytes(b"abc")
    (docs_root / "manual.pdf").write_bytes(b"%PDF-1.7\n")

    result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")

    assert len(result.output_paths) == 1
    assert len(result.skipped_files) == 2
    skipped_records = [
        json.loads(line)
        for line in result.skipped_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert {Path(record["file"]).name for record in skipped_records} == {
        "2018-11-03T10_53_51",
        "manual.pdf",
    }
    assert any(
        "Raw file size is not divisible by 4 bytes" in record["reason"]
        for record in skipped_records
    )
    assert any(
        "Filename does not contain a timestamp separator: manual.pdf" in record["reason"]
        for record in skipped_records
    )


def test_cli_accepts_custom_sampling_frequency_for_channel_validation(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()

    assert (
        main(
            [
                "-i",
                str(input_root),
                "-o",
                str(output_root),
                "-s",
                "P0023",
                "-c",
                "MHZ",
                "-fs",
                "5.0",
            ]
        )
        == 0
    )


def test_cli_prints_processed_and_skipped_counts(tmp_path, capsys):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    np.array([1, 2, 3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")
    (input_root / "manual.pdf").write_bytes(b"%PDF-1.7\n")

    assert main(["-i", str(input_root), "-o", str(output_root), "-s", "P0023"]) == 0

    stdout = capsys.readouterr().out
    assert "Processed 1 file(s); skipped 1 file(s)." in stdout
    assert "Transition log:" in stdout
    assert "Skipped log:" in stdout


def test_cli_rejects_channel_band_code_for_sampling_rate(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-i", "raw", "-o", "mseed", "-s", "P0023", "-c", "MHZ"])

    assert exc.value.code == 2
    assert "Channel code 'MHZ' has band code 'M'" in capsys.readouterr().err


def test_cli_rejects_nonpositive_sampling_frequency(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-i", "raw", "-o", "mseed", "-s", "P0023", "-fs", "0"])

    assert exc.value.code == 2
    assert "sampling_frequency_hz must be a positive finite value" in capsys.readouterr().err


def _segment(name: str, starttime: UTCDateTime, npts: int) -> SegmentInfo:
    return SegmentInfo(
        path=Path(name),
        source_timestamp=name,
        starttime=starttime,
        npts=npts,
    )
