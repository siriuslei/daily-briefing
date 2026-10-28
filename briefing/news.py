"""抓取新闻素材（RSS）与行情数据（Yahoo Finance），供写稿使用。只用标准库。"""
import datetime as dt
import email.utils
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/130 Safari/537.36"}


def gnews(query, lang="en"):
    """Google News RSS 搜索，限定最近一天。"""
    q = urllib.parse.quote(query + " when:1d")
    if lang == "zh":
        return f"https://news.google.com/rss/search?q={q}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    return f"https://news.google.com/rss/search?q={q}&hl=en-AU&gl=AU&ceid=AU:en"


FEEDS = {
    "australia": [
        "https://www.abc.net.au/news/feed/51120/rss.xml",
        "https://www.theguardian.com/australia-news/rss",
        gnews("Sydney OR NSW rent OR housing OR RBA OR migration"),
    ],
    "industry": [
        gnews("construction NSW OR Sydney facade OR cladding OR windows OR glazing OR balustrade"),
        gnews("Australia building approvals OR construction industry OR Building Commission NSW"),
    ],
    "china": [
        "https://feeds.bbci.co.uk/zhongwen/simp/rss.xml",
        gnews("China economy OR Beijing policy OR China Australia"),
        gnews("中国 经济 OR 政策 OR 中澳", "zh"),
    ],
    "world": [
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://www.theguardian.com/world/rss",
        gnews("Federal Reserve OR oil prices OR geopolitics"),
    ],
    "markets": [
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
        gnews("Nasdaq S&P 500 stocks OR gold price"),
    ],
}

TICKERS = {"纳斯达克综合指数": "^IXIC", "标普500指数": "^GSPC", "黄金期货(美元/盎司)": "GC=F",
           "美国10年期国债收益率": "^TNX", "澳元兑美元": "AUDUSD=X", "澳元兑人民币": "AUDCNY=X"}


def _get(url, timeout=30):
    # Yahoo 会拦截完整浏览器 UA，用简短 UA 反而能通过
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"} if "yahoo" in url else UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def fetch_feed(url, hours=36, limit=15):
    items = []
    try:
        root = ET.fromstring(_get(url))
    except Exception as e:
        print("  RSS 失败", url[:80], repr(e)[:80])
        return items
    now = dt.datetime.now(dt.timezone.utc)
    for it in root.iter("item"):
        title = _clean(it.findtext("title"))
        pub = it.findtext("pubDate")
        try:
            when = email.utils.parsedate_to_datetime(pub) if pub else None
            if when and when.tzinfo is None:
                when = when.replace(tzinfo=dt.timezone.utc)
        except (TypeError, ValueError):
            when = None
        if when and now - when > dt.timedelta(hours=hours):
            continue
        src = it.find("source")
        items.append({"title": title, "desc": _clean(it.findtext("description"))[:300],
                      "link": it.findtext("link") or "", "source": src.text if src is not None else "",
                      "time": when.strftime("%m-%d %H:%M UTC") if when else ""})
        if len(items) >= limit:
            break
    return items


def gather(category, limit=25):
    seen, out = set(), []
    for url in FEEDS[category]:
        for it in fetch_feed(url):
            key = re.sub(r"\W", "", it["title"].lower())[:40]
            if key and key not in seen:
                seen.add(key)
                out.append(it)
    return out[:limit]


def as_text(items):
    lines = []
    for i, it in enumerate(items, 1):
        desc = it["desc"] if it["desc"] and it["desc"][:30] not in it["title"] else ""
        lines.append(f"{i}. [{it['time']}] {it['title']}" + (f"（{it['source']}）" if it["source"] else "")
                     + (f"\n   {desc}" if desc else ""))
    return "\n".join(lines) or "（今天没有抓到素材）"


def market_snapshot():
    lines = []
    for name, sym in TICKERS.items():
        try:
            res = None
            for host in ("query2", "query1", "query2"):
                try:
                    url = "https://%s.finance.yahoo.com/v8/finance/chart/%s?range=1mo&interval=1d" % (host, urllib.parse.quote(sym))
                    res = json.loads(_get(url))["chart"]["result"][0]
                    break
                except Exception:
                    time.sleep(3)
            if res is None:
                raise RuntimeError("Yahoo 不可用")
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            last = closes[-1]
            chg = lambda n: (last / closes[-1 - n] - 1) * 100 if len(closes) > n else float("nan")
            f = (lambda v: f"{v:,.4f}") if last < 10 else (lambda v: f"{v:,.2f}")
            lines.append(f"{name}: 最新 {f(last)}，日 {chg(1):+.2f}%，周 {chg(5):+.2f}%，月 {(last/closes[0]-1)*100:+.2f}%，"
                         f"一个月区间 {f(min(closes))}–{f(max(closes))}")
        except Exception as e:
            print("  行情失败", sym, repr(e)[:80])
    return "\n".join(lines) or "（行情数据获取失败）"


if __name__ == "__main__":
    for c in FEEDS:
        items = gather(c)
        print(f"== {c}: {len(items)} 条")
        print(as_text(items[:5]))
    print(market_snapshot())
