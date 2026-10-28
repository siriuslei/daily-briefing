"""更新 GitHub Pages 倍速播放页：把新一期加入 site/<token>/，只保留最近 KEEP_DAYS 天。

用法: python -m briefing.pages site out
"""
import datetime as dt
import json
import os
import shutil
import sys

KEEP_DAYS = 21
HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    site, out = sys.argv[1], sys.argv[2]
    token = os.environ["PAGES_TOKEN"]
    meta = json.load(open(os.path.join(out, "meta.json"), encoding="utf-8"))
    base = os.path.join(site, token)
    os.makedirs(os.path.join(base, "audio"), exist_ok=True)

    shutil.copy(os.path.join(out, meta["name"] + ".mp3"), os.path.join(base, "audio", meta["name"] + ".mp3"))
    shutil.copy(os.path.join(out, meta["name"] + ".md"), os.path.join(base, "audio", meta["name"] + ".md"))

    idx_path = os.path.join(base, "episodes.json")
    eps = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else []
    eps = [e for e in eps if e["name"] != meta["name"]]
    eps.append({"name": meta["name"], "date": meta["date"], "slot_cn": meta["slot_cn"], "theme": meta["theme"],
                "outline": meta["outline"]})
    cutoff = (dt.date.today() - dt.timedelta(days=KEEP_DAYS)).isoformat()
    for e in [e for e in eps if e["date"] < cutoff]:
        for ext in (".mp3", ".md"):
            p = os.path.join(base, "audio", e["name"] + ext)
            if os.path.exists(p):
                os.remove(p)
    eps = sorted([e for e in eps if e["date"] >= cutoff], key=lambda e: e["name"], reverse=True)
    json.dump(eps, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    shutil.copy(os.path.join(HERE, "player.html"), os.path.join(base, "index.html"))
    with open(os.path.join(site, "index.html"), "w") as f:
        f.write("<!doctype html><meta name=robots content=noindex><title>404</title>Not found")
    with open(os.path.join(site, "robots.txt"), "w") as f:
        f.write("User-agent: *\nDisallow: /\n")
    open(os.path.join(site, ".nojekyll"), "w").close()
    print(f"播放页已更新，共 {len(eps)} 期")


if __name__ == "__main__":
    main()
