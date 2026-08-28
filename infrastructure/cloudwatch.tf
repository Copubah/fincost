resource "aws_cloudwatch_log_group" "scanner" {
  name              = "/aws/lambda/${local.name_prefix}-scanner"
  retention_in_days = 30
}

resource "aws_cloudwatch_metric_alarm" "scanner_errors" {
  alarm_name          = "${local.name_prefix}-scanner-errors"
  alarm_description   = "The S3 storage optimizer scanner reported an error."
  namespace           = "S3StorageOptimizer"
  metric_name         = "ScanErrors"
  statistic           = "Sum"
  period              = 86400
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
}

