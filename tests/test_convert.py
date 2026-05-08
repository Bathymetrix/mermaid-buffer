import json
from pathlib import Path

import numpy as np
import pytest
from obspy import UTCDateTime, read

import mermaid_buffer
from mermaid_buffer import __version__
from mermaid_buffer.cli import build_parser, main
from mermaid_buffer.convert import (
    DEFAULT_SAMPLING_FREQUENCY_HZ,
    SegmentInfo,
    build_trace,
    classify_transition,
    convert_tree,
    make_output_path,
    parse_starttime_from_filename,
    read_raw_samples,
    transition_record,
)
from mermaid_buffer.seed_codes import (
    band_code,
    band_codes_for_sample_rate,
    validate_channel_code,
    validate_data_quality_indicator,
    validate_sampling_frequency_hz,
)


def test_package_root_exposes_deliberate_v1_public_api():
    assert set(mermaid_buffer.__all__) == {"__version__"}
    assert mermaid_buffer.__version__ == __version__
    assert not hasattr(mermaid_buffer, "band_codes_for_sample_rate")
    assert not hasattr(mermaid_buffer, "DEFAULT_SAMPLING_FREQUENCY_HZ")


def test_seed_code_helpers_are_importable_from_submodule():
    from mermaid_buffer.seed_codes import band_codes_for_sample_rate
    from mermaid_buffer.seed_codes import validate_channel_code
    from mermaid_buffer.seed_codes import validate_data_quality_indicator
    from mermaid_buffer.seed_codes import validate_sampling_frequency_hz

    assert band_codes_for_sample_rate(40.01406) == ("B", "S")
    assert validate_channel_code("bdh", 40.01406) == "BDH"
    assert validate_data_quality_indicator(" r ") == "R"
    assert validate_sampling_frequency_hz("40.01406") == pytest.approx(40.01406)


def test_parse_starttime_with_fractional_seconds():
    starttime = parse_starttime_from_filename("2018-12-06T03_06_14.450000")

    assert starttime == UTCDateTime(2018, 12, 6, 3, 6, 14, 450000)


def test_parse_starttime_without_fractional_seconds():
    starttime = parse_starttime_from_filename("2018-11-03T10_53_50")

    assert starttime == UTCDateTime(2018, 11, 3, 10, 53, 50)


@pytest.mark.parametrize(
    "filename",
    [
        "manual.pdf",
        "2018-11-03T10:53:50",
        "2018-11-03T10_53",
        "2018-11-03T10_53_50.1",
        "2018-13-03T10_53_50",
    ],
)
def test_parse_starttime_rejects_malformed_timestamp_filenames(filename):
    with pytest.raises(ValueError, match="UTC timestamp"):
        parse_starttime_from_filename(filename)


def test_output_filename_generation(tmp_path):
    outpath = make_output_path(
        input_path=Path("2018-12-06T03_06_14.450000"),
        output_root=tmp_path,
        station="P0023",
    )

    assert outpath == tmp_path / "MH.P0023.20.BDH.2018-12-06T03_06_14.450000.mseed"


def test_reading_little_endian_int32_binary_data(tmp_path):
    raw_path = tmp_path / "2018-11-03T10_53_50"
    expected = np.array([-7, 0, 42, 2_147_483_647], dtype="<i4")
    expected.tofile(raw_path)

    samples = read_raw_samples(raw_path)

    assert samples.dtype == np.dtype("<i4")
    np.testing.assert_array_equal(samples, expected)


def test_default_sampling_frequency_constant():
    assert DEFAULT_SAMPLING_FREQUENCY_HZ == 40.01406


def test_sampling_frequency_validation_rejects_invalid_values():
    assert validate_sampling_frequency_hz("5.0") == 5.0

    with pytest.raises(ValueError, match="sampling_frequency_hz must be a positive finite value"):
        validate_sampling_frequency_hz(0)
    with pytest.raises(ValueError, match="sampling_frequency_hz must be a positive finite value"):
        validate_sampling_frequency_hz("nan")


@pytest.mark.parametrize("indicator", ["D", "R", "Q", "M", "d", " r "])
def test_data_quality_validation_normalizes_valid_indicators(indicator):
    assert validate_data_quality_indicator(indicator) == indicator.strip().upper()


