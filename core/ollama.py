import json, urllib.request
from core.config import OLLAMA

def call_ollama_keywords(title: str, body: str, max_total_chars: int = 50, seeds: str | None = None) -> str | None:
    if not OLLAMA.get("enable"):
        return None
    model = OLLAMA.get("model", "qwen2.5:latest")
    timeout = int(OLLAMA.get("timeout_sec", 30))
    seeds = (seeds or "").strip()

    prompt = (
        "你是中文关键词提取助手。基于“标题+正文节选”输出中文关键词，要求："
        "1) 只输出关键词，逗号分隔；2) 总长度<={max_len}字；3) 如果提供了“用户指定关键词(seeds)”，"
        "必须把 seeds 放在最前面（保持原顺序），再补充其他概括性关键词；4) 不要解释。"
        f"\nseeds: {seeds if seeds else '(无)'}"
        f"\n标题: {title[:80]}"
        f"\n正文节选: {body[:800]}"
        "\n输出："
    ).replace("{max_len}", str(max_total_chars))

    data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=data, headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            x = json.loads(resp.read().decode("utf-8"))
            out = (x.get("response") or "").strip().strip("，, \n")
            if seeds:
                if out:
                    pure = out
                    for tok in [s.strip() for s in seeds.split(";") if s.strip()]:
                        pure = pure.replace(tok, "")
                    out = (seeds + ", " + pure).strip("，, \n")
                else:
                    out = seeds
            if len(out) > max_total_chars:
                out = out[:max_total_chars]
            return out
    except Exception:
        return None
