"""Production dashboard: selection progress plus explicitly global import activity."""

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.editor.dashboard_repository import DashboardRepository
from app.api.imports.router import ImportRead
from app.api.production_structure.service import PlanningError
from app.api.workspace.schemas import ProductionResponse, SyncJobResponse


class ProductionDashboard(BaseModel):
    production: ProductionResponse
    progress_percent: float | None
    assets_ready: int
    missing_assets: int
    assets_to_review: int
    unplanned_shots: int
    required_assets: int
    ai_gaps: int | None = None
    credits_saved: float | None = None
    activity_scope: str = "shared_library"
    latest_sync_job: SyncJobResponse | None
    import_queue: int
    failed_imports: int
    latest_imports: list[ImportRead]


def planning_progress(ready: int, required: int, unplanned: int) -> float | None:
    denominator = required + unplanned
    if not denominator:
        return None
    percent = round(100 * ready / denominator, 1)
    return min(percent, 99.9) if ready < denominator else percent


def production_dashboard(session: Session, identifier: UUID) -> ProductionDashboard:
    facts = DashboardRepository(session).read(identifier)
    if facts is None:
        raise PlanningError(404, "record_not_found", "Production not found.")
    return ProductionDashboard(
        production=ProductionResponse.model_validate(facts.production),
        progress_percent=planning_progress(
            facts.ready, facts.required, facts.unplanned
        ),
        required_assets=facts.required,
        assets_ready=facts.ready,
        missing_assets=facts.missing,
        assets_to_review=facts.required - facts.ready - facts.missing,
        unplanned_shots=facts.unplanned,
        latest_sync_job=SyncJobResponse.model_validate(facts.job)
        if facts.job
        else None,
        import_queue=facts.queue,
        failed_imports=facts.failed,
        latest_imports=[ImportRead.model_validate(item) for item in facts.latest],
    )
