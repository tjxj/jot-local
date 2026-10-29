#!/usr/bin/env python3
"""
Jot 纯 Python 免编译独立客户端 (Standalone Push-to-Talk Client)
无需 Xcode 编译，macOS / Windows 终端直接运行，实现“按住热键说话、松手光标打字”

特性：
- 默认按键：按住 F8 说话（或通过环境变量 HOTKEY 修改）
- 录音引擎：sounddevice 内存流式缓冲
- ASR 识别：SenseVoice-Small
- 语义清洗：Qwen2.5
- 文本上屏：macOS 走 System Events ⌘V，Windows 走剪贴板 + Ctrl+V
"""

import os
import sys
import time
import json
import tempfile
import threading
import subprocess
import urllib.request

try:
    import sounddevice as sd
    import numpy as np
    import soundfile as sf
    from pynput import keyboard
except ImportError:
    print("缺少必要依赖，请运行: pip install sounddevice numpy soundfile pynput")

HOTKEY_NAME = os.environ.get("HOTKEY", "f8").lower()
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen2.5:1.5b")

SAMPLE_RATE = 16000
CHANNELS = 1

is_recording = False
audio_frames = []
lock = threading.Lock()

def record_callback(indata, frames, time_info, status):
    if is_recording:
        audio_frames.append(indata.copy())

def insert_text_into_active_app(text):
    """通过剪贴板 + 粘贴快捷键把文字送到当前光标（兼容中文和各种符号最稳）"""
    if not text:
        return
    if sys.platform == "darwin":
        p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, close_fds=True)
        p.communicate(text.encode('utf-8'))

        script = '''
        tell application "System Events"
            keystroke "v" using {command down}
        end tell
        '''
        subprocess.run(['osascript', '-e', script])
    elif sys.platform == "win32":
        # clip.exe 需要带 BOM 的 UTF-16 才能正确处理中文
        subprocess.run(['clip'], input=text.encode('utf-16'), check=True)
        controller = keyboard.Controller()
        with controller.pressed(keyboard.Key.ctrl):
            controller.press('v')
            controller.release('v')
    else:
        print(f"[提示] 当前系统暂不支持自动上屏，请手动复制：{text}")

def process_audio_and_type(audio_data):
    """后台异步处理转写与输入"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio_data, SAMPLE_RATE)
        wav_path = f.name

    print("\n[🎙️ 识别中...] 正在调用 SenseVoice-Small...")
    raw_text = ""
    try:
        from funasr import AutoModel
        model = AutoModel(model="iic/SenseVoiceSmall", vad_model="fsmn-vad", device="cpu", disable_update=True)
        res = model.generate(input=wav_path, language="auto", use_itn=True)
        raw_text = res[0]["text"] if res else ""
    except Exception as e:
        print(f"[ASR 错误] {e}")
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

    if not raw_text.strip():
        print("[提示] 未检测到有效语音")
        return

    print(f"[原始识别] {raw_text}")
    print("[🧠 润色中...] 正在调用 Qwen2.5 去口头禅...")

    prompt = f"""你是一个输入法语义清洗助手。请将以下粗糙口语转写重构为标准、得体、流畅的书面语：
1. 彻底剔除'嗯'、'那个'、'就是说'等口头禅与犹豫停顿
2. 识别说话人的中途改口（如'三点不对四点'保留'四点'），只保留最终决定
3. 补全规范标点
待处理文本：
{raw_text}
直接输出最终文本，不要解释。"""

    final_text = raw_text
    try:
        payload = {
            "model": QWEN_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 128}
        }
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            final_text = data.get("response", raw_text).strip()
    except Exception as e:
        print(f"[Qwen 响应异常，直接使用初稿] {e}")

    print(f"[✅ 上屏文本] {final_text}")
    insert_text_into_active_app(final_text)

def on_press(key):
    global is_recording, audio_frames
    try:
        key_char = key.char if hasattr(key, 'char') else str(key).replace("Key.", "")
        if key_char.lower() == HOTKEY_NAME:
            if not is_recording:
                is_recording = True
                audio_frames = []
                print("\n🔴 [开始录音...] 请说话（松开按键完成）", end="", flush=True)
    except Exception:
        pass

def on_release(key):
    global is_recording, audio_frames
    try:
        key_char = key.char if hasattr(key, 'char') else str(key).replace("Key.", "")
        if key_char.lower() == HOTKEY_NAME and is_recording:
            is_recording = False
            print("\n🟢 [录音结束] 正在转写与清洗...")
            if len(audio_frames) > 0:
                audio_data = np.concatenate(audio_frames, axis=0)
                threading.Thread(target=process_audio_and_type, args=(audio_data,)).start()
    except Exception:
        pass

def main():
    print("=" * 60)
    print("🚀 Jot-Local 纯 Python 独立打字工具已启动")
    print(f"⌨️ 默认热键: 按住【{HOTKEY_NAME.upper()}】说话，松手自动打字到光标所在处")
    print("🛡️ 100% 离线运行，无需外网，零泄密")
    print("=" * 60)

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, callback=record_callback)
    with stream:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()

if __name__ == "__main__":
    main()
