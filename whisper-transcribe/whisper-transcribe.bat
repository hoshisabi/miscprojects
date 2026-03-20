@echo off
if not defined GITHUB_ROOT set "GITHUB_ROOT=C:\github"
set "PROJECT_ROOT=%GITHUB_ROOT%\miscprojects\whisper-transcribe"

if not exist "%PROJECT_ROOT%\pyproject.toml" (
    echo Error: Cannot find project at %PROJECT_ROOT% 1>&2
    echo Set GITHUB_ROOT environment variable if your github directory is elsewhere. 1>&2
    exit /b 1
)

uv run --project "%PROJECT_ROOT%" python "%PROJECT_ROOT%\main.py" %*
exit /b %ERRORLEVEL%
