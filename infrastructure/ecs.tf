resource "aws_ecs_cluster" "main" {
  name = "next-voters-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

resource "aws_ecs_task_definition" "pipeline" {
  family                   = "next-voters-${var.environment}-pipeline"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([{
    name      = "next-voters-${var.environment}-pipeline"
    image     = "${aws_ecr_repository.pipeline.repository_url}:${var.pipeline_image_tag}"
    essential = true

    environment = [
      { name = "SQS_QUEUE_URL", value = aws_sqs_queue.report_ready.url },
      { name = "SQS_PIPELINE_DLQ_URL", value = aws_sqs_queue.pipeline_dlq.url },
      { name = "SQS_WORKER_QUEUE_URL", value = aws_sqs_queue.worker_jobs.url }
    ]

    # Secret values are injected from SSM at task start by the execution role.
    # Only ARNs appear here — never the secret values themselves.
    secrets = [
      { name = "OPENAI_API_KEY", valueFrom = aws_ssm_parameter.openai_api_key.arn },
      { name = "TAVILY_API_KEY", valueFrom = aws_ssm_parameter.tavily_api_key.arn },
      { name = "TOGETHER_API_KEY", valueFrom = aws_ssm_parameter.together_api_key.arn },
      { name = "SUPABASE_URL", valueFrom = aws_ssm_parameter.supabase_url.arn },
      { name = "SUPABASE_KEY", valueFrom = aws_ssm_parameter.supabase_key.arn }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.ecs_pipeline.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "pipeline"
      }
    }
  }])
}
