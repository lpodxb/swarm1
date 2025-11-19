from typing import Any, Dict


class MarketRegimeEngine:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def classify(self, f: Dict[str, Any]) -> Dict[str, Any]:
        vol = f.get("realized_vol_24h", 0.02)
        obi = f.get("orderbook_imbalance", 0.0)
        social_urg = f.get("social_urgency", 0.0)
        if vol > 0.05 and social_urg > 0.5:
            regime = "panic"
        elif abs(obi) > 0.15 and vol < 0.04:
            regime = "trend"
        elif vol < 0.015:
            regime = "quiet"
        else:
            regime = "chop"
        return {"regime": regime}

    def scale_consensus(self, c: Dict[str, float]) -> Dict[str, float]:
        sentiment = c["sentiment"]
        confidence = c["confidence"]
        max_pos = 0.05
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "max_position_size": max_pos,
        }
