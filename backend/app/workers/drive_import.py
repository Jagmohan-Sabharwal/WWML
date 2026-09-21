"""Run with python -m app.workers.drive_import [--once]."""

import argparse
import logging
import signal
from pathlib import Path
from threading import Event

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.api.drive.client import authenticated_client
from app.api.drive.errors import DriveReadError
from app.api.imports.service import ImportService
from app.api.imports.storage import AssetStorage, ImportFailure
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import create_database_engine

LOCK_ID = 879234651  # One writer per database, including across worker replicas.
logger = logging.getLogger("wwml")


def run_cycle(engine: Engine, settings: Settings) -> int:
    # Keep the lock on the same physical connection as every database write.
    # A lost connection aborts the cycle; a replacement connection cannot continue it.
    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID}
        )
        connection.commit()
        if not acquired:
            return 0
        try:
            with Session(bind=connection, expire_on_commit=False) as session:
                with authenticated_client(
                    settings.google_drive_request_timeout_seconds, download=True
                ) as client:
                    return ImportService(
                        session,
                        client,
                        settings,
                        AssetStorage(
                            Path(settings.import_storage_path),
                            settings.import_max_bytes,
                        ),
                    ).cycle()
        finally:
            # Closing an invalid connection releases its PostgreSQL session lock.
            if not connection.invalidated:
                connection.rollback()
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID}
                )
                connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--once", action="store_true", help="Run one recursive scan and exit."
    )
    args = parser.parse_args()
    settings = Settings()
    configure_logging(settings.log_level)
    if not settings.google_drive_folder_id:
        parser.error("GOOGLE_DRIVE_FOLDER_ID must be configured")
    stop = Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    engine = create_database_engine(settings)
    try:
        while not stop.is_set():
            try:
                completed = run_cycle(engine, settings)
                logger.info("Drive import cycle complete: %s registered", completed)
            except (DriveReadError, ImportFailure) as error:
                logger.error("Drive import cycle failed: %s", error.code)
                if args.once:
                    raise SystemExit(1) from None
            except Exception:
                # Do not log provider bodies, database parameters, or credential paths.
                logger.error(
                    "Drive import cycle failed; check configuration and service health"
                )
                if args.once:
                    raise SystemExit(1) from None
            if args.once:
                break
            stop.wait(settings.import_poll_seconds)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
