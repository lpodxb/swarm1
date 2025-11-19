from typing import Any, Dict, List

import numpy as np


class AgentArbitrationEngine:
    """
    Aggregates agent outputs into a single sentiment/confidence.

    Uses weights = agent_score * agent_confidence.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.agent_scores: Dict[str, float] = {}

    def calculate_weighted_consensus(self, responses: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not responses:
            return {
                "sentiment": 0.0,
                "confidence": 0.0,
                "dissent_score": 0.0,
                "weights": {},
                "agent_scores": self.agent_scores,
            }

        weights = []
        sentiments = []
        confidences = []
        for r in responses:
            agent_id = r["agent_id"]
            base_score = self.agent_scores.get(agent_id, 1.0)
            w = base_score * r["confidence"]
            weights.append(w)
            sentiments.append(r["sentiment"])
            confidences.append(r["confidence"])

        weights_arr = np.array(weights, dtype=float)
        if weights_arr.sum() <= 0:
            weights_arr = np.ones_like(weights_arr)
        weights_norm = weights_arr / weights_arr.sum()

        sentiment = float(np.dot(weights_norm, sentiments))
        confidence = float(np.dot(weights_norm, confidences))
        dissent_score = float(np.std(sentiments))

        weight_map = {r["agent_id"]: float(w) for r, w in zip(responses, weights_norm)}

        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "dissent_score": dissent_score,
            "weights": weight_map,
            "agent_scores": self.agent_scores,
        }
