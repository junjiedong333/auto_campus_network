#Requires -RunAsAdministrator
<#
注册 CampusAutoAuth 计划任务：
- 触发器1：网络连接事件 Microsoft-Windows-NetworkProfile/Operational 10000
- 触发器2：用户登录兜底
- 动作：pythonw.exe 运行 src/campus_auth.py（无窗口）
- 脚本内二次门控保证热点+Mihomo 时静默退出
用法：以管理员身份运行 powershell -ExecutionPolicy Bypass -File scripts\Register-CampusTask.ps1
#>
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Script = Join-Path $Repo "src\campus_auth.py"

$PythonW = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonW) {
    $py = (Get-Command python.exe -ErrorAction Stop).Source
    $PythonW = $py -replace "python\.exe$", "pythonw.exe"
}
Write-Host "Repo: $Repo"
Write-Host "Script: $Script"
Write-Host "pythonw: $PythonW"

$Action = New-ScheduledTaskAction -Execute $PythonW -Argument "`"$Script`"" -WorkingDirectory $Repo
$T1 = New-ScheduledTaskTrigger -AtLogOn
# 网络连接事件触发器（需用 XML 精确订阅 NetworkProfile 10000）
$TaskName = "CampusAutoAuth"
$Xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <EventTrigger>
      <Enabled>true</Enabled>
      <Subscription>&lt;QueryList&gt;&lt;Query Id="0" Path="Microsoft-Windows-NetworkProfile/Operational"&gt;&lt;Select Path="Microsoft-Windows-NetworkProfile/Operational"&gt;*[System[(EventID=10000)]]&lt;/Select&gt;&lt;/Query&gt;&lt;/QueryList&gt;</Subscription>
    </EventTrigger>
    <LogonTrigger><Enabled>true</Enabled></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$PythonW</Command>
      <Arguments>"$Script"</Arguments>
      <WorkingDirectory>$Repo</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
$Tmp = Join-Path $env:TEMP "CampusAutoAuth.xml"
$Xml | Out-File -FilePath $Tmp -Encoding Unicode
schtasks.exe /Create /TN $TaskName /XML $Tmp /F
Write-Host "Task [$TaskName] registered. Verify: schtasks /Query /TN $TaskName"
