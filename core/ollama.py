import json, urllib.request
from urllib.parse import urljoin
from core.config import OLLAMA
from core.settings import SETTINGS

def call_ollama_keywords(title: str, body: str, max_total_chars: int = 50, seeds: str | None = None) -> str | None:
    ai_cfg = SETTINGS.get("ai", {}) if isinstance(SETTINGS, dict) else {}
    provider = ai_cfg.get("provider") or "ollama"
    if provider not in ("ollama", ""):
        return None
    enable = ai_cfg.get("enable")
    if enable is not None:
        if not enable:
            return None
    elif not OLLAMA.get("enable"):
        return None

    model = ai_cfg.get("model") or OLLAMA.get("model", "llama3.1:latest")
    timeout = int(ai_cfg.get("timeout_sec") or OLLAMA.get("timeout_sec", 30))
    base_url = ai_cfg.get("url") or OLLAMA.get("url") or "http://127.0.0.1:11434"
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
    api_url = urljoin(base_url.rstrip('/')+'/', 'api/generate')
    req = urllib.request.Request(api_url, data=data, headers={"Content-Type":"application/json"})
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


def call_ollama_tags(title: str, body: str, max_labels: int = 5) -> str | None:
    """Use locally deployed Ollama model to generate classification tags.

    The implementation mirrors ``call_ollama_keywords`` but prompts the model to
    output a short comma-separated list of tags that describe the document. This
    behaviour is inspired by the Local-File-Organizer project's AI tagging
    feature so that the project can reuse a locally deployed model for both
    keyword extraction and tag classification.
    """

    ai_cfg = SETTINGS.get("ai", {}) if isinstance(SETTINGS, dict) else {}
    provider = ai_cfg.get("provider") or "ollama"
    if provider not in ("ollama", ""):
        return None
    enable = ai_cfg.get("enable")
    if enable is not None:
        if not enable:
            return None
    elif not OLLAMA.get("enable"):
        return None

    model = ai_cfg.get("model") or OLLAMA.get("model", "llama3.1:latest")
    timeout = int(ai_cfg.get("timeout_sec") or OLLAMA.get("timeout_sec", 30))
    base_url = ai_cfg.get("url") or OLLAMA.get("url") or "http://127.0.0.1:11434"

    prompt = (
        "你是本地文件分类助手。基于‘标题+正文节选’输出若干分类标签，要求："
        "1) 标签使用中文，逗号分隔；2) 标签数量不超过 {max_labels} 个；"
        "3) 标签尽量简洁且具有概括性；4) 不要任何解释。"
        f"\n标题: {title[:80]}"
        f"\n正文节选: {body[:800]}"
        "\n输出："
    ).replace("{max_labels}", str(max_labels))

    data = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
    api_url = urljoin(base_url.rstrip('/')+'/', 'api/generate')
    req = urllib.request.Request(api_url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            x = json.loads(resp.read().decode("utf-8"))
            tags = (x.get("response") or "").strip().strip("，, \n")
            return tags
    except Exception:
        return None


__all__ = ["call_ollama_keywords", "call_ollama_tags"]
