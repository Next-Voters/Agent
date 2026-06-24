"""AWS Lambda handler for the SQS-triggered worker function.

Triggered by messages on the ``next-voters-<env>-worker-jobs`` queue (defined in
``infrastructure/lambda.tf``). Each SQS record body is a JSON object naming a
finished report::

    {"region": "San Francisco", "report_id": 45}

For each message the worker loads that report from Supabase, verifies it belongs
to the given region, and stamps it as processed. The handler uses SQS partial
batch responses, so a failed message is retried and — after ``maxReceiveCount``
attempts — routed to the worker DLQ, while its batch-mates still succeed.
"""

import json
import logging
import os

from store import count_headers, fetch_report, mark_processed

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def process_message(payload: dict) -> None:
    """Process one decoded worker job of the form ``{"region", "report_id"}``.

    Loads the named report from Supabase, verifies it belongs to ``region``,
    counts its headers, and stamps ``processed_at``.

    Args:
        payload: The JSON-decoded body of one SQS message.

    Raises:
        ValueError: If required fields are missing/invalid, the report does not
            exist, or its region does not match the message. Raising marks the
            message failed so SQS retries it and eventually routes it to the DLQ.
    """
    region = payload.get("region")
    report_id = payload.get("report_id")

    if not isinstance(region, str) or not region.strip():
        raise ValueError(f"'region' must be a non-empty string, got: {region!r}")
    # bool is a subclass of int — reject it explicitly.
    if not isinstance(report_id, int) or isinstance(report_id, bool):
        raise ValueError(f"'report_id' must be an integer, got: {report_id!r}")

    report = fetch_report(report_id)
    if report is None:
        raise ValueError(f"report_id={report_id} not found in reports table")

    if report.get("region") != region:
        raise ValueError(
            f"region mismatch for report_id={report_id}: "
            f"message={region!r} but report={report.get('region')!r}"
        )

    headers = count_headers(report_id)
    mark_processed(report_id)
    logger.info(
        "Processed report_id=%s region=%s (%d headers) -> marked processed",
        report_id,
        region,
        headers,
    )


def lambda_handler(event: dict, context: object) -> dict:
    """Entry point for the SQS-triggered worker Lambda.

    Iterates the SQS batch, processing each record independently. Failed
    records are reported via ``batchItemFailures`` so only those messages are
    retried (partial batch response). For this to take effect, the event source
    mapping must set ``function_response_types = ["ReportBatchItemFailures"]``
    (see ``infrastructure/lambda.tf``).

    Args:
        event: SQS event payload with a ``Records`` list.
        context: Lambda runtime context (unused).

    Returns:
        A partial-batch-failure response: ``{"batchItemFailures": [...]}``.
    """
    failures: list[dict] = []

    for record in event.get("Records", []):
        message_id = record.get("messageId", "<unknown>")
        try:
            payload = json.loads(record["body"])
        except (KeyError, json.JSONDecodeError) as e:
            # A malformed body will never parse, so retrying is pointless;
            # report it as failed to send it toward the DLQ.
            logger.error("Malformed message %s: %s", message_id, e)
            failures.append({"itemIdentifier": message_id})
            continue

        try:
            process_message(payload)
        except Exception:
            logger.exception("Failed to process message %s", message_id)
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}
