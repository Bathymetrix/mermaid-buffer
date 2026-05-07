# Bathymetrix™
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

"""Convert raw MERMAID circular-buffer waveform files to miniSEED."""

from mermaid_buffer.convert import SAMPLING_RATE_HZ
from mermaid_buffer.seed_codes import (
    band_code,
    band_codes_for_sample_rate,
    validate_channel_code,
)

__author__ = "Joel D. Simon"
__license__ = "MIT"
__copyright__ = "© 2026 Bathymetrix, LLC"
__version__ = "0.1.0"

__all__ = [
    "SAMPLING_RATE_HZ",
    "band_code",
    "band_codes_for_sample_rate",
    "validate_channel_code",
]
