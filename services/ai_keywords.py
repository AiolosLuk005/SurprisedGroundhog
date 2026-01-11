# -*- coding: utf-8 -*-
import json
import requests
import re
import logging
from typing import List, Dict, Optional, Any
from core.config import CFG

logger = logging.getLogger(__name__)

class AIKeywordService:
    def __init__(self):
        pass
    
    @property
    def _ai_config(self) -> dict:
        return CFG.AI_CONFIG

    def _doc_type_hints(self, doc_type: str) -> str:
        dt = (doc_type or "TEXT").upper()
        if dt == "DATA":
            return "若出现表头/字段名/单位/指标（如MAU、ARPU、转化率），将其视作术语或实体；结合显著的数值变化提取关键词。"
        if dt == "SLIDES":
            return "标题与要点（bullet points）权重更高；忽略页脚模板、版权、页码。"
        if dt == "PDF":
            return "若文本带有分栏/页眉页脚/参考文献，请忽略这些噪声；优先正文与图表标题。"
        if dt in ("AUDIO","VIDEO"):
            return "去除口头语、寒暄；保留人名/组织名/关键决策/行动项（含动词短语）。"
        return "优先考虑标题/小标题/结论段/列表项中的名词短语；避免空词。"

    def _split_text(self, s: str, chunk_chars: int) -> List[str]:
        s = s or ""
        chunk_chars = max(500, int(chunk_chars or 2000))
        out, buf = [], []
        acc = 0
        for line in s.splitlines():
            L = len(line) + 1
            if acc + L > chunk_chars and acc > 0:
                out.append("\n".join(buf))
                buf, acc = [line], L
            else:
                buf.append(line); acc += L
        if buf:
            out.append("\n".join(buf))
        
        final = []
        for seg in out:
            if len(seg) <= chunk_chars:
                final.append(seg); continue
            for i in range(0, len(seg), chunk_chars):
                final.append(seg[i:i+chunk_chars])
        return final

    def _json_from_text(self, text: str) -> Optional[Dict]:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None

    def _ollama_generate(self, prompt: str) -> str:
        ai = self._ai_config
        if ai.get("provider") != "ollama":
            # For now, simplistic fallback or error
            if ai.get("provider") in ("chatgpt", "deepseek"):
               # TODO: Implement remote providers in next refactor step
               logger.warning("Remote providers not fully implemented in backend service yet.")
            raise RuntimeError(f"Current backend implementation only supports 'ollama' or has partial support. Provider set to: {ai.get('provider')}")

        url = (ai.get("url") or "http://localhost:11434").rstrip("/")
        model = ai.get("model") or "qwen2:7b"
        options = {
            "num_ctx": int(ai.get("num_ctx", 8192)),
            "temperature": float(ai.get("temperature", 0.3)),
            "top_p": float(ai.get("top_p", 0.9)),
            "repeat_penalty": float(ai.get("repeat_penalty", 1.1))
        }
        payload = {
            "model": model,
            "prompt": prompt,
            "options": options,
            "stream": False
        }
        try:
            resp = requests.post(f"{url}/api/generate", json=payload, timeout=int(ai.get("timeout_sec", 120)))
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            raise

    def map_reduce_keywords(self, title: str, body: str, doc_type: str, seeds: str = "", max_len: int = 50) -> dict:
        ai = self._ai_config
        prompts = CFG.get("prompts", {}) or {}
        language = ai.get("language", "zh")
        chunk_chars = int(ai.get("map_chunk_chars", 2000))
        top_n = int(ai.get("reduce_top_n", 16))
        top_pn = int(ai.get("reduce_top_pn", 8))

        if not body:
            return {"title": title, "language": language, "keywords": [], "keyphrases": [], "summary": ""}

        chunks = self._split_text(body, chunk_chars)
        map_prompt_tpl = prompts.get("map") or "Extract keywords as JSON from:\n\"\"\"\n{{chunk_text}}\n\"\"\""
        map_results = []

        for idx, ck in enumerate(chunks, 1):
            prompt = (map_prompt_tpl
                .replace("{{filename}}", title or "")
                .replace("{{path}}", "")
                .replace("{{doc_type}}", doc_type or "TEXT")
                .replace("{{language}}", language)
                .replace("{{chunk_text}}", ck)
            )
            hint = self._doc_type_hints(doc_type)
            prompt = prompt.replace("{{doc_type_hints}}", hint)
            
            try:
                text = self._ollama_generate(prompt)
                obj = self._json_from_text(text) or {}
            except Exception as e:
                logger.warning(f"Map step failed for chunk {idx}: {e}")
                obj = {}
            
            if "keywords" not in obj:
                obj = {
                    "language": language,
                    "keywords": [{"term": w.strip(), "weight": 0.5, "type": "主题"} for w in (seeds or title or "").split() if w.strip()],
                    "keyphrases": [],
                    "summary": ""
                }
            map_results.append(obj)

        reduce_tpl = prompts.get("reduce") or "Merge keyword JSON array:\n{{map_results_json}}"
        reduce_prompt = (reduce_tpl
            .replace("{{top_n}}", str(top_n))
            .replace("{{top_pn}}", str(top_pn))
            .replace("{{map_results_json}}", json.dumps(map_results, ensure_ascii=False))
        )
        try:
            red_text = self._ollama_generate(reduce_prompt)
            red_obj = self._json_from_text(red_text) or {}
        except Exception as e:
            logger.error(f"Reduce step failed: {e}")
            red_obj = {}

        kws = red_obj.get("keywords") or []
        seen, flat = set(), []
        for item in kws:
            term = (isinstance(item, dict) and item.get("term")) or (isinstance(item, str) and item) or ""
            term = term.strip()
            if not term or term.lower() in seen:
                continue
            seen.add(term.lower()); flat.append(term)
            if len(flat) >= max_len:
                break

        return {
            "title": red_obj.get("title") or title or "",
            "language": red_obj.get("language") or language,
            "keywords": kws,
            "keyphrases": red_obj.get("keyphrases") or [],
            "summary": red_obj.get("summary") or "",
            "flat_terms": flat
        }
