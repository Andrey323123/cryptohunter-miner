# core/database.py — v2.0: ПРЯМОЕ ЧТЕНИЕ MYSQLURL
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import os

# === ЧИТАЕМ MYSQLURL ПРЯМО ИЗ ПЕРЕМЕННЫХ RAILWAY ===
DATABASE_URL = os.getenv("MYSQLURL")

if not DATABASE_URL:
    raise ValueError("MYSQLURL not set in Railway Variables!")

# === ДВИЖОК ===
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
