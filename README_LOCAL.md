# Jot-Local：纯本地离线智能语音输入

告别 Google Gemini 3.5 Transcribe 云端 API，利用 **SenseVoice-Small + Qwen2.5** 纯本地离线复刻 Google Jot 的“按住说话、去口头禅、改口纠偏、直接上屏”极致体验。

---

## 🌟 核心特性

- 🎙️ **快速听写**：阿里通义实验室开源的 `SenseVoice-Small`，M4 上走 MPS，10.7 秒语音听写约 115ms。
- 🧠 **大模型语义重塑**：通义千问 `Qwen2.5-1.5B`，先由规则删口头禅和明确改口，再交给 Qwen 处理复杂情况，输出经过校验防止改写原意，自动过滤“嗯、那个、就是说”等语气词，并智能识别“改口反悔”（如“明天下午三点不对四点”保留最终结论）。
- 🛡️ **100% 纯本地离线**：声音不出本地，无网络依赖，零泄露风险，无需外币与 API Key。
- ⚡ **无缝双模式支持**：
  - **模式 A（Jot 官方客户端直连）**：内置 Gemini API 协议兼容服务，Jot 原生 Swift 应用（带悬浮动态药丸 HUD、Accessibility 光标穿透）直接连本地。
  - **模式 B（纯 Python 免编译独立运行）**：无需 Xcode，直接运行脚本按键打字。

---

## 🚀 快速上手

### 1. 安装基础依赖

```bash
pip install -r requirements.txt
```

确保本地已安装并运行 Ollama（用于 Qwen2.5 语义清洗）：
```bash
ollama pull qwen2.5:1.5b
```

### 2. 方式 A：启动本地服务并配合 Jot 原生客户端

1. 启动本地兼容服务：
   ```bash
   ./start.sh
   # 服务将运行在 http://127.0.0.1:8080
   ```
2. 运行 Jot 原生应用：
   - 源码中的 `GeminiConfig` 默认已配置为 `http://127.0.0.1:8080`。
   - 或在 Jot 设置中（Settings → Advanced），确认 Endpoint 指向 `http://127.0.0.1:8080`，API Key 填写任意字符即可。
3. 全局按住 `fn` 键说话，松手直接打字上屏。

### 3. 方式 B：免编译独立运行（纯 Python 方案）

如果不需要 Xcode 编译，直接在终端启动：
```bash
python3 standalone_voice_input.py
```
macOS 默认按住 **右侧 Option**、Windows 默认按住 **右侧 Ctrl** 说话，松开手后，文字将自动录入当前光标所在的应用窗口。

Windows 用户同样使用这个方式（`python standalone_voice_input.py`），详见 README 的「Windows 用户」一节。

---

## 📁 目录结构

```text
jot-local/
├── engine.py                   # 识别与清洗引擎（两种模式共用）
├── server.py                   # Gemini API 本地兼容服务（SenseVoice + Qwen2.5）
├── standalone_voice_input.py   # 纯 Python 独立打字客户端（免编译直接跑）
├── start.sh                    # 一键启动脚本
├── requirements.txt            # Python 依赖清单
├── JotCore/                    # Jot 核心 Swift 源码（默认已改为本地 8080 端点）
├── App/                        # Jot 原生 macOS UI 与工程配置
└── project.yml                 # XcodeGen 工程配置文件
```
