from __future__ import annotations

import json
from typing import Iterable

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class GoogleSheetsClient:
    def __init__(self, service_account_json: str, spreadsheet_id: str) -> None:
        credentials_info = json.loads(service_account_json)
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self._spreadsheet_id = spreadsheet_id

    def read_sheet_records(self, sheet_name: str) -> list[dict[str, str]]:
        response = (
            self._service.spreadsheets()
            .values()
            .get(spreadsheetId=self._spreadsheet_id, range=sheet_name)
            .execute()
        )
        values = response.get("values", [])
        if not values:
            return []

        headers = [str(value).strip() for value in values[0]]
        rows = []
        for raw_row in values[1:]:
            row = {header: raw_row[idx] if idx < len(raw_row) else "" for idx, header in enumerate(headers)}
            rows.append(row)
        return rows

    def replace_sheet_records(
        self,
        sheet_name: str,
        columns: list[str],
        records: Iterable[dict[str, object]],
    ) -> None:
        values: list[list[str]] = [columns]
        for record in records:
            values.append([self._stringify(record.get(column, "")) for column in columns])

        body = {"values": values}
        self._service.spreadsheets().values().clear(
            spreadsheetId=self._spreadsheet_id,
            range=sheet_name,
            body={},
        ).execute()
        self._service.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=f"{sheet_name}!A1",
            valueInputOption="RAW",
            body=body,
        ).execute()

    @staticmethod
    def _stringify(value: object) -> str:
        if value is None:
            return ""
        return str(value)
