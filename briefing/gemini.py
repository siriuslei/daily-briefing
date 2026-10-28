"""Gemini REST 调用（带 Google 搜索落地），只用标准库。"""
import json
import os
import re
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_model = None


def pick_model():
    """优先用 GEMINI_MODEL；否则从可用模型里选最新的 flash（旧型号下线后自动跟进）。"""
    global _model
    if _model:
        return _model
    want = os.environ.get("GEMINI_MODEL", "").strip()
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                                 headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        models = [m["name"].split("/", 1)[1] for m in json.load(r).get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", [])]
    if want in models:
        _model = want
    else:
        def score(n):
            nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", n.split("-")[1])] if "-" in n else [0]
            return (nums[0] if nums else 0, "preview" not in n and "exp" not in n, "latest" in n)
        flash = [m for m in models if m.startswith("gemini-") and "flash" in m and "lite" not in m
                 and not any(k in m for k in ("image", "tts", "audio", "live", "embedding", "thinking"))]
        _model = max(flash or models, key=score)
    print("使用模型:", _model)
    return _model


def generate(prompt, search=True, temperature=0.7, max_tokens=8192, retries=6):
    """返回 (正文, 来源列表[{title, uri}])。"""
    model = pick_model()
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if search:
        body["tools"] = [{"google_search": {}}]
    req = urllib.request.Request(
        API.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    delay = 15
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.load(r)
            cand = data["candidates"][0]
            text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
            if not text.strip():
                raise ValueError("empty response: %s" % cand.get("finishReason"))
            chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
            sources = [c["web"] for c in chunks if "web" in c]
            return text.strip(), sources
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="ignore")[:300]
            if e.code not in (429, 500, 502, 503, 504) or attempt == retries - 1:
                raise RuntimeError("Gemini %s: %s" % (e.code, msg))
            print("Gemini %s, retry in %ss" % (e.code, delay))
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            if attempt == retries - 1:
                raise
            print("Gemini error %r, retry in %ss" % (e, delay))
        time.sleep(delay)
        delay = min(delay * 2, 120)
