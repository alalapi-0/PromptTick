# Cron 定时运行 PromptTick 示例

本文档展示如何在 Linux/Unix 环境使用 cron 每 5 分钟执行一次 `PromptTick`。示例默认以当前用户身份运行。

## 基本计划任务
使用 `crontab -e` 编辑当前用户的计划任务，添加以下条目：

```cron
*/5 * * * * cd /home/YOUR_USERNAME/PromptTick && /usr/bin/python3 main.py --once --config config.yaml >> logs/cron.log 2>&1
```

说明：
- `*/5 * * * *` 表示每 5 分钟执行一次。
- 使用 `cd` 切换到仓库目录，确保读取配置与状态文件。
- 将标准输出和错误输出重定向到 `logs/cron.log` 便于排查。

## 避免并发重入
若任务执行时间可能超过 5 分钟，建议使用 `flock` 防止重复启动：

```cron
*/5 * * * * cd /home/YOUR_USERNAME/PromptTick && /usr/bin/flock -n /tmp/prompTick.lock /usr/bin/python3 main.py --once --config config.yaml >> logs/cron.log 2>&1
```

`flock -n` 会尝试获取锁文件 `/tmp/prompTick.lock`，若锁已被占用则直接退出。

## 设置环境变量
PromptTick 运行时需要的环境变量（如 `OPENAI_API_KEY`）有两种常见配置方式：
1. 在 crontab 顶部直接声明：
   ```cron
   OPENAI_API_KEY=sk-xxxx
   */5 * * * * cd /home/YOUR_USERNAME/PromptTick && /usr/bin/python3 main.py --once --config config.yaml >> logs/cron.log 2>&1
   ```
2. 将变量写入 `~/.profile` 或 `~/.bashrc`，并在 crontab 中通过 `bash -lc` 启动：
   ```cron
   */5 * * * * cd /home/YOUR_USERNAME/PromptTick && /bin/bash -lc '/usr/bin/python3 main.py --once --config config.yaml >> logs/cron.log 2>&1'
   ```

根据实际部署环境调整 Python 路径、仓库位置及日志文件名。日志仍会写入 `logs/run-YYYYMMDD.log` 便于长期追踪。
