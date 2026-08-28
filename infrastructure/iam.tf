data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scanner" {
  name               = "${local.name_prefix}-scanner"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

data "aws_iam_policy_document" "scanner" {
  statement {
    sid    = "WriteApplicationLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["${aws_cloudwatch_log_group.scanner.arn}:*"]
  }

  statement {
    sid       = "PublishOptimizerMetrics"
    effect    = "Allow"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["S3StorageOptimizer"]
    }
  }

  # Permissions required by subsequent, read-only analysis phases.
  statement {
    sid    = "DiscoverAndInspectS3"
    effect = "Allow"
    actions = [
      "s3:ListAllMyBuckets",
      "s3:GetBucketLocation",
      "s3:GetBucketEncryption",
      "s3:GetBucketLifecycleConfiguration",
      "s3:GetBucketVersioning",
      "s3:GetBucketPublicAccessBlock",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "InspectBucketContents"
    effect = "Allow"
    actions = [
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:ListBucketVersions",
    ]
    resources = ["arn:aws:s3:::*"]
  }

  statement {
    sid    = "PersistAnalysisResults"
    effect = "Allow"
    actions = [
      "dynamodb:BatchWriteItem",
      "dynamodb:PutItem",
    ]
    resources = [aws_dynamodb_table.analysis_results.arn]
  }
}

resource "aws_iam_role_policy" "scanner" {
  name   = "${local.name_prefix}-scanner-policy"
  role   = aws_iam_role.scanner.id
  policy = data.aws_iam_policy_document.scanner.json
}
