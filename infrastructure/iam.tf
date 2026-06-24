data "aws_caller_identity" "current" {}

# --- ECS Task Execution Role ---

resource "aws_iam_role" "ecs_task_execution" {
  name = "next-voters-${var.environment}-ecs-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_logs" {
  name = "LogsAccess"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = aws_cloudwatch_log_group.ecs_pipeline.arn
    }]
  })
}

# Lets the ECS agent inject SSM SecureString secrets into the pipeline container
# at task start. Scoped to exactly the pipeline parameters; kms:Decrypt is gated
# to calls made via SSM (so this role can never decrypt anything else).
resource "aws_iam_role_policy" "ecs_task_execution_ssm" {
  name = "SsmSecretsAccess"
  role = aws_iam_role.ecs_task_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "ssm:GetParameters"
        Resource = [
          aws_ssm_parameter.openai_api_key.arn,
          aws_ssm_parameter.tavily_api_key.arn,
          aws_ssm_parameter.together_api_key.arn,
          aws_ssm_parameter.supabase_url.arn,
          aws_ssm_parameter.supabase_key.arn,
        ]
      },
      {
        Effect    = "Allow"
        Action    = "kms:Decrypt"
        Resource  = "*"
        Condition = { StringEquals = { "kms:ViaService" = local.ssm_via_service_kms } }
      }
    ]
  })
}

# --- ECS Task Role ---

resource "aws_iam_role" "ecs_task" {
  name = "next-voters-${var.environment}-ecs-task"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "ecs_task_sqs" {
  name = "SqsAccess"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage", "sqs:GetQueueUrl"]
      Resource = [aws_sqs_queue.report_ready.arn, aws_sqs_queue.pipeline_dlq.arn]
    }]
  })
}

# --- Dispatcher Lambda Role ---

resource "aws_iam_role" "dispatcher_lambda" {
  name = "next-voters-${var.environment}-dispatcher-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "dispatcher_lambda_access" {
  name = "DispatcherAccess"
  role = aws_iam_role.dispatcher_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecs:RunTask"
        Resource = "arn:aws:ecs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:task-definition/next-voters-${var.environment}-pipeline:*"
        Condition = {
          ArnEquals = { "ecs:cluster" = aws_ecs_cluster.main.arn }
        }
      },
      {
        # DescribeTaskDefinition does not support resource-level permissions.
        Effect   = "Allow"
        Action   = "ecs:DescribeTaskDefinition"
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = [aws_iam_role.ecs_task_execution.arn, aws_iam_role.ecs_task.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.dispatcher_lambda.arn}:*"
      }
    ]
  })
}

# --- Email Lambda Role ---

resource "aws_iam_role" "email_lambda" {
  name = "next-voters-${var.environment}-email-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "email_lambda_access" {
  name = "EmailAccess"
  role = aws_iam_role.email_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.report_ready.arn
      },
      # Mailgun sends go out over HTTPS (no AWS send permission). The Lambda only
      # needs to read its secrets from SSM. Scoped to its three parameters;
      # kms:Decrypt is gated to SSM-originated calls.
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = [
          aws_ssm_parameter.mailgun_api_key.arn,
          aws_ssm_parameter.supabase_url.arn,
          aws_ssm_parameter.supabase_key.arn,
        ]
      },
      {
        Effect    = "Allow"
        Action    = "kms:Decrypt"
        Resource  = "*"
        Condition = { StringEquals = { "kms:ViaService" = local.ssm_via_service_kms } }
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.email_lambda.arn}:*"
      }
    ]
  })
}

# --- Worker Lambda Role ---

resource "aws_iam_role" "worker_lambda" {
  name = "next-voters-${var.environment}-worker-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "worker_lambda_access" {
  name = "WorkerAccess"
  role = aws_iam_role.worker_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.worker_jobs.arn
      },
      # Reads Supabase credentials from SSM at cold start. Scoped to the two
      # Supabase parameters; kms:Decrypt is gated to SSM-originated calls.
      {
        Effect = "Allow"
        Action = ["ssm:GetParameter", "ssm:GetParameters"]
        Resource = [
          aws_ssm_parameter.supabase_url.arn,
          aws_ssm_parameter.supabase_key.arn,
        ]
      },
      {
        Effect    = "Allow"
        Action    = "kms:Decrypt"
        Resource  = "*"
        Condition = { StringEquals = { "kms:ViaService" = local.ssm_via_service_kms } }
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.worker_lambda.arn}:*"
      }
    ]
  })
}

# --- GitHub Actions OIDC ---

resource "aws_iam_openid_connect_provider" "github_actions" {
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_actions" {
  name = "next-voters-${var.environment}-github-actions"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github_actions.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/${var.github_repo}:*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_actions_cicd" {
  name = "CiCdAccess"
  role = aws_iam_role.github_actions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # GetAuthorizationToken is account-level and cannot be resource-scoped.
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:BatchCheckLayerAvailability",
          "ecr:CompleteLayerUpload",
          "ecr:GetDownloadUrlForLayer",
          "ecr:InitiateLayerUpload",
          "ecr:PutImage",
          "ecr:UploadLayerPart"
        ]
        Resource = [
          aws_ecr_repository.pipeline.arn,
          aws_ecr_repository.dispatcher.arn,
          aws_ecr_repository.email.arn,
          aws_ecr_repository.worker.arn,
        ]
      },
      {
        # Register/DescribeTaskDefinition do not support resource-level permissions.
        Effect   = "Allow"
        Action   = ["ecs:DescribeTaskDefinition", "ecs:RegisterTaskDefinition"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = [aws_iam_role.ecs_task_execution.arn, aws_iam_role.ecs_task.arn]
      },
      {
        # Lets CI roll the worker Lambda to a freshly pushed image. Scoped to
        # the worker function; GetFunctionConfiguration backs the
        # `aws lambda wait function-updated` poll after update-function-code.
        Effect   = "Allow"
        Action   = ["lambda:UpdateFunctionCode", "lambda:GetFunction", "lambda:GetFunctionConfiguration"]
        Resource = aws_lambda_function.worker.arn
      }
    ]
  })
}

# --- EventBridge Scheduler Role (prod only) ---

resource "aws_iam_role" "eventbridge_scheduler" {
  count = var.environment == "production" ? 1 : 0
  name  = "next-voters-${var.environment}-eventbridge-scheduler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "eventbridge_invoke_dispatcher" {
  count = var.environment == "production" ? 1 : 0
  name  = "InvokeDispatcher"
  role  = aws_iam_role.eventbridge_scheduler[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.dispatcher.arn
    }]
  })
}
