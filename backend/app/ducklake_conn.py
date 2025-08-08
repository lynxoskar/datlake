from __future__ import annotations
import duckdb
from datetime import datetime
from typing import Dict, Any

from .config import get_settings
from .main import log_event  # reuse structured logger

# Global DuckDB connection
con = duckdb.connect(database=":memory:", read_only=False)


def install_and_load_extensions() -> None:
    """Install and load required DuckDB extensions for DuckLake and Postgres/S3."""
    # Idempotent in runtime container; INSTALL is cached by DuckDB
    con.execute("INSTALL ducklake;")
    con.execute("INSTALL postgres;")
    con.execute("INSTALL s3;")
    con.execute("LOAD ducklake;")
    con.execute("LOAD postgres;")
    con.execute("LOAD s3;")


def _create_postgres_secret(settings) -> None:
    sql = f"""
    CREATE OR REPLACE SECRET postgres_catalog (
        TYPE POSTGRES,
        HOST '{settings.database.postgres_host}',
        PORT {settings.database.postgres_port},
        DATABASE '{settings.database.postgres_db}',
        USER '{settings.database.postgres_user}',
        PASSWORD '{settings.database.postgres_password.get_secret_value()}'
    );
    """
    con.execute(sql)


def _create_s3_secret(settings) -> str:
    endpoint = ("https" if settings.storage.minio_secure else "http") + "://" + settings.storage.minio_endpoint
    sql = f"""
    CREATE OR REPLACE SECRET s3_storage (
        TYPE S3,
        ENDPOINT '{endpoint}',
        ACCESS_KEY_ID '{settings.storage.minio_access_key}',
        SECRET_ACCESS_KEY '{settings.storage.minio_secret_key.get_secret_value()}',
        REGION '{settings.storage.minio_region}',
        USE_SSL {'true' if settings.storage.minio_secure else 'false'}
    );
    """
    con.execute(sql)
    data_path = f"s3://{settings.storage.default_bucket}/ducklake-data/"
    return data_path


def _create_ducklake_secret(data_path: str) -> None:
    # Note: using METADATA_PARAMETERS map to reference the Postgres secret
    sql = f"""
    CREATE OR REPLACE SECRET ducklake_main (
        TYPE DUCKLAKE,
        METADATA_PATH '',
        DATA_PATH '{data_path}',
        METADATA_PARAMETERS MAP {{
            'TYPE': 'postgres',
            'SECRET': 'postgres_catalog'
        }}
    );
    """
    con.execute(sql)


def _build_attach_clause(settings) -> str:
    params = []
    if settings.database.ducklake_metadata_schema != "main":
        params.append(f"METADATA_SCHEMA '{settings.database.ducklake_metadata_schema}'")
    if settings.database.ducklake_metadata_catalog != "ducklake_metadata":
        params.append(f"METADATA_CATALOG '{settings.database.ducklake_metadata_catalog}'")
    if settings.database.ducklake_encrypted:
        params.append("ENCRYPTED true")
    if settings.database.ducklake_data_inlining_row_limit > 0:
        params.append(f"DATA_INLINING_ROW_LIMIT {settings.database.ducklake_data_inlining_row_limit}")
    if settings.database.ducklake_snapshot_version:
        params.append(f"SNAPSHOT_VERSION '{settings.database.ducklake_snapshot_version}'")
    if settings.database.ducklake_snapshot_time:
        params.append(f"SNAPSHOT_TIME '{settings.database.ducklake_snapshot_time}'")
    if settings.database.ducklake_read_only:
        params.append("READ_ONLY")
    clause = "ATTACH 'ducklake:ducklake_main' AS ducklake"
    if params:
        clause += f" ({', '.join(params)})"
    clause += ";"
    return clause


def setup_ducklake() -> Dict[str, Any]:
    """Install extensions, create secrets, and attach DuckLake using Postgres-backed catalog.

    Returns a status dict for health checks.
    """
    settings = get_settings()
    try:
        install_and_load_extensions()
        _create_postgres_secret(settings)
        data_path = _create_s3_secret(settings)
        _create_ducklake_secret(data_path)
        con.execute(_build_attach_clause(settings))
        con.execute("USE ducklake;")
        log_event("INFO", "DuckLake attached (Postgres catalog)", data_path=data_path,
                  host=settings.database.postgres_host, db=settings.database.postgres_db)
        # Basic validation
        con.execute("SELECT 1;")
        return {"connected": True, "timestamp": datetime.now().isoformat(), "environment": settings.environment.value}
    except Exception as e:
        log_event("ERROR", "DuckLake attachment failed", error=str(e))
        return {"connected": False, "error": str(e), "timestamp": datetime.now().isoformat()}
