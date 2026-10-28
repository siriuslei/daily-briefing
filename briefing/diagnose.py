"""诊断 Gemini key：对几个模型分别试有/无谷歌搜索，打印完整错误。"""
import json
import os
import urllib.error
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta/models"
for model in ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-flash-latest"]:
    for search in (False, True):
        body = {"contents": [{"role": "user", "parts": [{"text": "用一句话说今天的日期"}]}]}
        if search:
            body["tools"] = [{"google_search": {}}]
        req = urllib.request.Request("%s/%s:generateContent" % (BASE, model), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", "x-goog-api-key": os.environ["GEMINI_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                print(model, "search" if search else "plain", "OK")
        except urllib.error.HTTPError as e:
            print(model, "search" if search else "plain", e.code, e.read().decode(errors="ignore")[:1500])
