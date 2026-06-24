resource "aws_sqs_queue" "email_dlq" {
  name                      = "next-voters-${var.environment}-email-dlq"
  message_retention_seconds = var.dlq_message_retention_seconds
  sqs_managed_sse_enabled   = true

  # Only the report-ready queue may target this DLQ. Built as a string ARN to
  # avoid a dependency cycle (report_ready already references this queue's ARN).
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = ["arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:next-voters-${var.environment}-report-ready"]
  })
}

resource "aws_sqs_queue" "report_ready" {
  name                       = "next-voters-${var.environment}-report-ready"
  visibility_timeout_seconds = var.report_queue_visibility_timeout
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.email_dlq.arn
    maxReceiveCount     = var.email_dlq_max_receive_count
  })
}

resource "aws_sqs_queue" "pipeline_dlq" {
  name                      = "next-voters-${var.environment}-pipeline-dlq"
  message_retention_seconds = var.dlq_message_retention_seconds
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "worker_dlq" {
  name                      = "next-voters-${var.environment}-worker-dlq"
  message_retention_seconds = var.dlq_message_retention_seconds
  sqs_managed_sse_enabled   = true

  # Only the worker-jobs queue may target this DLQ. Built as a string ARN to
  # avoid a dependency cycle (worker_jobs already references this queue's ARN).
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue"
    sourceQueueArns   = ["arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:next-voters-${var.environment}-worker-jobs"]
  })
}

resource "aws_sqs_queue" "worker_jobs" {
  name                       = "next-voters-${var.environment}-worker-jobs"
  visibility_timeout_seconds = var.worker_queue_visibility_timeout
  sqs_managed_sse_enabled    = true

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.worker_dlq.arn
    maxReceiveCount     = var.worker_dlq_max_receive_count
  })
}
