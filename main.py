# main.py 修复完整版
import os
import subprocess
import textwrap
import time
import json

import requests
from deep_translator import GoogleTranslator
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydub import AudioSegment
from starlette.responses import FileResponse

# ====================== 核心配置 ======================
VOICE_MAP = {
    "jack": "en-US-GuyNeural",
    "rose": "en-US-AriaNeural",
}
BACKGROUND_IMAGE = "bg.jpg"
OUTPUT_VIDEO = "final_video.mp4"
IMAGE_FOLDER = "scene_images"

CALL_API = False

# --- ASR & Image Generation Config ---
API_KEY = ""
WORKSPACE_ID = ""

# --- OpenRouter LLM 配置 ---
OPENROUTER_API_KEY = ""
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "stepfun/step-3.5-flash:free"

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


# ------------------------------------------------------------------------------
# LLM 改写
# ------------------------------------------------------------------------------
def llm_rewrite_text2(original_text: str) -> str:
    start_time = time.time()
    print("\n[LLM] 开始调用大模型文本改写...")

    if not OPENROUTER_API_KEY:
        print("[LLM] 未配置 API Key，直接返回原文")
        return original_text

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    prompt = f"""
请你对下面的文本进行改写，保持原意、口语化、字数相近。
必须输出 JSON 格式：{{"content": ["句子1", "句子2", ...]}}
每行一个完整句子。

原文：
{original_text}
""".strip()

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 2048
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()

        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        json_str = content[json_start:json_end]

        data = json.loads(json_str)
        lines = data.get("content", [])
        rewritten = "\n".join([line.strip() for line in lines if line.strip()])
        cost = round(time.time() - start_time, 2)
        print(f"[LLM] ✅ 改写完成，耗时：{cost}s")
        return rewritten

    except Exception as e:
        print(f"[LLM] 改写失败：{e}, 返回原始内容~")
        return original_text


# ------------------------------------------------------------------------------
# LLM 改写 【修复：只改写、不翻译，保持原语言】
# ------------------------------------------------------------------------------
def llm_rewrite_text3(original_text: str) -> str:
    start_time = time.time()
    print("\n[LLM] 开始调用大模型文本改写...")

    if not OPENROUTER_API_KEY:
        print("[LLM] 未配置 API Key，直接返回原文")
        return original_text

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # 🔥 超级强化：强制要求 只改写、不翻译、保持原语言
    prompt = f"""
You are a text optimizer. Please follow these rules strictly:
1. ONLY PARAPHRASE the text, DO NOT translate.
2. Keep the original meaning.
3. Keep the original language (English remains English, Chinese remains Chinese).
4. Make the expression smoother, more natural, more fluent.
5. Split into complete sentences, one per line.
6. Output MUST be valid JSON only, no extra text.
7. JSON format: {{"content": ["sentence 1", "sentence 2", "sentence 3"]}}

Text to paraphrase:
{original_text}
""".strip()

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "max_tokens": 2048
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()

        # 安全提取 JSON
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        json_str = content[json_start:json_end]

        data = json.loads(json_str)
        lines = data.get("content", [])
        rewritten = "\n".join([line.strip() for line in lines if line.strip()])

        cost = round(time.time() - start_time, 2)
        print(f"[LLM] ✅ 改写完成，耗时：{cost}s")
        return rewritten

    except Exception as e:
        print(f"[LLM] 改写失败：{e}, 返回原始内容~")
        return original_text


