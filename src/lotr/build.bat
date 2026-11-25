@echo off
rem 引数なし: 配布版 ..\build\dinput8.dll ／ build.bat test: 試験版 ..\build\test\dinput8.dll（配布しない）
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d "%~dp0"
set O=..\build\release
set OUT=..\build\dinput8.dll
set DEF=
set EXTRA=
if "%1"=="test" (
  set O=..\build\test
  set OUT=..\build\test\dinput8.dll
  set DEF=/DLOTRJP_TEST
  set EXTRA=testio.c
)
if not exist %O% mkdir %O%
if exist lotrjp.rc rc /nologo /fo %O%\lotrjp.res lotrjp.rc || exit /b 1
set RES=
if exist %O%\lotrjp.res set RES=%O%\lotrjp.res
cl /nologo /utf-8 /O2 /MT /W3 /LD /D_CRT_SECURE_NO_WARNINGS %DEF% /Fo%O%\ proxy.c lotrjp.c dat.c %EXTRA% %RES% /Fe%OUT% /link /DEF:dinput8.def kernel32.lib user32.lib gdi32.lib cabinet.lib || exit /b 1
