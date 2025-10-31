# PromptTick：按计划定时消费本地 Prompt 并生成输出

## 快速开始（Round 1）

### 环境要求
- Python 3.9+
- `pip install pyyaml`

### 目录说明
- `main.py`：程序入口
- `config.yaml`：基础配置文件
- `state.json`：状态存储（已处理文件列表）
- `adapters/`：适配器目录，当前提供 `echo_adapter`
- `in_prompts/`：输入 Prompt 占位目录
- `out/`：输出目录占位
- `logs/`：日志目录，占位

### 如何运行首轮自检
```bash
python main.py --once
```

## 使用与运行（Round 2）
- 单轮模式：`python main.py --once`，按配置处理一批文件后立即退出。
- 定时模式：`python main.py`，持续轮询输入目录，每轮间隔 `config.yaml` 中的 `interval_seconds` 秒，可用 `Ctrl+C` 停止。
- 重新扫描：`python main.py --rescan --once`，先清空 `state.json` 的已处理记录，再执行一轮处理。
- 文件处理规则：
  - 仅处理 `file_extensions` 列表中列出的扩展名（不区分大小写），并跳过 `.part` / `.lock` / `.tmp` 结尾的临时文件。
  - `ordering: name` 采用自然排序（`001_foo` < `2_bar` < `10_baz`），`ordering: mtime` 按修改时间升序。
  - 每轮最多处理 `batch_size` 个文件，读取内容后会去除首尾空白，空文件直接标记已处理并跳过生成。
  - 生成输出写入 `output_dir`，文件名格式为 `YYYYMMDD-HHMMSS_<源文件名>.out.txt`。
- 断点续跑：程序使用 `state.json` 记录已处理文件的绝对路径字符串。成功或被判定为空白的文件会加入 `processed` 列表；失败的文件不会记入，便于下一轮重试。

## 配置说明（Round 1）
- `input_dir`、`output_dir`、`log_dir`、`state_path`：基础路径设置
- `file_extensions`、`ordering`：文件过滤与排序占位
- `adapter`：适配器名称占位
- `log_level`：日志级别（INFO/DEBUG）
- `openai`、`generic_http`：未来外部服务配置占位

## 版本规划（Roadmap）
1. Round 1：脚手架与配置、日志、自检（当前）
2. Round 2：定时循环与批处理、适配器调用
3. Round 3：OpenAI API / 通用 HTTP 适配器实现
4. Round 4：本地模型占位与扩展
5. Round 5：运维能力（状态恢复、监控与告警）
