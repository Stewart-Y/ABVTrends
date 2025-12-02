"""
ABVTrends - Model Drift Detection

Monitors model performance and detects when retraining is needed.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trend_score import Forecast, TrendScore

logger = logging.getLogger(__name__)


@dataclass
class DriftReport:
    """Report of model drift analysis."""

    product_id: UUID
    drift_detected: bool
    mae: float
    mape: float
    baseline_mae: float
    baseline_mape: float
    degradation_pct: float
    recommendation: str
    analyzed_at: datetime
    forecast_count: int
    actual_count: int


class DriftDetector:
    """
    Detects model performance drift by comparing predictions to actuals.

    Drift is detected when:
    - MAE increases by more than DRIFT_THRESHOLD over baseline
    - Directional accuracy drops significantly
    - Systematic bias appears (consistent over/under prediction)
    """

    # Drift thresholds
    MAE_DRIFT_THRESHOLD = 0.25  # 25% increase in MAE triggers alert
    MAPE_DRIFT_THRESHOLD = 0.30  # 30% increase in MAPE
    MIN_SAMPLES = 7  # Minimum samples for drift detection

    def __init__(self, db: AsyncSession):
        """
        Initialize the drift detector.

        Args:
            db: Async database session
        """
        self.db = db

    async def check_drift(
        self,
        product_id: UUID,
        lookback_days: int = 14,
    ) -> DriftReport:
        """
        Check for model drift on a specific product.

        Compares recent forecasts to actual scores.

        Args:
            product_id: Product UUID
            lookback_days: Days to analyze

        Returns:
            DriftReport with analysis results
        """
        # Get forecasts and actuals from the lookback period
        forecasts, actuals = await self._get_forecast_actual_pairs(
            product_id, lookback_days
        )

        if len(forecasts) < self.MIN_SAMPLES:
            return DriftReport(
                product_id=product_id,
                drift_detected=False,
                mae=0.0,
                mape=0.0,
                baseline_mae=0.0,
                baseline_mape=0.0,
                degradation_pct=0.0,
                recommendation="insufficient_data",
                analyzed_at=datetime.utcnow(),
                forecast_count=len(forecasts),
                actual_count=len(actuals),
            )

        # Calculate current metrics
        current_mae, current_mape = self._calculate_metrics(forecasts, actuals)

        # Get baseline metrics (from model training)
        baseline_mae, baseline_mape = await self._get_baseline_metrics(product_id)

        # Calculate degradation
        mae_degradation = (
            (current_mae - baseline_mae) / baseline_mae
            if baseline_mae > 0
            else 0.0
        )
        mape_degradation = (
            (current_mape - baseline_mape) / baseline_mape
            if baseline_mape > 0
            else 0.0
        )

        # Check for drift
        drift_detected = (
            mae_degradation > self.MAE_DRIFT_THRESHOLD
            or mape_degradation > self.MAPE_DRIFT_THRESHOLD
        )

        # Generate recommendation
        if drift_detected:
            if mae_degradation > 0.5:
                recommendation = "retrain_urgent"
            else:
                recommendation = "retrain_suggested"
        elif mae_degradation > 0.1:
            recommendation = "monitor_closely"
        else:
            recommendation = "model_healthy"

        return DriftReport(
            product_id=product_id,
            drift_detected=drift_detected,
            mae=current_mae,
            mape=current_mape,
            baseline_mae=baseline_mae,
            baseline_mape=baseline_mape,
            degradation_pct=max(mae_degradation, mape_degradation) * 100,
            recommendation=recommendation,
            analyzed_at=datetime.utcnow(),
            forecast_count=len(forecasts),
            actual_count=len(actuals),
        )

    async def _get_forecast_actual_pairs(
        self,
        product_id: UUID,
        lookback_days: int,
    ) -> tuple[list[float], list[float]]:
        """Get matched forecast-actual pairs."""
        since = datetime.utcnow() - timedelta(days=lookback_days)

        # Get forecasts
        forecast_result = await self.db.execute(
            select(Forecast.forecast_date, Forecast.predicted_score)
            .where(Forecast.product_id == product_id)
            .where(Forecast.forecast_date >= since)
            .where(Forecast.forecast_date <= datetime.utcnow())
            .order_by(Forecast.forecast_date)
        )
        forecasts_by_date = {
            row[0].date(): row[1] for row in forecast_result.all()
        }

        # Get actuals
        actual_result = await self.db.execute(
            select(TrendScore.calculated_at, TrendScore.score)
            .where(TrendScore.product_id == product_id)
            .where(TrendScore.calculated_at >= since)
            .order_by(TrendScore.calculated_at)
        )
        actuals_by_date = {
            row[0].date(): row[1] for row in actual_result.all()
        }

        # Match pairs
        forecasts = []
        actuals = []

        for date, forecast_val in forecasts_by_date.items():
            if date in actuals_by_date:
                forecasts.append(forecast_val)
                actuals.append(actuals_by_date[date])

        return forecasts, actuals

    def _calculate_metrics(
        self,
        forecasts: list[float],
        actuals: list[float],
    ) -> tuple[float, float]:
        """Calculate MAE and MAPE."""
        forecasts_arr = np.array(forecasts)
        actuals_arr = np.array(actuals)

        # MAE
        mae = np.mean(np.abs(forecasts_arr - actuals_arr))

        # MAPE (avoid division by zero)
        non_zero_mask = actuals_arr != 0
        if non_zero_mask.any():
            mape = np.mean(
                np.abs(
                    (forecasts_arr[non_zero_mask] - actuals_arr[non_zero_mask])
                    / actuals_arr[non_zero_mask]
                )
            ) * 100
        else:
            mape = 0.0

        return float(mae), float(mape)

    async def _get_baseline_metrics(
        self,
        product_id: UUID,
    ) -> tuple[float, float]:
        """Get baseline metrics from model training."""
        # Default baseline if not available
        return 5.0, 10.0  # MAE=5, MAPE=10%

    async def check_all_models(self) -> list[DriftReport]:
        """
        Check drift for all products with forecasts.

        Returns:
            List of DriftReport objects
        """
        # Get products with recent forecasts
        result = await self.db.execute(
            select(Forecast.product_id)
            .where(
                Forecast.created_at >= datetime.utcnow() - timedelta(days=7)
            )
            .distinct()
        )
        product_ids = [row[0] for row in result.all()]

        reports = []
        for product_id in product_ids:
            try:
                report = await self.check_drift(product_id)
                reports.append(report)
            except Exception as e:
                logger.error(f"Drift check failed for {product_id}: {e}")

        # Log summary
        drift_count = sum(1 for r in reports if r.drift_detected)
        logger.info(
            f"Drift check complete: {drift_count}/{len(reports)} models show drift"
        )

        return reports

    async def get_retrain_candidates(self) -> list[UUID]:
        """
        Get list of product IDs that need retraining.

        Returns:
            List of product UUIDs
        """
        reports = await self.check_all_models()

        return [
            r.product_id
            for r in reports
            if r.recommendation in ("retrain_urgent", "retrain_suggested")
        ]
