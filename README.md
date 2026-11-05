# Python 最小 ReAct Agent

使用 Python 3.12+ 标准库从零实现的 ReAct Agent，提供命令行和浏览器聊天入口。核心运行时自行完成模型决策、工具执行、Observation 回传和循环终止。项目依赖清单位于 `pyproject.toml`，第三方依赖为零。

## 1. 快速运行

以下命令在项目根目录执行。

### 离线演示

```powershell
python --version
python agent.py --demo --user A --session window1
```

也支持 `python -m react_agent --demo`。演示模式使用确定性规则，适合检查运行流程，支持天气、搜索、计算、待办及简单历史回顾。

### 真实模型

使用兼容 Chat Completions 的 HTTP 接口。在启动程序的同一个 PowerShell 窗口设置配置。

```powershell
$env:LLM_API_KEY = '替换为你的密钥'
$env:LLM_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
$env:LLM_MODEL = '替换为控制台确认可调用的模型ID'
python agent.py --user A --session window1
```

程序在 Base URL 后追加 `/chat/completions`。地址、地域、模型及密钥应对应供应商控制台的调用示例。网络超时为 30 秒。`LLM_API_KEY` 必填；建议显式设置全部三个变量，避免使用不适用于账号的默认模型。

通过 PyCharm 启动时，在对应运行配置的“环境变量”中设置以上变量。代码直接读取进程环境，`.env` 文件需另行加载后才会生效。

### 浏览器页面

```powershell
# 真实模型，沿用上述环境变量
python -m react_agent.web_server

# 或选择离线演示
python -m react_agent.web_server --demo
```

