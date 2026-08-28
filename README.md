# S3 Cost Optimization & Storage Lifecycle Analyzer

A serverless FinOps portfolio project that will safely analyze Amazon S3
storage, identify lifecycle and security gaps, and estimate optimization
opportunities. It never deletes or transitions production data automatically.

## Phase 1

Phase 1 provisions the secure serverless foundation: a scheduled Lambda,
encrypted DynamoDB analysis table, constrained IAM role, CloudWatch logs and a
scanner-error alarm. The Lambda performs a safe readiness invocation and emits
scan metrics; S3 object discovery is deliberately introduced in Phase 2.

## Prerequisites

- Python 3.12 (3.9+ is sufficient for local unit tests)
- Terraform 1.6+
- AWS CLI configured with credentials for the intended account

## Local verification

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest backend/tests -q

cd infrastructure
terraform init
terraform fmt -check
terraform validate
terraform plan -var-file=terraform.tfvars
```

Copy `infrastructure/terraform.tfvars.example` to
`infrastructure/terraform.tfvars` and set the target region/environment. Do
not commit the resulting `.tfvars` file. AWS credentials must be supplied via
the AWS CLI/profile/environment, never source files.

## Deployment and smoke test

```bash
cd infrastructure
terraform apply -var-file=terraform.tfvars
aws lambda invoke \
  --function-name "$(terraform output -raw scanner_function_name)" \
  --payload '{}' response.json
cat response.json
aws logs tail "$(terraform output -raw scanner_log_group_name)" --since 10m
```

The response should have `statusCode: 200` and `status: initialized`; the log
stream should contain `scan_started` and `scan_completed` records.

## Cost and security posture

This foundation uses Lambda, EventBridge, CloudWatch, and DynamoDB on-demand.
Cost is normally negligible for low-volume portfolio scans, but CloudWatch log
retention and AWS regional pricing still apply. IAM excludes write actions for
S3 and does not use `AdministratorAccess`; the table has encryption and point-
in-time recovery enabled.

## Project roadmap

1. Foundation and safe scanner (current)
2. Bucket discovery and object analysis
3. Governance, versioning, multipart, and duplicate analysis
4. Cost Explorer and recommendation engine
5. Persistence and observability expansion
6. API, dashboard, delivery automation, and full documentation

