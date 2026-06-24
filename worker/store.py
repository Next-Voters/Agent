"""Supabase access for the worker Lambda.

Self-contained on purpose: the Lambda image only ships the ``worker/`` directory
(see ``docker/Dockerfile.worker``), so this cannot import the repo's ``utils``
package. Secrets are resolved once per cold start — directly from
``SUPABASE_URL`` / ``SUPABASE_KEY`` when present (local / docker runs), otherwise
fetched and decrypted from SSM Parameter Store using the ``SUPABASE_URL_PARAM`` /
``SUPABASE_KEY_PARAM`` env vars (the names the Lambda is given at deploy time).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache

from supabase import Client, create_client


def _resolve_secret(value_env: str, param_env: str) -> str:
    """Resolve one secret from a direct env var or an SSM parameter.

    Args:
        value_env: Env var that may hold the literal value (e.g. ``SUPABASE_URL``),
            used for local/docker runs.
        param_env: Env var holding the SSM parameter NAME to fetch and decrypt
            (e.g. ``SUPABASE_URL_PARAM``), used in the Lambda runtime.

    Returns:
        The resolved secret value.

    Raises:
        RuntimeError: If neither source yields a value.
    """
    direct = os.getenv(value_env)
    if direct:
        return direct

    param_name = os.getenv(param_env)
    if not param_name:
        raise RuntimeError(
            f"Neither {value_env} nor {param_env} is set; cannot resolve secret."
        )

    # boto3 ships in the Lambda runtime; imported lazily so env-var (local) runs
    # don't need it installed.
    import boto3

    ssm = boto3.client("ssm")
    resp = ssm.get_parameter(Name=param_name, WithDecryption=True)
    return resp["Parameter"]["Value"]


@lru_cache(maxsize=1)
def get_client() -> Client:
    """Return a process-cached Supabase client built from resolved secrets."""
    url = _resolve_secret("SUPABASE_URL", "SUPABASE_URL_PARAM")
    key = _resolve_secret("SUPABASE_KEY", "SUPABASE_KEY_PARAM")
    return create_client(url, key)


def fetch_report(report_id: int) -> dict | None:
    """Fetch a single ``reports`` row by primary key, or None if absent."""
    resp = (
        get_client()
        .table("reports")
        .select("id, region, report_date")
        .eq("id", report_id)
        .maybe_single()
        .execute()
    )
    return resp.data if resp and resp.data else None


def count_headers(report_id: int) -> int:
    """Return the number of ``report_headers`` rows for a report."""
    resp = (
        get_client()
        .table("report_headers")
        .select("report_id", count="exact")
        .eq("report_id", report_id)
        .execute()
    )
    return resp.count or 0


def mark_processed(report_id: int) -> None:
    """Stamp the report's ``processed_at`` with the current UTC time (idempotent)."""
    now = datetime.now(timezone.utc).isoformat()
    get_client().table("reports").update({"processed_at": now}).eq(
        "id", report_id
    ).execute()