# ------------------------------------------------------------------------------
# LLM 改写 【修复：兼容 content=None 场景，强制输出到 content】
# ------------------------------------------------------------------------------
def llm_rewrite_text4(original_text: str) -> str:
    start_time = time.time()
    print("\n[LLM] 开始调用大模型文本改写...")

    if not OPENROUTER_API_KEY:
        print("[LLM] 未配置 API Key，直接返回原文")
        return original_text

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # 🔥 强化 Prompt：强制模型把改写结果输出到 content，不要放在 reasoning 里
    prompt = f"""
You are a text optimizer. Follow these rules STRICTLY:
1. ONLY PARAPHRASE the text, DO NOT translate. Keep the original language (English→English, Chinese→Chinese).
2. Keep the original meaning, make expression smoother and natural.
3. Split into complete sentences, one per line.
4. YOUR OUTPUT MUST BE ONLY VALID JSON, NO extra text, NO reasoning, NO explanations.
5. JSON format: {{"content": ["sentence 1", "sentence 2", ...]}}

Text to paraphrase:
{original_text}
""".strip()

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,  # 降低温度，让输出更稳定、更遵守格式
        "max_tokens": 2048
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=60)
        resp.raise_for_status()
        result = resp.json()

        # 🔥 安全读取 content：优先 content，为空则尝试读取 reasoning
        message = result["choices"][0]["message"]
        content = message.get("content")
        if content is None:
            content = message.get("reasoning", "")
        if not content:
            raise ValueError("模型未返回任何有效内容")

        content = content.strip()

        # 安全提取 JSON
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        if json_start == -1 or json_end == 0:
            raise ValueError("未找到有效的 JSON 格式内容")
        json_str = content[json_start:json_end]

        data = json.loads(json_str)
        lines = data.get("content", [])
        rewritten = "\n".join([line.strip() for line in lines if line.strip()])

        cost = round(time.time() - start_time, 2)
        print(f"[LLM] ✅ 改写完成，耗时：{cost}s")
        return rewritten

    except Exception as e:
        print(f"[LLM] 改写失败：{e}, 返回原始内容~")
        return original_text


def llm_rewrite_text5(original_text: str) -> str:
    start_time = time.time()
    print("\n[LLM] 开始调用大模型文本改写...")

    if not OPENROUTER_API_KEY:
        print("[LLM] 未配置 API Key，直接返回原文")
        return original_text.strip()

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # 极简高压指令：禁止推理、禁止解释、只原样语言改写、只输出JSON
    prompt = """Strict rules:
1. Only paraphrase, NEVER translate. Same language only.
2. Keep original meaning, smooth natural dialogue.
3. Output ONLY pure JSON, no explanation, no reasoning, no extra words.
4. Format exactly: {"content":["sent1","sent2"]}

Text:
""" + original_text

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4096,  # 扩容防截断
        "stop": ["\n\nReason", "explanation:"]
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=90)
        resp.raise_for_status()
        result = resp.json()

        msg = result["choices"][0]["message"]
        # 丢弃reasoning垃圾，只拿正规content
        raw = msg.get("content")
        if not raw:
            print("[LLM 警告] content为空，模型截断/跑偏，直接返回原文")
            return original_text

        raw = raw.strip()
        # 安全截取JSON
        s_idx = raw.find("{")
        e_idx = raw.rfind("}")
        if s_idx == -1 or e_idx == -1:
            raise ValueError("无合法JSON边界")

        json_str = raw[s_idx:e_idx + 1]
        arr = json.loads(json_str).get("content", [])
        ok_txt = "\n".join([x.strip() for x in arr if x.strip()])

        cost = round(time.time() - start_time, 2)
        print(f"[LLM] ✅ 改写成功 耗时:{cost}s")
        return ok_txt

    except Exception as e:
        print(f"[LLM] 改写异常/截断/格式错误:{str(e)}，兜底返回原文")
        return original_text


