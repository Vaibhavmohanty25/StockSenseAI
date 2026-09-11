from django.conf import settings
from django.db import DatabaseError, connection
from redis import Redis
from redis.exceptions import RedisError


def dependency_health() -> dict[str, str]:
    result = {"application": "ok", "database": "ok", "redis": "ok"}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (DatabaseError, OSError):
        result["database"] = "unavailable"
    try:
        with Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2
        ) as redis:
            redis.ping()
    except (RedisError, OSError, ValueError):
        result["redis"] = "unavailable"
    if "unavailable" in result.values():
        result["application"] = "degraded"
    return result
