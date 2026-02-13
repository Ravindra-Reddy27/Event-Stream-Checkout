provider "aws" {
  region = var.aws_region
}

# ==============================================================================
# 1. Dead Letter Queue (DLQ)
# ==============================================================================
resource "aws_sqs_queue" "order_dlq" {
  name = "${var.project_name}-order-dlq"
}

# ==============================================================================
# 2. SQS Queue (Order Created) - NOW WITH DLQ
# ==============================================================================
resource "aws_sqs_queue" "order_created_queue" {
  name                      = "${var.project_name}-order-created-queue"
  message_retention_seconds = 86400
  visibility_timeout_seconds = 30

  # Redrive Policy links this queue to the DLQ
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.order_dlq.arn
    maxReceiveCount     = 3 # Move to DLQ after 3 failed attempts
  })
}

# ==============================================================================
# 2. Lambda Function (Order Ingest) 
# ==============================================================================

# ZIP the Python code automatically
data "archive_file" "ingest_lambda_zip" {
  type        = "zip"
  source_dir  = "../src/ingest_order"
  output_path = "${path.module}/ingest_order.zip"
}

# IAM Role: Allows Lambda to run
resource "aws_iam_role" "ingest_lambda_role" {
  name = "${var.project_name}-ingest-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# IAM Policy: Allow Logging and SQS Sending
resource "aws_iam_role_policy" "ingest_lambda_policy" {
  name = "${var.project_name}-ingest-policy"
  role = aws_iam_role.ingest_lambda_role.id

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
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.order_created_queue.arn
      }
    ]
  })
}

# The Lambda Function Resource
resource "aws_lambda_function" "ingest_order" {
  filename         = data.archive_file.ingest_lambda_zip.output_path
  function_name    = "${var.project_name}-ingest-order"
  role             = aws_iam_role.ingest_lambda_role.arn
  handler          = "app.lambda_handler"
  runtime          = "python3.9"
  source_code_hash = data.archive_file.ingest_lambda_zip.output_base64sha256

  environment {
    variables = {
      ORDER_QUEUE_URL = aws_sqs_queue.order_created_queue.id
    }
  }
}

# ==============================================================================
# 3. API Gateway (HTTP API) 
# ==============================================================================
resource "aws_apigatewayv2_api" "api_gateway" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.api_gateway.id
  name        = "$default"
  auto_deploy = true
}

# Integration: Connect API Gateway to Lambda
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id           = aws_apigatewayv2_api.api_gateway.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.ingest_order.invoke_arn
  payload_format_version = "2.0"
}

# Route: POST /api/orders
resource "aws_apigatewayv2_route" "post_orders" {
  api_id    = aws_apigatewayv2_api.api_gateway.id
  route_key = "POST /api/orders"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# Permission: Allow API Gateway to invoke the Lambda
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest_order.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api_gateway.execution_arn}/*/*/api/orders"
}