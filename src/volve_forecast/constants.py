from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnGuess:
    # Include confirmed Volve daily production headers:
    date: tuple[str, ...] = ("DATEPRD", "DATE", "Date", "date", "DATO", "PROD_DATE")
    well: tuple[str, ...] = (
        "WELL_BORE_CODE",
        "WELL",
        "Well",
        "WELLBORE",
        "WELL_BORE",
        "BORE",
        "WELL_NAME",
    )
    oil_rate: tuple[str, ...] = (
        # Volve daily production volume (per day), commonly treated as daily rate for DCA:
        "OIL",
        "Oil",
        "OIL_RATE",
        "OILRATE",
        "BORE_OIL_VOL",
        "BORE_OIL_VOL_SM3",
        "QO",
        "QOIL",
    )
    gas_rate: tuple[str, ...] = (
        "GAS",
        "Gas",
        "GAS_RATE",
        "GASRATE",
        "BORE_GAS_VOL",
        "BORE_GAS_VOL_SM3",
        "QG",
        "QGAS",
    )
    water_rate: tuple[str, ...] = (
        "WATER",
        "Water",
        "WATER_RATE",
        "WATERRATE",
        "BORE_WAT_VOL",
        "BORE_WAT_VOL_SM3",
        "QW",
        "QWAT",
    )
    on_stream_hrs: tuple[str, ...] = ("ON_STREAM_HRS", "ON_STREAM", "On Stream", "ON_STREAM_HOURS")


DEFAULT_GUESS = ColumnGuess()


# ---------------------------------------------------------------------------
# Emission factors (operational / Scope 1+2)
# ---------------------------------------------------------------------------
# These are REAL industry values with documented sources.
# Units: kg CO2 per Sm3 oil produced (operational emissions, not combustion)
#
# Sources:
# - Norwegian Petroleum Directorate (NPD) Environment Report 2023:
#   Average NCS emission intensity ~8 kg CO2/boe, range 5-25 depending on field.
#   1 boe ≈ 0.159 Sm3 oil, so ~50 kg CO2/Sm3 average.
# - Equinor Sustainability Report 2023:
#   Upstream emission intensity target <6 kg CO2/boe by 2030.
# - Volve was a small mature field with FPSO (Maersk Inspirer), likely
#   higher intensity than electrified platforms.
#
# We use a configurable default with documented range for sensitivity analysis.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EmissionFactors:
    """
    Operational CO2 emission intensity factors.
    
    These represent Scope 1+2 emissions from production operations
    (power generation, flaring, fugitive emissions), NOT combustion
    of the produced hydrocarbons.
    
    Source references:
    - NPD Environment Report 2023: https://www.npd.no/
    - Equinor Sustainability Report 2023: https://www.equinor.com/sustainability
    - IOGP Environmental Performance Indicators 2022
    """
    # kg CO2 per Sm3 oil produced (operational emissions)
    # NCS average ~50, range 30-150 depending on field characteristics
    co2_per_sm3_oil_default: float = 50.0  # kg CO2 / Sm3 oil
    co2_per_sm3_oil_low: float = 30.0      # efficient/electrified
    co2_per_sm3_oil_high: float = 100.0    # small/mature/FPSO
    
    # kg CO2 per Sm3 gas produced (operational, much lower than oil)
    co2_per_sm3_gas_default: float = 0.05  # kg CO2 / Sm3 gas
    
    # Conversion factors (standard conditions)
    sm3_oil_per_boe: float = 0.159  # 1 boe = 0.159 Sm3 oil
    
    # Volve-specific assumption: small mature FPSO field, higher intensity
    volve_assumed_intensity: float = 70.0  # kg CO2 / Sm3 oil


DEFAULT_EMISSION_FACTORS = EmissionFactors()
