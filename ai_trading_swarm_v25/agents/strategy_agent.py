from typing import Any, Dict, List

from loguru import logger

from .base_agent import BaseAgent


class StrategyDeveloperAgent(BaseAgent):
    def _vectorize(self, f: Dict[str, Any]) -> List[float]:
        keys = [
            "onchain_whale_signal",
            "stablecoin_net_flow",
            "options_flow_signal",
            "funding_rate",
            "realized_vol_24h",
        ]
        return [float(f.get(k, 0.0)) for k in keys]

    async def analyze(self, features: Dict[str, Any]) -> Dict[str, Any]:
        vec = self._vectorize(features)
        similar = self.memory.get_similar_examples(vec, top_k=5)
        stats = self.memory.get_stats(lookback=200)

        examples_text = []
        for ex, sim in similar:
            label = (
                "win"
                if ex.pnl and ex.pnl > 0
                else "loss"
                if ex.pnl and ex.pnl < 0
                else "unknown"
            )
            examples_text.append(
                f"- {ex.timestamp}: sent={ex.sentiment:.2f}, conf={ex.confidence:.2f}, "
                f"pnl={ex.pnl}, label={label}, sim={sim:.2f}"
            )

        if stats.with_pnl:
            memory_summary = (
                f"Recent decisions: {stats.count} total, {stats.with_pnl} with known PnL.\n"
                f"Win rate: {stats.win_rate:.2%} avg PnL: {stats.avg_pnl:.4f}"
            )
        else:
            memory_summary = f"Recent decisions: {stats.count}, no PnL stats yet."

        system_prompt = (
            "You are the StrategyDeveloperAgent in an AI trading swarm.\n"
            "You focus on structural flows (on-chain, stables, options, funding).\n"
            "Return JSON: sentiment (-1..1, where negative implies short bias), confidence, risk_level, notes."
        )

        user_prompt = (
            "Structural features (JSON):\n"
            f"{features}\n\n"
            "Your performance on similar regimes:\n"
            f"{memory_summary}\n\n"
            "Most similar regimes from your history:\n"
            + ("\n".join(examples_text) if examples_text else "None.")
            + "\n\nRespond ONLY with a JSON object."
        )

        resp = await self._chat_ollama(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        content = resp["message"]["content"]
        parsed = self._safe_parse_json(content)

        sentiment = parsed.get("sentiment", 0.0)
        confidence = parsed.get("confidence", 0.5)
        risk_level = str(parsed.get("risk_level", "medium"))
        notes = str(parsed.get("notes", ""))

        clamped = self._clamp_output(sentiment, confidence)
        self.memory.log_decision(vec, clamped["sentiment"], clamped["confidence"], risk_level)

        result = {
            "sentiment": clamped["sentiment"],
            "confidence": clamped["confidence"],
            "risk_level": risk_level,
            "notes": notes,
        }
        logger.debug(f"StrategyDeveloperAgent result: {result}")
        return result
