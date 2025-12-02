"""
ABVTrends - LSTM Model Training

Trains LSTM neural networks for time series forecasting.
LSTM captures complex patterns and dependencies in sequential data.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from uuid import UUID

import numpy as np
import pandas as pd

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    tf = None

from app.core.config import settings

logger = logging.getLogger(__name__)


class LSTMTrainer:
    """
    Trains LSTM models for trend score forecasting.

    LSTM is well-suited for:
    - Capturing long-term dependencies
    - Learning complex patterns
    - Handling non-linear relationships
    """

    # Model architecture parameters
    SEQUENCE_LENGTH = 14  # Look back 14 days
    LSTM_UNITS = 50
    DROPOUT_RATE = 0.2
    EPOCHS = 100
    BATCH_SIZE = 32

    def __init__(self, model_dir: Optional[str] = None):
        """
        Initialize the trainer.

        Args:
            model_dir: Directory to save models
        """
        if not TENSORFLOW_AVAILABLE:
            logger.warning("TensorFlow not available. LSTM training disabled.")

        self.model_dir = Path(model_dir or settings.model_storage_path)
        self.model_dir.mkdir(parents=True, exist_ok=True)

    def prepare_data(
        self,
        scores: list[tuple[datetime, float]],
        sequence_length: int = None,
    ) -> Tuple[np.ndarray, np.ndarray, float, float]:
        """
        Prepare data for LSTM training.

        Creates sequences of historical data for supervised learning.

        Args:
            scores: List of (datetime, score) tuples
            sequence_length: Number of time steps to look back

        Returns:
            Tuple of (X, y, scale_min, scale_max) for training
        """
        sequence_length = sequence_length or self.SEQUENCE_LENGTH

        # Convert to array and sort by date
        df = pd.DataFrame(scores, columns=["date", "score"])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        values = df["score"].values.astype(float)

        # Normalize to 0-1 range
        scale_min = values.min()
        scale_max = values.max()
        if scale_max - scale_min > 0:
            normalized = (values - scale_min) / (scale_max - scale_min)
        else:
            normalized = values

        # Create sequences
        X, y = [], []
        for i in range(len(normalized) - sequence_length):
            X.append(normalized[i : i + sequence_length])
            y.append(normalized[i + sequence_length])

        X = np.array(X)
        y = np.array(y)

        # Reshape for LSTM [samples, time steps, features]
        X = X.reshape((X.shape[0], X.shape[1], 1))

        return X, y, scale_min, scale_max

    def build_model(
        self,
        sequence_length: int = None,
        lstm_units: int = None,
    ) -> "Sequential":
        """
        Build LSTM model architecture.

        Args:
            sequence_length: Input sequence length
            lstm_units: Number of LSTM units

        Returns:
            Compiled Keras model
        """
        if not TENSORFLOW_AVAILABLE:
            raise RuntimeError("TensorFlow is not available")

        sequence_length = sequence_length or self.SEQUENCE_LENGTH
        lstm_units = lstm_units or self.LSTM_UNITS

        model = Sequential([
            LSTM(
                lstm_units,
                activation="relu",
                input_shape=(sequence_length, 1),
                return_sequences=True,
            ),
            Dropout(self.DROPOUT_RATE),
            LSTM(lstm_units // 2, activation="relu"),
            Dropout(self.DROPOUT_RATE),
            Dense(25, activation="relu"),
            Dense(1),
        ])

        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss="mse",
            metrics=["mae"],
        )

        return model

    def train(
        self,
        product_id: UUID,
        scores: list[tuple[datetime, float]],
        validation_split: float = 0.2,
    ) -> Tuple["Sequential", dict]:
        """
        Train LSTM model for a product.

        Args:
            product_id: Product UUID
            scores: Historical score data
            validation_split: Fraction of data for validation

        Returns:
            Tuple of (trained model, training metrics)
        """
        if not TENSORFLOW_AVAILABLE:
            raise RuntimeError("TensorFlow is not available for LSTM training")

        logger.info(f"Training LSTM model for product {product_id}")

        # Prepare data
        X, y, scale_min, scale_max = self.prepare_data(scores)

        if len(X) < 10:
            raise ValueError(f"Insufficient sequences: {len(X)} (need at least 10)")

        # Split data
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]

        # Build model
        model = self.build_model()

        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor="val_loss",
                patience=10,
                restore_best_weights=True,
            ),
        ]

        # Train
        history = model.fit(
            X_train, y_train,
            epochs=self.EPOCHS,
            batch_size=self.BATCH_SIZE,
            validation_data=(X_val, y_val),
            callbacks=callbacks,
            verbose=0,
        )

        # Calculate metrics
        metrics = self._calculate_metrics(
            model, X_val, y_val, scale_min, scale_max, history
        )

        # Save model and scaling parameters
        self._save_model(model, product_id, scale_min, scale_max)

        logger.info(
            f"LSTM model trained for {product_id}: "
            f"MAE={metrics['mae']:.2f}, Val Loss={metrics['val_loss']:.4f}"
        )

        return model, metrics

    def _calculate_metrics(
        self,
        model: "Sequential",
        X_val: np.ndarray,
        y_val: np.ndarray,
        scale_min: float,
        scale_max: float,
        history,
    ) -> dict:
        """Calculate training metrics."""
        # Predictions on validation set
        y_pred = model.predict(X_val, verbose=0).flatten()

        # Denormalize
        y_val_actual = y_val * (scale_max - scale_min) + scale_min
        y_pred_actual = y_pred * (scale_max - scale_min) + scale_min

        # Calculate metrics
        mae = np.mean(np.abs(y_val_actual - y_pred_actual))
        rmse = np.sqrt(np.mean((y_val_actual - y_pred_actual) ** 2))
        mape = np.mean(np.abs((y_val_actual - y_pred_actual) / y_val_actual)) * 100

        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "mape": float(mape),
            "val_loss": float(history.history["val_loss"][-1]),
            "train_loss": float(history.history["loss"][-1]),
            "epochs_trained": len(history.history["loss"]),
            "trained_at": datetime.utcnow().isoformat(),
        }

    def forecast(
        self,
        product_id: UUID,
        recent_scores: list[float],
        periods: int = 7,
    ) -> list[dict]:
        """
        Generate forecast using trained model.

        Args:
            product_id: Product UUID
            recent_scores: Most recent scores (at least SEQUENCE_LENGTH)
            periods: Number of days to forecast

        Returns:
            List of forecast dictionaries
        """
        model, scale_min, scale_max = self._load_model(product_id)

        if model is None:
            raise ValueError(f"No trained model found for product {product_id}")

        # Ensure we have enough data
        if len(recent_scores) < self.SEQUENCE_LENGTH:
            raise ValueError(
                f"Need at least {self.SEQUENCE_LENGTH} recent scores, "
                f"got {len(recent_scores)}"
            )

        # Normalize
        scores_array = np.array(recent_scores[-self.SEQUENCE_LENGTH:])
        if scale_max - scale_min > 0:
            normalized = (scores_array - scale_min) / (scale_max - scale_min)
        else:
            normalized = scores_array

        # Generate forecasts iteratively
        forecasts = []
        current_sequence = normalized.copy()

        for i in range(periods):
            # Reshape for prediction
            X = current_sequence.reshape((1, self.SEQUENCE_LENGTH, 1))

            # Predict
            pred_normalized = model.predict(X, verbose=0)[0, 0]

            # Denormalize
            pred_actual = pred_normalized * (scale_max - scale_min) + scale_min

            # Clamp to valid range
            pred_actual = max(0, min(100, pred_actual))

            forecasts.append({
                "day": i + 1,
                "predicted": float(pred_actual),
            })

            # Update sequence for next prediction
            current_sequence = np.roll(current_sequence, -1)
            current_sequence[-1] = pred_normalized

        return forecasts

    def _save_model(
        self,
        model: "Sequential",
        product_id: UUID,
        scale_min: float,
        scale_max: float,
    ) -> str:
        """Save model and scaling parameters."""
        model_path = self.model_dir / f"lstm_{product_id}.keras"
        params_path = self.model_dir / f"lstm_{product_id}_params.npy"

        model.save(model_path)
        np.save(params_path, np.array([scale_min, scale_max]))

        return str(model_path)

    def _load_model(
        self,
        product_id: UUID,
    ) -> Tuple[Optional["Sequential"], float, float]:
        """Load model and scaling parameters."""
        model_path = self.model_dir / f"lstm_{product_id}.keras"
        params_path = self.model_dir / f"lstm_{product_id}_params.npy"

        if not model_path.exists():
            return None, 0.0, 100.0

        model = load_model(model_path)
        params = np.load(params_path)

        return model, float(params[0]), float(params[1])

    def model_exists(self, product_id: UUID) -> bool:
        """Check if model exists."""
        model_path = self.model_dir / f"lstm_{product_id}.keras"
        return model_path.exists()


class LSTMBatchTrainer:
    """Batch training of LSTM models."""

    def __init__(self, trainer: Optional[LSTMTrainer] = None):
        self.trainer = trainer or LSTMTrainer()

    def train_all(
        self,
        products_data: dict[UUID, list[tuple[datetime, float]]],
        min_data_points: int = 30,
    ) -> dict[UUID, dict]:
        """
        Train LSTM models for multiple products.

        Args:
            products_data: Dict mapping product_id to score history
            min_data_points: Minimum data points required

        Returns:
            Dict mapping product_id to training results
        """
        if not TENSORFLOW_AVAILABLE:
            logger.warning("TensorFlow not available. Skipping LSTM training.")
            return {
                pid: {"status": "skipped", "reason": "tensorflow_unavailable"}
                for pid in products_data
            }

        results = {}

        for product_id, scores in products_data.items():
            if len(scores) < min_data_points:
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
                logger.error(f"Failed to train LSTM for {product_id}: {e}")
                results[product_id] = {
                    "status": "failed",
                    "error": str(e),
                }

        successful = sum(1 for r in results.values() if r["status"] == "success")
        logger.info(f"LSTM batch training: {successful}/{len(products_data)} models trained")

        return results
