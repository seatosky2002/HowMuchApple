from sqlalchemy import event
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

# MySQL 세션 타임존을 UTC로 고정한다. 컬럼 기본값이 NOW()인 곳(created_at 계열)이
# 서버 타임존을 그대로 따라가는데, 컨테이너가 TZ=Asia/Seoul이라 KST로 저장돼
# 애플리케이션이 쓰는 UTC 값과 9시간 어긋났다(item 24%가 updated_at < created_at).
# compose에도 --default-time-zone=+00:00을 주지만, 로컬 개발 DB처럼 설정이 다른
# 환경에서도 보장되도록 커넥션 단위로 한 번 더 건다.
@event.listens_for(engine.sync_engine, "connect")
def _force_utc_session(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("SET time_zone = '+00:00'")
    finally:
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
