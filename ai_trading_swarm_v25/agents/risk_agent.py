from typing import Any, Dict, List

from loguru import logger

from .base_agent import BaseAgent


class RiskManagerAgent(BaseAgent):
    def _vectorize(self, f: Dict[str, Any]) -> List[float]:
        keys = [
            "realized_vol_1h",
            "realized_vol_24h",
            "funding_rate",
            "funding_imbalance",
            "orderbook_spread_bps",
            "orderbook_depth_usd",
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
            "You are the RiskManagerAgent in an AI trading swarm.\n"
            "Your job is to judge how dangerous the environment is. "
            "Negative sentiment from you means 'risk off'.\n"
            "Return JSON: sentiment, confidence, risk_level, notes."
        )

        user_prompt = (
            "Risk-related features (JSON):\n"
            f"{features}\n\n"
            "Your recent performance:\n"
            f"{memory_summary}\n\n"
            "Similar high-risk regimes:\n"
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
        confidence = parsed.get("confidence", 0.6)
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
        logger.debug(f"RiskManagerAgent result: {result}")
        return result
