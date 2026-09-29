import os
import json
import re
from typing import Dict, Any, Optional
from backend.config import settings

class LLMProvider:
    """
    Pluggable LLM interface supporting Gemini, OpenAI, Claude, and built-in expert DevOps reasoning engine.
    """
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.gemini_key = settings.GEMINI_API_KEY
        self.openai_key = settings.OPENAI_API_KEY
        self.anthropic_key = settings.ANTHROPIC_API_KEY

    def is_configured_for_remote(self) -> bool:
        if self.gemini_key or self.openai_key or self.anthropic_key:
            return True
        return False

    def generate_json_reasoning(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        Attempts to call the configured external LLM if API keys are set.
        Returns parsed JSON or None if unavailable/fails.
        """
        # 1. Try Gemini if configured
        if self.gemini_key and (self.provider in ("gemini", "auto")):
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.gemini_key)
                model = genai.GenerativeModel("gemini-1.5-flash")
                resp = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
                # Extract JSON from response
                match = re.search(r"\{.*\}", resp.text, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
            except Exception as e:
                print(f"[LLMProvider] Gemini error: {e}")

        # 2. Try OpenAI if configured
        if self.openai_key and (self.provider in ("openai", "auto")):
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "response_format": {"type": "json_object"}
                }
                res = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=8)
                if res.status_code == 200:
                    data = res.json()
                    return json.loads(data["choices"][0]["message"]["content"])
            except Exception as e:
                print(f"[LLMProvider] OpenAI error: {e}")

        # Return None to trigger intelligent internal DevOps reasoning
        return None

llm_provider = LLMProvider()
