#!/bin/bash

# 이 스크립트는 워커/비트/플라워 서비스만 재빌드하고
# 모든 서비스를 --no-build 옵션으로 시작합니다.

# 명령어 실행 중 오류가 발생하면 즉시 스크립트를 중지합니다.
set -e

echo "[1/2] Rebuilding worker, beat, and flower services..."

# 재빌드할 서비스 목록을 지정하여 build 명령어 실행
docker-compose build \
  worker-search \
  worker-crawl \
  worker-analyze \
  worker-telegram \
  worker-poll \
  beat \
  flower

echo
echo "[2/2] Build complete. Starting all services (detached)..."

# --no-build 플래그로 빌드 없이 모든 서비스 시작
docker-compose up --no-build -d

echo
echo "All services are starting up."
