from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

import ollama
from loguru import logger

from .memory import AgentMemory


class BaseAgent:
    """
    Base class for all LLM agents.

    Provides:
    - model_config (name, temperature, max_tokens, etc.)
    - AgentMemory
    - Ollama chat helper
    - JSON parsing helper
    - sentiment/confidence clamping
    """

    def __init__(self, model_config: Dict[str, Any], gpu_lru=None, warm_filter=None):
        self.model_config = model_config
        self.role = model_config["role"]
        self.model_name = model_config["name"]
        self.agent_id = f"{self.role}:{self.model_name}"
        self.gpu_lru = gpu_lru
        self.warm_filter = warm_filter

        mem_dir = Path("data/memory") / self.role
        mem_path = mem_dir / "memory.sqlite"
        self.memory = AgentMemory(str(mem_path), self.agent_id)

        logger.info(
            f"{self.__class__.__name__} initialized for role={self.role}, model={self.model_name}"
        )

    async def analyze(self, features: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    async def _chat_ollama(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Async wrapper around Ollama chat (blocking) using thread executor.
        """
        def _call():
            return ollama.chat(
                model=self.model_name,
                messages=messages,
                options={
                    "temperature": self.model_config.get("temperature", 0.4),
                    "num_predict": self.model_config.get("max_tokens", 512),
                },
            )

        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(None, _call)
        return resp

    def _safe_parse_json(self, text: str) -> Dict[str, Any]:
        """
        Best-effort JSON extraction from LLM output.
        """
        try:
            return json.loads(text)
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            try:
                return json.loads(snippet)
            except Exception:
                pass

        logger.warning(f"Failed to parse JSON from LLM output: {text[:200]}...")
        return {}

    def _clamp_output(self, sentiment: float, confidence: float) -> Dict[str, float]:
        s = max(min(float(sentiment), 1.0), -1.0)
        c = max(min(float(confidence), 1.0), 0.0)
        return {"sentiment": s, "confidence": c}
