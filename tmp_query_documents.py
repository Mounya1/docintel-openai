import asyncio
from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Document, User
from sqlalchemy import select

async def run():
    print("DB URL:", get_settings().database_url)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Document).order_by(Document.created_at))
        docs = result.scalars().all()
        print("DOCUMENT_COUNT:", len(docs))
        for d in docs:
            uploader = None
            if d.uploaded_by:
                uploader = await session.get(User, d.uploaded_by)
            print({
                "id": d.id,
                "name": d.name,
                "original_name": d.original_name,
                "doc_type": d.doc_type,
                "status": d.status,
                "uploaded_by": d.uploaded_by,
                "uploaded_by_name": uploader.name if uploader else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            })

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as exc:
        print("ERROR", type(exc).__name__, exc)
