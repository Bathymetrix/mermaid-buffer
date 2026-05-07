# Bathymetrix™
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

"""Command-line interface for raw MERMAID buffer conversion."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from mermaid_buffer.convert import (
    DEFAULT_CHANNEL,
    DEFAULT_LOCATION,
    DEFAULT_NETWORK,
    SAMPLING_RATE_HZ,
    convert_tree,
    validate_sampling_frequency_hz,
)
from mermaid_buffer.seed_codes import validate_channel_code


class _DefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _get_help_string(self, action: argparse.Action) -> str:
        if action.default is None:
            return action.help or ""
        return super()._get_help_string(action)

    def _format_action_invocation(self, action: argparse.Action) -> str:
        if not action.option_strings:
            return super()._format_action_invocation(action)

        option_strings = ", ".join(action.option_strings)
        if action.nargs == 0:
            return option_strings

        default_metavar = self._get_default_metavar_for_optional(action)
        args_string = self._format_args(action, default_metavar)
        return f"{option_strings} {args_string}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="buffer2mseed",
        description="Convert raw MERMAID circular-buffer int32 waveform files to miniSEED.",
        formatter_class=_DefaultsHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input-root",
        required=True,
        type=Path,
        help="root directory to recursively search for raw binary input files",
    )
    parser.add_argument(
        "-o",
        "--output-root",
        required=True,
        type=Path,
        help="directory for flat output .mseed files and the transition JSONL log",
    )
    parser.add_argument(
        "-S",
        "--station",
        required=True,
        help="station code to write into every output trace and filename",
    )
    parser.add_argument(
        "-fs",
        "--sampling-frequency",
        type=float,
        default=SAMPLING_RATE_HZ,
        metavar="HZ",
        help="sampling frequency in Hz to write into traces and use for transition timing",
    )
    parser.add_argument(
        "-N",
        "--network",
        default=DEFAULT_NETWORK,
        help="network code to write into every output trace and filename",
    )
    parser.add_argument(
        "-L",
        "--location",
        default=DEFAULT_LOCATION,
        help="location code to write into every output trace and filename",
    )
    parser.add_argument(
        "-C",
        "--channel",
        default=DEFAULT_CHANNEL,
        help="channel code to write into every output trace and filename",
    )
    parser.set_defaults(func=_convert_command)

    return parser


def _convert_command(args: argparse.Namespace) -> int:
    result = convert_tree(
        input_root=args.input_root,
        output_root=args.output_root,
        station=args.station,
        network=args.network,
        location=args.location,
        channel=args.channel,
        sampling_frequency_hz=args.sampling_frequency,
    )
    print(f"Converted {len(result.output_paths)} file(s).")
    print(f"Output root: {result.output_root}")
    print(f"Transition log: {result.transition_log_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.sampling_frequency = validate_sampling_frequency_hz(args.sampling_frequency)
        args.channel = validate_channel_code(args.channel, args.sampling_frequency)
    except ValueError as exc:
        parser.error(str(exc))
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
