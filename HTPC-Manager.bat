@echo off

(
if not exist Htpc.py (
    for %%X in (git.exe) do (set FOUND=%%~$PATH:X)
    if defined FOUND (
        DEL "%~f0"
        git clone https://github.com/HTPC-Manager/HTPC-Manager.git .
    ) else (
        echo "Git not installed. Install from: https://gitforwindows.org/"
        pause
        exit
    )
)
start cmd /c python3 Htpc.py
exit
)
