from typing import Any, Dict

from loguru import logger
import torch


class GPUSingleScheduler:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.models_config = config["llm_swarm"]["models"]
        logger.info("GPUSingleScheduler initialized (stub).")

    async def initialize_models(self):
        if not torch.cuda.is_available():
            logger.warning("CUDA not available; models will run on CPU (Ollama will handle).")
            return
        logger.info("CUDA available; GPU ready for LLM offload.")

    async def _rotate_models(self):
        logger.debug("[GPUSingleScheduler] rotate_models (stub).")
