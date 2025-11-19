from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger

from state.global_state import get_global_state


@dataclass
class MarketFeatures:
    timestamp: datetime
    asset: str
    realized_vol_1h: float
    realized_vol_24h: float
    orderbook_imbalance: float
    funding_rate: float
    funding_imbalance: float
    onchain_whale_signal: float
    stablecoin_flow_signal: float
    options_flow_signal: float
    social_urgency: float
    social_signal: float


class EnhancedConsensusEngine:
    """
    Aggregates alt-data into a feature vector and calls all agents with it.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.current_asset: str = config["trading"].get("primary_asset", "BTC")
        self.state = get_global_state(config)
        logger.info(f"EnhancedConsensusEngine initialized (asset={self.current_asset})")

    async def collect_agent_responses(
        self,
        agents: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        features = self._build_feature_snapshot()
        if features is None:
            logger.warning("No alt-data snapshot yet, skipping agent calls.")
            return []

        tasks = [self._call_agent(role, agent, features) for role, agent in agents.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses: List[Dict[str, Any]] = []
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Agent call error: {res}")
                continue
            if res:
                responses.append(res)
        return responses

    async def _call_agent(
        self,
        role: str,
        agent: Any,
        features: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            resp = await agent.analyze(features)
        except Exception as exc:
            logger.error(f"Agent {role} failed: {exc}")
            return None

        if not isinstance(resp, dict):
            return None

        sentiment = float(resp.get("sentiment", 0.0))
        confidence = float(resp.get("confidence", 0.0))
        risk_level = str(resp.get("risk_level", "medium"))

        return {
            "agent_id": getattr(agent, "agent_id", role),
            "role": role,
            "sentiment": max(min(sentiment, 1.0), -1.0),
            "confidence": max(min(confidence, 1.0), 0.0),
            "risk_level": risk_level,
            "asset": self.current_asset,
            "features": features,
            "raw": resp,
        }

    def _build_feature_snapshot(self) -> Optional[Dict[str, Any]]:
        alt = self.state.alt_data_snapshot
        if alt is None:
            return None

        obi = alt.get("orderbook", {})
        funding = alt.get("funding", {})
        onchain = alt.get("onchain", {})
        stables = onchain.get("stablecoin_flows", {})
        stables_net = (
            sum(v.get("net_flow", 0.0) for v in stables.values()) if stables else 0.0
        )
        options = alt.get("options", {})
        social = alt.get("social", {})
        vol = alt.get("volatility", {})

        realized_vol_1h = float(vol.get("realized_vol_1h", 0.01))
        realized_vol_24h = float(vol.get("realized_vol_24h", 0.02))

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "asset": self.current_asset,
            "price": float(alt.get("price", {}).get(self.current_asset, 0.0)),
            "realized_vol_1h": realized_vol_1h,
            "realized_vol_24h": realized_vol_24h,
            "orderbook_imbalance": float(obi.get("imbalance", 0.0)),
            "orderbook_spread_bps": float(obi.get("spread_bps", 0.0)),
            "orderbook_depth_usd": float(obi.get("depth_usd", 0.0)),
            "funding_rate": float(funding.get("funding_rate", 0.0)),
            "funding_imbalance": float(funding.get("long_short_ratio", 0.0)),
            "onchain_whale_signal": float(onchain.get("aggregate_signal", 0.0)),
            "stablecoin_net_flow": float(stables_net),
            "options_flow_signal": float(options.get("signal", 0.0)),
            "options_strength": float(options.get("strength", 0.0)),
            "social_signal": float(social.get("signal", 0.0)),
            "social_urgency": float(social.get("avg_urgency", 0.0)),
        }

    def get_latest_market_features(self) -> Dict[str, Any]:
        feat = self._build_feature_snapshot()
        if feat is None:
            return {
                "asset": self.current_asset,
                "realized_vol_1h": 0.01,
                "realized_vol_24h": 0.02,
                "orderbook_imbalance": 0.0,
                "orderbook_spread_bps": 2.0,
                "orderbook_depth_usd": 1_000_000.0,
                "funding_rate": 0.0,
                "funding_imbalance": 0.0,
                "onchain_whale_signal": 0.0,
                "stablecoin_net_flow": 0.0,
                "options_flow_signal": 0.0,
                "options_strength": 0.0,
                "social_signal": 0.0,
                "social_urgency": 0.0,
            }
        return {
            "asset": feat["asset"],
            "realized_vol_1h": feat["realized_vol_1h"],
            "realized_vol_24h": feat["realized_vol_24h"],
            "orderbook_imbalance": feat["orderbook_imbalance"],
            "orderbook_spread_bps": feat["orderbook_spread_bps"],
            "orderbook_depth_usd": feat["orderbook_depth_usd"],
            "funding_rate": feat["funding_rate"],
            "funding_imbalance": feat["funding_imbalance"],
            "onchain_whale_signal": feat["onchain_whale_signal"],
            "stablecoin_net_flow": feat["stablecoin_net_flow"],
            "options_flow_signal": feat["options_flow_signal"],
            "options_strength": feat["options_strength"],
            "social_signal": feat["social_signal"],
            "social_urgency": feat["social_urgency"],
        }
