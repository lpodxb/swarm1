from __future__ import annotations

from pathlib import Path
import asyncio
import signal
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
from loguru import logger
import ccxt

from configs.config_loader import ConfigLoader
from state.global_state import get_global_state

from infrastructure.gpu_scheduler import GPUSingleScheduler
from infrastructure.gpu_lru import GPULRUManager
from infrastructure.llm_warm_filter import LLMWarmFilter

from events.event_bus import event_bus
from events.publishers.onchain_publisher import OnChainPublisher
from events.publishers.options_publisher import OptionsPublisher
from events.publishers.telegram_publisher import TelegramPublisher
from data.orderbook.imbalance import OrderbookImbalanceEngine
from data.funding.funding_rate import FundingRateEngine

from trading.kelly_sizer import KellyPositionSizer
from trading.execution_engine import ExecutionEngine
from risk.correlation_manager import CorrelationRiskManager
from risk.trade_validator import TradeValidator
from monitoring.failsafe import FailsafeMonitor

from lab.storage import init_db as init_lab_db
from journal.storage import init_db as init_journal_db
from context.pair_context import build_contexts_from_config, PairContext

from strategies.portfolio import StrategyPortfolioPlanner
from strategies.executor import StrategyExecutionEngine, ProposedTrade
from journal.engine import JournalEngine

from agents.technical_agent import TechnicalNewsAgent
from agents.sentiment_agent import SentimentAnalyzerAgent
from agents.risk_agent import RiskManagerAgent
from agents.strategy_agent import StrategyDeveloperAgent
from agents.consensus_engine import EnhancedConsensusEngine
from agents.arbitration_engine import AgentArbitrationEngine
from analysis.regime_engine import MarketRegimeEngine