def llm_rewrite_text6(original_text: str) -> str:
    start_time = time.time()
    print("\n[LLM] 开始调用大模型文本改写...")

    if not OPENROUTER_API_KEY:
        print("[LLM] 未配置 API Key，直接返回原文")
        return original_text.strip()

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # 极简指令：强制模型把结果塞进 content，禁止任何思考
    prompt = """
RULES:
1. ONLY PARAPHRASE, NO TRANSLATION. Keep original language.
2. Output ONLY JSON, NO reasoning, NO explanation, NO extra text.
3. Format: {"content":["sent1","sent2",...]}

Text:
""" + original_text

    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,  # 极度保守，减少发散
        "max_tokens": 4096,
        "stream": False
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=120)
        resp.raise_for_status()
        res = resp.json()

        msg = res["choices"][0]["message"]
        raw = msg.get("content")

        # 兜底：如果 content 为空，尝试从 reasoning 里捞 JSON（最后手段）
        if not raw:
            print("[LLM 警告] content 为空，尝试从 reasoning 提取 JSON...")
            reasoning = msg.get("reasoning", "")
            # 从 reasoning 里找 {...}
            s = reasoning.find("{")
            e = reasoning.rfind("}")
            if s != -1 and e != -1:
                raw = reasoning[s:e + 1]
            else:
                print("[LLM 严重警告] 无法提取任何 JSON，直接返回原文")
                return original_text

        # 清洗并解析 JSON
        raw = raw.strip()
        s_idx = raw.find("{")
        e_idx = raw.rfind("}")
        if s_idx == -1 or e_idx == -1:
            raise ValueError("未找到合法 JSON 边界")

        json_str = raw[s_idx:e_idx + 1]
        arr = json.loads(json_str).get("content", [])
        final = "\n".join([x.strip() for x in arr if x.strip()])

        cost = round(time.time() - start_time, 2)
        print(f"[LLM] ✅ 改写成功，耗时: {cost}s")
        return final

    except Exception as e:
        print(f"[LLM] 改写失败: {e}，返回原文")
        return original_text

    # ------------------------------------------------------------------------------


def llm_rewrite_text(original_text: str) -> str:
    start_time = time.time()
    print("\n[LLM] 开始英文纯改写(不许翻译)...")
    raw_txt = original_text.strip()
    if not raw_txt:
        return original_text

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    # 极致高压指令，杜绝废话
    prompt = """Hard Rules:
1. Only paraphrase English, DO NOT translate. Keep English only.
2. Output ONLY clean JSON: {"content":["line1","line2"...]}
3. No thinking, no explanation, no extra words outside JSON.

Text:
""" + raw_txt

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.05,
        "max_tokens": 8092,  # 扩容防截断
        "stop": ["\n\nReason", "explanation:"],
        "timeout": 120
    }

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        res_json = resp.json()
        msg = res_json["choices"][0]["message"]

        # 1.优先拿content
        out = msg.get("content", "")
        # 2.content空 → 强制从reasoning捞
        if not out:
            print("[警告] content为空，立刻抓取reasoning中的JSON...")
            out = msg.get("reasoning", "")

        # 精准抠 { ... }
        left = out.find("{")
        right = out.rfind("}")
        if left == -1 or right == -1:
            raise Exception("全文找不到合法JSON包围符")

        pure_json = out[left:right + 1]
        data = json.loads(pure_json)
        arr = data.get("content", [])
        final_str = "\n".join([x.strip() for x in arr if x.strip()])

        print(f"[成功] 改写完成，耗时{round(time.time() - start_time, 2)}s")
        return final_str

    except Exception as e:
        print(f"[改写异常精准日志]: {str(e)}")
        # 最坏兜底：返回原文不崩流程
        return original_text


