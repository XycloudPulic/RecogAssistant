# SPDX-License-Identifier: MIT

"""Export framework for invoice recognition results.

Design goals:
- Open/Closed: add a new exporter by implementing BaseExporter and registering it.
- SRP: exporters only serialize; selection/config comes from DB/API layer.
"""

from __future__ import annotations

import abc
import csv
import io
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExportSpec:
    format: str  # csv/xlsx/txt/...
    filename: str
    options: dict[str, Any]


@dataclass(frozen=True)
class ExportArtifact:
    filename: str
    media_type: str
    content: bytes


class BaseExporter(abc.ABC):
    """Exporter strategy."""

    @abc.abstractmethod
    def format(self) -> str: ...

    @abc.abstractmethod
    def export(
        self, *, spec: ExportSpec, headers: list[str], rows: list[dict[str, Any]]
    ) -> ExportArtifact: ...


class ExporterRegistry:
    def __init__(self) -> None:
        self._by_format: dict[str, BaseExporter] = {}

    def register(self, exporter: BaseExporter) -> None:
        self._by_format[exporter.format().lower()] = exporter

    def get(self, fmt: str) -> BaseExporter:
        key = (fmt or "").lower().strip()
        if key not in self._by_format:
            raise ValueError(f"Unknown export format: {fmt}")
        return self._by_format[key]


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (str, int, float, bool)):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


class CsvExporter(BaseExporter):
    def format(self) -> str:
        return "csv"

    def export(
        self, *, spec: ExportSpec, headers: list[str], rows: list[dict[str, Any]]
    ) -> ExportArtifact:
        delimiter = str(spec.options.get("delimiter", ","))
        lineterminator = str(spec.options.get("lineterminator", "\n"))
        encoding = str(spec.options.get("encoding", "utf-8-sig"))

        out = io.StringIO()
        writer = csv.writer(out, delimiter=delimiter, lineterminator=lineterminator)
        writer.writerow(headers)
        for r in rows:
            writer.writerow([_cell(r.get(h)) for h in headers])

        return ExportArtifact(
            filename=spec.filename
            if spec.filename.lower().endswith(".csv")
            else f"{spec.filename}.csv",
            media_type="text/csv; charset=utf-8",
            content=out.getvalue().encode(encoding, errors="replace"),
        )


class TxtExporter(BaseExporter):
    def format(self) -> str:
        return "txt"

    def export(
        self, *, spec: ExportSpec, headers: list[str], rows: list[dict[str, Any]]
    ) -> ExportArtifact:
        # default: TSV with header row
        sep = str(spec.options.get("separator", "\t"))
        encoding = str(spec.options.get("encoding", "utf-8"))
        out = io.StringIO()
        out.write(sep.join(headers) + "\n")
        for r in rows:
            out.write(sep.join([_cell(r.get(h)) for h in headers]) + "\n")
        return ExportArtifact(
            filename=spec.filename
            if spec.filename.lower().endswith(".txt")
            else f"{spec.filename}.txt",
            media_type="text/plain; charset=utf-8",
            content=out.getvalue().encode(encoding, errors="replace"),
        )


class XlsxExporter(BaseExporter):
    def format(self) -> str:
        return "xlsx"

    def export(
        self, *, spec: ExportSpec, headers: list[str], rows: list[dict[str, Any]]
    ) -> ExportArtifact:
        try:
            from openpyxl import Workbook
        except Exception as e:  # pragma: no cover
            raise RuntimeError("openpyxl is required for xlsx export") from e

        sheet_name = str(spec.options.get("sheet_name", "Sheet1"))[:31] or "Sheet1"
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        ws.append(headers)
        for r in rows:
            ws.append([_cell(r.get(h)) for h in headers])

        bio = io.BytesIO()
        wb.save(bio)
        return ExportArtifact(
            filename=spec.filename
            if spec.filename.lower().endswith(".xlsx")
            else f"{spec.filename}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            content=bio.getvalue(),
        )


def default_registry() -> ExporterRegistry:
    reg = ExporterRegistry()
    reg.register(CsvExporter())
    reg.register(TxtExporter())
    reg.register(XlsxExporter())
    return reg
