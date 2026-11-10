@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" (
    echo Open an x64 Native Tools Command Prompt for Visual Studio first.
    exit /b 1
)
if not exist build mkdir build
cl /nologo /std:c++20 /EHsc /W4 /WX /O2 /MT /Fo:build\audio-capture.obj /Fe:build\audio-capture.exe loopback.cpp ole32.lib mmdevapi.lib winmm.lib
exit /b %errorlevel%
