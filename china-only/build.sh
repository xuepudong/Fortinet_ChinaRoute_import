#!/usr/bin/env bash
# 构建并推送多架构镜像（linux/amd64 + linux/arm64）到 Docker Hub
#
# 用法:
#   ./build.sh <dockerhub-用户名>/<镜像名> [标签]
# 示例:
#   docker login
#   ./build.sh youruser/fortigate-cn-updater v1.0.0
#
# 只想本地验证不推送:
#   PUSH=0 ./build.sh youruser/fortigate-cn-updater

set -euo pipefail

IMAGE="${1:?用法: ./build.sh <user>/<image> [tag]}"
TAG="${2:-latest}"
PUSH="${PUSH:-1}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
VCS_REF="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

# 多架构构建需要 docker-container driver 的 builder
BUILDER=fortigate-cn-builder
if ! docker buildx inspect "$BUILDER" >/dev/null 2>&1; then
  echo ">> 创建 builder: $BUILDER"
  docker buildx create --name "$BUILDER" --driver docker-container --bootstrap
fi

ARGS=(
  buildx build
  --builder "$BUILDER"
  --platform "$PLATFORMS"
  --build-arg "VERSION=$TAG"
  --build-arg "VCS_REF=$VCS_REF"
  -t "$IMAGE:$TAG"
)

# 语义化版本额外打 latest
if [ "$TAG" != "latest" ]; then
  ARGS+=(-t "$IMAGE:latest")
fi

if [ "$PUSH" = "1" ]; then
  ARGS+=(--push)
  echo ">> 构建并推送 $IMAGE:$TAG ($PLATFORMS)"
else
  # 多平台镜像无法 --load 进本地 docker，仅做构建校验
  echo ">> 仅构建校验（不推送、不载入本地）$PLATFORMS"
fi

docker "${ARGS[@]}" .

if [ "$PUSH" = "1" ]; then
  echo ">> 完成，验证 manifest:"
  docker buildx imagetools inspect "$IMAGE:$TAG"
fi
