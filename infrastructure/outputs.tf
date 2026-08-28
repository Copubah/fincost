output "analysis_results_table_name" {
  description = "DynamoDB table used for scan records."
  value       = aws_dynamodb_table.analysis_results.name
}

output "scanner_function_name" {
  description = "Name of the EventBridge-triggered scanner Lambda."
  value       = aws_lambda_function.scanner.function_name
}

output "scanner_log_group_name" {
  description = "CloudWatch log group for scanner execution logs."
  value       = aws_cloudwatch_log_group.scanner.name
}

