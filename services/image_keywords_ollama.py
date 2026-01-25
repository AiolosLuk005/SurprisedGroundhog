# -*- coding: utf-8 -*-
"""
Image keyword extraction using Ollama Vision models (e.g., qwen3-vl:8b).
"""
import base64
import requests
import logging
from pathlib import Path
from typing import List, Dict, Any
from core.config import CFG

logger = logging.getLogger(__name__)

class OllamaImageKeywordService:
    """Service for extracting keywords from images using Ollama vision models."""
    
    def __init__(self, model: str = None, url: str = None, timeout: int = None):
        """
        Initialize the Ollama image keyword service.
        
        Args:
            model: Vision model name (default: qwen3-vl:8b)
            url: Ollama API URL (default: from config)
            timeout: Request timeout in seconds (default: from config)
        """
        ai_config = CFG.AI_CONFIG
        self.model = model or ai_config.get("vision_model", "qwen3-vl:8b")
        self.url = (url or ai_config.get("url", "http://localhost:11434")).rstrip("/")
        self.timeout = timeout or int(ai_config.get("timeout_sec", 120))
        
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    
    def _call_ollama_vision(self, image_path: str, prompt: str) -> str:
        """
        Call Ollama vision API with an image.
        
        Args:
            image_path: Path to the image file
            prompt: Text prompt for the vision model
            
        Returns:
            Model response text
        """
        try:
            # Encode image
            image_b64 = self._encode_image(image_path)
            
            # Prepare request
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            }
            
            # Call API
            resp = requests.post(
                f"{self.url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            resp.raise_for_status()
            
            data = resp.json()
            return data.get("response", "")
            
        except Exception as e:
            logger.error(f"Ollama vision call failed for {image_path}: {e}")
            raise
    
    def extract_keywords(self, image_path: str, language: str = "zh", max_keywords: int = 20) -> List[str]:
        """
        Extract keywords from an image.
        
        Args:
            image_path: Path to the image file
            language: Language for keywords (zh/en)
            max_keywords: Maximum number of keywords to extract
            
        Returns:
            List of keyword strings
        """
        # Validate file
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        # Prepare prompt based on language
        if language == "zh":
            prompt = f"""请仔细分析这张图片，提取最多 {max_keywords} 个关键词来描述图片内容。

要求：
1. 关键词应该准确描述图片中的主要元素、场景、风格、情绪等
2. 优先提取具体的名词（人物、物体、场景）
3. 包含重要的形容词（颜色、风格、氛围）
4. 如果有文字，提取关键文字内容
5. 只输出关键词，用中文逗号分隔，不要编号或解释

输出格式示例：蓝天，白云，山峰，自然风光，宁静，壮丽"""
        else:
            prompt = f"""Please analyze this image carefully and extract up to {max_keywords} keywords that describe the image content.

Requirements:
1. Keywords should accurately describe main elements, scenes, styles, emotions, etc.
2. Prioritize concrete nouns (people, objects, scenes)
3. Include important adjectives (colors, styles, atmosphere)
4. If there's text, extract key text content
5. Output only keywords, separated by commas, no numbering or explanation

Example format: blue sky, white clouds, mountain peak, natural scenery, peaceful, magnificent"""
        
        try:
            # Call vision model
            response = self._call_ollama_vision(image_path, prompt)
            
            # Parse keywords
            keywords = []
            if response:
                # Split by comma or Chinese comma
                parts = response.replace("，", ",").split(",")
                for part in parts:
                    kw = part.strip().strip("\"'")
                    if kw and len(kw) > 0:
                        keywords.append(kw)
                        if len(keywords) >= max_keywords:
                            break
            
            logger.info(f"Extracted {len(keywords)} keywords from {image_path}")
            return keywords[:max_keywords]
            
        except Exception as e:
            logger.error(f"Keyword extraction failed for {image_path}: {e}")
            # Return filename as fallback
            return [Path(image_path).stem]
    
    def extract(self, image_path: str, max_chars: int = None) -> Dict[str, Any]:
        """
        Extract keywords in plugin-compatible format.
        
        Args:
            image_path: Path to the image file
            max_chars: Not used, kept for compatibility
            
        Returns:
            Dict with 'meta' containing 'tags' list
        """
        try:
            keywords = self.extract_keywords(image_path)
            return {
                "text": ", ".join(keywords),
                "meta": {
                    "tags": keywords,
                    "model": self.model
                }
            }
        except Exception as e:
            return {
                "text": "",
                "meta": {
                    "tags": [],
                    "error": str(e)
                }
            }
