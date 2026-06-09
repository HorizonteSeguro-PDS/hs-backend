from io import BytesIO
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from dependencies.auth import CurrentUser, require_role
from dependencies.session import get_session
from domain.inventory.schemas import ShelterSpreadsheetImportResponse
from services.shelter_spreadsheet_service import ShelterSpreadsheetService


router = APIRouter(prefix="/shelters", tags=["shelter-spreadsheets"])

_AnyAuth = Annotated[
    CurrentUser,
    Depends(require_role("dev", "crisis_manager", "shelter_manager")),
]
_SessionDep = Annotated[Session, Depends(get_session)]
_UploadDep = Annotated[UploadFile, File()]

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/{shelter_id}/spreadsheet/template")
def download_template(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _AnyAuth,
) -> StreamingResponse:
    content = ShelterSpreadsheetService(session).build_template(shelter_id=shelter_id)
    return _xlsx_response(
        content,
        filename=f"shelter-{shelter_id}-template.xlsx",
    )


@router.get("/{shelter_id}/spreadsheet/export")
def export_spreadsheet(
    shelter_id: UUID,
    session: _SessionDep,
    _user: _AnyAuth,
) -> StreamingResponse:
    content = ShelterSpreadsheetService(session).export_spreadsheet(
        shelter_id=shelter_id
    )
    return _xlsx_response(
        content,
        filename=f"shelter-{shelter_id}-export.xlsx",
    )


@router.post(
    "/{shelter_id}/spreadsheet/import",
    response_model=ShelterSpreadsheetImportResponse,
)
def import_spreadsheet(
    shelter_id: UUID,
    file: _UploadDep,
    session: _SessionDep,
    user: _AnyAuth,
) -> ShelterSpreadsheetImportResponse:
    result = ShelterSpreadsheetService(session).import_spreadsheet(
        shelter_id=shelter_id,
        actor_id=user.id,
        content=file.file.read(),
    )
    session.commit()
    return result


def _xlsx_response(content: bytes, *, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(content),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
