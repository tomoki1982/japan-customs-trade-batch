from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SOURCE_NAME = "customs_trade_statistics"

ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"

MASTER_CODES_PATH = CONFIG_DIR / "master_codes.csv"
RAW_TRADE_PATH = DATA_DIR / "raw_trade.csv"
CALC_UNIT_PRICE_PATH = DATA_DIR / "calc_unit_price.csv"

CUSTOMS_DOWNLOAD_INDEX_URL = (
    "https://www.e-stat.go.jp/en/stat-search/files"
    "?cycle=1&cycle_facet=cycle&data=1&layout=datalist&metadata=1&page=1"
    "&tclass1=000001013180&tclass2=000001013182&tclass3val=0"
    "&toukei=00350300&tstat=000001013141"
)
CUSTOMS_COUNTRY_CODE_URL = "https://www.customs.go.jp/toukei/sankou/code/country_e.htm"

RAW_TRADE_COLUMNS = [
    "year_month",
    "hs_code",
    "item_name",
    "category",
    "country_name",
    "country_code",
    "import_value_yen",
    "quantity_2",
    "quantity_2_unit",
    "calc_unit_name",
    "source",
    "source_url",
    "fetched_at",
]

CALC_UNIT_PRICE_COLUMNS = [
    "year_month",
    "hs_code",
    "item_name",
    "category",
    "country_name",
    "country_code",
    "import_value_yen",
    "quantity_2",
    "quantity_2_unit",
    "calc_unit_name",
    "unit_multiplier",
    "unit_price",
    "formula_note",
    "source",
    "source_url",
    "fetched_at",
]

MASTER_CODE_REQUIRED_FIELDS = [
    "hs_code",
    "item_name",
    "category",
    "priority",
    "unit_name",
    "country_name",
    "country_code",
    "enabled",
]


@dataclass(frozen=True)
class AppConfig:
    master_codes_path: Path = MASTER_CODES_PATH
    raw_trade_path: Path = RAW_TRADE_PATH
    calc_unit_price_path: Path = CALC_UNIT_PRICE_PATH
