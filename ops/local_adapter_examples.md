# 本地适配器示例

本地模型适配器仅负责把 Prompt 写入临时文件，并按照命令行模板调用你的可执行程序；它**不包含任何模型权重或推理逻辑**。模板中可使用以下占位符：

- `${PROMPT_PATH}`：临时 prompt 文件的绝对路径
- `${MODEL}`：`config.yaml` 中 `local.model` 的值
- `${ARGS}`：`local.args` 列表拼接后的字符串
- `${OUT_PATH}`：输出文件路径，仅在 `output_mode: file` 时有效

## 输出模式

- `stdout`：子进程把生成文本打印到标准输出。
- `file`：子进程把生成文本写入 `${OUT_PATH}` 指定的文件。

## 示例 A：使用 fake_local_model.py 自测（跨平台）

```yaml
adapter: local_stub_adapter
local:
  engine: "cmd"
  timeout_seconds: 30
  output_mode: "file"
  command_template: >
    python scripts/fake_local_model.py --in ${PROMPT_PATH} --out ${OUT_PATH}
```

## 示例 B：Ollama（Linux/macOS Bash）

```yaml
adapter: local_stub_adapter
local:
  engine: "ollama"
  model: "llama3:instruct"
  timeout_seconds: 120
  output_mode: "stdout"
  command_template: >
    ollama run ${MODEL} -p "$(cat ${PROMPT_PATH})"
```

## 示例 C：Ollama（Windows PowerShell）

```yaml
command_template: >
  powershell -NoProfile -Command "$p = Get-Content -Raw '${PROMPT_PATH}'; ollama run ${MODEL} -p $p"
output_mode: "stdout"
```

## 安全提醒

由于模板是以 `shell=True` 执行的，存在命令注入风险。本项目假设你在受信任的目录中使用，生产环境请务必加上路径白名单或更严格的转义策略。

## 性能提示

当 Prompt 较大或命令行长度受限时，推荐使用 `output_mode: file`，由程序读写文件避免 shell 参数过长。

## 常见问题

- **找不到命令**：请确认程序已加入 `PATH`，或在模板中写绝对路径。
- **超时**：增加 `timeout_seconds`，或检查程序是否卡住。
- **编码问题**：所有文件均按 UTF-8 读写，必要时显式指定编码。
