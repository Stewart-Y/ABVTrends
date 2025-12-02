"""
ABVTrends - Forecast Engine Service

Orchestrates ML model training and forecasting.
Combines Prophet and LSTM predictions into ensemble forecasts.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.ml.training import LSTMTrainer, ProphetTrainer
from app.models.source import ModelVersion
from app.models.trend_score import Forecast, TrendScore

logger = logging.getLogger(__name__)


class ForecastEngineError(Exception):
    """Exception raised during forecasting."""

    pass


class ForecastEngine:
    """
    Orchestrates trend score forecasting using ensemble methods.

    Combines:
    - Prophet: For seasonality and holiday effects
    - LSTM: For complex pattern recognition

    Ensemble method: Weighted average based on recent performance.
    """

    # Default ensemble weights (Prophet, LSTM)
    DEFAULT_WEIGHTS = (0.6, 0.4)

    # Confidence interval percentiles
    CI_80 = 0.80
    CI_95 = 0.95

    def __init__(self, db: AsyncSession):
        """
        Initialize the forecast engine.

        Args:
            db: Async database session
        """
        self.db = db
        self.prophet_trainer = ProphetTrainer()
        self.lstm_trainer = LSTMTrainer()

    async def train_models(
        self,
        product_id: UUID,
    ) -> dict:
        """
        Train both Prophet and LSTM models for a product.

        Args:
            product_id: Product UUID

        Returns:
            Training results dictionary
        """
        # Get historical scores
        scores = await self._get_score_history(product_id)

        if len(scores) < settings.min_data_points_for_training:
            raise ForecastEngineError(
                f"Insufficient data: {len(scores)} points "
                f"(need {settings.min_data_points_for_training})"
            )

        results = {
            "product_id": str(product_id),
            "data_points": len(scores),
            "prophet": None,
            "lstm": None,
        }

        # Train Prophet
        try:
            _, prophet_metrics = self.prophet_trainer.train(product_id, scores)
            results["prophet"] = {
                "status": "success",
                "metrics": prophet_metrics,
            }
        except Exception as e:
            logger.error(f"Prophet training failed for {product_id}: {e}")
            results["prophet"] = {"status": "failed", "error": str(e)}

        # Train LSTM
        try:
            _, lstm_metrics = self.lstm_trainer.train(product_id, scores)
            results["lstm"] = {
                "status": "success",
                "metrics": lstm_metrics,
            }
        except Exception as e:
            logger.error(f"LSTM training failed for {product_id}: {e}")
            results["lstm"] = {"status": "failed", "error": str(e)}

        # Save model version
        await self._save_model_version(product_id, results)

        return results

    async def generate_forecast(
        self,
        product_id: UUID,
        horizon_days: int = None,
    ) -> list[Forecast]:
        """
        Generate ensemble forecast for a product.

        Args:
            product_id: Product UUID
            horizon_days: Number of days to forecast

        Returns:
            List of Forecast objects
        """
        horizon_days = horizon_days or settings.forecast_horizon_days

        # Get recent scores for LSTM
        recent_scores = await self._get_recent_scores(product_id, limit=30)

        if len(recent_scores) < 14:
            raise ForecastEngineError(
                f"Need at least 14 recent scores, got {len(recent_scores)}"
            )

        # Generate Prophet forecast
        prophet_forecast = None
        if self.prophet_trainer.model_exists(product_id):
            try:
                prophet_forecast = self.prophet_trainer.forecast(
                    product_id, periods=horizon_days
                )
            except Exception as e:
                logger.warning(f"Prophet forecast failed: {e}")

        # Generate LSTM forecast
        lstm_forecast = None
        if self.lstm_trainer.model_exists(product_id):
            try:
                lstm_forecast = self.lstm_trainer.forecast(
                    product_id,
                    [s for _, s in recent_scores],
                    periods=horizon_days,
                )
            except Exception as e:
                logger.warning(f"LSTM forecast failed: {e}")

        # Combine forecasts
        forecasts = self._ensemble_forecasts(
            product_id,
            prophet_forecast,
            lstm_forecast,
            horizon_days,
        )

        # Save to database
        for forecast in forecasts:
            self.db.add(forecast)
        await self.db.commit()

        logger.info(f"Generated {len(forecasts)} day forecast for {product_id}")

        return forecasts

    def _ensemble_forecasts(
        self,
        product_id: UUID,
        prophet_df,
        lstm_list: Optional[list[dict]],
        horizon_days: int,
    ) -> list[Forecast]:
        """
        Combine Prophet and LSTM forecasts.

        Uses weighted average with confidence intervals.
        """
        forecasts = []
        today = datetime.utcnow().date()

        # Get weights
        prophet_weight, lstm_weight = self.DEFAULT_WEIGHTS

        for i in range(horizon_days):
            forecast_date = datetime.combine(
                today + timedelta(days=i + 1),
                datetime.min.time(),
            )

            # Get predictions
            prophet_pred = None
            prophet_lower = None
            prophet_upper = None

            if prophet_df is not None and len(prophet_df) > i:
                row = prophet_df.iloc[i]
                prophet_pred = float(row["predicted"])
                prophet_lower = float(row["lower_95"])
                prophet_upper = float(row["upper_95"])

            lstm_pred = None
            if lstm_list and len(lstm_list) > i:
                lstm_pred = lstm_list[i]["predicted"]

            # Calculate ensemble prediction
            if prophet_pred is not None and lstm_pred is not None:
                # Weighted average
                ensemble_pred = (
                    prophet_pred * prophet_weight + lstm_pred * lstm_weight
                )
                # Use Prophet's confidence intervals scaled by ensemble
                scale = ensemble_pred / prophet_pred if prophet_pred else 1.0
                lower_95 = prophet_lower * scale if prophet_lower else None
                upper_95 = prophet_upper * scale if prophet_upper else None
            elif prophet_pred is not None:
                ensemble_pred = prophet_pred
                lower_95 = prophet_lower
                upper_95 = prophet_upper
            elif lstm_pred is not None:
                ensemble_pred = lstm_pred
                # Approximate confidence intervals for LSTM
                std = ensemble_pred * 0.1  # 10% standard deviation
                lower_95 = ensemble_pred - 2 * std
                upper_95 = ensemble_pred + 2 * std
            else:
                # Fallback: use last known score
                ensemble_pred = 50.0  # Neutral
                lower_95 = 30.0
                upper_95 = 70.0

            # Clamp predictions to valid range
            ensemble_pred = max(0, min(100, ensemble_pred))
            lower_95 = max(0, min(100, lower_95)) if lower_95 else None
            upper_95 = max(0, min(100, upper_95)) if upper_95 else None

            # Calculate 80% CI from 95% CI
            if lower_95 and upper_95:
                range_95 = upper_95 - lower_95
                range_80 = range_95 * 0.8
                lower_80 = ensemble_pred - range_80 / 2
                upper_80 = ensemble_pred + range_80 / 2
            else:
                lower_80 = None
                upper_80 = None

            forecast = Forecast(
                product_id=product_id,
                forecast_date=forecast_date,
                predicted_score=ensemble_pred,
                confidence_lower_80=lower_80,
                confidence_upper_80=upper_80,
                confidence_lower_95=lower_95,
                confidence_upper_95=upper_95,
                model_version=self._get_model_version(),
                model_type="ensemble",
            )
            forecasts.append(forecast)

        return forecasts

    async def _get_score_history(
        self,
        product_id: UUID,
        days: int = 90,
    ) -> list[tuple[datetime, float]]:
        """Get historical trend scores for training."""
        since = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(TrendScore.calculated_at, TrendScore.score)
            .where(TrendScore.product_id == product_id)
            .where(TrendScore.calculated_at >= since)
            .order_by(TrendScore.calculated_at.asc())
        )

        return [(row[0], row[1]) for row in result.all()]

    async def _get_recent_scores(
        self,
        product_id: UUID,
        limit: int = 30,
    ) -> list[tuple[datetime, float]]:
        """Get most recent scores for forecasting."""
        result = await self.db.execute(
            select(TrendScore.calculated_at, TrendScore.score)
            .where(TrendScore.product_id == product_id)
            .order_by(TrendScore.calculated_at.desc())
            .limit(limit)
        )

        rows = result.all()
        # Reverse to chronological order
        return [(row[0], row[1]) for row in reversed(rows)]

    async def _save_model_version(
        self,
        product_id: UUID,
        results: dict,
    ) -> ModelVersion:
        """Save model version metadata."""
        version = ModelVersion(
            version=self._get_model_version(),
            model_type="ensemble",
            metrics={
                "prophet": results.get("prophet"),
                "lstm": results.get("lstm"),
            },
            is_active=True,
            training_completed_at=datetime.utcnow(),
        )

        # Deactivate previous versions
        result = await self.db.execute(
            select(ModelVersion)
            .where(ModelVersion.model_type == "ensemble")
            .where(ModelVersion.is_active == True)  # noqa: E712
        )
        for old_version in result.scalars():
            old_version.is_active = False

        self.db.add(version)
        await self.db.commit()

        return version

    def _get_model_version(self) -> str:
        """Generate model version string."""
        return f"v1.0.{datetime.utcnow().strftime('%Y%m%d')}"

    async def get_product_forecast(
        self,
        product_id: UUID,
    ) -> list[Forecast]:
        """
        Get existing forecast for a product.

        Args:
            product_id: Product UUID

        Returns:
            List of Forecast objects
        """
        today = datetime.utcnow().date()

        result = await self.db.execute(
            select(Forecast)
            .where(Forecast.product_id == product_id)
            .where(Forecast.forecast_date >= today)
            .order_by(Forecast.forecast_date.asc())
        )

        return list(result.scalars().all())

    async def batch_forecast(
        self,
        product_ids: list[UUID],
    ) -> dict[UUID, list[Forecast]]:
        """
        Generate forecasts for multiple products.

        Args:
            product_ids: List of product UUIDs

        Returns:
            Dict mapping product_id to forecasts
        """
        results = {}

        for product_id in product_ids:
            try:
                forecasts = await self.generate_forecast(product_id)
                results[product_id] = forecasts
            except Exception as e:
                logger.error(f"Forecast failed for {product_id}: {e}")
                results[product_id] = []

        return results