@pytest.mark.parametrize("indicator", ["", "X", "A", "RR"])
def test_data_quality_validation_rejects_invalid_indicators(indicator):
    with pytest.raises(ValueError, match="data_quality must be one of"):
        validate_data_quality_indicator(indicator)


def test_band_codes_for_mermaid_sampling_rate():
    assert band_codes_for_sample_rate(DEFAULT_SAMPLING_FREQUENCY_HZ) == ("B", "S")


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
    assert band_code(DEFAULT_SAMPLING_FREQUENCY_HZ, corner_period_seconds=10) == "B"
    assert band_code(DEFAULT_SAMPLING_FREQUENCY_HZ, corner_period_seconds=9.999) == "S"

    with pytest.raises(ValueError, match="corner_period_seconds is required"):
        band_code(DEFAULT_SAMPLING_FREQUENCY_HZ)


def test_channel_code_validation_rejects_invalid_band_code():
    assert validate_channel_code("BDH", DEFAULT_SAMPLING_FREQUENCY_HZ) == "BDH"
    assert validate_channel_code("bdh", DEFAULT_SAMPLING_FREQUENCY_HZ) == "BDH"
    assert validate_channel_code("SHZ", DEFAULT_SAMPLING_FREQUENCY_HZ) == "SHZ"
    assert validate_channel_code("MHZ", 5.0) == "MHZ"

    with pytest.raises(ValueError, match="40.01406 Hz allows B or S"):
        validate_channel_code("MHZ", DEFAULT_SAMPLING_FREQUENCY_HZ)


def test_transition_classification_adjacent_gap_overlap():
    start = UTCDateTime(2018, 12, 6, 3, 6, 14, 450000)
    previous = _segment("previous", start, 10)
    expected_next = start + 10 / DEFAULT_SAMPLING_FREQUENCY_HZ

    adjacent = transition_record(previous, _segment("adjacent", expected_next, 5))
    gap = transition_record(previous, _segment("gap", expected_next + 1 / DEFAULT_SAMPLING_FREQUENCY_HZ, 5))
    overlap = transition_record(previous, _segment("overlap", expected_next - 1 / DEFAULT_SAMPLING_FREQUENCY_HZ, 5))

    assert adjacent["kind"] == "adjacent"
    assert gap["kind"] == "gap"
    assert overlap["kind"] == "overlap"


def test_transition_classification_tolerance_edges():
    tolerance = 0.5 / DEFAULT_SAMPLING_FREQUENCY_HZ

    assert classify_transition(0.0) == "adjacent"
    assert classify_transition(tolerance) == "adjacent"
    assert classify_transition(-tolerance) == "adjacent"
    assert classify_transition(tolerance * 0.999999) == "adjacent"
    assert classify_transition(-tolerance * 0.999999) == "adjacent"
    assert classify_transition(tolerance * 1.000001) == "gap"
    assert classify_transition(-tolerance * 1.000001) == "overlap"
    assert classify_transition(1.0) == "gap"
    assert classify_transition(-1.0) == "overlap"


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
    assert written.stats.channel == "BDH"
    assert written.stats.sampling_rate == pytest.approx(DEFAULT_SAMPLING_FREQUENCY_HZ)


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


def test_build_trace_accepts_custom_data_quality(tmp_path):
    trace = build_trace(
        samples=np.array([1, 2, 3], dtype="<i4"),
        starttime=UTCDateTime(2018, 12, 6, 3, 6, 14, 450000),
        station="P0023",
        data_quality="Q",
    )
    outpath = tmp_path / "metadata.mseed"

    trace.write(str(outpath), format="MSEED")
    written = read(str(outpath))[0]

    assert written.stats.mseed.dataquality == "Q"


