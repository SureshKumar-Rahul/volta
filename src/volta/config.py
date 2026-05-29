"""Configuration: battery model and project constants."""

from dataclasses import dataclass
from pathlib import Path

ZONE = "DE_LU"  # ENTSO-E bidding zone code
DB_PATH = Path("data/volta.db")


@dataclass
class BatteryConfig:
    capacity_mwh: float = 10.0
    power_mw: float = 5.0
    efficiency: float = 0.9          # round-trip
    soc_min_frac: float = 0.10
    soc_max_frac: float = 0.90
    start_soc_frac: float = 0.50

    def one_way_eff(self) -> float:
        return self.efficiency ** 0.5


def default_battery() -> BatteryConfig:
    return BatteryConfig()
