from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

from config import CALC_UNIT_PRICE_COLUMNS, MASTER_CODE_REQUIRED_FIELDS, RAW_TRADE_COLUMNS, SOURCE_NAME


JP = {
    "statistical_code": "\u7d71\u8a08\u756a\u53f7",
    "statistical_item_code": "\u7d71\u8a08\u54c1\u76ee\u756a\u53f7",
    "statistical_item_code_alt": "\u7d71\u8a08\u54c1\u76ee\u30b3\u30fc\u30c9",
    "item_code": "\u54c1\u76ee\u30b3\u30fc\u30c9",
    "item_name": "\u54c1\u540d",
    "item_name_alt": "\u54c1\u76ee\u540d",
    "category": "\u30ab\u30c6\u30b4\u30ea",
    "classification": "\u5206\u985e",
    "priority": "\u512a\u5148\u5ea6",
    "unit": "\u5358\u4f4d",
    "calc_unit": "\u8a08\u7b97\u5358\u4f4d",
    "country_name": "\u56fd\u540d",
    "partner_country_name": "\u76f8\u624b\u56fd\u540d",
    "country_code": "\u56fd\u30b3\u30fc\u30c9",
    "partner_country_code": "\u76f8\u624b\u56fd\u30b3\u30fc\u30c9",
    "enabled": "\u6709\u52b9",
    "target": "\u5bfe\u8c61",
    "amount": "\u91d1\u984d",
    "amount_thousand_yen": "\u91d1\u984d(\u5343\u5186)",
    "quantity2": "\u7b2c2\u6570\u91cf",
    "quantity2_alt": "\u6570\u91cf2",
    "quantity2_unit": "\u7b2c2\u6570\u91cf\u5358\u4f4d",
    "quantity2_unit_alt": "\u6570\u91cf2\u5358\u4f4d",
    "formula_note": "\u91d1\u984d\u00d7\u5358\u4f4d\u00f7\u7b2c2\u6570\u91cf",
    "yen_per_kg": "\u5186/KG",
    "yen_per_mt": "\u5186/MT",
    "yen_per_kl": "\u5186/KL",
}

MASTER_HEADER_ALIASES: dict[str, list[str]] = {
    "hs_code": ["hs_code", "hscode", "hs code", JP["statistical_code"], JP["statistical_item_code"], JP["statistical_item_code_alt"], JP["item_code"]],
    "item_name": ["item_name", "item", JP["item_name"], JP["item_name_alt"], "item name"],
    "category": ["category", JP["category"], JP["classification"]],
    "priority": ["priority", JP["priority"]],
    "unit_name": ["unit_name", "calc_unit_name", "unit", JP["unit"], JP["calc_unit"]],
    "country_name": ["country_name", "country", JP["country_name"], JP["partner_country_name"]],
    "country_code": ["country_code", "country code", JP["country_code"], JP["partner_country_code"]],
    "enabled": ["enabled", "enable", JP["target"], JP["enabled"]],
}

CUSTOMS_HEADER_ALIASES: dict[str, list[str]] = {
    "hs_code": [
        JP["statistical_item_code"],
        JP["statistical_code"],
        JP["statistical_item_code_alt"],
        JP["item_code"],
        "commodity code",
        "commoditycode",
        "statistical code",
        "code",
    ],
    "country_code": [JP["partner_country_code"], JP["country_code"], "partner code", "country code", "countrycode"],
    "country_name": [JP["partner_country_name"], JP["country_name"], "partner name", "country name", "country"],
    "import_value": [JP["amount"], "value", "import value", JP["amount_thousand_yen"], "value(1,000yen)"],
    "quantity_2": [JP["quantity2"], JP["quantity2_alt"], "2nd quantity", "quantity2"],
    "quantity_2_unit": [JP["quantity2_unit"], JP["quantity2_unit_alt"], "2nd quantity unit", "unit2"],
}

FORMULA_NOTE = JP["formula_note"]


@dataclass(frozen=True)
class MasterCodeRecord:
    hs_code: str
    item_name: str
    category: str
    priority: str
    unit_name: str
    country_name: str
    country_code: str
    enabled: bool


def normalize_header(value: str) -> str:
    compact = re.sub(r"[\s\r\n\t_/()-]+", "", value or "")
    return compact.lower()


def normalize_hs_code(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def normalize_country_code(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value or "").upper()


def normalize_country_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (value or "").casefold())


def find_header_mapping(headers: Iterable[str], aliases: dict[str, list[str]]) -> dict[str, str]:
    normalized_to_original = {normalize_header(header): header for header in headers}
    mapping: dict[str, str] = {}
    for canonical_name, candidates in aliases.items():
        for candidate in candidates:
            hit = normalized_to_original.get(normalize_header(candidate))
            if hit:
                mapping[canonical_name] = hit
                break
    return mapping


def load_master_codes(rows: list[dict[str, str]]) -> list[MasterCodeRecord]:
    if not rows:
        return []

    header_mapping = find_header_mapping(rows[0].keys(), MASTER_HEADER_ALIASES)
    missing = [field for field in MASTER_CODE_REQUIRED_FIELDS if field not in header_mapping]
    if missing:
        raise ValueError("master_codes sheet is missing required columns: " + ", ".join(missing))

    results: list[MasterCodeRecord] = []
    for row in rows:
        enabled_value = str(row.get(header_mapping["enabled"], "")).strip()
        if enabled_value not in {"1", "true", "TRUE", "True", "yes", "YES"}:
            continue

        hs_code = normalize_hs_code(row.get(header_mapping["hs_code"], ""))
        if len(hs_code) != 9:
            raise ValueError(f"master_codes hs_code must be 9 digits: {hs_code or '(empty)'}")

        results.append(
            MasterCodeRecord(
                hs_code=hs_code,
                item_name=str(row.get(header_mapping["item_name"], "")).strip(),
                category=str(row.get(header_mapping["category"], "")).strip(),
                priority=str(row.get(header_mapping["priority"], "")).strip(),
                unit_name=str(row.get(header_mapping["unit_name"], "")).strip().upper(),
                country_name=str(row.get(header_mapping["country_name"], "")).strip(),
                country_code=normalize_country_code(str(row.get(header_mapping["country_code"], "")).strip()),
                enabled=True,
            )
        )

    return results