def test_convert_help_lists_metadata_defaults(capsys):
    parser = build_parser()

    try:
        parser.parse_args(["--help"])
    except SystemExit as exc:
        assert exc.code == 0

    help_text = capsys.readouterr().out
    assert "-i, --input-root INPUT_ROOT" in help_text
    assert "--version" in help_text
    assert "-o, --output-root OUTPUT_ROOT" in help_text
    assert "-fs, --sampling-frequency HZ" in help_text
    assert "-s, --station STATION" in help_text
    assert "-n, --network NETWORK" in help_text
    assert "-c, --channel CHANNEL" in help_text
    assert "-l, --location LOCATION" in help_text
    assert "--data_quality INDICATOR" in help_text
    assert "(default: MH)" in help_text
    assert "(default: 20)" in help_text
    assert "(default: BDH)" in help_text
    assert "(default: 40.01406)" in help_text
    assert "(default: R)" in help_text


def test_cli_version_reports_package_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert f"buffer2mseed {__version__}" in capsys.readouterr().out


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
            "--data_quality",
            "Q",
        ]
    )

    assert args.input_root == tmp_path / "in"
    assert args.output_root == tmp_path / "out"
    assert args.station == "P0023"
    assert args.network == "XX"
    assert args.location == "00"
    assert args.channel == "BDF"
    assert args.sampling_frequency == 20.0
    assert args.data_quality == "Q"


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


