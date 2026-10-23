@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
"%CSC%" /nologo /target:winexe /optimize+ /platform:anycpu /win32icon:pet.ico /win32manifest:Pet.manifest /out:..\小黄桌宠.exe /reference:System.Drawing.dll /reference:System.Windows.Forms.dll /reference:System.IO.Compression.dll /reference:System.IO.Compression.FileSystem.dll /reference:System.Web.Extensions.dll Naiwa.cs AssemblyInfo.cs
if errorlevel 1 (pause & exit /b 1)
echo 编译完成，exe 已输出到上一层目录。
pause
