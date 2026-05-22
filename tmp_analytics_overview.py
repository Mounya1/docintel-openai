import asyncio
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Document, Extraction, Review
from sqlalchemy import select, func
from sqlalchemy import text

async def run():
    print("DB URL:", get_settings().database_url)
    async with AsyncSessionLocal() as db:
        total = (await db.execute(select(func.count(Document.id)))).scalar() or 0
        status_res = await db.execute(select(Document.status, func.count(Document.id)).group_by(Document.status))
        by_status = {row[0]: row[1] for row in status_res.all()}
        type_res = await db.execute(select(Document.doc_type, func.count(Document.id)).group_by(Document.doc_type))
        by_type = {(row[0] or "unknown"): row[1] for row in type_res.all()}
        conf_res = await db.execute(select(func.avg(Extraction.confidence_overall)).where(Extraction.status == "completed"))
        avg_conf = round(float(conf_res.scalar() or 0), 1)
        pending_rev = (await db.execute(select(func.count(Review.id)).where(Review.status == "pending"))).scalar() or 0
        ms_res = await db.execute(select(func.avg(Extraction.processing_time_ms)))
        avg_secs = round(float(ms_res.scalar() or 0) / 1000, 1)

        # Try to use PostgreSQL date function if available, otherwise fallback to Python
        try:
            daily_res = await db.execute(text("""
                SELECT date(created_at) as day, COUNT(*) as count
                FROM documents
                WHERE created_at >= current_date - interval '7 days'
                GROUP BY date(created_at)
                ORDER BY day
            """))
            last_7 = [{"day": str(row[0]), "count": row[1]} for row in daily_res.all()]
        except Exception:
            from datetime import datetime, timedelta
            last_week = datetime.utcnow() - timedelta(days=7)
            result = await db.execute(select(Document.created_at).where(Document.created_at >= last_week))
            counts = {}
            for row in result.all():
                d = row[0].date()
                counts[d] = counts.get(d, 0) + 1
            last_7 = [{"day": str(day), "count": counts[day]} for day in sorted(counts)]

        high_res = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall >= 90))
        med_res = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall.between(70, 89.99)))
        low_res = await db.execute(select(func.count(Extraction.id)).where(Extraction.confidence_overall < 70))

        print({
            "total_documents": total,
            "by_status": by_status,
            "by_type": by_type,
            "avg_confidence": avg_conf,
            "pending_review": pending_rev,
            "avg_processing_seconds": avg_secs,
            "last_7_days": last_7,
            "confidence_distribution": {
                "high": high_res.scalar() or 0,
                "medium": med_res.scalar() or 0,
                "low": low_res.scalar() or 0,
            },
        })

if __name__ == "__main__":
    asyncio.run(run())
