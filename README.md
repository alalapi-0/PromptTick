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
