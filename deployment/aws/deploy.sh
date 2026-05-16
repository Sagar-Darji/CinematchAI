#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# deployment/aws/deploy.sh
# Builds the Lambda container image, pushes to ECR, and updates the function.
#
# Usage:
#   export AWS_REGION=us-east-1
#   export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
#   export LAMBDA_FUNCTION_NAME=cinematch-api
#   ./deployment/aws/deploy.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:?Set AWS_ACCOUNT_ID}"
LAMBDA_FUNCTION_NAME="${LAMBDA_FUNCTION_NAME:-cinematch-api}"
ECR_REPO="${LAMBDA_FUNCTION_NAME}"
IMAGE_TAG="latest"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}"

echo "==> Logging in to ECR ..."
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin \
  "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "==> Creating ECR repo (idempotent) ..."
aws ecr describe-repositories --repository-names "${ECR_REPO}" --region "${AWS_REGION}" \
  >/dev/null 2>&1 || \
  aws ecr create-repository --repository-name "${ECR_REPO}" --region "${AWS_REGION}"

echo "==> Building Lambda container image (linux/arm64) ..."
docker buildx build \
  --platform linux/arm64 \
  --provenance=false \
  --sbom=false \
  --load \
  -f Dockerfile.lambda \
  -t "${ECR_URI}" \
  .

echo "==> Pushing image to ECR ..."
docker push "${ECR_URI}"

echo "==> Updating Lambda function code ..."
aws lambda update-function-code \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --image-uri "${ECR_URI}" \
  --region "${AWS_REGION}"

echo "==> Waiting for update to complete ..."
aws lambda wait function-updated \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}"

# Cost-runaway safeguards. Re-apply on every deploy so the function
# cannot drift back to AWS defaults (2 async retries + 6h event age),
# which let a single buggy invocation replay for hours and amplify
# self-invoke chains into runaway spend.
echo "==> Applying async-invoke safeguards (retries=0, max event age=300s) ..."
aws lambda put-function-event-invoke-config \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --maximum-retry-attempts 0 \
  --maximum-event-age-in-seconds 300 \
  >/dev/null

# Reserved concurrency cap — best-effort. Will fail if the account's
# unreserved pool would drop below AWS's 10-execution minimum (common
# on new accounts with the default 10 ConcurrentExecutions quota). In
# that case the account-level cap already bounds blast radius.
echo "==> Attempting reserved-concurrency cap (best-effort) ..."
aws lambda put-function-concurrency \
  --function-name "${LAMBDA_FUNCTION_NAME}" \
  --region "${AWS_REGION}" \
  --reserved-concurrent-executions 10 \
  >/dev/null 2>&1 || echo "   (skipped — account quota too low to reserve)"

echo ""
echo "✅  Deploy complete: ${ECR_URI}"
echo "    Lambda function '${LAMBDA_FUNCTION_NAME}' updated."
