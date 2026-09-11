# Existing IAM user ARN that is allowed to assume the operator role.
variable "operator_principal_arn" {
  type = string

  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:user/.+$", var.operator_principal_arn))
    error_message = "operator_principal_arn must be an IAM user ARN."
  }
}

# Operator role used only for scenario setup and cleanup.
resource "aws_iam_role" "scenario_01_operator" {
  name                 = "ops-maintenance"
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        AWS = var.operator_principal_arn
      }
    }]
  })
}

# IAM user reused across Scenario 01 runs.
# The access key itself will be created by the attack script.
resource "aws_iam_user" "scenario_01_persistence_target" {
  name          = "inventory-service"
  force_destroy = false
}

# Credentials belonging to this user can call ListUsers.
resource "aws_iam_user_policy" "scenario_01_target_permissions" {
  name = "inventory-service-permissions"
  user = aws_iam_user.scenario_01_persistence_target.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "iam:ListUsers"
      Resource = "*"
    }]
  })
}

# Role whose temporary credentials represent the compromised session.
resource "aws_iam_role" "scenario_01_attacker" {
  name                 = "ops-automation"
  max_session_duration = 3600

  # The operator role prepares this session during setup.
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = "sts:AssumeRole"
      Principal = {
        AWS = aws_iam_role.scenario_01_operator.arn
      }
    }]
  })
}

# This role can create an access key for inventory-service.
# It intentionally does not have ListUsers permission.
resource "aws_iam_role_policy" "scenario_01_attacker_permissions" {
  name = "ops-automation-permissions"
  role = aws_iam_role.scenario_01_attacker.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "iam:CreateAccessKey"
      Resource = aws_iam_user.scenario_01_persistence_target.arn
    }]
  })
}

# Permissions required only for setup and cleanup.
resource "aws_iam_role_policy" "scenario_01_operator_permissions" {
  name = "ops-maintenance-permissions"
  role = aws_iam_role.scenario_01_operator.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "sts:AssumeRole"
        Resource = aws_iam_role.scenario_01_attacker.arn
      },
      {
        Effect = "Allow"
        Action = [
          "iam:GetUser",
          "iam:ListAccessKeys",
          "iam:DeleteAccessKey"
        ]
        Resource = aws_iam_user.scenario_01_persistence_target.arn
      }
    ]
  })
}

# Values used later by the Python scripts.
output "scenario_01_operator_role_arn" {
  value = aws_iam_role.scenario_01_operator.arn
}

output "scenario_01_attacker_role_arn" {
  value = aws_iam_role.scenario_01_attacker.arn
}

output "scenario_01_target_user_name" {
  value = aws_iam_user.scenario_01_persistence_target.name
}