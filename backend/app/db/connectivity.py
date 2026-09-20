"""Bounded connectivity probes for PostgreSQL and Redis."""

import psycopg
from redis import Redis
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from app.core.config import Settings


def postgres_ready(settings: Settings) -> bool:
    """Execute a minimal query, closing the connection after every probe."""
    if not settings.postgres_password.get_secret_value():
        return False
    try:
        with psycopg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
            connect_timeout=3,
        ) as connection:
            return connection.execute("SELECT 1").fetchone() == (1,)
    except psycopg.Error:
        return False


def redis_ready(settings: Settings) -> bool:
    """Ping Redis once with bounded timeouts and no automatic retries."""
    try:
        with Redis.from_url(
            settings.redis_url.get_secret_value(),
            socket_connect_timeout=1,
            socket_timeout=1,
            retry=Retry(NoBackoff(), 0),
        ) as client:
            return bool(client.ping())
    except (RedisError, ValueError):
        return False
