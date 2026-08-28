resource "aws_dynamodb_table" "analysis_results" {
  name         = "${local.name_prefix}-analysis"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "scan_id"
  range_key    = "record_key"

  attribute {
    name = "scan_id"
    type = "S"
  }

  attribute {
    name = "record_key"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

