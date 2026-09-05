from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# pool_recycle이 없으면 하루 한 번 도는 크롤 배치가 매번 죽은 커넥션을 집는다.
# MySQL wait_timeout이 8시간인데 크롤 주기는 24시간이라 풀의 커넥션은 항상 만료 상태고,
# pool_pre_ping이 그걸 감지해 폐기하려는 순간 asyncmy가 이미 닫힌 uvloop 전송에
# ensure_closed()를 호출해 RuntimeError로 터진다(= 배치 전체 실패). 만료 전에 버려서
# 그 경로 자체를 타지 않게 한다.
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