# ASR
# ------------------------------------------------------------------------------
def call_alibaba_asr(audio_file_path: str) -> str:
    start_time = time.time()
    print(f"\n[耗时日志] 开始调用阿里ASR语音识别...")

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    with open(audio_file_path, 'rb') as f:
        file_response = requests.post("https://dashscope.aliyuncs.com/api/v1/uploads",
                                      headers=headers, data={"purpose": "asr"}, files={"file": f})
        file_response.raise_for_status()
        upload_url = file_response.json()['data']['url']

    payload = {
        "model": "paraformer-realtime-v1",
        "input": upload_url,
        "parameters": {"format": "txt", "response_format": "plain_text"}
    }

    create_task_response = requests.post("https://dashscope.aliyuncs.com/api/v1/services/asr/sync-infer",
                                         json=payload, headers=headers)
    create_task_response.raise_for_status()
    result_data = create_task_response.json()

    if result_data['code'] != 'Success':
        raise HTTPException(status_code=500, detail="ASR失败")

    task_id = result_data['output']['task_id']
    status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

    while True:
        time.sleep(5)
        status_response = requests.get(status_url, headers=headers)
        status_data = status_response.json()
        task_status = status_data['output']['task_status']

        if task_status == 'SUCCEEDED':
            cost = round(time.time() - start_time, 2)
            print(f"[耗时日志] ✅ ASR识别完成，耗时：{cost}s")
            return status_data['output']['result']
        elif task_status == 'FAILED':
            raise HTTPException(status_code=500, detail="ASR任务失败")


def translate_text(text):
    # 空内容直接返回
    if not text or not text.strip():
        return ""

    try:
        # 强制清理空白 + 严格英译中
        clean_text = text.strip()
        translated = GoogleTranslator(source='en', target='zh-CN').translate(clean_text)
        print(f"【翻译成功】英文: {clean_text}")
        print(f"【翻译成功】中文: {translated}")
        return translated
    except Exception as e:
        print(f"【翻译失败】: {e} → 返回英文原文")
        return text


def get_audio_duration(file_path):
    try:
        return len(AudioSegment.from_file(file_path)) / 1000
    except:
        return 3.0


# ------------------------------------------------------------------------------
# 核心：自动给纯文本添加默认说话人（修复空音频问题）
# ------------------------------------------------------------------------------
def add_default_speaker(content: str) -> str:
    lines = content.strip().split("\n")
    new_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            new_lines.append(f"jack: {line}")
        else:
            new_lines.append(line)
    return "\n".join(new_lines)