def extract_target_records(
    customs_rows: list[dict[str, str]],
    master_records: list[MasterCodeRecord],
    country_candidates: dict[str, set[str]],
) -> list[tuple[MasterCodeRecord, dict[str, str]]]:
    master_by_key = {(record.hs_code, record.country_code): record for record in master_records}
    matched: list[tuple[MasterCodeRecord, dict[str, str]]] = []

    for row in customs_rows:
        hs_code = normalize_hs_code(row.get("hs_code", ""))
        row_country_code = normalize_country_code(row.get("country_code", ""))
        row_country_name = normalize_country_name(row.get("country_name", ""))

        for (master_hs, master_country), master_record in master_by_key.items():
            if hs_code != master_hs:
                continue
            candidates = country_candidates.get(master_country, {master_country})
            if row_country_code in candidates or row_country_name in candidates:
                matched.append((master_record, row))
                break

    return matched


def build_raw_trade_record(
    year_month: str,
    master_record: MasterCodeRecord,
    customs_row: dict[str, str],
    fetched_at: str,
    source_url: str,
) -> dict[str, object]:
    import_value = parse_decimal(customs_row.get("import_value"))
    quantity_2 = parse_decimal(customs_row.get("quantity_2"))
    quantity_2_unit = str(customs_row.get("quantity_2_unit", "")).strip().upper()

    return {
        "year_month": year_month,
        "hs_code": master_record.hs_code,
        "item_name": master_record.item_name,
        "category": master_record.category,
        "country_name": master_record.country_name,
        "country_code": master_record.country_code,
        "import_value_yen": decimal_to_string(import_value),
        "quantity_2": decimal_to_string(quantity_2),
        "quantity_2_unit": quantity_2_unit,
        "calc_unit_name": master_record.unit_name,
        "source": SOURCE_NAME,
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


def build_calc_unit_price_record(raw_record: dict[str, object], warning_messages: list[str]) -> dict[str, object] | None:
    import_value = parse_decimal(str(raw_record.get("import_value_yen", "")))
    quantity_2 = parse_decimal(str(raw_record.get("quantity_2", "")))
    quantity_2_unit = str(raw_record.get("quantity_2_unit", "")).strip().upper()
    calc_unit_name = str(raw_record.get("calc_unit_name", "")).strip().upper()
    hs_code = str(raw_record.get("hs_code", ""))
    country_code = str(raw_record.get("country_code", ""))
    year_month = str(raw_record.get("year_month", ""))

    if import_value is None or quantity_2 is None or quantity_2 == 0:
        warning_messages.append(
            "skip calc_unit_price because amount or quantity is missing/zero: "
            f"year_month={year_month}, hs_code={hs_code}, country_code={country_code}"
        )
        return None

    multiplier = resolve_unit_multiplier(calc_unit_name, quantity_2_unit)
    if multiplier is None:
        warning_messages.append(
            "skip calc_unit_price because unit conversion is unsupported: "
            f"calc_unit_name={calc_unit_name}, quantity_2_unit={quantity_2_unit}, hs_code={hs_code}"
        )
        return None

    unit_price = (import_value * multiplier) / quantity_2
    record = dict(raw_record)
    record.update(
        {
            "unit_multiplier": decimal_to_string(multiplier),
            "unit_price": decimal_to_string(unit_price),
            "formula_note": FORMULA_NOTE,
        }
    )
    return {column: record.get(column, "") for column in CALC_UNIT_PRICE_COLUMNS}


def upsert_records(
    existing_records: list[dict[str, str]],
    new_records: list[dict[str, object]],
    key_fields: list[str],
    output_columns: list[str],
) -> list[dict[str, object]]:
    merged: dict[tuple[str, ...], dict[str, object]] = {}

    for record in existing_records:
        normalized = {column: record.get(column, "") for column in output_columns}
        merged[_make_key(normalized, key_fields)] = normalized

    for record in new_records:
        normalized = {column: record.get(column, "") for column in output_columns}
        merged[_make_key(normalized, key_fields)] = normalized

    return list(merged.values())


def ensure_raw_trade_shape(records: list[dict[str, object]]) -> list[dict[str, object]]:
    return [{column: record.get(column, "") for column in RAW_TRADE_COLUMNS} for record in records]


def decimal_to_string(value: Decimal | None) -> str:
    if value is None:
        return ""
    normalized = value.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if number == number.to_integral():
        return Decimal(int(number))
    return number


def resolve_unit_multiplier(calc_unit_name: str, quantity_2_unit: str) -> Decimal | None:
    if calc_unit_name == JP["yen_per_kg"]:
        return Decimal("1")
    if calc_unit_name == JP["yen_per_mt"]:
        return Decimal("1000")
    if calc_unit_name == JP["yen_per_kl"] and quantity_2_unit == "KL":
        return Decimal("1")
    return None


def _make_key(record: dict[str, object], key_fields: list[str]) -> tuple[str, ...]:
    return tuple(str(record.get(field, "")) for field in key_fields)
