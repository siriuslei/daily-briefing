"""朗读稿 → mp3（edge-tts，分段合成后按帧拼接，避免单次请求过长）。

用法: python -m briefing.tts out/<name>.txt out/<name>.mp3
"""
import asyncio
import os
import re
import sys

import edge_tts

VOICE = os.environ.get("TTS_VOICE", "zh-CN-YunxiNeural")
RATE = os.environ.get("TTS_RATE", "+5%")


def chunks(text, limit=1500):
    buf = ""
    for para in re.split(r"\n\s*\n", text):
        if buf and len(buf) + len(para) > limit:
            yield buf
            buf = ""
        buf = (buf + "\n\n" + para).strip()
    if buf:
        yield buf


async def synth(text, out):
    with open(out, "wb") as f:
        for i, part in enumerate(chunks(text)):
            for attempt in range(4):
                try:
                    audio = b""
                    async for msg in edge_tts.Communicate(part, VOICE, rate=RATE).stream():
                        if msg["type"] == "audio":
                            audio += msg["data"]
                    f.write(audio)
                    break
                except Exception as e:  # 网络抖动重试
                    if attempt == 3:
                        raise
                    print(f"  段 {i} 失败 {e!r}，重试")
                    await asyncio.sleep(5 * (attempt + 1))


def main():
    src, out = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as f:
        asyncio.run(synth(f.read(), out))
    size = os.path.getsize(out)
    print(f"音频完成：{out}，{size/1e6:.1f} MB，约 {size*8/48000/60:.1f} 分钟")


if __name__ == "__main__":
    main()
