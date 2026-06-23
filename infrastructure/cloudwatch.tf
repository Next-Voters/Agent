resource "aws_cloudwatch_log_group" "ecs_pipeline" {
  name              = "/ecs/next-voters-${var.environment}-pipeline"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "dispatcher_lambda" {
  name              = "/aws/lambda/next-voters-${var.environment}-dispatcher"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "email_lambda" {
  name              = "/aws/lambda/next-voters-${var.environment}-email"
  retention_in_days = var.log_retention_days
}
