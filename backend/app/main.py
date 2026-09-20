"""Minimal WWML API and dependency readiness checks."""
import os

import psycopg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis import Redis
from redis.exceptions import RedisError

app = FastAPI(title="WWML API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    # Separate connection parameters avoid password URL-encoding mistakes.
    checks = {"postgres": False, "redis": False}
    try:
        with psycopg.connect(
            host=os.environ.get("POSTGRES_HOST", "postgres"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            dbname=os.environ.get("POSTGRES_DB", "wwml"),
            user=os.environ.get("POSTGRES_USER", "wwml"),
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=3,
        ) as connection:
            checks["postgres"] = connection.execute("SELECT 1").fetchone() == (1,)
    except (psycopg.Error, KeyError, ValueError):
        pass

    try:
        with Redis.from_url(
            os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            socket_connect_timeout=1,
            socket_timeout=1,
        ) as client:
            checks["redis"] = bool(client.ping())
    except (RedisError, ValueError):
        pass

    ready = all(checks.values())
    # Do not return connection strings or exception messages containing secrets.
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "unavailable", "checks": checks},
    )
