from __future__ import annotations

import argparse
from datetime import datetime
from zoneinfo import ZoneInfo

from config import (
    AppConfig,
    CALC_UNIT_PRICE_COLUMNS,
    RAW_TRADE_COLUMNS,
    SHEET_CALC_UNIT_PRICE,
    SHEET_MASTER_CODES,
    SHEET_RAW_TRADE,
)
from customs_fetcher import CustomsTradeFetcher
from logging_utils import get_logger, setup_logging
from sheets_client import GoogleSheetsClient
from transformers import (
    build_calc_unit_price_record,
    build_raw_trade_record,
    ensure_raw_trade_shape,
    extract_target_records,
    load_master_codes,
    upsert_records,
)

logger = get_logger(__name__)
JST = ZoneInfo("Asia/Tokyo")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Japan customs trade data and write to Google Sheets.")
    parser.add_argument("--year-month", help="Target month in YYYY-MM format. Defaults to previous month.")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to Google Sheets.")
    return parser.parse_args()


def resolve_target_year_month(explicit_year_month: str | None) -> str:
    if explicit_year_month:
        datetime.strptime(explicit_year_month, "%Y-%m")
        return explicit_year_month

    now = datetime.now(JST)
    year = now.year
    month = now.month - 1
    if month == 0:
        year -= 1
        month = 12
    return f"{year:04d}-{month:02d}"


def main() -> None:
    setup_logging()
    args = parse_args()
    year_month = resolve_target_year_month(args.year_month)
    fetched_at = datetime.now(JST).isoformat()

    logger.info("Start batch: year_month=%s dry_run=%s", year_month, args.dry_run)

    config = AppConfig.from_env()
    sheets_client = GoogleSheetsClient(config.google_service_account_json, config.spreadsheet_id)
    fetcher = CustomsTradeFetcher()

    master_sheet_rows = sheets_client.read_sheet_records(SHEET_MASTER_CODES)
    master_records = load_master_codes(master_sheet_rows)
    if not master_records:
        raise RuntimeError("No enabled records were found in master_codes.")

    logger.info("master_codes records: %s", len(master_records))

    trade_rows, source_urls = fetcher.fetch_trade_rows(
        year_month=year_month,
        target_hs_codes=[record.hs_code for record in master_records],
    )
    logger.info("customs rows fetched: %s", len(trade_rows))

    country_candidates = fetcher.build_country_candidates([record.country_code for record in master_records])
    matched_records = extract_target_records(trade_rows, master_records, country_candidates)
    logger.info("target rows matched: %s", len(matched_records))

    primary_source_url = source_urls[0] if source_urls else ""
    raw_records = [
        build_raw_trade_record(
            year_month=year_month,
            master_record=master_record,
            customs_row=customs_row,
            fetched_at=fetched_at,
            source_url=primary_source_url,
        )
        for master_record, customs_row in matched_records
    ]
    raw_records = ensure_raw_trade_shape(raw_records)

    warning_messages: list[str] = []
    calc_records = []
    for raw_record in raw_records:
        calc_record = build_calc_unit_price_record(raw_record, warning_messages)
        if calc_record is not None:
            calc_records.append(calc_record)

    for warning_message in warning_messages:
        logger.warning(warning_message)

    logger.info("raw save rows: %s", len(raw_records))
    logger.info("calc save rows: %s", len(calc_records))
    logger.info("warning count: %s", len(warning_messages))

    if args.dry_run:
        logger.info("Dry-run mode enabled. Skipped Google Sheets update.")
        return

    existing_raw = sheets_client.read_sheet_records(SHEET_RAW_TRADE)
    merged_raw = upsert_records(
        existing_records=existing_raw,
        new_records=raw_records,
        key_fields=["year_month", "hs_code", "country_code"],
        output_columns=RAW_TRADE_COLUMNS,
    )
    sheets_client.replace_sheet_records(SHEET_RAW_TRADE, RAW_TRADE_COLUMNS, merged_raw)

    existing_calc = sheets_client.read_sheet_records(SHEET_CALC_UNIT_PRICE)
    merged_calc = upsert_records(
        existing_records=existing_calc,
        new_records=calc_records,
        key_fields=["year_month", "hs_code", "country_code"],
        output_columns=CALC_UNIT_PRICE_COLUMNS,
    )
    sheets_client.replace_sheet_records(SHEET_CALC_UNIT_PRICE, CALC_UNIT_PRICE_COLUMNS, merged_calc)

    logger.info("Google Sheets update completed.")


if __name__ == "__main__":
    main()
