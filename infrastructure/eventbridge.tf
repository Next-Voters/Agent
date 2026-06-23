resource "aws_scheduler_schedule" "weekly" {
  count = var.environment == "production" ? 1 : 0
  name  = "next-voters-${var.environment}-weekly"

  schedule_expression = var.schedule_expression

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.dispatcher.arn
    role_arn = aws_iam_role.eventbridge_scheduler[0].arn
  }
}
