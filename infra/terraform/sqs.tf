# 1. Create an SQS queue to buffer notifications for new CloudTrail log objects.
resource "aws_sqs_queue" "cloudtrail_ingestion" {

  name                       = "agentic-soc-cloudtrail-ingestion"
  message_retention_seconds  = 1209600 # Retain messages for up to 14 days.
  visibility_timeout_seconds = 300     # After a consumer reads a message, hide it from other consumers for up to 5 minutes while processing. 
  # Delete it immediately on success, otherwise it becomes visible again for retry. 
  # Good-practice SQS setting: mainly useful for multiple consumers/retries; not critical in our current single Elastic-Agent (~single consumer) setup.

  tags = {
    Project = "Agentic-SoC"
    Purpose = "CloudTrail-Elastic-Ingestion"
  }
}


# 2. Define the policy that allows S3 to send notifications to this SQS queue.
data "aws_iam_policy_document" "cloudtrail_sqs_policy" {

  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions = [
      "sqs:SendMessage"
    ]

    # Allow messages to be sent only to this SQS queue.
    resources = [
      aws_sqs_queue.cloudtrail_ingestion.arn
    ]

    # Allow notifications only from our CloudTrail S3 bucket.
    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [aws_s3_bucket.cloudtrail_logs.arn]
    }
  }
}


# 3. Attach the policy defined above to the actual SQS queue.
resource "aws_sqs_queue_policy" "cloudtrail_ingestion" {
  queue_url = aws_sqs_queue.cloudtrail_ingestion.id
  policy    = data.aws_iam_policy_document.cloudtrail_sqs_policy.json
}


# 4. Send an SQS notification whenever a new CloudTrail log object is created in S3.
resource "aws_s3_bucket_notification" "cloudtrail_to_sqs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  queue {
    queue_arn = aws_sqs_queue.cloudtrail_ingestion.arn

    # Trigger when a new S3 object is created.
    events = ["s3:ObjectCreated:*"]

    # Only watch the CloudTrail event-log path, not CloudTrail-Digest.
    filter_prefix = "AWSLogs/${data.aws_caller_identity.current.account_id}/CloudTrail/"
  }

  # Ensure S3 has permission to send messages before configuring the notification.
  depends_on = [
    aws_sqs_queue_policy.cloudtrail_ingestion
  ]
}


# 5. Output the SQS URL for later Elastic configuration.
output "cloudtrail_sqs_url" {
  value = aws_sqs_queue.cloudtrail_ingestion.url
}


# 6. Output the SQS ARN for AWS resource references and verification.
output "cloudtrail_sqs_arn" {
  value = aws_sqs_queue.cloudtrail_ingestion.arn
}


