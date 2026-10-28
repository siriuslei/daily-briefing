"""Gemini REST 调用（带 Google 搜索落地），只用标准库。"""
import json
import os
import time
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def generate(prompt, search=True, temperature=0.7, max_tokens=8192, retries=6):
    """返回 (正文, 来源列表[{title, uri}])。"""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
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
