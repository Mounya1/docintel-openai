"""Analytics routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Document, Extraction, Review, User
from app.schemas import AnalyticsOverview, DailyCount, ConfidenceDistribution
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total_res   = await db.execute(select(func.count(Document.id)))
    total       = total_res.scalar() or 0

    status_res  = await db.execute(select(Document.status, func.count(Document.id)).group_by(Document.status))
    by_status   = {row[0]: row[1] for row in status_res.all()}

    type_res    = await db.execute(select(Document.doc_type, func.count(Document.id)).group_by(Document.doc_type))
    by_type     = {(row[0] or "unknown"): row[1] for row in type_res.all()}

    conf_res    = await db.execute(select(func.avg(Extraction.confidence_overall)).where(Extraction.status == "completed"))
    avg_conf    = round(float(conf_res.scalar() or 0), 1)

    rev_res     = await db.execute(select(func.count(Review.id)).where(Review.status == "pending"))
    pending_rev = rev_res.scalar() or 0

    ms_res      = await db.execute(select(func.avg(Extraction.processing_time_ms)))
    avg_ms      = float(ms_res.scalar() or 0)
    avg_secs    = round(avg_ms / 1000, 1)

    # Last 7 days document volume
    daily_res = await db.execute(text("""
        SELECT DATE(created_at) as day, COUNT(*) as count
        FROM documents
        WHERE created_at >= NOW() - INTERVAL '7 days'
        GROUP BY DATE(created_at)
        ORDER BY day
    """))
    last_7 = [DailyCount(day=str(row[0]), count=row[1]) for row in daily_res.all()]

    # Confidence distribution
    high_res   = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall >= 90))
    med_res    = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall.between(70, 89.99)))
    low_res    = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall < 70))
    dist       = ConfidenceDistribution(high=high_res.scalar() or 0, medium=med_res.scalar() or 0, low=low_res.scalar() or 0)

    return AnalyticsOverview(
        total_documents=total,
        by_status=by_status,
        by_type=by_type,
        avg_confidence=avg_conf,
        pending_review=pending_rev,
        avg_processing_seconds=avg_secs,
        last_7_days=last_7,
        confidence_distribution=dist,
    )