class TradingSwarmV25:
    """
    AI Trading Swarm v2.5

    - Multi-context (multiple pairs/timeframes, via PairContext)
    - LLM swarm agents (4 roles) → consensus
    - Strategy Lab gating (only trade if approved strategies exist)
    - Strategy portfolio planner + execution engine
    - Kelly sizing + correlation + validator + failsafe
    - Journal logging (regimes + trades)
    - Live OHLCV candles via CCXT (Binance)
    """

    def __init__(self, config_path: str = "configs/config.yaml"):
        # Logging
        Path("logs").mkdir(parents=True, exist_ok=True)
        logger.add("logs/swarm_v25.log", rotation="500 MB", retention="14 days")
        logger.info("AI Trading Swarm v2.5 starting...")

        # Config + global state
        self.config: Dict[str, Any] = ConfigLoader(config_path).load()
        self.state = get_global_state(self.config)

        # DBs
        init_lab_db()
        init_journal_db()

        # Build contexts from config
        self.contexts: List[PairContext] = build_contexts_from_config(self.config)
        if not self.contexts:
            logger.warning("No pair contexts built from config. Check 'pairs' in config.yaml.")
        else:
            logger.info(
                "Active contexts: "
                + ", ".join(f"{c.symbol} {c.timeframe}" for c in self.contexts)
            )

        # Infra
        self.gpu_scheduler = GPUSingleScheduler(self.config)
        self.gpu_lru = GPULRUManager(self.config)
        self.llm_warm_filter = LLMWarmFilter()

        # Agents
        self.agents = self._init_agents()
        self.consensus_engine = EnhancedConsensusEngine(self.config)
        self.arbitration = AgentArbitrationEngine(self.config)
        self.regime_engine = MarketRegimeEngine(self.config)

        # Data feeds
        self.onchain_publisher = OnChainPublisher(self.config)
        self.options_publisher = OptionsPublisher(self.config)
        self.telegram_publisher = TelegramPublisher(self.config)
        self.orderbook_engine = OrderbookImbalanceEngine(self.config)
        self.funding_engine = FundingRateEngine(self.config)

        # Trading & risk
        self.kelly_sizer = KellyPositionSizer(self.config)
        self.correlation_manager = CorrelationRiskManager(self.config)
        self.trade_validator = TradeValidator(self.config)
        self.execution_engine = ExecutionEngine(self.config)
        self.failsafe = FailsafeMonitor(self.config)

        # Strategy portfolio + execution
        self.portfolio_planner = StrategyPortfolioPlanner()
        self.strategy_executor = StrategyExecutionEngine()

        # Journal
        self.journal = JournalEngine()

        # CCXT exchange for live candles
        self.exchange = self._init_exchange()

        # Control
        self._stop_event = asyncio.Event()
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        logger.success("TradingSwarmV25 fully initialized.")

    def _init_agents(self) -> Dict[str, Any]:
        """
        Map llm_swarm.models roles → concrete agent classes.

        Current config uses roles: "one", "two", "three", "four"
          one   -> TechnicalNewsAgent
          two   -> SentimentAnalyzerAgent
          three -> RiskManagerAgent
          four  -> StrategyDeveloperAgent
        """
        role_to_class = {
            "one": TechnicalNewsAgent,
            "two": SentimentAnalyzerAgent,
            "three": RiskManagerAgent,
            "four": StrategyDeveloperAgent,
        }

        agents: Dict[str, Any] = {}
        for mc in self.config["llm_swarm"]["models"]:
            role = mc["role"]
            cls = role_to_class.get(role)
            if cls is None:
                logger.warning(f"Unknown agent role in config: {role}, skipping.")
                continue
            agent = cls(mc, gpu_lru=self.gpu_lru, warm_filter=self.llm_warm_filter)
            agents[role] = agent

        logger.info("Agents initialized: " + ", ".join(agents.keys()))
        return agents

    def _init_exchange(self):
        """
        Initialize a CCXT exchange instance for fetching live candles.
        Uses public Binance spot; no API key needed for OHLCV.
        """
        exchange_id = self.config["trading"].get("exchange", "binance")
        try:
            cls = getattr(ccxt, exchange_id)
        except AttributeError:
            raise RuntimeError(f"Unsupported exchange_id in config: {exchange_id}")

        exchange = cls({
            "enableRateLimit": True,
        })

        logger.info(f"CCXT exchange initialized: {exchange_id}")
        return exchange

    async def start(self):
        # Initialize GPU (if available)
        await self.gpu_scheduler.initialize_models()

        # EventBus
        bus_task = asyncio.create_task(event_bus.run(), name="event_bus")

        # Background tasks
        tasks = [
            asyncio.create_task(self.onchain_publisher.start(), name="onchain_publisher"),
            asyncio.create_task(self.options_publisher.start(), name="options_publisher"),
            asyncio.create_task(self.telegram_publisher.start(), name="telegram_publisher"),
            asyncio.create_task(self.orderbook_engine.start(), name="orderbook_engine"),
            asyncio.create_task(self.funding_engine.start(), name="funding_engine"),
            asyncio.create_task(self.gpu_lru.periodic_maintenance(), name="gpu_lru_maintenance"),
            asyncio.create_task(self.failsafe.start(), name="failsafe_monitor"),
        ]

        # Main loop
        main_loop_task = asyncio.create_task(self._main_loop(), name="swarm_main_loop")

        # Wait for stop
        await self._stop_event.wait()
        logger.warning("Stop event received, shutting down...")

        for t in tasks + [bus_task, main_loop_task]:
            t.cancel()
        await asyncio.gather(*tasks, bus_task, main_loop_task, return_exceptions=True)
        await self.execution_engine.stop()
        logger.info("Swarm v2.5 shutdown complete.")

    async def _main_loop(self):
        iteration = 0
        cycle_seconds = 30
        cfg_cons = self.config["llm_swarm"]["consensus"]

        while not self._stop_event.is_set():
            try:
                iteration += 1
                logger.info(f"[GLOBAL] Iteration {iteration} @ {datetime.utcnow().isoformat()}")

                if self.state.is_trading_paused:
                    logger.warning("[GLOBAL] Trading paused by failsafe; skipping all contexts.")
                    await asyncio.sleep(cycle_seconds)
                    continue

                # One cycle per context
                for ctx in self.contexts:
                    await self._run_cycle_for_context(ctx, iteration, cfg_cons)

                await asyncio.sleep(cycle_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[GLOBAL] Main loop error: {e}")
                await asyncio.sleep(60)

    def _get_live_candles_for_context(self, ctx: PairContext) -> pd.DataFrame:
        """
        Fetch recent OHLCV candles for the given context using CCXT.

        Returns a DataFrame with columns: open, high, low, close, volume
        and a DatetimeIndex in UTC.
        """
        symbol = ctx.symbol          # e.g. "BTC/USDT"
        timeframe = ctx.timeframe    # e.g. "15m", "1h"
        limit = 200                  # number of candles

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        except Exception as e:
            logger.error(f"[CTX {symbol}] Error fetching OHLCV via CCXT: {e}")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        if not ohlcv:
            logger.warning(f"[CTX {symbol}] No OHLCV data returned from exchange.")
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # CCXT OHLCV format: [timestamp, open, high, low, close, volume]
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.set_index("timestamp").sort_index()

        return df[["open", "high", "low", "close", "volume"]]

    async def _run_cycle_for_context(
        self,
        ctx: PairContext,
        iteration: int,
        cfg_cons: Dict[str, Any],
    ) -> None:
        if not ctx.enabled:
            return

        symbol = ctx.symbol
        base_asset = ctx.base_asset or symbol.split("/")[0]

        logger.info(f"[CTX {symbol} {ctx.timeframe}] Cycle start (iter={iteration})")

        # Refresh approved strategies periodically (lab gate)
        if iteration % 10 == 1:
            ctx.refresh_approved_strategies()

        if not ctx.approved_strategies:
            logger.warning(
                f"[CTX {symbol}] [LAB GATE] No approved strategies for {symbol} "
                f"{ctx.timeframe}. Skipping."
            )
            return

        # Set current asset for feature-building & logging
        self.consensus_engine.current_asset = base_asset

        # 1) LLM agent responses
        agent_responses = await self.consensus_engine.collect_agent_responses(self.agents)
        if not agent_responses:
            logger.info(f"[CTX {symbol}] No agent responses this cycle.")
            return

        # 2) Swarm arbitration
        arb = self.arbitration.calculate_weighted_consensus(agent_responses)

        consensus = {
            "sentiment": arb["sentiment"],
            "confidence": arb["confidence"],
            "dissent": arb["dissent_score"],
            "asset": base_asset,
            "pair": symbol,
            "direction": "long" if arb["sentiment"] > 0 else "short",
            "meta": {
                "weights": arb["weights"],
                "agent_scores": arb["agent_scores"],
                "context_timeframe": ctx.timeframe,
                "approved_strategies": list(ctx.approved_strategies),
            },
        }

        # 3) Regime classification & scaling
        features = self.consensus_engine.get_latest_market_features()
        regime = self.regime_engine.classify(features)
        self.state.update_market_regime(regime["regime"], **features)

        # Log regime snapshot
        self.journal.log_regime(symbol, ctx.timeframe, regime["regime"], features)

        scaled = self.regime_engine.scale_consensus(
            {"sentiment": consensus["sentiment"], "confidence": consensus["confidence"]}
        )
        consensus["sentiment"] = scaled["sentiment"]
        consensus["confidence"] = scaled["confidence"]
        consensus["max_position_size"] = scaled["max_position_size"]

        # Record consensus
        self.state.consensus_history.append(
            {
                "time": datetime.utcnow().isoformat(),
                "asset": base_asset,
                "pair": symbol,
                "sentiment": consensus["sentiment"],
                "confidence": consensus["confidence"],
                "regime": self.state.market_regime.regime,
            }
        )

        # 4) Confidence gate
        if consensus["confidence"] < cfg_cons["confidence_threshold"]:
            logger.info(
                f"[CTX {symbol}] Consensus confidence too low "
                f"({consensus['confidence']:.2f}), skipping."
            )
            return

        # 5) Strategy portfolio planning
        allocations = self.portfolio_planner.plan_portfolio(
            ctx.approved_strategies,
            consensus["sentiment"],
            consensus["confidence"],
        )
        if not allocations:
            logger.info(f"[CTX {symbol}] No strategy allocations (planner returned empty).")
            return

        # 6) Live candles for strategy execution
        candles = self._get_live_candles_for_context(ctx)
        if candles.empty:
            logger.info(f"[CTX {symbol}] No candles available, skipping.")
            return

        proposed_trades: List[ProposedTrade] = self.strategy_executor.generate_trades_for_context(
            ctx, candles, allocations
        )
        if not proposed_trades:
            logger.info(f"[CTX {symbol}] No proposed trades from strategies this cycle.")
            return

        # 7) Kelly budget
        stats = self.kelly_sizer.get_backtest_stats("swarm_v2_5")
        total_budget = self.kelly_sizer.calculate_position_size(
            {"confidence": consensus["confidence"], "risk_level": "medium"},
            backtest_stats=stats,
        )
        total_budget = min(total_budget, consensus["max_position_size"])
        if total_budget <= 0:
            logger.info(f"[CTX {symbol}] Kelly budget <= 0, skipping.")
            return

        raw_sum = sum(max(t.position_frac, 0.0) for t in proposed_trades)
        if raw_sum <= 0:
            logger.info(f"[CTX {symbol}] Proposed trades have zero total fraction, skipping.")
            return

        # 8) Scale each trade by Kelly budget, apply risk filters, execute
        for t in proposed_trades:
            base_frac = max(t.position_frac, 0.0)
            if base_frac <= 0:
                continue

            effective_frac = total_budget * (base_frac / raw_sum)
            if effective_frac <= 0:
                continue

            open_positions = await self.execution_engine.get_open_positions()
            allowed_corr = await self.correlation_manager.check_trade_allowed(
                base_asset, effective_frac, open_positions
            )
            if not allowed_corr:
                logger.warning(
                    f"[CTX {symbol}] Trade from {t.strategy_id} blocked by correlation."
                )
                continue

            proposed_dict = {
                "symbol": t.symbol,
                "side": t.side,
                "position_frac": effective_frac,
                "strategy_id": t.strategy_id,
            }
            validation = await self.trade_validator.validate(proposed_dict)
            if not validation["valid"]:
                logger.warning(
                    f"[CTX {symbol}] Trade from {t.strategy_id} rejected: {validation['reason']}"
                )
                self.state.trades_rejected += 1
                continue

            # Strategy-specific consensus meta
            trade_consensus = dict(consensus)
            meta = dict(trade_consensus.get("meta", {}))
            meta["strategy_id"] = t.strategy_id
            meta["strategy_weight"] = t.meta.get("weight")
            meta["proposed_position_frac"] = t.position_frac
            trade_consensus["meta"] = meta

            trade_result = await self.execution_engine.execute_trade(
                symbol=t.symbol,
                side=t.side,
                position_frac=effective_frac,
                consensus=trade_consensus,
            )
            if trade_result and trade_result.get("status") == "filled":
                logger.success(
                    f"[CTX {symbol}] Trade executed: {t.symbol} {t.side} "
                    f"{effective_frac:.2%} via {t.strategy_id}"
                )
                self.journal.log_trade(
                    symbol=t.symbol,
                    timeframe=ctx.timeframe,
                    trade=trade_result,
                    consensus=trade_consensus,
                )

    def _handle_signal(self, signum, frame):
        logger.warning(f"Shutdown signal received: {signum}")
        self._stop_event.set()


async def main():
    swarm = TradingSwarmV25()
    await swarm.start()


if __name__ == "__main__":
    asyncio.run(main())
