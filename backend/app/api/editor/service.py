"""Derive editorial selection readiness from stored facts."""

import re
from uuid import UUID

from app.api.editor.repository import EditorRepository
from app.api.editor.schemas import (
    EditorPage,
    EditorRow,
    NodeLabel,
    Readiness,
    RequirementLabel,
    SelectedAsset,
)
from app.api.production_structure.schemas import LockResponse
from app.api.production_structure.service import PlanningError
from app.api.workspace.schemas import PageQuery, ProductionResponse
from app.models import Asset
from app.models.production_structure import LockedAsset, RequiredAsset


def readiness(
    requirement: RequiredAsset | None, lock: LockedAsset | None, asset: Asset | None
) -> tuple[Readiness, str]:
    if requirement is None:
        return "UNPLANNED", "No required assets have been defined for this shot."
    if lock is None:
        return "MISSING", "Choose and lock an asset for this requirement."
    if asset is None or asset.deleted_at is not None:
        return "REVIEW", "The selected asset is no longer active in the registry."
    if asset.media_type != requirement.media_type:
        return "REVIEW", "The selected media type no longer matches this requirement."
    if asset.sha256 != lock.checksum or asset.storage_uri != lock.storage_uri:
        return (
            "REVIEW",
            "The registry file reference changed after this selection was locked.",
        )
    return "READY", "The locked selection matches the active registry record."


def asset_reference(asset: Asset) -> str:
    # Optional display label only; UUID remains the authoritative identifier.
    code = asset.asset_metadata.get("asset_code")
    if isinstance(code, str) and re.fullmatch(
        r"WWML-(?:VID|AUD|IMG|DOC|OTH)-[0-9]{6}", code
    ):
        return code
    return asset.name


class EditorService:
    def __init__(self, repository: EditorRepository) -> None:
        self.repository = repository

    def review(self, production_id: UUID, query: PageQuery) -> EditorPage:
        production = self.repository.production(production_id)
        if production is None:
            raise PlanningError(404, "record_not_found", "Production not found.")
        rows, total = self.repository.rows(production_id, query)
        items = []
        for sequence, scene, shot, requirement, lock, asset in rows:
            status, reason = readiness(requirement, lock, asset)
            items.append(
                EditorRow(
                    sequence=NodeLabel(
                        id=sequence.id, name=sequence.name, position=sequence.position
                    ),
                    scene=NodeLabel(
                        id=scene.id, name=scene.name, position=scene.position
                    ),
                    shot=NodeLabel(id=shot.id, name=shot.name, position=shot.position),
                    requirement=RequirementLabel.model_validate(
                        requirement, from_attributes=True
                    )
                    if requirement
                    else None,
                    selected_asset=SelectedAsset(
                        id=asset.id, name=asset.name, reference=asset_reference(asset)
                    )
                    if asset
                    else None,
                    locked_asset=LockResponse.model_validate(lock) if lock else None,
                    status=status,
                    reason=reason,
                )
            )
        return EditorPage(
            production=ProductionResponse.model_validate(production),
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            total_pages=(total + query.page_size - 1) // query.page_size,
        )