def test_convert_tree_uses_custom_data_quality_for_outputs(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    np.array([1, 2, 3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")

    result = convert_tree(
        input_root=input_root,
        output_root=output_root,
        station="P0023",
        data_quality="Q",
    )

    written = read(str(result.output_paths[0]))[0]
    assert written.stats.mseed.dataquality == "Q"


def test_convert_tree_accepts_timestamp_filenames_with_and_without_fractional_seconds(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    np.array([1, 2], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")
    np.array([3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_51.250000")

    result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")

    assert [path.name for path in result.output_paths] == [
        "MH.P0023.20.BDH.2018-11-03T10_53_50.mseed",
        "MH.P0023.20.BDH.2018-11-03T10_53_51.250000.mseed",
    ]


def test_convert_tree_skips_and_logs_invalid_raw_byte_counts(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    invalid_files = {
        "2018-11-03T10_53_50": b"",
        "2018-11-03T10_53_51": b"a",
        "2018-11-03T10_53_52": b"ab",
        "2018-11-03T10_53_53": b"abc",
        "2018-11-03T10_53_54": b"abcde",
    }
    for filename, payload in invalid_files.items():
        (input_root / filename).write_bytes(payload)

    result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")

    assert result.output_paths == []
    assert len(result.skipped_files) == len(invalid_files)
    skipped_records = [
        json.loads(line)
        for line in result.skipped_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert {Path(record["file"]).name for record in skipped_records} == set(invalid_files)
    assert any("Raw file is empty" in record["reason"] for record in skipped_records)
    assert sum(
        "Raw file size is not divisible by 4 bytes" in record["reason"]
        for record in skipped_records
    ) == 4


def test_convert_tree_skips_and_logs_malformed_timestamp_filenames(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    for filename in [
        "manual.pdf",
        "2018-11-03T10:53:50",
        "2018-11-03T10_53_50.1",
    ]:
        np.array([1, 2], dtype="<i4").tofile(input_root / filename)

    result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")

    assert result.output_paths == []
    skipped_records = [
        json.loads(line)
        for line in result.skipped_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert {Path(record["file"]).name for record in skipped_records} == {
        "manual.pdf",
        "2018-11-03T10:53:50",
        "2018-11-03T10_53_50.1",
    }
    assert all("supported UTC timestamp" in record["reason"] for record in skipped_records)


def test_convert_tree_logs_skipped_files_without_crashing(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    docs_root = input_root / "docs"
    docs_root.mkdir(parents=True)
    np.array([1, 2, 3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")
    (input_root / "2018-11-03T10_53_51").write_bytes(b"abc")
    (input_root / ".DS_Store").write_bytes(b"metadata")
    (docs_root / "manual.pdf").write_bytes(b"%PDF-1.7\n")

    result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")

    assert len(result.output_paths) == 1
    assert len(result.skipped_files) == 3
    skipped_records = [
        json.loads(line)
        for line in result.skipped_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert {Path(record["file"]).name for record in skipped_records} == {
        "2018-11-03T10_53_51",
        ".DS_Store",
        "manual.pdf",
    }
    assert any(
        "Raw file size is not divisible by 4 bytes" in record["reason"]
        for record in skipped_records
    )
    assert any(
        "Filename is not a supported UTC timestamp" in record["reason"]
        for record in skipped_records
    )
    assert any(
        Path(record["file"]).name == ".DS_Store" and record["reason"] == "Dot file is skipped"
        for record in skipped_records
    )


def test_convert_tree_prunes_hidden_directories(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    hidden_root = input_root / ".hidden"
    hidden_root.mkdir(parents=True)
    np.array([1, 2], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")
    np.array([3, 4], dtype="<i4").tofile(hidden_root / "2018-11-03T10_53_51")

    result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")

    assert len(result.output_paths) == 1
    assert result.output_paths[0].name == "MH.P0023.20.BDH.2018-11-03T10_53_50.mseed"
    skipped_records = [
        json.loads(line)
        for line in result.skipped_log_path.read_text(encoding="utf-8").splitlines()
    ]
    assert skipped_records == [
        {
            "file": str(hidden_root),
            "reason": "Hidden directory is skipped",
        }
    ]


def test_convert_tree_rewrites_expected_outputs_and_leaves_extra_files(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    output_root.mkdir()
    raw_path = input_root / "2018-11-03T10_53_50"
    extra_output = output_root / "stale-output.mseed"
    extra_output.write_text("stale", encoding="utf-8")
    np.array([1, 2, 3, 4], dtype="<i4").tofile(raw_path)

    first_result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")
    first_output = first_result.output_paths[0]
    np.testing.assert_array_equal(read(str(first_output))[0].data, np.array([1, 2, 3, 4]))
    first_result.transition_log_path.write_text("stale transition\n", encoding="utf-8")
    first_result.skipped_log_path.write_text("stale skipped\n", encoding="utf-8")

    np.array([9, 8], dtype="<i4").tofile(raw_path)
    second_result = convert_tree(input_root=input_root, output_root=output_root, station="P0023")

    assert second_result.output_paths == [first_output]
    np.testing.assert_array_equal(read(str(first_output))[0].data, np.array([9, 8]))
    assert second_result.transition_log_path.read_text(encoding="utf-8") == ""
    assert second_result.skipped_log_path.read_text(encoding="utf-8") == ""
    assert extra_output.read_text(encoding="utf-8") == "stale"


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


def test_cli_accepts_custom_data_quality(tmp_path):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    np.array([1, 2, 3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")

    assert (
        main(
            [
                "-i",
                str(input_root),
                "-o",
                str(output_root),
                "-s",
                "P0023",
                "--data_quality",
                "q",
            ]
        )
        == 0
    )

    written = read(str(next(output_root.glob("*.mseed"))))[0]
    assert written.stats.mseed.dataquality == "Q"


def test_cli_prints_processed_and_skipped_counts(tmp_path, capsys):
    input_root = tmp_path / "raw"
    output_root = tmp_path / "mseed"
    input_root.mkdir()
    np.array([1, 2, 3, 4], dtype="<i4").tofile(input_root / "2018-11-03T10_53_50")
    np.array([5, 6], dtype="<i4").tofile(input_root / "2018-11-03T10_53_51")
    (input_root / "manual.pdf").write_bytes(b"%PDF-1.7\n")

    assert main(["-i", str(input_root), "-o", str(output_root), "-s", "P0023"]) == 0

    stdout = capsys.readouterr().out
    assert (
        "[1/2] 2018-11-03T10_53_50 -> MH.P0023.20.BDH.2018-11-03T10_53_50.mseed"
        in stdout
    )
    assert (
        "[2/2] 2018-11-03T10_53_51 -> MH.P0023.20.BDH.2018-11-03T10_53_51.mseed"
        in stdout
    )
    assert "Processed 2 file(s); skipped 1 file(s)." in stdout
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


def test_cli_rejects_invalid_data_quality(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["-i", "raw", "-o", "mseed", "-s", "P0023", "--data_quality", "X"])

    assert exc.value.code == 2
    assert "data_quality must be one of" in capsys.readouterr().err


def _segment(name: str, starttime: UTCDateTime, npts: int) -> SegmentInfo:
    return SegmentInfo(
        path=Path(name),
        source_timestamp=name,
        starttime=starttime,
        npts=npts,
    )
