import pytest
import asyncio
from typing import AsyncGenerator

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.db.postgres import Base, get_db_session

# Test database
TEST_DATABASE_URL = "postgresql+asyncpg://hayat:hayat_secret@localhost:5432/hayat_test"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest.fixture
def sample_case_data():
    return {
        "title": "Test Case v Respondent",
        "citation": "BLD 2024 HCD 001",
        "case_number": "Civil Suit No. 1/2024",
        "court": "High Court Division",
        "court_level": "supreme_court_high_court_division",
        "date": "2024-01-15",
        "area_of_law": "Civil",
        "petitioner": "Test Case",
        "respondent": "Respondent",
        "judges": ["Mr. Justice Test"],
    }
