@echo off
:: Reclaim C: Drive Disk Space from Docker / WSL2 VHDX
echo ===================================================
echo     Reclaiming C: Drive Space from Docker VHDX
echo ===================================================
echo.

:: 1. Shut down WSL to release file locks
echo [1/3] Shutting down WSL...
wsl --shutdown

:: 2. Create diskpart compaction script
set DISKPART_SCRIPT=%TEMP%\compact_docker_vhd.txt
echo select vdisk file="%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx" > "%DISKPART_SCRIPT%"
echo attach vdisk readonly >> "%DISKPART_SCRIPT%"
echo compact vdisk >> "%DISKPART_SCRIPT%"
echo detach vdisk >> "%DISKPART_SCRIPT%"

:: 3. Run diskpart compaction
echo [2/3] Compacting Docker VHDX file (reclaiming 25+ GB)...
diskpart /s "%DISKPART_SCRIPT%"

:: 4. Cleanup
del /f /q "%DISKPART_SCRIPT%" >nul 2>&1

echo.
echo ===================================================
echo   Successfully Compacted! Check your C: drive space.
echo ===================================================
echo.
pause
