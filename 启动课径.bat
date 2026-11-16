@echo off
chcp 65001 >nul
title 课径 CoursePath - 启动器

echo.
echo   课径 CoursePath
echo   ----------------------------------------
echo   即将打开两个窗口：后端 8000、前端 5173
echo   关闭这两个窗口即可停止服务；无需任何 API Key。
echo.

pushd "%~dp0backend"
start "课径-后端 8000" cmd /k "..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
popd

pushd "%~dp0frontend"
start "课径-前端 5173" cmd /k "npm run dev"
popd

echo   等待服务启动（约 6 秒）...
timeout /t 6 >nul
start "" http://localhost:5173

echo.
echo   浏览器已打开。若提示连不上后端，请看「课径-后端 8000」窗口的报错。
echo   本窗口可以关闭。
timeout /t 4 >nul
