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
docker build \
  --platform linux/arm64 \
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

echo ""
echo "✅  Deploy complete: ${ECR_URI}"
echo "    Lambda function '${LAMBDA_FUNCTION_NAME}' updated."
