"""
ABVTrends - Prophet Model Training

Trains Facebook Prophet models for time series forecasting of trend scores.
Prophet excels at capturing seasonality and holiday effects.
"""

import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import numpy as np
import pandas as pd
from prophet import Prophet

from app.core.config import settings

logger = logging.getLogger(__name__)


class ProphetTrainer:
    """
    Trains Prophet models for trend score forecasting.

    Prophet is well-suited for:
    - Capturing weekly and yearly seasonality
    - Handling holidays (alcohol sales spikes)
    - Robust to missing data
    - Fast training
    """

    def __init__(self, model_dir: Optional[str] = None):
        """
        Initialize the trainer.

        Args:
            model_dir: Directory to save models
        """
        self.model_dir = Path(model_dir or settings.model_storage_path)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def prepare_data(
        self,
        scores: list[tuple[datetime, float]],
    ) -> pd.DataFrame:
        """
        Prepare data for Prophet training.

        Prophet requires a DataFrame with 'ds' (date) and 'y' (value) columns.

        Args:
            scores: List of (datetime, score) tuples

        Returns:
            DataFrame in Prophet format
        """
        df = pd.DataFrame(scores, columns=["ds", "y"])
        df["ds"] = pd.to_datetime(df["ds"])
        df = df.sort_values("ds").reset_index(drop=True)

        # Remove duplicates (keep last for same date)
        df = df.drop_duplicates(subset=["ds"], keep="last")

        return df

    def create_holidays_df(self) -> pd.DataFrame:
        """
        Create holidays dataframe for alcohol-relevant dates.

        Returns:
            DataFrame with holiday dates
        """
        # Key holidays for alcohol industry
        holidays = []

        # Generate holidays for several years
        for year in range(2020, 2030):
            holidays.extend([
                {"holiday": "new_years", "ds": f"{year}-01-01"},
                {"holiday": "valentines", "ds": f"{year}-02-14"},
                {"holiday": "st_patricks", "ds": f"{year}-03-17"},
                {"holiday": "cinco_de_mayo", "ds": f"{year}-05-05"},
                {"holiday": "memorial_day", "ds": f"{year}-05-27"},  # Approx
                {"holiday": "july_4th", "ds": f"{year}-07-04"},
                {"holiday": "labor_day", "ds": f"{year}-09-02"},  # Approx
                {"holiday": "halloween", "ds": f"{year}-10-31"},
                {"holiday": "thanksgiving", "ds": f"{year}-11-28"},  # Approx
                {"holiday": "christmas_eve", "ds": f"{year}-12-24"},
                {"holiday": "christmas", "ds": f"{year}-12-25"},
                {"holiday": "new_years_eve", "ds": f"{year}-12-31"},
            ])

        return pd.DataFrame(holidays)

    def train(
        self,
        product_id: UUID,
        scores: list[tuple[datetime, float]],
        include_holidays: bool = True,
    ) -> tuple[Prophet, dict]:
        """
        Train a Prophet model for a product.

        Args:
            product_id: Product UUID
            scores: Historical score data
            include_holidays: Whether to include holiday effects

        Returns:
            Tuple of (trained model, training metrics)
        """
        logger.info(f"Training Prophet model for product {product_id}")

        # Prepare data
        df = self.prepare_data(scores)

        if len(df) < settings.min_data_points_for_training:
            raise ValueError(
                f"Insufficient data: {len(df)} points "
                f"(need {settings.min_data_points_for_training})"
            )

        # Initialize Prophet
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            seasonality_mode="multiplicative",
            changepoint_prior_scale=0.05,  # Flexibility of trend
            interval_width=0.95,  # Prediction intervals
        )

        # Add holidays
        if include_holidays:
            holidays_df = self.create_holidays_df()
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                holidays=holidays_df,
                seasonality_mode="multiplicative",
                changepoint_prior_scale=0.05,
                interval_width=0.95,
            )

        # Train
        model.fit(df)

        # Calculate training metrics
        metrics = self._calculate_metrics(model, df)

        # Save model
        self._save_model(model, product_id)

        logger.info(
            f"Prophet model trained for {product_id}: "
            f"MAE={metrics['mae']:.2f}, MAPE={metrics['mape']:.2f}%"
        )

        return model, metrics

    def _calculate_metrics(
        self,
        model: Prophet,
        df: pd.DataFrame,
    ) -> dict:
        """
        Calculate training metrics.

        Uses cross-validation for robust metrics.
        """
        # In-sample predictions
        predictions = model.predict(df)

        y_true = df["y"].values
        y_pred = predictions["yhat"].values

        # Mean Absolute Error
        mae = np.mean(np.abs(y_true - y_pred))

        # Mean Absolute Percentage Error
        mape = np.mean(np.abs((y_true - y_pred) / y_true)) * 100

        # Root Mean Square Error
        rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))

        # Directional accuracy (did we predict direction correctly?)
        if len(y_true) > 1:
            actual_direction = np.sign(np.diff(y_true))
            pred_direction = np.sign(np.diff(y_pred))
            directional_accuracy = np.mean(actual_direction == pred_direction) * 100
        else:
            directional_accuracy = 0

        return {
            "mae": float(mae),
            "mape": float(mape),
            "rmse": float(rmse),
            "directional_accuracy": float(directional_accuracy),
            "data_points": len(df),
            "trained_at": datetime.utcnow().isoformat(),
        }

    def forecast(
        self,
        product_id: UUID,
        periods: int = 7,
    ) -> pd.DataFrame:
        """
        Generate forecast using trained model.

        Args:
            product_id: Product UUID
            periods: Number of days to forecast

        Returns:
            DataFrame with forecasts
        """
        model = self._load_model(product_id)

        if model is None:
            raise ValueError(f"No trained model found for product {product_id}")

        # Create future dataframe
        future = model.make_future_dataframe(periods=periods)

        # Generate predictions
        forecast = model.predict(future)

        # Return only future predictions
        return forecast.tail(periods)[
            ["ds", "yhat", "yhat_lower", "yhat_upper"]
        ].rename(columns={
            "ds": "date",
            "yhat": "predicted",
            "yhat_lower": "lower_95",
            "yhat_upper": "upper_95",
        })

    def _save_model(self, model: Prophet, product_id: UUID) -> str:
        """Save model to disk."""
        filepath = self.model_dir / f"prophet_{product_id}.pkl"

        with open(filepath, "wb") as f:
            pickle.dump(model, f)

        return str(filepath)

    def _load_model(self, product_id: UUID) -> Optional[Prophet]:
        """Load model from disk."""
        filepath = self.model_dir / f"prophet_{product_id}.pkl"

        if not filepath.exists():
            return None

        with open(filepath, "rb") as f:
            return pickle.load(f)

    def model_exists(self, product_id: UUID) -> bool:
        """Check if a model exists for a product."""
        filepath = self.model_dir / f"prophet_{product_id}.pkl"
        return filepath.exists()


