# Bathymetrix™
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

"""Command-line interface for buffmaid."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from buffmaid.convert import (
    DEFAULT_CHANNEL,
    DEFAULT_LOCATION,
    DEFAULT_NETWORK,
    convert_tree,
)


class _DefaultsHelpFormatter(argparse.ArgumentDefaultsHelpFormatter):
    def _get_help_string(self, action: argparse.Action) -> str:
        if action.default is None:
            return action.help or ""
        return super()._get_help_string(action)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="buffmaid",
        description="Convert raw MERMAID circular-buffer int32 waveform files to miniSEED.",
        formatter_class=_DefaultsHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    convert_parser = subparsers.add_parser(
        "convert",
        help="convert raw int32 waveform files to miniSEED",
        formatter_class=_DefaultsHelpFormatter,
    )
    convert_parser.add_argument(
        "--input-root",
        required=True,
        type=Path,
        help="root directory to recursively search for raw binary input files",
    )
    convert_parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
        help="directory for flat output .mseed files and the transition JSONL log",
    )
    convert_parser.add_argument(
        "--station",
        required=True,
        help="station code to write into every output trace and filename",
    )
    convert_parser.add_argument(
        "--network",
        default=DEFAULT_NETWORK,
        help="network code to write into every output trace and filename",
    )
    convert_parser.add_argument(
        "--location",
        default=DEFAULT_LOCATION,
        help="location code to write into every output trace and filename",
    )
    convert_parser.add_argument(
        "--channel",
        default=DEFAULT_CHANNEL,
        help="channel code to write into every output trace and filename",
    )
    convert_parser.set_defaults(func=_convert_command)

    return parser


def _convert_command(args: argparse.Namespace) -> int:
    result = convert_tree(
        input_root=args.input_root,
        output_root=args.output_root,
        station=args.station,
        network=args.network,
        location=args.location,
        channel=args.channel,
    )
    print(f"Converted {len(result.output_paths)} file(s).")
    print(f"Output root: {result.output_root}")
    print(f"Transition log: {result.transition_log_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
