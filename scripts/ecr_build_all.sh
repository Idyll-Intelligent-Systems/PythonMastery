#!/usr/bin/env bash
set -euo pipefail

# Build and push all service images to ECR
# Usage:
#   ./scripts/ecr_build_all.sh [region] [account_id] [tag]
# Defaults: region=eu-north-1, account=879584802968, tag=latest

REGION=${1:-eu-north-1}
ACCOUNT=${2:-879584802968}
TAG=${3:-latest}
ECR_URL="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

login() {
  aws ecr get-login-password --region "${REGION}" | docker login --username AWS --password-stdin "${ECR_URL}"
}

build_push() {
  local srv_path="$1"; shift
  local repo="$1"; shift
  local tag="$1"; shift
  echo "[${repo}] Building at ${srv_path} ..."
  docker build -t "${repo}:${tag}" "${srv_path}"
  docker tag "${repo}:${tag}" "${ECR_URL}/${repo}:${tag}"
  echo "[${repo}] Pushing ${ECR_URL}/${repo}:${tag} ..."
  docker push "${ECR_URL}/${repo}:${tag}"
}

main(){
  login
  # Game (gateway/ui)
  build_push "VEZEPyUniQVerse" "veze/uniqverse" "${TAG}"
  # Game runtime service
  build_push "VEZEPyGame" "veze/game" "${TAG}"
  # Email service
  build_push "VEZEPyEmail" "veze/email" "${TAG}"
}

main "$@"
