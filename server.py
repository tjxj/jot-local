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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

import engine

PORT = int(os.environ.get("JOT_LOCAL_PORT", "8080"))


def run_sensevoice(audio_bytes):
    """音频听写，失败返回空串（Jot 会按无语音处理，不会打出错误文字）"""
    try:
        return engine.transcribe_bytes(audio_bytes)
    except Exception as e:
        print(f"[ASR 运行异常] {e}")
        return ""


def cleanup_prompt_raw(prompt):
    """从 Jot 自带清洗提示词里取出原文（格式为 ...RAW: <原文>\nCLEAN:）"""
    m = re.search(r"RAW: (.*)\nCLEAN:\s*$", prompt, re.S)
    return m.group(1).strip() if m else None


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

                raw_text = run_sensevoice(audio_bytes)
                print(f"[ASR 原始初稿] {raw_text}")

                output_text = engine.qwen_clean(raw_text, vocab)
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

                raw_text = run_sensevoice(audio_bytes)
                output_text = engine.qwen_clean(raw_text, vocab)
            except Exception as e:
                print(f"[Transcribe 异常] {e}")
                output_text = ""

        elif "cleanup" in self.path or "flash-lite" in self.path:
            try:
                parts = req_data.get("contents", [{}])[0].get("parts", [{}])
                prompt = parts[0].get("text", "")
                raw = cleanup_prompt_raw(prompt)
                # 听写阶段已经用 Qwen 清洗过，这里原样返回，避免二次改写和额外等待
                output_text = raw if raw is not None else engine.qwen_generate(prompt)
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
    print("正在加载模型，首次运行会自动下载 SenseVoice（约 900MB）...")
    asr_ok, qwen_ok = engine.warmup()
    if not asr_ok:
        print("❌ SenseVoice 加载失败，请检查依赖安装后重试")
        sys.exit(1)

    server_address = ("127.0.0.1", PORT)
    httpd = ThreadingHTTPServer(server_address, JotLocalHandler)
    print("=" * 60)
    print(f"🚀 Jot 本地离线服务端已启动: http://127.0.0.1:{PORT}")
    print(f"🎙️ ASR 引擎: SenseVoice-Small（{engine.device()}，已预热）")
    if qwen_ok:
        print(f"🧠 LLM 引擎: {engine.QWEN_MODEL}（已预热）")
    else:
        print(f"⚠️ 未连上 Ollama，改口识别不可用，只做基础口头禅过滤")
        print(f"   开启方式: ollama pull {engine.QWEN_MODEL}，再确保 Ollama 在运行")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已关闭")

if __name__ == "__main__":
    main()
