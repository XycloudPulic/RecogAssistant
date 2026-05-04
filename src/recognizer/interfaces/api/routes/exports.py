# SPDX-License-Identifier: MIT

"""Export generated common_result into files (csv/xlsx/txt...)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from recognizer.application.services.export_service import ExportService

router = APIRouter(prefix="/exports", tags=["exports"])
export_service = ExportService()


@router.post("/generate")
def generate_export(payload: dict) -> Response:
    return export_service.generate_export(payload)


@router.post("/from-runs")
def export_from_runs(payload: dict) -> Response:
    return export_service.export_from_runs(payload)
