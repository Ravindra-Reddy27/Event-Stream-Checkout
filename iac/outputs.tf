output "api_endpoint" {
  description = "API Gateway Endpoint"
  value       = "${aws_apigatewayv2_api.api_gateway.api_endpoint}/api/orders"
}

output "sqs_queue_url" {
  description = "SQS Queue URL"
  value       = aws_sqs_queue.order_created_queue.id
}

output "db_endpoint" {
  description = "Database Endpoint"
  value       = aws_db_instance.default.address
}

output "db_password" {
  description = "Database Password"
  value       = random_password.db_password.result
  sensitive   = true
}