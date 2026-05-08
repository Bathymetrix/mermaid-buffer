# Bathymetrix™
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

"""Convert raw MERMAID circular-buffer waveform files to miniSEED."""

from mermaid_buffer.convert import (
    DEFAULT_SAMPLING_FREQUENCY_HZ,
    validate_data_quality_indicator,
    validate_sampling_frequency_hz,
)
from mermaid_buffer.seed_codes import (
    band_codes_for_sample_rate,
    validate_channel_code,
)

__author__ = "Joel D. Simon"
__license__ = "MIT"
__copyright__ = "© 2026 Bathymetrix, LLC"
__version__ = "1.0.0rc1"

__all__ = [
    "DEFAULT_SAMPLING_FREQUENCY_HZ",
    "__version__",
    "band_codes_for_sample_rate",
    "validate_channel_code",
    "validate_data_quality_indicator",
    "validate_sampling_frequency_hz",
]
