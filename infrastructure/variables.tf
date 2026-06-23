variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be staging or production."
  }
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "public_subnet_a_cidr" {
  type    = string
  default = "10.0.1.0/24"
}

variable "public_subnet_b_cidr" {
  type    = string
  default = "10.0.2.0/24"
}

variable "ecs_task_cpu" {
  type    = string
  default = "512"
}

variable "ecs_task_memory" {
  type    = string
  default = "1024"
}

variable "pipeline_image_tag" {
  type    = string
  default = "latest"
}

variable "dispatcher_image_tag" {
  type    = string
  default = "latest"
}

variable "email_image_tag" {
  type    = string
  default = "latest"
}

variable "schedule_expression" {
  type        = string
  default     = "cron(0 9 ? * MON *)"
  description = "Weekly cron for EventBridge Scheduler (prod only)."
}

variable "mailgun_domain" {
  type        = string
  description = "Mailgun sending domain (the domain configured in Mailgun, e.g. mg.example.org)."
}

variable "mailgun_sender" {
  type        = string
  description = "From header for outbound mail, e.g. 'Next Voters <noreply@mg.example.org>'."
}

variable "mailgun_base_url" {
  type        = string
  default     = "https://api.mailgun.net"
  description = "Mailgun API base URL. Use https://api.eu.mailgun.net for EU-region accounts."
}

variable "share_base_url" {
  type        = string
  description = "Public base URL the Email Lambda uses to render report share links (no trailing slash)."
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "dlq_message_retention_seconds" {
  type        = number
  default     = 1209600
  description = "14 days."
}

variable "report_queue_visibility_timeout" {
  type        = number
  default     = 300
  description = "Aligned with Email Lambda timeout."
}

variable "email_dlq_max_receive_count" {
  type    = number
  default = 3
}

variable "github_org" {
  type    = string
  default = "Next-Voters"
}

variable "github_repo" {
  type    = string
  default = "Agent"
}
