@echo off
rem build.bat test         : 試験版 ..\build\test\dinput8.dll（共通。差し替えデータは環境変数 LEGOJP_PACK で渡す。配布しない）
rem build.bat <game>       : 配布版 ..\<game>\build\dinput8.dll（..\<game>\build\pack.bin と rc\<game>.rc を入れる）
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
cd /d "%~dp0"
if "%1"=="" exit /b 1
if "%1"=="test" goto test
set O=..\%1\build\obj
set OUT=..\%1\build\dinput8.dll
if not exist %O% mkdir %O%
rc /nologo /fo %O%\legojp.res rc\%1.rc || exit /b 1
cl /nologo /utf-8 /O2 /MT /W3 /LD /D_CRT_SECURE_NO_WARNINGS /Fo%O%\ proxy.c legojp.c dat.c %O%\legojp.res /Fe%OUT% /link /DEF:dinput8.def kernel32.lib user32.lib gdi32.lib cabinet.lib || exit /b 1
exit /b 0
:test
set O=..\build\test
if not exist %O% mkdir %O%
cl /nologo /utf-8 /O2 /MT /W3 /LD /D_CRT_SECURE_NO_WARNINGS /DLEGOJP_TEST /Fo%O%\ proxy.c legojp.c dat.c testio.c /Fe%O%\dinput8.dll /link /DEF:dinput8.def kernel32.lib user32.lib gdi32.lib cabinet.lib || exit /b 1
