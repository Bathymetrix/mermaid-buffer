# Bathymetrix™
# https://bathymetrix.com
# © 2026 Bathymetrix, LLC
# Author: Joel D. Simon <jdsimon@bathymetrix.com>
# SPDX-License-Identifier: MIT

"""Internal SEED channel-code helpers for miniSEED metadata validation."""

from __future__ import annotations

from math import isfinite

CORNER_PERIOD_THRESHOLD_SECONDS = 10.0
MINISEED_DATA_QUALITY_INDICATORS = ("D", "R", "Q", "M")


def band_codes_for_sample_rate(sample_rate_hz: float) -> tuple[str, ...]:
    """Return waveform band codes allowed by a SEED sample-rate range.

    Codes that also depend on instrument response corner period are returned
    together because sample rate alone cannot distinguish them.
    """
    rate = _positive_sample_rate(sample_rate_hz)
    nominal_rel_tol = 0.05  # ±5% for nominal L/V/U bands

    if 1000 <= rate < 5000:
        return ("F", "G")
    if 250 <= rate < 1000:
        return ("C", "D")
    if 80 <= rate < 250:
        return ("H", "E")
    if 10 <= rate < 80:
        return ("B", "S")
    if 1.0 * (1 - nominal_rel_tol) <= rate <= 1.0 * (1 + nominal_rel_tol):
        return ("L",)
    if 0.1 * (1 - nominal_rel_tol) <= rate <= 0.1 * (1 + nominal_rel_tol):
        return ("V",)
    if 0.01 * (1 - nominal_rel_tol) <= rate <= 0.01 * (1 + nominal_rel_tol):
        return ("U",)
    if 1 < rate < 10:
        return ("M",)
    if 0.0001 <= rate < 0.001:
        return ("R",)
    if 0.00001 <= rate < 0.0001:
        return ("P",)
    if 0.000001 <= rate < 0.00001:
        return ("T",)
    if 0 < rate < 0.000001:
        return ("Q",)
    return ()


def band_code(sample_rate_hz: float, corner_period_seconds: float | None = None) -> str:
    """Return the SEED band code for a sample rate and optional corner period."""

    rate = _positive_sample_rate(sample_rate_hz)
    if 1000 <= rate < 5000:
        return _period_band_code(rate, corner_period_seconds, long_period_code="F", short_period_code="G")
    if 250 <= rate < 1000:
        return _period_band_code(rate, corner_period_seconds, long_period_code="C", short_period_code="D")
    if 80 <= rate < 250:
        return _period_band_code(rate, corner_period_seconds, long_period_code="H", short_period_code="E")
    if 10 <= rate < 80:
        return _period_band_code(rate, corner_period_seconds, long_period_code="B", short_period_code="S")

    codes = band_codes_for_sample_rate(rate)
    if len(codes) == 1:
        return codes[0]
    raise ValueError(f"No waveform SEED band code is defined for {_format_sample_rate(rate)} Hz")


def validate_channel_code(channel: str, sample_rate_hz: float) -> str:
    """Return a normalized channel code or raise ValueError with a user-facing reason."""

    normalized = channel.strip().upper()
    if len(normalized) != 3:
        raise ValueError(f"Channel code must be exactly 3 characters; got {channel!r}")
    if not normalized.isalnum():
        raise ValueError(f"Channel code must contain only letters and numbers; got {channel!r}")

    allowed_codes = band_codes_for_sample_rate(sample_rate_hz)
    if not allowed_codes:
        raise ValueError(
            f"No waveform SEED band code is defined for {_format_sample_rate(sample_rate_hz)} Hz"
        )

    if normalized[0] not in allowed_codes:
        raise ValueError(
            f"Channel code {normalized!r} has band code {normalized[0]!r}, "
            f"but {_format_sample_rate(sample_rate_hz)} Hz allows {_format_code_list(allowed_codes)}"
        )
    return normalized


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


def _period_band_code(
    sample_rate_hz: float,
    corner_period_seconds: float | None,
    *,
    long_period_code: str,
    short_period_code: str,
) -> str:
    if corner_period_seconds is None:
        allowed_codes = _format_code_list((long_period_code, short_period_code))
        raise ValueError(
            f"{_format_sample_rate(sample_rate_hz)} Hz allows {allowed_codes}; "
            "corner_period_seconds is required to choose one band code"
        )
    if corner_period_seconds <= 0:
        raise ValueError(f"corner_period_seconds must be positive; got {corner_period_seconds!r}")
    if corner_period_seconds >= CORNER_PERIOD_THRESHOLD_SECONDS:
        return long_period_code
    return short_period_code


def _positive_sample_rate(sample_rate_hz: float) -> float:
    rate = float(sample_rate_hz)
    if rate <= 0:
        raise ValueError(f"sample_rate_hz must be positive; got {sample_rate_hz!r}")
    return rate


def _format_code_list(codes: tuple[str, ...]) -> str:
    if len(codes) == 1:
        return codes[0]
    if len(codes) == 2:
        return f"{codes[0]} or {codes[1]}"
    return f"{', '.join(codes[:-1])}, or {codes[-1]}"


def _format_sample_rate(sample_rate_hz: float) -> str:
    return f"{float(sample_rate_hz):.12f}".rstrip("0").rstrip(".")
