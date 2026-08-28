data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "phase2_integration" {
  bucket = "${local.name_prefix}-${data.aws_caller_identity.current.account_id}-phase2-test"
}

resource "aws_s3_bucket_public_access_block" "phase2_integration" {
  bucket                  = aws_s3_bucket.phase2_integration.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "phase2_integration" {
  bucket = aws_s3_bucket.phase2_integration.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
