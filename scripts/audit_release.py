#!/usr/bin/env python
# Bathymetrix™
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

"""Release-readiness checks for the mermaid-buffer v1 interface."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, entry_points, version
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))

import mermaid_buffer
from mermaid_buffer.seed_codes import (
    band_codes_for_sample_rate,
    validate_channel_code,
    validate_data_quality_indicator,
    validate_sampling_frequency_hz,
)


EXPECTED_ROOT_EXPORTS = {"__version__"}
FORBIDDEN_ROOT_EXPORTS = {
    "DEFAULT_SAMPLING_FREQUENCY_HZ",
    "band_codes_for_sample_rate",
    "validate_channel_code",
    "validate_data_quality_indicator",
    "validate_sampling_frequency_hz",
}


def main() -> int:
    failures: list[str] = []

    root_exports = set(getattr(mermaid_buffer, "__all__", ()))
    if root_exports != EXPECTED_ROOT_EXPORTS:
        failures.append(f"package root __all__ is {sorted(root_exports)!r}")

    for name in sorted(FORBIDDEN_ROOT_EXPORTS):
        if hasattr(mermaid_buffer, name):
            failures.append(f"package root unexpectedly exposes {name}")

    if band_codes_for_sample_rate(40.01406) != ("B", "S"):
        failures.append("seed_codes.band_codes_for_sample_rate returned unexpected default codes")
    if validate_channel_code("bdh", 40.01406) != "BDH":
        failures.append("seed_codes.validate_channel_code did not normalize BDH")
    if validate_data_quality_indicator(" r ") != "R":
        failures.append("seed_codes.validate_data_quality_indicator did not normalize R")
    if validate_sampling_frequency_hz("40.01406") != 40.01406:
        failures.append("seed_codes.validate_sampling_frequency_hz did not parse default frequency")

    try:
        installed_version = version("mermaid-buffer")
    except PackageNotFoundError:
        installed_version = None
    if installed_version is not None and installed_version != mermaid_buffer.__version__:
        failures.append(
            "installed mermaid-buffer version does not match package version: "
            f"{installed_version!r} != {mermaid_buffer.__version__!r}"
        )

    console_scripts = entry_points(group="console_scripts")
    buffer_entry_points = [entry for entry in console_scripts if entry.name == "buffer2mseed"]
    if buffer_entry_points:
        if not any(entry.value == "mermaid_buffer.cli:main" for entry in buffer_entry_points):
            failures.append("buffer2mseed console script does not point to mermaid_buffer.cli:main")
    elif installed_version is not None:
        failures.append("installed mermaid-buffer distribution has no buffer2mseed console script")

    if failures:
        print("Release audit failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Release audit passed: buffer2mseed is primary; root API is minimal; helpers import from submodules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
