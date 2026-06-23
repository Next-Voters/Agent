output "vpc_id" {
  value = aws_vpc.main.id
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "ecs_task_definition_arn" {
  value = aws_ecs_task_definition.pipeline.arn
}

output "pipeline_ecr_repo_uri" {
  value = aws_ecr_repository.pipeline.repository_url
}

output "dispatcher_ecr_repo_uri" {
  value = aws_ecr_repository.dispatcher.repository_url
}

output "email_ecr_repo_uri" {
  value = aws_ecr_repository.email.repository_url
}

output "report_queue_url" {
  value = aws_sqs_queue.report_ready.url
}

output "pipeline_dlq_url" {
  value = aws_sqs_queue.pipeline_dlq.url
}

output "dispatcher_lambda_arn" {
  value = aws_lambda_function.dispatcher.arn
}

output "email_lambda_arn" {
  value = aws_lambda_function.email.arn
}

output "github_actions_role_arn" {
  value = aws_iam_role.github_actions.arn
}
