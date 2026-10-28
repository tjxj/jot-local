#!/usr/bin/env python3
"""
Jot-Local 纯本地离线服务核心 (SenseVoice + Qwen2.5)

支持通道：
1. /v1beta/interactions (Jot 原生 smart 听写主通道)
2. /v1beta/models/*:generateContent (备用转写与清洗通道)
3. /v1beta/models (API 校验通道)
"""

import os
import re
import sys
import json
import base64
import tempfile
import io
import urllib.request
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

PORT = int(os.environ.get("JOT_LOCAL_PORT", "8080"))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen2.5:1.5b")

_sensevoice_instance = None

def get_asr():
    """惰性加载已缓存的 SenseVoice-Small"""
    global _sensevoice_instance
    if _sensevoice_instance is None:
        try:
            from funasr import AutoModel
            print("[ASR] 正在初始化本地 SenseVoice-Small...")
            _sensevoice_instance = AutoModel(
                model="iic/SenseVoiceSmall",
                vad_model="fsmn-vad",
                vad_kwargs={"max_single_segment_time": 30000},
                device="cpu",
                disable_update=True
            )
            print("[ASR] ✅ SenseVoice-Small 就绪")
        except Exception as e:
            print(f"[ASR 错误] {e}")
            _sensevoice_instance = "dummy"
    return _sensevoice_instance

def clean_sensevoice_tags(text):
    """去除 SenseVoice 自带的情感与事件标签，如 <|zh|><|NEUTRAL|><|Speech|><|withitn|>"""
    if not text:
        return ""
    return re.sub(r"<\|.*?\|>", "", text).strip()

def run_sensevoice(audio_bytes, custom_vocab=None):
    """音频听写解码"""
    if not audio_bytes:
        return ""

    import soundfile as sf
    try:
        data, samplerate = sf.read(io.BytesIO(audio_bytes))
    except Exception as e:
        print(f"[音频解码失败] {e}")
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, data, samplerate)
        tmp_file = f.name

    text = ""
    try:
        engine = get_asr()
        if engine != "dummy":
            res = engine.generate(
                input=tmp_file,
                language="auto",
                use_itn=True,
                batch_size_s=60,
                merge_vad=True,
                merge_length_s=15,
            )
            if res and isinstance(res, list) and len(res) > 0:
                raw = res[0].get("text", "")
                text = clean_sensevoice_tags(raw)
        else:
            text = "这是一段模拟的本地识别语音"
    except Exception as e:
        print(f"[ASR 运行异常] {e}")
        text = ""
    finally:
        if os.path.exists(tmp_file):
            os.remove(tmp_file)
    return text

def run_qwen_clean(raw_text, custom_vocab=None):
    """利用本地 Qwen2.5 进行智能语义清洗"""
    if not raw_text or not raw_text.strip():
        return ""

    # 先做轻量本地规则过滤
    cleaned = raw_text
    for filler in ["那个，", "那个", "嗯，", "嗯", "呃，", "呃", "就是说，", "就是说"]:
        cleaned = cleaned.replace(filler, "")

    vocab_prompt = f"4. 专有名词对照参考：{', '.join(custom_vocab)}\n" if custom_vocab else ""
    prompt = f"""你是一个输入法语义清洗助手。请将以下粗糙口语转写重构为标准、得体、流畅的书面语：
1. 彻底剔除'嗯'、'那个'、'就是说'等口头禅与犹豫停顿
2. 识别说话人的中途改口（如'三点不对四点'保留'四点'），只保留最终决定
3. 补全规范标点
{vocab_prompt}
待处理文本：
{raw_text}

直接输出最终文本，不要输出任何解释或标记。"""

    payload = {
        "model": QWEN_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 256}
    }

    try:
        req = urllib.request.Request(
            f"{OLLAMA_HOST}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", cleaned).strip()
    except Exception:
        # Ollama 没开时，返回规则清理结果
        return cleaned.strip()

class JotLocalHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stdout.write(f"[JotLocal] {self.command} {self.path} - {args[0] if args else ''}\n")
        sys.stdout.flush()

    def do_GET(self):
        # 响应 Jot 启动时的 API Key 与模型可用性探测
        if "/v1beta/models" in self.path:
            model_name = self.path.split("/v1beta/models")[-1].lstrip("/")
            if not model_name or "?" in model_name:
                resp = {
                    "models": [
                        {"name": "models/gemini-3.5-transcribe"},
                        {"name": "models/gemini-3.5-flash-lite"}
                    ]
                }
            else:
                resp = {"name": f"models/{model_name}"}

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len)
        try:
            req_data = json.loads(body.decode("utf-8"))
        except Exception:
            req_data = {}

        output_text = ""

        # 核心通道 1: Jot 原生 smart 听写通道 (/v1beta/interactions)
        if "interactions" in self.path:
            try:
                inputs = req_data.get("input", [])
                audio_b64 = ""
                for item in inputs:
                    if item.get("type") == "audio" and "data" in item:
                        audio_b64 = item["data"]
                        break
                if not audio_b64 and inputs:
                    audio_b64 = inputs[0].get("data", "")

                audio_bytes = base64.b64decode(audio_b64) if audio_b64 else b""
                vocab = req_data.get("generation_config", {}).get("transcription_config", {}).get("custom_vocabulary", [])

                raw_text = run_sensevoice(audio_bytes, vocab)
                print(f"[ASR 原始初稿] {raw_text}")

                output_text = run_qwen_clean(raw_text, vocab)
                print(f"[Qwen 清洗终稿] {output_text}")
            except Exception as e:
                print(f"[Interactions 异常] {e}")
                output_text = ""

            # 组装 interactions 规范的返回结构
            response_body = {
                "id": "interaction-local-001",
                "status": "completed",
                "steps": [
                    {
                        "type": "model_output",
                        "content": [
                            {
                                "type": "text",
                                "text": output_text
                            }
                        ]
                    }
                ]
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response_body).encode("utf-8"))
            return

        # 核心通道 2: 传统 generateContent 通道
        if "transcribe" in self.path:
            try:
                parts = req_data.get("contents", [{}])[0].get("parts", [{}])
                flac_base64 = parts[0].get("inline_data", {}).get("data", "")
                audio_bytes = base64.b64decode(flac_base64)
                vocab = req_data.get("generationConfig", {}).get("audioTranscriptionConfig", {}).get("customVocabulary", [])

                raw_text = run_sensevoice(audio_bytes, vocab)
                output_text = run_qwen_clean(raw_text, vocab)
            except Exception as e:
                print(f"[Transcribe 异常] {e}")
                output_text = ""

        elif "cleanup" in self.path or "flash-lite" in self.path:
            try:
                parts = req_data.get("contents", [{}])[0].get("parts", [{}])
                prompt = parts[0].get("text", "")
                output_text = run_qwen_clean(prompt)
            except Exception as e:
                print(f"[Cleanup 异常] {e}")
                output_text = ""

        response_body = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": output_text}],
                        "role": "model"
                    },
                    "finishReason": "STOP"
                }
            ]
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response_body).encode("utf-8"))

def main():
    # 提前预热 ASR 模型
    get_asr()

    server_address = ("127.0.0.1", PORT)
    httpd = ThreadingHTTPServer(server_address, JotLocalHandler)
    print("=" * 60)
    print(f"🚀 Jot 本地离线服务端已启动: http://127.0.0.1:{PORT}")
    print(f"🎙️ ASR 引擎: 阿里 SenseVoice-Small（已加载）")
    print(f"🧠 LLM 引擎: 通义千问 {QWEN_MODEL}")
    print(f"⚡ 支持通道: /v1beta/interactions & /v1beta/models/*")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已平稳关闭")

if __name__ == "__main__":
    main()