class ProphetBatchTrainer:
    """
    Batch training of Prophet models for multiple products.
    """

    def __init__(self, trainer: Optional[ProphetTrainer] = None):
        self.trainer = trainer or ProphetTrainer()

    def train_all(
        self,
        products_data: dict[UUID, list[tuple[datetime, float]]],
        min_data_points: int = 30,
    ) -> dict[UUID, dict]:
        """
        Train models for multiple products.

        Args:
            products_data: Dict mapping product_id to score history
            min_data_points: Minimum data points required

        Returns:
            Dict mapping product_id to training results
        """
        results = {}

        for product_id, scores in products_data.items():
            if len(scores) < min_data_points:
                logger.warning(
                    f"Skipping {product_id}: only {len(scores)} data points"
                )
                results[product_id] = {
                    "status": "skipped",
                    "reason": "insufficient_data",
                }
                continue

            try:
                _, metrics = self.trainer.train(product_id, scores)
                results[product_id] = {
                    "status": "success",
                    "metrics": metrics,
                }
            except Exception as e:
                logger.error(f"Failed to train model for {product_id}: {e}")
                results[product_id] = {
                    "status": "failed",
                    "error": str(e),
                }

        # Log summary
        successful = sum(1 for r in results.values() if r["status"] == "success")
        logger.info(f"Batch training complete: {successful}/{len(products_data)} models trained")

        return results
