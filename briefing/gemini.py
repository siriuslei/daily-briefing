"""Gemini REST 调用（带 Google 搜索落地），只用标准库。"""
import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
_candidates = None


def candidates():
    """可用模型按优先级排序：GEMINI_MODEL 优先，其后新版 flash → flash-lite → 其他。
    免费档里新模型常常没有额度，遇到额度超限会依次换下一个。"""
    global _candidates
    if _candidates is not None:
        return _candidates
    req = urllib.request.Request(BASE + "?pageSize=1000", headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    with urllib.request.urlopen(req, timeout=60) as r:
        models = [m["name"].split("/", 1)[1] for m in json.load(r).get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", [])]
    models = [m for m in models if m.startswith("gemini-")
              and not any(k in m for k in ("image", "tts", "audio", "live", "embedding", "robotics", "computer"))]

    def score(n):
        v = re.match(r"gemini-(\d+(?:\.\d+)?)", n)
        tier = 2 if "flash" in n and "lite" not in n else 1 if "lite" in n else 0
        stable = "preview" not in n and "exp" not in n
        return (tier, stable, float(v.group(1)) if v else 0)

    ordered = sorted(models, key=score, reverse=True)
    want = os.environ.get("GEMINI_MODEL", "").strip()
    if want in ordered:
        ordered.remove(want)
        ordered.insert(0, want)
    _candidates = ordered
    print("候选模型:", ", ".join(ordered[:8]))
    return _candidates


def _call(model, body):
    req = urllib.request.Request(
        "%s/%s:generateContent" % (BASE, model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=150) as r:
        data = json.load(r)
    print("  [%s] %.0fs" % (model, time.time() - t0), flush=True)
    return data


def generate(prompt, search=True, temperature=0.7, max_tokens=8192, retries=5):
    """返回 (正文, 来源列表[{title, uri}])。"""
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    if search:
        body["tools"] = [{"google_search": {}}]
    cands = candidates()
    while cands:
        model = cands[0]
        delay = 15
        for attempt in range(retries):
            try:
                data = _call(model, body)
                cand = data["candidates"][0]
                text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
                if not text.strip():
                    raise ValueError("empty response: %s" % cand.get("finishReason"))
                chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
                return text.strip(), [c["web"] for c in chunks if "web" in c]
            except urllib.error.HTTPError as e:
                msg = e.read().decode(errors="ignore")
                # 额度为 0 或日额度用完：换下一个模型；分钟级限速：等一会儿重试
                if e.code == 429 and ("limit: 0" in msg or "PerDay" in msg) or e.code in (400, 403, 404):
                    print("模型 %s 不可用 (%s)，换下一个" % (model, e.code))
                    break
                if e.code not in (429, 500, 502, 503, 504):
                    raise RuntimeError("Gemini %s: %s" % (e.code, msg[:500]))
                print("%s %s，%ss 后重试" % (model, e.code, delay))
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
                print("%s 出错 %r，%ss 后重试" % (model, e, delay))
            time.sleep(delay)
            delay = min(delay * 2, 90)
        else:
            print("模型 %s 多次失败，换下一个" % model)
        cands.pop(0)
    raise RuntimeError("所有 Gemini 模型都不可用")
