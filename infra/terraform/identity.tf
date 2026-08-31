data "aws_caller_identity" "current" {}

output "terraform_aws_identity" {
  value = data.aws_caller_identity.current.arn
}