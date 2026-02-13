# ==============================================================================
# 1. Notification Lambda Role
# ==============================================================================
resource "aws_iam_role" "notification_role" {
  name = "${var.project_name}-notification-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "notification_policy" {
  name = "${var.project_name}-notification-policy"
  role = aws_iam_role.notification_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.order_processed_queue.arn
      }
    ]
  })
}

# ==============================================================================
# 2. Notification Lambda Function
# ==============================================================================
data "archive_file" "notification_zip" {
  type        = "zip"
  source_dir  = "../src/notification_sender"
  output_path = "${path.module}/notification_sender.zip"
}

resource "aws_lambda_function" "notification_sender" {
  filename         = data.archive_file.notification_zip.output_path
  function_name    = "${var.project_name}-notification-sender"
  role             = aws_iam_role.notification_role.arn
  handler          = "app.lambda_handler"
  runtime          = "python3.9"
  source_code_hash = data.archive_file.notification_zip.output_base64sha256
}

# ==============================================================================
# 3. Trigger: Connect Processed Queue to Lambda
# ==============================================================================
resource "aws_lambda_event_source_mapping" "notification_trigger" {
  event_source_arn = aws_sqs_queue.order_processed_queue.arn
  function_name    = aws_lambda_function.notification_sender.arn
  batch_size       = 1
  enabled          = true
}