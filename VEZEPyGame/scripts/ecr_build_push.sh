#!/usr/bin/env bash
set -euo pipefail

# AWS ECR push helper for VEZEPyUniQVerse / VEZEPyGame
# Prerequisites:
# - AWS CLI v2 installed and configured with permissions to push to the target ECR repo
# - Docker installed and running
# - Logged into AWS account that owns the repo
#
# Usage:
#   ./scripts/ecr_build_push.sh [region] [account_id] [repo_name] [image_tag]
# Defaults:
#   region=eu-north-1
#   account_id=879584802968
#   repo_name=veze/game
#   image_tag=latest

REGION=${1:-eu-north-1}
ACCOUNT=${2:-879584802968}
REPO=${3:-veze/game}
TAG=${4:-latest}

ECR_URL="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
IMAGE_LOCAL="${REPO}:${TAG}"
IMAGE_REMOTE="${ECR_URL}/${REPO}:${TAG}"

echo "Logging into ECR ${ECR_URL} ..."
aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_URL}"

echo "Building image ${IMAGE_LOCAL} ..."
docker build -t "${IMAGE_LOCAL}" "$(dirname "$0")/.."

echo "Tagging ${IMAGE_LOCAL} as ${IMAGE_REMOTE} ..."
docker tag "${IMAGE_LOCAL}" "${IMAGE_REMOTE}"

echo "Pushing ${IMAGE_REMOTE} ..."
docker push "${IMAGE_REMOTE}"

echo "Done."
