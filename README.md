# Jot Local（纯本地离线版）

> 把 Google Jot 背后的 Gemini 云端接口换成本机的 **SenseVoice-Small + Qwen2.5**：免费、断网可用、语音不出本机

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey.svg)](#windows-用户)
[![ASR](https://img.shields.io/badge/ASR-SenseVoice--Small-green.svg)](https://github.com/FunAudioLLM/SenseVoice)
[![LLM](https://img.shields.io/badge/LLM-Qwen2.5--1.5B-orange.svg)](https://github.com/QwenLM/Qwen2.5)

---

## 能做什么

- **按住说话，松手上屏**：官方 Jot 客户端直连本地服务，或者用纯 Python 版（macOS / Windows）
- **删口头禅**：“嗯”“呃”“那个，”“就是说”、口吃重复（我我我觉得）
- **听懂改口**：“明天上午10点不对，改到下午2点” → “明天下午2点”；“发给张总，算了，还是先发给李经理吧” → “先发给李经理吧”
- **不乱改**：Qwen 的输出会经过校验，删得太多、出现原文没有的字（比如它去翻译、去回答问题）都会退回规则清洗的结果
- **Ollama 没开也能用**：只是改口识别能力弱一些

## 实测速度（M4 · 16GB）

| 环节 | 耗时 |
| :--- | :--- |
| SenseVoice 听写（MPS，10.7 秒语音） | 约 115ms |
| Qwen2.5-1.5B 清洗一句短话 | 中位数约 160ms |
| Qwen2.5-1.5B 清洗 10 秒长句 | 约 350ms |

Apple 芯片自动用 MPS，NVIDIA 显卡自动用 CUDA，否则用 CPU（CPU 下 10 秒语音约 0.6 秒）。可用环境变量 `JOT_DEVICE=cpu` 强制指定

清洗效果：自建的 40 条测试句（口头禅、改口、正常句子各类混合），规则 + Qwen 通过 39 条，唯一没处理好的是“把字体调大一点，算了，还是保持原样吧”这种前后没有对应词的改口

---

## 快速上手

### 1. 安装依赖

```bash
git clone https://github.com/tjxj/jot-local.git
cd jot-local
pip install -r requirements.txt
```

SenseVoice 模型（约 900MB）会在第一次启动时从 ModelScope 自动下载

### 2. 安装 Ollama 和 Qwen2.5

从 [ollama.com](https://ollama.com/download) 安装 Ollama，然后：

```bash
ollama pull qwen2.5:1.5b
```

<details>
<summary>国内网络 pull 失败？从 ModelScope 下载 GGUF 手动导入</summary>

```bash
curl -L -o qwen2.5-1.5b-instruct-q4_k_m.gguf \
  https://modelscope.cn/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/master/qwen2.5-1.5b-instruct-q4_k_m.gguf
echo "FROM ./qwen2.5-1.5b-instruct-q4_k_m.gguf" > Modelfile
ollama create qwen2.5:1.5b -f Modelfile
```

</details>

保持 Ollama 在后台运行即可，服务启动时会自动预热模型

### 3A. 搭配 Jot 官方 macOS 客户端（推荐）

```bash
./start.sh        # 或 python3 server.py，监听 http://127.0.0.1:8080
```

1. 下载 [Jot-0.4.0.dmg](https://github.com/google-gemini/jot-gemini-transcribe-macOS/releases/download/v0.4.0/Jot-0.4.0.dmg) 并安装
2. Settings → Advanced，Endpoint 填 `http://127.0.0.1:8080`，API Key 随便填几个字符
3. 在任意输入框按住 **fn** 说话，松手上屏

### 3B. 纯 Python 独立版（免装 Jot）

```bash
python3 standalone_voice_input.py
```

- macOS 默认按住 **右侧 Option**，Windows 默认按住 **右侧 Ctrl**，说完松手
- 按下前 0.3 秒的声音也会录进去，开头的字不会被吞；按不到 0.3 秒视为误触
- 开始/结束有提示音，`JOT_SOUND=0` 关闭
- 文字通过剪贴板粘贴到光标处，粘贴后自动恢复原来的剪贴板内容
- 换热键：`HOTKEY=f9 python3 standalone_voice_input.py`（可选 `alt_r`、`ctrl_r`、`cmd_r`、`f1`～`f12` 等）
- macOS 第一次运行需要在 系统设置 → 隐私与安全性 里给终端开启「麦克风」「输入监控」「辅助功能」

### Windows 用户

Jot 官方客户端只有 macOS 版，Windows 用 3B 的独立版：

1. 安装 Python 3.10+ 和 [Ollama for Windows](https://ollama.com/download/windows)，执行 `ollama pull qwen2.5:1.5b`
2. PowerShell 里：
   ```powershell
   git clone https://github.com/tjxj/jot-local.git
   cd jot-local
   pip install -r requirements.txt
   python standalone_voice_input.py
   ```
3. 按住 **右侧 Ctrl** 说话，松手上屏；想换键：`$env:HOTKEY="f9"; python standalone_voice_input.py`

有 NVIDIA 显卡且装了 CUDA 版 PyTorch 会自动用显卡听写。Windows 部分作者没有真机实测，遇到问题欢迎提 Issue

---

## 环境变量

| 变量 | 默认值 | 作用 |
| :--- | :--- | :--- |
| `HOTKEY` | macOS `alt_r` / Windows `ctrl_r` | 独立版的按住说话键 |
| `JOT_SOUND` | `1` | 独立版提示音，`0` 关闭 |
| `JOT_DEVICE` | 自动 | 听写设备：`mps` / `cuda` / `cpu` |
| `QWEN_MODEL` | `qwen2.5:1.5b` | Ollama 里的清洗模型 |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama 地址 |
| `QWEN_TIMEOUT` | `4` | 清洗超时秒数，超时退回规则清洗 |

---

## 项目结构

```text
jot-local/
├── engine.py                   # 识别与清洗引擎（两种模式共用）
├── server.py                   # Gemini /v1beta/interactions 兼容服务，供 Jot 客户端连接
├── standalone_voice_input.py   # 纯 Python 按住说话客户端（macOS / Windows）
├── start.sh                    # 一键启动服务
├── requirements.txt
├── README_LOCAL.md             # 协议与实现细节
├── JotCore/ App/               # Jot 原生 Swift 源码（默认端点已改为本地 8080）
```

## 开源许可

基于 Google Jot（Apache 2.0）二次开发，遵循 Apache 2.0 协议
