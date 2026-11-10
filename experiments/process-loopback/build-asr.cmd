@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if /i not "%VSCMD_ARG_TGT_ARCH%"=="x64" (
    echo Open an x64 Native Tools Command Prompt for Visual Studio first.
    exit /b 1
)
set "SOURCE=build\asr\whisper.cpp-1.9.2"
set "RUNTIME=build\asr\runtime\Release"
if not exist "%SOURCE%\include\whisper.h" (
    echo Extract the whisper.cpp v1.9.2 source archive into build\asr first.
    exit /b 1
)
if not exist "%RUNTIME%\whisper.dll" (
    echo Extract the whisper.cpp v1.9.2 Windows x64 runtime first.
    exit /b 1
)
cl /nologo /std:c++20 /utf-8 /EHsc /W4 /WX /O2 /MT /I"%SOURCE%\include" /I"%SOURCE%\ggml\include" /Fo:build\asr\asr_worker.obj /Fe:"%RUNTIME%\asr-worker.exe" asr_worker.cpp
exit /b %errorlevel%
