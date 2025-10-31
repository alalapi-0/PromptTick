# Windows 任务计划程序示例：每 5 分钟运行 PromptTick

本示例帮助你在 Windows 10/11 上通过任务计划程序定期执行 `python main.py --once --config config.yaml`。

## 图形界面配置步骤
1. 打开“开始菜单”，搜索并启动 **任务计划程序**。
2. 在右侧操作窗格点击 **创建任务…**（不是“创建基本任务”）。
3. 在“常规”选项卡填写：
   - 名称：`PromptTick Every 5 Minutes`
   - 选择“无论用户是否登录都要运行”或按需调整。
   - 如果需要网络或环境变量，请勾选“使用最高权限运行”。
4. 切换到“触发器”选项卡，点击 **新建…**：
   - 开始任务：`按照计划` → `每天`
   - 设置开始日期/时间。
   - 勾选“重复任务间隔”，选择 **5 分钟**。
   - “持续时间”选择 **无限期**。
   - 确认后点击“确定”。
5. 在“操作”选项卡点击 **新建…**：
   - 操作：`启动程序`
   - 程序或脚本：`C:\Path\To\python.exe`
   - 添加参数（可选）：`main.py --once --config config.yaml`
   - 起始于（可选）：`C:\Path\To\PromptTick`
   - 点击“确定”。
6. 根据需要在“条件”和“设置”选项卡中启用：
   - “若错过计划运行时间，则尽快运行任务”。
   - “允许按需运行任务”。
7. 点击“确定”保存任务，如选择“无论用户是否登录”，系统会提示输入凭据。

任务创建后，可在“任务计划程序库”中右键任务执行“运行”测试。日志输出位于仓库的 `logs/run-YYYYMMDD.log`。

## XML 导入模板
也可以直接导入以下 XML（保存为 `PromptTick.xml`，然后在任务计划程序中选择“导入任务…”）。请按需修改 `COMMAND`、`ARGUMENTS` 与 `WORKDIR`。

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Date>2024-01-01T00:00:00</Date>
    <Author>PromptTick</Author>
    <Description>Run PromptTick once every five minutes.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2024-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
      <Repetition>
        <Interval>PT5M</Interval>
        <Duration>P1D</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <RunLevel>LeastPrivilege</RunLevel>
      <LogonType>Password</LogonType>
      <UserId>DOMAIN\USERNAME</UserId>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>false</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>C:\Path\To\python.exe</Command>
      <Arguments>main.py --once --config config.yaml</Arguments>
      <WorkingDirectory>C:\Path\To\PromptTick</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
```

导入后仍可在图形界面中编辑触发器与账号。若要常驻循环模式，可将参数改为 `main.py --config config.yaml`。
