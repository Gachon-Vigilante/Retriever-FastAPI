@echo off
setlocal

:: 이 스크립트는 워커/비트/플라워 서비스만 재빌드하고
:: 모든 서비스를 --no-build 옵션으로 시작합니다.

echo [1/2] Rebuilding worker, beat, and flower services...

:: 재빌드할 서비스 목록을 지정하여 build 명령어 실행
docker-compose build ^
  worker-search ^
  worker-crawl ^
  worker-analyze ^
  worker-telegram ^
  worker-poll ^
  beat ^
  flower

:: build 명령어의 성공 여부 확인
if %errorlevel% neq 0 (
  echo.
  echo ERROR: Docker build failed. Aborting script.
  endlocal
  exit /b %errorlevel%
)

echo.
echo [2/2] Build complete. Starting all services (detached)...

:: --no-build 플래그로 빌드 없이 모든 서비스 시작
docker-compose up --no-build -d

echo.
echo All services are starting up.

:: =======================================================
:: ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
::
::              사용자 설정 (여기를 수정하세요)
::
:: =======================================================

:: 1. docker-compose.yml 파일이 있는 프로젝트 경로
set "PROJECT_DIR=.\"

:: 2. 로그를 볼 서비스 5개 (V1: docker-compose 기준)
set "LOG_COMMAND_1=docker-compose logs -f worker-search"
set "LOG_COMMAND_2=docker-compose logs -f worker-crawl"
set "LOG_COMMAND_3=docker-compose logs -f worker-analyze"
set "LOG_COMMAND_4=docker-compose logs -f worker-poll"
set "LOG_COMMAND_5=docker-compose logs -f worker-telegram"
set "LOG_COMMAND_6=docker-compose logs -f beat"
set "LOG_COMMAND_7=docker-compose logs -f fastapi"

:: (참고: Docker Compose V2 (docker compose) 사용 시)
:: (아래 5줄의 주석을 풀고, 위 5줄을 주석 처리하세요)
:: set "LOG_COMMAND_1=docker compose logs -f worker-search"
:: set "LOG_COMMAND_2=docker compose logs -f worker-crawl"
:: set "LOG_COMMAND_3=docker compose logs -f worker-analyze"
:: set "LOG_COMMAND_4=docker compose logs -f worker-telegram"
:: set "LOG_COMMAND_5=docker compose logs -f beat"

:: =======================================================
:: ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
:: =======================================================

echo Starting 7 log tabs in %PROJECT_DIR%...

:: wt 명령어 실행
:: -d : 시작 디렉토리 지정
:: --title : 탭 제목 지정
:: cmd /k : 지정된 명령을 실행하고, 종료된 후에도 cmd 세션을 유지 (탭이 닫히지 않음)
:: ^ : 배치 파일에서 긴 명령어를 여러 줄로 나누기 위한 줄바꿈 문자

wt -d "%PROJECT_DIR%" --title "Log-search" cmd /k "%LOG_COMMAND_1%" ; ^
   new-tab -d "%PROJECT_DIR%" --title "Log-crawl" cmd /k "%LOG_COMMAND_2%" ; ^
   new-tab -d "%PROJECT_DIR%" --title "Log-analyze" cmd /k "%LOG_COMMAND_3%" ; ^
   new-tab -d "%PROJECT_DIR%" --title "Log-poll" cmd /k "%LOG_COMMAND_4%" ; ^
   new-tab -d "%PROJECT_DIR%" --title "Log-telegram" cmd /k "%LOG_COMMAND_5%" ; ^
   new-tab -d "%PROJECT_DIR%" --title "Log-beat" cmd /k "%LOG_COMMAND_6%" ; ^
   new-tab -d "%PROJECT_DIR%" --title "Log-fastapi" cmd /k "%LOG_COMMAND_7%"

echo Done.
endlocal
