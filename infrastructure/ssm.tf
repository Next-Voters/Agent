# --- SSM Parameter Store: application secrets ---
#
# Secrets are NEVER stored in this repo or in *.tfvars. Terraform creates each
# parameter as a SecureString shell with a placeholder value, then ignores the
# value forever (lifecycle.ignore_changes). After the first `terraform apply`,
# set the real values out-of-band and Terraform will not revert them, e.g.:
#
#   aws ssm put-parameter --overwrite --type SecureString \
#     --name /next-voters/staging/OPENAI_API_KEY --value "sk-..."
#
# Consumers read these at runtime:
#   - ECS pipeline task  -> injected as env vars via the container `secrets`
#                           block (fetched by the ECS task EXECUTION role).
#   - Email Lambda       -> fetched at cold start via ssm:GetParameter using the
#                           *_PARAM env vars (the Lambda role grants read access).
#
# IMPORTANT: `ignore_changes = [value]` stops Terraform from reverting the
# placeholder, but it does NOT keep secrets out of state — on every refresh
# Terraform reads the decrypted SecureString value back into terraform.tfstate.
# So once real values are set, state contains plaintext secrets: enable the
# encrypted, locked remote backend (the commented block in main.tf) BEFORE
# setting real values, and never commit *.tfstate (enforced by .gitignore).

locals {
  ssm_prefix          = "/next-voters/${var.environment}"
  ssm_placeholder     = "PLACEHOLDER_SET_OUT_OF_BAND"
  ssm_via_service_kms = "ssm.${var.aws_region}.amazonaws.com"
}

# Pipeline (ECS) secrets
resource "aws_ssm_parameter" "openai_api_key" {
  name  = "${local.ssm_prefix}/OPENAI_API_KEY"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "tavily_api_key" {
  name  = "${local.ssm_prefix}/TAVILY_API_KEY"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "together_api_key" {
  name  = "${local.ssm_prefix}/TOGETHER_API_KEY"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }
}

# Shared by the pipeline (ECS) and the Email Lambda (reads the reports table)
resource "aws_ssm_parameter" "supabase_url" {
  name  = "${local.ssm_prefix}/SUPABASE_URL"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "supabase_key" {
  name  = "${local.ssm_prefix}/SUPABASE_KEY"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }
}

# Email Lambda secret (Mailgun)
resource "aws_ssm_parameter" "mailgun_api_key" {
  name  = "${local.ssm_prefix}/MAILGUN_API_KEY"
  type  = "SecureString"
  value = local.ssm_placeholder

  lifecycle {
    ignore_changes = [value]
  }
}
