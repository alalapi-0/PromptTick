# systemd 部署 PromptTick 示例

本示例展示如何将 `PromptTick` 部署为 Linux systemd 服务。下述内容默认以非 root 用户运行，可按需调整。

## 服务文件位置
1. 将仓库中的 [`ops/systemd.service`](./systemd.service) 复制到服务器：
   - 系统级：`/etc/systemd/system/prompTick.service`
   - 或者用户级：`~/.config/systemd/user/prompTick.service`
2. 修改 `User`、`WorkingDirectory` 与 `ExecStart` 中的用户名、路径和 Python 解释器。
3. 若存放于用户级目录，请通过 `systemctl --user` 管理，并确保 `systemd --user` 会话随登录启动。

## 启用与启动
```bash
sudo systemctl daemon-reload
sudo systemctl enable prompTick.service
sudo systemctl start prompTick.service
sudo systemctl status prompTick.service
```

若使用用户级 systemd，请将命令中的 `sudo systemctl` 改为 `systemctl --user`。

## 查看日志
```bash
journalctl -u prompTick.service -e
```

日志默认仍会写入仓库目录下的 `logs/run-YYYYMMDD.log`，可配合 `journalctl` 定位问题。

## 可选：使用 systemd timer 定时运行
如果希望每 5 分钟运行一次 `python main.py --once`，可以使用如下 `prompTick.timer`（放置于与 service 同级目录）：

```ini
[Unit]
Description=Run PromptTick every five minutes

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
Unit=prompTick.service

[Install]
WantedBy=timers.target
```

启用步骤：

```bash
sudo systemctl daemon-reload
sudo systemctl enable prompTick.timer
sudo systemctl start prompTick.timer
sudo systemctl list-timers --all | grep prompTick
```

保持 `prompTick.service` 为单次运行模式（包含 `--once`），timer 会按计划触发执行。若希望服务常驻循环运行，可移除 `--once` 并禁用 timer。
