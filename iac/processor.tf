# ==============================================================================
# 1. SQS Queue (Order Processed - Output)
# ==============================================================================
resource "aws_sqs_queue" "order_processed_queue" {
  name                      = "${var.project_name}-order-processed-queue"
  message_retention_seconds = 86400
  visibility_timeout_seconds = 30
}

# ==============================================================================
# 2. IAM Role & Policy for Processor
# ==============================================================================
resource "aws_iam_role" "processor_role" {
  name = "${var.project_name}-processor-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "processor_policy" {
  name = "${var.project_name}-processor-policy"
  role = aws_iam_role.processor_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Logs
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      # Read from Input Queue (OrderCreated)
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = aws_sqs_queue.order_created_queue.arn
      },
      # Write to Output Queue (OrderProcessed)
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.order_processed_queue.arn
      }
    ]
  })
}

# ==============================================================================
# 3. Lambda Function (Order Processor)
# ==============================================================================
data "archive_file" "processor_zip" {
  type        = "zip"
  source_dir  = "../src/order_processor"
  output_path = "${path.module}/order_processor.zip"
}

resource "aws_lambda_function" "order_processor" {
  filename         = data.archive_file.processor_zip.output_path
  function_name    = "${var.project_name}-order-processor"
  role             = aws_iam_role.processor_role.arn
  handler          = "app.lambda_handler"
  runtime          = "python3.9"
  source_code_hash = data.archive_file.processor_zip.output_base64sha256
  timeout          = 30 

  environment {
    variables = {
      PROCESSED_QUEUE_URL = aws_sqs_queue.order_processed_queue.id
      DB_HOST             = aws_db_instance.default.address
      DB_USER             = "admin"
      DB_PASSWORD         = random_password.db_password.result
      DB_NAME             = "ecommerce"
    }
  }
}

# ==============================================================================
# 4. Trigger: Connect Input Queue to Lambda
# ==============================================================================
resource "aws_lambda_event_source_mapping" "sqs_trigger" {
  event_source_arn = aws_sqs_queue.order_created_queue.arn
  function_name    = aws_lambda_function.order_processor.arn
  batch_size       = 1
  enabled          = true
}