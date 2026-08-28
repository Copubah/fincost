resource "aws_cloudwatch_event_rule" "daily_scan" {
  name                = "${local.name_prefix}-daily-scan"
  description         = "Triggers the S3 storage optimizer scanner."
  schedule_expression = var.scan_schedule_expression
}

resource "aws_cloudwatch_event_target" "scanner" {
  rule      = aws_cloudwatch_event_rule.daily_scan.name
  target_id = "scanner"
  arn       = aws_lambda_function.scanner.arn
}

resource "aws_lambda_permission" "eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scanner.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_scan.arn
}

