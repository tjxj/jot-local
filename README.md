# Jot Local (纯本地离线版)

> **告别 Google Gemini 云端 API！基于阿里 SenseVoice-Small + 通义千问 Qwen2.5 的 100% 纯本地、完全免费、隐私安全的智能语音输入方案。**

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](https://github.com/google-gemini/jot-gemini-transcribe-macOS)
[![Model](https://img.shields.io/badge/ASR-SenseVoice--Small-green.svg)](https://github.com/FunAudioLLM/SenseVoice)
[![LLM](https://img.shields.io/badge/LLM-Qwen2.5-orange.svg)](https://github.com/QwenLM/Qwen2.5)

---

## 🌟 核心亮点

- 💸 **100% 完全免费**：一分钱不花！无需申请海外 API Key，无需绑定外币信用卡，无任何配额上限。
- ⚡ **极速毫秒级响应**：阿里通义实验室开源的 `SenseVoice-Small` 模型本地单次解码仅需 30~50ms，远快于 Whisper，真正做到“松手即上屏”。
- 🧠 **去口头禅与改口修正**：自动过滤“嗯、那个、然后、就是说”等语气词；说话中途改口反悔（例如“明天下午三点不对四点开会”），自动只保留最终结论。
- 🛡️ **数据绝对不出本地**：所有音频录音与大模型处理均在 Mac 本地单机完成，离线断网亦可全速运行，彻底免除商业机密与个人隐私泄露风险。
- 💻 **开箱即用支持双模式**：
  1. **方案 A（Jot 官方应用无缝直连）**：内置 Gemini API 兼容代理服务，拦截原生请求并支持最新的 `/v1beta/interactions` 协议，享受官方动态药丸 HUD 与 Accessibility 光标注入。
  2. **方案 B（纯 Python 免编译独立运行）**：无需 Xcode，macOS / Windows 终端直接运行脚本，按快捷键即可打字。

---

## 🚀 快速上手

### 1. 安装环境与依赖

```bash
cd /Users/zz/Downloads/jot-local
pip install -r requirements.txt
```

### 2. 启动本地离线服务

```bash
./start.sh
# 或直接运行：python3 server.py
```
服务将在后台监听 `http://127.0.0.1:8080`，首次启动会自动加载并预热本地 `SenseVoice-Small` 模型。

### 3. 连接与使用

#### 方案一：搭配 Jot 官方 macOS 客户端（推荐）
1. 从官方 Releases 下载 [Jot-0.4.0.dmg](https://github.com/google-gemini/jot-gemini-transcribe-macOS/releases/download/v0.4.0/Jot-0.4.0.dmg) 并拖入“应用程序”文件夹
2. 在终端配置或在应用设置（Settings → Advanced）中将 **Endpoint** 设为：
   ```text
   http://127.0.0.1:8080
   ```
3. API Key 输入任意字符保存
4. 在任意输入框中长按键盘 **fn** 说话，松手直接上屏

#### 方案二：纯 Python 独立模式（免客户端）
直接运行：
```bash
python3 standalone_voice_input.py
```
按住 **F8** 说话，松开手文字自动输入到当前光标所在窗口。

#### Windows 用户

Jot 官方客户端只有 macOS 版，Windows 用户请使用上面的纯 Python 独立模式：

1. 安装 Python 3.10+ 与 [Ollama for Windows](https://ollama.com/download/windows)，然后运行 `ollama run qwen2.5:1.5b`
2. 在 PowerShell 中安装依赖并启动：
   ```powershell
   git clone https://github.com/tjxj/jot-local.git
   cd jot-local
   pip install -r requirements.txt
   python standalone_voice_input.py
   ```
3. 按住 **F8** 说话，松手后文字通过剪贴板 + Ctrl+V 粘贴到当前光标
4. 部分笔记本的 F8 需要配合 Fn 键，可以换一个热键：
   ```powershell
   $env:HOTKEY="f9"; python standalone_voice_input.py
   ```

> 注意：文字上屏会占用一次系统剪贴板。

---

## 📂 项目结构

```text
jot-local/
├── server.py                   # Gemini /v1beta/interactions 本地代理服务
├── standalone_voice_input.py   # 纯 Python 独立热键语音输入工具
├── start.sh                    # 一键启动脚本
├── requirements.txt            # Python 依赖清单
├── README_LOCAL.md             # 详细中文架构与部署指南
├── JotCore/                    # Jot 核心 Swift 源码（已预置本地 8080 端点）
└── App/                        # Jot 原生 macOS UI 与工程定义
```

---

## 📄 开源许可

本项目基于 Google Jot（Apache 2.0 许可）二次扩展开发，遵循 Apache 2.0 开源协议。
