from __future__ import annotations

import os
from dataclasses import dataclass


SOURCE_NAME = "customs_trade_statistics"
SHEET_MASTER_CODES = "master_codes"
SHEET_RAW_TRADE = "raw_trade"
SHEET_CALC_UNIT_PRICE = "calc_unit_price"

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
    spreadsheet_id: str
    google_service_account_json: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
        service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()

        if not spreadsheet_id:
            raise ValueError("環境変数 SPREADSHEET_ID が設定されていません。")
        if not service_account_json:
            raise ValueError("環境変数 GOOGLE_SERVICE_ACCOUNT_JSON が設定されていません。")

        return cls(
            spreadsheet_id=spreadsheet_id,
            google_service_account_json=service_account_json,
        )
