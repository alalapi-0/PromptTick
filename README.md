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

## 通用 HTTP 适配器（generic_http_adapter）

### 依赖准备
```bash
pip install httpx
```

### 快速配置示例
将 `config.yaml` 中的 `adapter` 设置为 `generic_http_adapter`，并补充 `generic_http` 段：

```yaml
adapter: "generic_http_adapter"
generic_http:
  url: "https://api.example.com/generate"
  method: "POST"
  timeout: 60
  headers:
    Authorization: "Bearer ${ENV:THIRD_PARTY_API_KEY}"
    Content-Type: "application/json"
  body_template: |
    {
      "prompt": "${PROMPT}",
      "params": {"temperature": 0.7, "max_tokens": 800}
    }
  response_json_pointer: "/data/text"
  retries:
    max_attempts: 3
    backoff_seconds: 1.0
    retry_on_status: [429, 500, 502, 503, 504]
```

### 字段说明
- `url` / `method` / `timeout`：目标接口地址、HTTP 方法与超时（秒）。
- `headers`：HTTP 头模板，支持 `${ENV:VAR}` 占位符在加载时替换环境变量。
- `body_template`：请求体模板，先进行环境变量替换，再用 `${PROMPT}` 注入实际 prompt 文本。
- `response_json_pointer`：返回 JSON 中目标字段的 JSON Pointer 路径（如 `/choices/0/message/content`）。
- `retries.max_attempts` / `backoff_seconds` / `retry_on_status`：重试次数、指数退避初始等待（秒）与触发重试的 HTTP 状态码列表。

当 `Content-Type` 为 `application/json`（忽略大小写及可选 charset）时，`body_template` 会被解析为 JSON 对象发送；否则作为原始文本发送。

### 安全与日志
- 日志仅会打印打码后的敏感头（如 `Authorization: Bearer ***`），不要把密钥写进仓库。
- 所有异常（网络失败、JSON 解析错误、环境变量缺失等）都会返回可读的错误文本并写入输出文件，便于排查。

### 本地自测（可选）
1. 启动本地 mock：`python scripts/mock_http_echo.py`
2. 在 `config.yaml` 中将 `generic_http.url` 改为 `http://127.0.0.1:8787/generate`
3. 准备 Prompt 文件后运行 `python main.py --rescan --once`
4. 期望输出以 `[MOCK]` 开头，日志展示调用信息且敏感头被打码。

## 版本规划（Roadmap）
1. Round 1：脚手架与配置、日志、自检（当前）
2. Round 2：定时循环与批处理、适配器调用
3. Round 3：OpenAI API / 通用 HTTP 适配器实现
4. Round 4：本地模型占位与扩展
5. Round 5：运维能力（状态恢复、监控与告警）
