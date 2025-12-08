"""ABVTrends ML Training - Prophet and LSTM model trainers."""

import logging

logger = logging.getLogger(__name__)

# Lazy imports to allow app to start without heavy ML dependencies
try:
    from app.ml.training.lstm_train import LSTMBatchTrainer, LSTMTrainer
except ImportError as e:
    logger.warning(f"LSTM training not available: {e}")
    LSTMTrainer = None
    LSTMBatchTrainer = None

try:
    from app.ml.training.prophet_train import ProphetBatchTrainer, ProphetTrainer
except ImportError as e:
    logger.warning(f"Prophet training not available: {e}")
    ProphetTrainer = None
    ProphetBatchTrainer = None

__all__ = [
    "ProphetTrainer",
    "ProphetBatchTrainer",
    "LSTMTrainer",
    "LSTMBatchTrainer",
]
