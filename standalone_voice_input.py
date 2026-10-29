#!/usr/bin/env python3
"""
Jot 纯 Python 免编译独立客户端 (Standalone Push-to-Talk Client)
无需 Xcode 编译，macOS / Windows 终端直接运行，实现“按住热键说话、松手光标打字”

特性：
- 默认按键：macOS 按住右侧 Option，Windows 按住右侧 Ctrl（可用环境变量 HOTKEY 修改，如 HOTKEY=f8）
- 录音引擎：sounddevice 常开麦克风流，保留按键前 0.3 秒，开头的字不会被吞
- ASR 识别：SenseVoice-Small（Apple 芯片走 MPS，NVIDIA 显卡走 CUDA）
- 语义清洗：Qwen2.5（Ollama），不可用时退回规则清洗
- 文本上屏：剪贴板 + 粘贴快捷键，粘贴后恢复原剪贴板内容
"""

import os
import sys
import time
import queue
import collections
import subprocess
import threading

try:
    import numpy as np
    import pyperclip
    import sounddevice as sd
    from pynput import keyboard
except ImportError as e:
    print(f"缺少依赖（{e.name}），请先运行: pip install -r requirements.txt")
    sys.exit(1)

import engine

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

HOTKEY_NAME = os.environ.get("HOTKEY", "alt_r" if IS_MAC else "ctrl_r").lower()
HOTKEY_LABEL = {"alt_r": "右侧 Option" if IS_MAC else "右侧 Alt", "ctrl_r": "右侧 Ctrl", "cmd_r": "右侧 Command"}.get(HOTKEY_NAME, HOTKEY_NAME.upper())
SOUND = os.environ.get("JOT_SOUND", "1") != "0"

SAMPLE_RATE = engine.SAMPLE_RATE
BLOCK_SIZE = 1024
PRE_ROLL_SECONDS = 0.3
MIN_PRESS_SECONDS = 0.3

state_lock = threading.Lock()
is_recording = False
press_started = 0.0
audio_frames = []
pre_roll = collections.deque(maxlen=int(PRE_ROLL_SECONDS * SAMPLE_RATE / BLOCK_SIZE) + 1)
jobs = queue.Queue()
kb = keyboard.Controller()


def record_callback(indata, frames, time_info, status):
    with state_lock:
        if is_recording:
            audio_frames.append(indata.copy())
        else:
            pre_roll.append(indata.copy())


def play_cue(start):
    """开始/结束录音的提示音（JOT_SOUND=0 关闭）"""
    if not SOUND:
        return

    def _play():
        try:
            if IS_MAC:
                sound = "Tink" if start else "Pop"
                subprocess.run(["afplay", f"/System/Library/Sounds/{sound}.aiff"], check=False)
            elif IS_WIN:
                import winsound
                winsound.Beep(880 if start else 660, 60)
        except Exception:
            pass

    threading.Thread(target=_play, daemon=True).start()


def insert_text_into_active_app(text):
    """通过剪贴板 + 粘贴快捷键把文字送到当前光标（兼容中文和各种符号最稳），之后恢复原剪贴板"""
    if not text:
        return
    try:
        previous = pyperclip.paste()
    except Exception:
        previous = None

    pyperclip.copy(text)
    time.sleep(0.05)
    modifier = keyboard.Key.cmd if IS_MAC else keyboard.Key.ctrl
    with kb.pressed(modifier):
        kb.press("v")
        kb.release("v")

    if previous is not None:
        # 等目标应用读完剪贴板再恢复
        time.sleep(0.5)
        try:
            if pyperclip.paste() == text:
                pyperclip.copy(previous)
        except Exception:
            pass


def worker():
    """按说话顺序依次处理，避免前后两句上屏顺序错乱"""
    while True:
        audio = jobs.get()
        t0 = time.time()
        try:
            raw_text = engine.transcribe(audio)
        except Exception as e:
            print(f"[识别出错] {e}")
            continue
        if not raw_text:
            print("[提示] 没听到有效语音")
            continue
        t1 = time.time()
        final_text = engine.qwen_clean(raw_text)
        t2 = time.time()
        print(f"  原文：{raw_text}")
        print(f"  上屏：{final_text}  （识别 {(t1 - t0) * 1000:.0f}ms，清洗 {(t2 - t1) * 1000:.0f}ms）")
        insert_text_into_active_app(final_text)


def key_name(key):
    if isinstance(key, keyboard.KeyCode):
        return (key.char or "").lower()
    return str(key).replace("Key.", "").lower()


def on_press(key):
    global is_recording, press_started, audio_frames
    if key_name(key) != HOTKEY_NAME:
        return
    with state_lock:
        if is_recording:
            return
        is_recording = True
        press_started = time.time()
        audio_frames = list(pre_roll)
    play_cue(True)
    print("🔴 录音中…松开结束")


def on_release(key):
    global is_recording
    if key_name(key) != HOTKEY_NAME:
        return
    with state_lock:
        if not is_recording:
            return
        is_recording = False
        held = time.time() - press_started
        frames = audio_frames
    if held < MIN_PRESS_SECONDS or not frames:
        print("⚪ 按得太短，已忽略")
        return
    play_cue(False)
    jobs.put(np.concatenate(frames, axis=0)[:, 0])


def main():
    print("正在加载模型，首次运行会自动下载 SenseVoice（约 900MB）...")
    asr_ok, qwen_ok = engine.warmup()
    if not asr_ok:
        print("❌ SenseVoice 加载失败，请检查依赖安装后重试")
        sys.exit(1)

    try:
        stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=BLOCK_SIZE, callback=record_callback)
        stream.start()
    except Exception as e:
        print(f"❌ 打不开麦克风：{e}")
        if IS_MAC:
            print("   请在 系统设置 → 隐私与安全性 → 麦克风 中允许当前终端")
        sys.exit(1)

    threading.Thread(target=worker, daemon=True).start()

    print("=" * 60)
    print("🚀 Jot-Local 独立版已就绪")
    print(f"⌨️ 按住【{HOTKEY_LABEL}】说话，松手自动打字到光标所在处")
    print(f"🎙️ 识别：SenseVoice-Small（{engine.device()}）")
    if qwen_ok:
        print(f"🧠 清洗：{engine.QWEN_MODEL}")
    else:
        print(f"⚠️ 未连上 Ollama，只用规则清洗（口头禅和标准改口能处理，复杂改口会弱一些）（ollama pull {engine.QWEN_MODEL} 后重启即可）")
    if IS_MAC:
        print("ℹ️ 首次使用需在 系统设置 → 隐私与安全性 里给终端开启「输入监控」和「辅助功能」")
    print("🛡️ 全程离线，Ctrl+C 退出")
    print("=" * 60)

    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    except KeyboardInterrupt:
        pass
    finally:
        stream.stop()
        print("\n已退出")


if __name__ == "__main__":
    main()