# ------------------------------------------------------------------------------
# 视频生成流水线
# ------------------------------------------------------------------------------
async def run_video_generation_pipeline(dialogue_file_path: str):
    total_start = time.time()
    print("\n=============================================")
    print(f"🚀 开始执行视频生成全流程")
    print("=============================================\n")

    from edge_tts import Communicate

    async def text_to_speech(text, voice, path):
        await Communicate(text, voice=voice).save(path)

    def parse_line(line):
        if ":" not in line:
            return None, line.strip()
        s, c = line.split(":", 1)
        return s.strip().lower(), c.strip()

    # ===================== 读取文本并自动添加说话人 =====================
    with open(dialogue_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    content = add_default_speaker(content)
    lines = content.strip().split("\n")

    audios = []
    tts_start = time.time()
    print(f"[阶段1] 开始TTS语音合成...")

    for idx, line in enumerate(lines, 1):
        sp, ct = parse_line(line)
        if not ct:
            continue

        # 如果没有角色，默认用 jack
        if sp is None or sp not in VOICE_MAP:
            sp = "jack"

        fn = f"audio_{idx}_{sp}.mp3"
        await text_to_speech(ct, VOICE_MAP[sp], fn)
        translated_text = translate_text(ct)
        audios.append({
            "index": idx,
            "speaker": sp,
            "text": ct,
            "translation": translated_text,
            "audio_file": fn
        })

    # ===================== 【超级修复】空音频直接报错 =====================
    if not audios:
        raise HTTPException(status_code=400, detail="没有可合成的语音，请检查文本格式！")

    tts_cost = round(time.time() - tts_start, 2)
    print(f"[阶段1] ✅ TTS 完成，总耗时：{tts_cost}s\n")

    # --- 音频拼接 ---
    merge_start = time.time()
    print(f"[阶段2] 开始拼接音频...")

    def merge_all_audio(audio_files, output="full_audio.mp3"):
        full = AudioSegment.empty()
        for f in audio_files:
            full += AudioSegment.from_file(f["audio_file"])
        full.export(output, format="mp3")
        return output

    full_a = merge_all_audio(audios)
    merge_cost = round(time.time() - merge_start, 2)
    print(f"[阶段2] ✅ 音频拼接完成\n 合成耗时：{merge_cost}")

    # --- 字幕 ---
    sub_start = time.time()
    print(f"[阶段3] 生成字幕...")

    def generate_double_ass(audio_files):
        def fmt(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            cs = int((t - int(t)) * 100)
            return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

        ass_header = """[Script Info]
Title: Dual Language Subtitles
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
"""
        style_en = "Style: English,Microsoft YaHei,28,&H00FFFFFF,&H000000FF,&H80000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,40,1"
        style_cn = "Style: Chinese,Microsoft YaHei,36,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,1,0,8,10,10,80,1"

        with open("subtitle_en.ass", "w", encoding="utf-8") as f_en, \
                open("subtitle_cn.ass", "w", encoding="utf-8") as f_cn:
            f_en.write(
                ass_header + style_en + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            f_cn.write(
                ass_header + style_cn + "\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

            cur = 0.0
            for item in audio_files:
                text = item['text']
                translation = item['translation']
                lines_wrapped = textwrap.wrap(translation, width=20)
                formatted_text = r"\N".join(lines_wrapped)
                duration = get_audio_duration(item["audio_file"])
                start_time = fmt(cur)
                end_time = fmt(cur + duration)
                f_en.write(f"Dialogue: 0,{start_time},{end_time},English,,0,0,0,,{{\\fad(200,200)}}{text}\n")
                f_cn.write(f"Dialogue: 0,{start_time},{end_time},Chinese,,0,0,0,,{{\\fad(200,200)}}{formatted_text}\n")
                cur += duration
        return "subtitle_en.ass", "subtitle_cn.ass"

    en_sub, cn_sub = generate_double_ass(audios)
    print(f"[阶段3] ✅ 字幕生成完成\n")

    # --- 场景 ---
    def generate_all_scene_images(audio_files):
        scenes = []
        for item in audio_files:
            scenes.append({"image": BACKGROUND_IMAGE, "duration": get_audio_duration(item["audio_file"])})
        return scenes

    scenes = generate_all_scene_images(audios)
    print(f"[阶段4] ✅ 场景处理完成\n")

    # --- FFmpeg ---
    print(f"[阶段5] 开始FFmpeg视频合成...")

    def make_video_with_scenes(scene_files, audio, en_sub, cn_sub, output):
        total_dur = get_audio_duration(audio)
        cmd = ["ffmpeg", "-y"]
        for s in scene_files:
            cmd.extend(["-loop", "1", "-t", str(s["duration"]), "-i", s["image"]])
        cmd.extend(["-i", audio, "-i", "bgm.mp3"])

        filter_complex_parts = [
            f"concat=n={len(scene_files)}:v=1:a=0[v_concat]",
            "[v_concat]scale=1280:720[v_scaled]",
            "[v_scaled]zoompan=z='min(zoom+0.001,1.2)':x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':d=25*duration[v_zoom]",
            f"[v_zoom]ass={cn_sub}[v_sub_cn]",
            f"[v_sub_cn]ass={en_sub}[v_final]",
            f"[{len(scene_files)}:a]volume=1.0[voice]",
            f"[{len(scene_files) + 1}:a]volume=0.18[bgm]",
            "[voice][bgm]amix=inputs=2:duration=first[a_final]"
        ]

        cmd.extend([
            "-filter_complex", ";".join(filter_complex_parts),
            "-map", "[v_final]", "-map", "[a_final]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-t", str(total_dur), output
        ])
        subprocess.run(cmd, check=True, capture_output=True)

    make_video_with_scenes(scenes, full_a, en_sub, cn_sub, OUTPUT_VIDEO)
    print(f"[阶段5] ✅ FFmpeg视频合成完成\n")

    # --- 清理 ---
    for audio_info in audios:
        try:
            os.remove(audio_info["audio_file"])
        except:
            pass

    total_cost = round(time.time() - total_start, 2)
    print("=============================================")
    print(f"✅ 视频生成全流程完成！总耗时：{total_cost}s")
    print("=============================================\n")


# ------------------------------------------------------------------------------
# 文件读取工具
# ------------------------------------------------------------------------------
def read_file_content(file_path: str, filename: str) -> str:
    ext = filename.lower().split(".")[-1]
    try:
        if ext in ["txt", "md"]:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        elif ext in ["docx", "doc"]:
            from docx import Document
            doc = Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        elif ext in ["xlsx", "xls"]:
            import pandas as pd
            df = pd.read_excel(file_path)
            lines = []
            for _, row in df.iterrows():
                val = " ".join([str(v) for v in row if pd.notna(v)])
                if val.strip():
                    lines.append(val.strip())
            return "\n".join(lines)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
    except:
        raise HTTPException(status_code=500, detail="文件读取失败")


# ------------------------------------------------------------------------------
# 统一处理
# ------------------------------------------------------------------------------
async def process_file_to_dialogue(file: UploadFile, temp_path: str) -> str:
    filename = file.filename.lower()
    if filename.endswith((".mp3", ".wav", ".m4a")):
        text = call_alibaba_asr(temp_path)
    elif filename.endswith((".txt", ".md", ".doc", ".docx", ".xls", ".xlsx")):
        text = read_file_content(temp_path, file.filename)
        print(f"[文件读取] 成功读取文本，长度：{len(text)}")
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式")

    if not text.strip():
        raise HTTPException(status_code=400, detail="文件内容为空")

    text = llm_rewrite_text(text)
    return text


# ------------------------------------------------------------------------------
# 上传接口
# ------------------------------------------------------------------------------
@app.post("/generate/upload")
async def generate_from_upload(file: UploadFile = File(...)):
    allowed = (".mp3", ".wav", ".m4a", ".txt", ".md", ".doc", ".docx", ".xls", ".xlsx")
    if not file.filename.lower().endswith(allowed):
        raise HTTPException(status_code=400, detail="仅支持：音频、文本、文档、表格")

    temp = f"temp_{file.filename}"
    try:
        with open(temp, "wb") as f:
            f.write(await file.read())
        # TODO 根据传进来的总体内容去--> LLM -->生产不同的场景 --> 去调用生图模型得到图片 + 后面融合TTS --> 生产视频
        text = await process_file_to_dialogue(file, temp)
        dialogue_path = "dialogue_upload_file_updated.txt"

        with open(dialogue_path, "w", encoding="utf-8") as f:
            f.write(text)

        await run_video_generation_pipeline(dialogue_path)
        return JSONResponse(content={"message": "✅ 视频生成成功！"})

    finally:
        if os.path.exists(temp):
            os.remove(temp)


@app.post("/generate/record")
async def generate_from_record(audio_data: UploadFile = File(...)):
    temp = "temp_recorded.wav"
    try:
        with open(temp, "wb") as f:
            f.write(await audio_data.read())
        text = call_alibaba_asr(temp)
        text = llm_rewrite_text(text)
        with open("dialogue_record.txt", "w", encoding="utf-8") as f:
            f.write(text)
        await run_video_generation_pipeline("dialogue_record.txt")
        return JSONResponse(content={"message": "✅ 录音生成成功！"})
    finally:
        if os.path.exists(temp):
            os.remove(temp)


@app.post("/generate/default")
async def generate_from_default():
    if not os.path.exists("dialogue.txt"):
        raise HTTPException(status_code=404, detail="dialogue.txt 不存在")
    await run_video_generation_pipeline("dialogue.txt")
    return JSONResponse(content={"message": "✅ 默认视频生成成功！"})


@app.get("/")
async def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
