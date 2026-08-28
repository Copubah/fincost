data "archive_file" "scanner" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/lambda"
  output_path = "${path.module}/lambda_package.zip"
}

resource "aws_lambda_function" "scanner" {
  function_name    = "${local.name_prefix}-scanner"
  description      = "Safely analyzes S3 storage for FinOps recommendations."
  filename         = data.archive_file.scanner.output_path
  source_code_hash = data.archive_file.scanner.output_base64sha256
  role             = aws_iam_role.scanner.arn
  handler          = "scanner.lambda_handler"
  runtime          = "python3.12"
  timeout          = var.lambda_timeout_seconds
  memory_size      = var.lambda_memory_mb

  environment {
    variables = {
      ANALYSIS_TABLE_NAME = aws_dynamodb_table.analysis_results.name
      LOG_LEVEL           = "INFO"
      LARGE_OBJECT_MB     = tostring(var.large_object_mb)
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.scanner,
    aws_iam_role_policy.scanner,
  ]
}
