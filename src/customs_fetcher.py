from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from urllib.parse import urljoin

import pycountry
import requests
from bs4 import BeautifulSoup

from config import CUSTOMS_COUNTRY_CODE_URL, CUSTOMS_DOWNLOAD_INDEX_URL
from logging_utils import get_logger
from transformers import (
    CUSTOMS_HEADER_ALIASES,
    find_header_mapping,
    normalize_country_code,
    normalize_country_name,
    normalize_hs_code,
    parse_decimal,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class CsvResource:
    title: str
    csv_url: str


class CustomsTradeFetcher:
    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._session.headers.update({"User-Agent": "customs-trade-batch/1.0"})

    def fetch_trade_rows(self, year_month: str, target_hs_codes: list[str]) -> tuple[list[dict[str, str]], list[str]]:
        month_page_url = self._find_month_page_url(year_month)
        csv_resources = self._find_csv_resources(month_page_url, target_hs_codes)

        if not csv_resources:
            raise RuntimeError(f"no matching CSV resources found for {year_month}")

        rows: list[dict[str, str]] = []
        source_urls: list[str] = []
        for resource in csv_resources:
            logger.info("Downloading customs CSV: %s", resource.csv_url)
            csv_text = self._download_text(resource.csv_url)
            parsed_rows = self._parse_trade_csv(csv_text, resource.csv_url)
            rows.extend(parsed_rows)
            source_urls.append(resource.csv_url)

        return rows, source_urls

    def build_country_candidates(self, master_country_codes: list[str]) -> dict[str, set[str]]:
        customs_map = self._fetch_customs_country_code_map()
        candidates: dict[str, set[str]] = {}
        for master_country_code in master_country_codes:
            normalized = normalize_country_code(master_country_code)
            items = {normalized}
            if normalized.isdigit():
                items.add(normalized.zfill(3))
            else:
                resolved = self._resolve_customs_country_code(normalized, customs_map)
                if resolved:
                    items.add(resolved)
                country = pycountry.countries.get(alpha_2=normalized) or pycountry.countries.get(alpha_3=normalized)
                if country:
                    items.add(normalize_country_name(country.name))
                    official_name = getattr(country, "official_name", "")
                    if official_name:
                        items.add(normalize_country_name(official_name))
            candidates[normalized] = items
        return candidates

    def _find_month_page_url(self, year_month: str) -> str:
        response = self._session.get(CUSTOMS_DOWNLOAD_INDEX_URL, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        target_label = self._build_month_label(year_month)
        target_year = year_month.split("-")[0]
        current_year: str | None = None

        for element in soup.select("a, li, span"):
            text = element.get_text(strip=True)
            if re.fullmatch(r"\d{4}", text):
                current_year = text
                continue
            if element.name == "a" and current_year == target_year and text == target_label:
                href = element.get("href", "")
                if href:
                    return urljoin(response.url, href)

        raise RuntimeError(f"month page not found for {year_month}")

    def _find_csv_resources(self, month_page_url: str, target_hs_codes: list[str]) -> list[CsvResource]:
        response = self._session.get(month_page_url, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        target_chapters = {int(hs_code[:2]) for hs_code in target_hs_codes if hs_code}
        resources: list[CsvResource] = []
        seen_urls: set[str] = set()

        for link in soup.find_all("a", href=True):
            text = link.get_text(" ", strip=True)
            href = urljoin(response.url, link["href"])
            if "CSV" not in text.upper():
                continue

            title = self._extract_nearby_title(link)
            if target_chapters and not self._title_matches_chapters(title, target_chapters):
                continue
            if href in seen_urls:
                continue

            resources.append(CsvResource(title=title, csv_url=href))
            seen_urls.add(href)

        return resources

    def _parse_trade_csv(self, csv_text: str, source_url: str) -> list[dict[str, str]]:
        rows = list(csv.reader(io.StringIO(csv_text)))
        if not rows:
            raise RuntimeError(f"empty CSV: {source_url}")

        header_row_index = self._detect_header_row(rows)
        headers = rows[header_row_index]
        data_rows = rows[header_row_index + 1 :]
        header_mapping = find_header_mapping(headers, CUSTOMS_HEADER_ALIASES)
        required_fields = ["hs_code", "country_code", "country_name", "import_value", "quantity_2", "quantity_2_unit"]
        missing = [field for field in required_fields if field not in header_mapping]
        if missing:
            raise RuntimeError(f"customs CSV columns could not be resolved: {', '.join(missing)} ({source_url})")

        header_index = {header: idx for idx, header in enumerate(headers)}
        parsed: list[dict[str, str]] = []
        for row in data_rows:
            if not any(cell.strip() for cell in row):
                continue

            hs_code = self._get_cell(row, header_index, header_mapping["hs_code"])
            if len(normalize_hs_code(hs_code)) != 9:
                continue

            import_value = parse_decimal(self._get_cell(row, header_index, header_mapping["import_value"]))
            if import_value is not None:
                import_value *= 1000

            parsed.append(
                {
                    "hs_code": normalize_hs_code(hs_code),
                    "country_code": self._get_cell(row, header_index, header_mapping["country_code"]).strip(),
                    "country_name": self._get_cell(row, header_index, header_mapping["country_name"]).strip(),
                    "import_value": "" if import_value is None else str(import_value),
                    "quantity_2": self._get_cell(row, header_index, header_mapping["quantity_2"]).strip(),
                    "quantity_2_unit": self._get_cell(row, header_index, header_mapping["quantity_2_unit"]).strip(),
                }
            )
        return parsed

    def _fetch_customs_country_code_map(self) -> dict[str, str]:
        response = self._session.get(CUSTOMS_COUNTRY_CODE_URL, timeout=60)
        response.raise_for_status()
        text = BeautifulSoup(response.text, "html.parser").get_text("\n")

        result: dict[str, str] = {}
        for match in re.finditer(r"(?m)^\s*(\d{3})\s+(.+?)\s*$", text):
            numeric_code = match.group(1)
            country_name = normalize_country_name(match.group(2))
            if country_name:
                result[country_name] = numeric_code
        return result

    def _resolve_customs_country_code(self, alpha_code: str, customs_map: dict[str, str]) -> str | None:
        country = pycountry.countries.get(alpha_2=alpha_code) or pycountry.countries.get(alpha_3=alpha_code)
        if not country:
            return None

        candidates = [country.name, getattr(country, "official_name", "")]
        alias_map = {
            "KR": ["Republic of Korea", "Korea, Republic of"],
            "KP": ["North Korea", "Korea, Democratic People's Republic of"],
            "VN": ["Viet Nam"],
            "TW": ["Taiwan"],
            "IR": ["Iran", "Iran, Islamic Republic of"],
            "RU": ["Russia", "Russian Federation"],
            "TZ": ["Tanzania", "Tanzania, United Republic of"],
            "VE": ["Venezuela", "Venezuela, Bolivarian Republic of"],
            "SY": ["Syria", "Syrian Arab Republic"],
            "LA": ["Laos", "Lao People's Democratic Republic"],
            "MD": ["Moldova", "Moldova, Republic of"],
            "BO": ["Bolivia", "Bolivia, Plurinational State of"],
        }
        candidates.extend(alias_map.get(alpha_code, []))

        for candidate in candidates:
            normalized = normalize_country_name(candidate)
            if normalized in customs_map:
                return customs_map[normalized]
        return None

    @staticmethod
    def _build_month_label(year_month: str) -> str:
        month = int(year_month.split("-")[1])
        return ["Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."][month - 1]

    @staticmethod
    def _extract_nearby_title(link: object) -> str:
        current = getattr(link, "parent", None)
        for _ in range(5):
            if current is None:
                break
            text = current.get_text(" ", strip=True)
            if "Chapter" in text or "Commodity by Country" in text:
                return text
            current = getattr(current, "parent", None)
        return getattr(link, "get_text", lambda *args, **kwargs: "")(" ", strip=True)

    @staticmethod
    def _title_matches_chapters(title: str, target_chapters: set[int]) -> bool:
        chapter_ranges = re.findall(r"Chapter\s+(\d{2})(?:-(\d{2}))?", title, flags=re.IGNORECASE)
        if not chapter_ranges:
            return True

        covered: set[int] = set()
        for start_text, end_text in chapter_ranges:
            start = int(start_text)
            end = int(end_text or start_text)
            covered.update(range(start, end + 1))
        return bool(target_chapters & covered)

    @staticmethod
    def _detect_header_row(rows: list[list[str]]) -> int:
        for idx, row in enumerate(rows[:20]):
            header_mapping = find_header_mapping(row, CUSTOMS_HEADER_ALIASES)
            if len(header_mapping) >= 4:
                return idx
        raise RuntimeError("customs CSV header row could not be detected")

    def _download_text(self, url: str) -> str:
        response = self._session.get(url, timeout=120)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8-sig"
        return response.text

    @staticmethod
    def _get_cell(row: list[str], header_index: dict[str, int], header_name: str) -> str:
        idx = header_index[header_name]
        return row[idx] if idx < len(row) else ""
