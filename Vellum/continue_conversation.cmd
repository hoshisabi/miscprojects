@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo === Ancient Nations relay: Vellum directory ===
echo.

if not exist "WREN_REPLY.md" (
  echo No WREN_REPLY.md found in:
  echo   %cd%
  echo.
  echo Ask Wren ^(or proxy^) to create WREN_REPLY.md here, then run this script again.
  goto :open_scratch
)

echo ----- Contents of WREN_REPLY.md -----
type "WREN_REPLY.md"
echo ----- end -----
echo.

set "STAMP="
for /f "delims=" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-ddTHH:mm:ss"') do set "STAMP=%%i"

(
  echo.
  echo ---
  echo ## Wren ^(!STAMP!^)
  echo.
  type "WREN_REPLY.md"
) >> "CONVERSATION.md"

echo Appended WREN_REPLY.md to CONVERSATION.md
echo.

:open_scratch
if not exist "VELLUM_SCRATCH.md" (
  > "VELLUM_SCRATCH.md" echo # Vellum - next message
  >> "VELLUM_SCRATCH.md" echo.
  >> "VELLUM_SCRATCH.md" echo Draft your follow-up for Wren or the human; copy into ANCIENT_NATIONS_REVIEW.md or CONVERSATION.md as you prefer.
)

start "" notepad "VELLUM_SCRATCH.md"

echo Opened VELLUM_SCRATCH.md in Notepad.
echo Tip: after you finish a reply cycle, you can clear or archive WREN_REPLY.md so the next merge is obvious.
echo.
pause