打开 [本地聊天页面](http://127.0.0.1:8000)。端口可通过 `--port 8001` 修改。页面支持新建与切换会话、连续对话、查看待办及执行日志。服务绑定 `127.0.0.1`，适用于本地使用。日志在整轮运行完成后返回。

### 常用命令与参数

| 项目 | 用法 |
| --- | --- |
| 查看最近 trace | CLI 输入 `/trace` |
| 切换会话 | CLI 输入 `/session window2` |
| 退出 | CLI 输入 `/exit` |
| 数据目录 | CLI 或网页服务传入 `--data-dir data` |
| 决策次数上限 | CLI 传入 `--max-steps 8`，网页服务默认 8 次 |
| 运行测试 | `python -m unittest -v` |

## 2. 系统设计

```text
命令行 / 浏览器
      ↓
SessionStore.transact(user, session_id)
      ↓ 加载状态并取得当前会话文件锁
Agent.run(session, input)
      ↓
压缩历史 → 组装 context → 请求模型 → 解析 JSON
                               ↑          ├─ final → 结束
                               │          └─ action
                               │               ↓
                               └─ Observation ← 参数校验与工具执行
      ↓
保存对话、待办、摘要和 trace → 原子替换会话文件 → 返回用户
```

`Agent.run` 使用普通 Python 循环执行 ReAct。每个 action 处理一个工具调用，复杂任务可连续执行多次 action。模型根据提示词中的工具 Schema 选择工具。工具结果作为后续请求中的 Observation，帮助模型决定继续执行或返回答案。

### 模块职责

```text
python-react-agent/
├── agent.py                 # CLI 启动入口
├── pyproject.toml           # Python 版本与依赖声明
├── react_agent/
│   ├── __init__.py          # 包公共入口
│   ├── __main__.py          # python -m react_agent
│   ├── cli.py               # 命令行参数与交互
│   ├── web_server.py        # 本地 HTTP 服务与 JSON API
│   ├── runtime.py           # ReAct 核心循环
│   ├── models.py            # Chat Completions HTTP 适配
│   ├── demo.py              # 离线规则适配
│   ├── protocol.py          # action / final 输出解析
│   ├── registry.py          # 工具注册和 Schema 子集校验
│   ├── tools.py             # 四个工具的实现与注册
│   ├── context.py           # 历史压缩
│   └── session.py           # 会话加载、文件锁和原子保存
├── web/                     # HTML、CSS、JavaScript 页面
├── test_agent.py            # 基础功能测试
├── test_requirements.py     # 协议、HTTP、工具追问等回归测试
├── AI_PROMPTS_AND_SOLUTIONS.md
└── README.md
```

### 模型输出协议

```json
{"type":"action","thought":"需要查询杭州天气","tool":"weather","arguments":{"city":"杭州"}}
```

```json
{"type":"final","thought":"已有查询结果","answer":"杭州示例天气为多云，22℃。"}
```

`thought` 表示简短决策摘要。协议解析器支持 JSON 文本和 JSON 代码围栏。工具 Schema 通过 system 消息传入模型，自定义 action JSON 由 Runtime 解析执行。

### 工具

| 名称 | 参数 | 行为 |
| --- | --- | --- |
| calculator | expression | AST 白名单四则运算，支持括号和正负号 |
| search | query | 返回标记为 mock 的示例知识库结果 |
| weather | city | 返回标记为 mock 的示例天气 |
| todo | action、text、id | 添加、列出和完成当前会话待办 |

注册项包含名称、描述、参数 Schema 和执行函数。校验覆盖项目使用的 Schema 子集，包括必填项、额外字段、字符串长度、整数下限和枚举。新增工具在 `tools.py` 注册，Runtime 会从注册表获取可用工具列表。

## 3. Memory 的召回时机与放置方式

### 保存哪些信息

| 字段 | 内容 | 用途 |
| --- | --- | --- |
| turns | 最近保留的完整对话轮次，包含输入、action、Observation、最终答案 | 支持连续对话和工具追问 |
| summary | 较早轮次的压缩摘录 | 在有限上下文中保留部分旧信息 |
| todos | 结构化待办状态 | 支持跨轮查询与修改 |
| trace | 最近一次执行的决策、参数、观察和错误 | 调试与页面展示 |

会话保存在 `data/<hash>.json`，hash 由 `[user, session_id]` 计算。每次 CLI 输入或网页 API 请求进入 `SessionStore.transact` 时，从磁盘读取对应会话。运行结束后保存，重启进程仍能通过相同 user 和 session ID 继续。

### 何时召回

1. **请求开始**，按 user 和 session ID 精确加载会话状态。
2. **每次模型决策前**，调用 `compress`，随后将 summary、todos、近期 turns 与当前轮消息组装到 context。
3. **工具执行后**，将 action 和 Observation 追加到当前轮，下一次模型请求即可读取这些结果。
4. **本轮结束**，追加最终答案，保存完整轮次，再次执行历史压缩并持久化。

召回采用当前会话内的确定性加载与拼接，范围由会话 ID 限定。长历史经过压缩后只保留摘录和近期轮次。

### 放到模型请求的哪里

```text
messages[0] / system
  ReAct 协议提示词
  tools   工具名称、描述、参数 Schema
  summary 历史摘要
  todos   当前结构化待办

messages[1:] / 历史及当前轮
  user       用户问题
  assistant  action JSON（含 thought 摘要）
  user       Observation 前缀 + 工具结果或错误
  assistant  最终回复
  ...后续轮次...
```

`trace` 用于调试和展示。进入模型 context 的决策与工具结果来自 turns 及当前轮消息。API 请求由 `models.py` 完成，将上述内容编码到 `model` 和 `messages` 字段。

### 压缩策略与边界

历史 turns 的 JSON 文本长度超过 12000 字符且轮次数大于 1 时，逐次移除最早轮次。每条消息取前 500 字符加入 summary，summary 保留末尾最多 4000 字符。工具结果进入 context 前截取最多 4000 字符。

这是基础有损压缩。早期细节可能丢失，移除的完整轮次会从持久化状态中消失。当前轮次、工具 Schema 和 todos 另外进入请求，因此 12000 字符是历史软预算。至少保留一个完整轮次，该轮次可能超过预算。当前实现以字符数估算长度。

### 窗口隔离与恢复

```powershell
# 窗口 1
python agent.py --user A --session window1
# 窗口 2
python agent.py --user A --session window2
```

两个窗口分别维护天气待办与周报待办。使用同一 ID 可恢复对应会话。网页会话目录保存在 localStorage，当前选中 ID 保存在 sessionStorage，内容由 Python 服务端保存；网页使用用户 A 命名空间。复制标签页可能复制 sessionStorage，需要点击“新建会话”获得独立 ID。

同会话文件锁覆盖加载、执行和写入，冲突返回错误。临时文件加原子替换避免半写入。当前工具的可变状态限于会话待办，随本地事务一起提交。用户 ID 用于本地命名空间隔离，身份认证需要后续接入。

## 4. 异常处理与执行日志

- 模型请求失败时结束本轮并记录 model_error。
- JSON 解析失败时反馈协议要求，在剩余轮次内允许模型修正。
- 未知工具、参数错误和工具异常作为失败 Observation 回传。
- 默认最多 8 次模型决策，达到上限返回明确提示。
- trace 包含决策摘要、调用参数、结果、工具耗时及错误。只保存最近一次执行。
- HTTP 错误展示状态码与服务端详情，对当前 API Key 做脱敏。

## 5. 测试与验收

```powershell
python -m unittest -v
```

当前 20 项测试覆盖计算、注册和 Schema、协议解析、直接回复、连续工具调用、纯对话追问、依赖前次结果的工具追问、最大轮次、解析恢复、模型失败、待办完成、压缩、用户和窗口隔离、重启恢复、失败事务、HTTP 模型适配及网页接口。

自动化测试使用规则模型、脚本模型和模拟 HTTP 响应。网页集成测试启动临时本地 HTTP 服务。已完成一次真实模型验证，模型调用 calculator 计算 `(12+8)*3`，读取 Observation 后返回 `60`。真实模型可用性取决于运行时配置和账号权限。页面尚未完成浏览器截图验收。

建议演示顺序为“查杭州天气并记待办”→“查看待办”→新建会话→“查看待办”。真实模型模式还可演示“计算 2+3”→“再乘以二”。

## 6. AI 辅助开发记录与提交

开发提示、设计决策和问题解决过程见 [AI Prompt 与问题解决记录](AI_PROMPTS_AND_SOLUTIONS.md)。

`.gitignore` 排除 `.env`、本地会话数据、虚拟环境、IDE 文件和 Python 缓存。密钥通过环境变量传入。若密钥曾进入 Git 历史，应在供应商控制台轮换，并单独处理历史记录。提交目录选用当前 Python 项目根目录。
