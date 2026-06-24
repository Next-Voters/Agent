"""AWS Lambda handler for the SQS-triggered worker function.

Triggered by messages on the ``next-voters-<env>-worker-jobs`` queue (defined in
``infrastructure/lambda.tf``). Each SQS record body is expected to be a JSON
object describing one unit of work.

This is a minimal scaffold: replace the body of :func:`process_message` with the
real job logic. The handler uses SQS partial batch responses, so a failed
message is retried and — after ``maxReceiveCount`` attempts — routed to the
worker DLQ, while its batch-mates still succeed.
"""

import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))


def process_message(payload: dict) -> None:
    """Process a single decoded worker job.

    Args:
        payload: The JSON-decoded body of one SQS message.

    Replace this stub with the real work. Raising an exception marks the
    message as failed so SQS retries it and eventually routes it to the DLQ.
    """
    logger.info("Processing worker job: %s", payload)


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
