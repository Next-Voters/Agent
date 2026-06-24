resource "aws_lambda_function" "dispatcher" {
  function_name = "next-voters-${var.environment}-dispatcher"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.dispatcher.repository_url}:${var.dispatcher_image_tag}"
  role          = aws_iam_role.dispatcher_lambda.arn
  memory_size   = 256
  timeout       = 300

  environment {
    variables = {
      ECS_CLUSTER         = aws_ecs_cluster.main.name
      ECS_TASK_DEFINITION = aws_ecs_task_definition.pipeline.arn
      ECS_CONTAINER_NAME  = "next-voters-${var.environment}-pipeline"
      ECS_SUBNETS         = "${aws_subnet.public_a.id},${aws_subnet.public_b.id}"
      ECS_SECURITY_GROUP  = aws_security_group.ecs.id
    }
  }

  depends_on = [aws_cloudwatch_log_group.dispatcher_lambda]
}

resource "aws_lambda_function" "email" {
  function_name                  = "next-voters-${var.environment}-email"
  package_type                   = "Image"
  image_uri                      = "${aws_ecr_repository.email.repository_url}:${var.email_image_tag}"
  role                           = aws_iam_role.email_lambda.arn
  memory_size                    = 256
  timeout                        = 60
  reserved_concurrent_executions = 5

  environment {
    variables = {
      SHARE_BASE_URL   = var.share_base_url
      MAILGUN_DOMAIN   = var.mailgun_domain
      MAILGUN_SENDER   = var.mailgun_sender
      MAILGUN_BASE_URL = var.mailgun_base_url

      # SSM parameter NAMES (not values). The Lambda fetches these at cold start
      # via ssm:GetParameter(WithDecryption=true); only the names live in the
      # Lambda env — the secret values are never placed in this env block.
      MAILGUN_API_KEY_PARAM = aws_ssm_parameter.mailgun_api_key.name
      SUPABASE_URL_PARAM    = aws_ssm_parameter.supabase_url.name
      SUPABASE_KEY_PARAM    = aws_ssm_parameter.supabase_key.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.email_lambda]
}

resource "aws_lambda_event_source_mapping" "email_sqs_trigger" {
  event_source_arn = aws_sqs_queue.report_ready.arn
  function_name    = aws_lambda_function.email.arn
  batch_size       = 1
  enabled          = true
}

resource "aws_lambda_function" "worker" {
  function_name = "next-voters-${var.environment}-worker"
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.worker.repository_url}:${var.worker_image_tag}"
  role          = aws_iam_role.worker_lambda.arn
  memory_size   = 256
  timeout       = 60

  depends_on = [aws_cloudwatch_log_group.worker_lambda]

  # CI (push-worker-to-ecr.yml) deploys new images via update-function-code to
  # an immutable :<sha> tag. Terraform owns the function but not its rolling
  # image, so ignore image_uri drift to avoid reverting CI deploys to :latest.
  lifecycle {
    ignore_changes = [image_uri]
  }
}

resource "aws_lambda_event_source_mapping" "worker_sqs_trigger" {
  event_source_arn = aws_sqs_queue.worker_jobs.arn
  function_name    = aws_lambda_function.worker.arn
  batch_size       = 1
  enabled          = true

  # The handler returns SQS partial batch responses; without this, a reported
  # failure would be silently dropped instead of retried / sent to the DLQ.
  function_response_types = ["ReportBatchItemFailures"]
}
