"""
Machine Learning Pipeline

Isolation Forest-based anomaly detection with lightweight, explainable inference.
Trains on baseline normal behavior, detects deviations.
"""

import pickle
import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
import json
from pathlib import Path

try:
    from sklearn.ensemble import IsolationForest
except ImportError:
    IsolationForest = None

logger = logging.getLogger(__name__)


@dataclass
class AnomalyScore:
    """Anomaly detection result"""
    event_id: str
    timestamp: str
    anomaly_score: float  # -1 to 1, where 1 is most anomalous
    is_anomaly: bool
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    confidence: float
    contributing_features: Dict[str, float]  # Feature importance
    explanation: str


class IsolationForestModel:
    """Wrapper around sklearn Isolation Forest"""
    
    def __init__(
        self,
        contamination: float = 0.1,
        n_estimators: int = 100,
        max_samples: int = 256,
        random_state: int = 42
    ):
        if IsolationForest is None:
            raise ImportError("scikit-learn required for ML pipeline")
        
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            max_samples=max_samples,
            random_state=random_state,
        )
        self.feature_names = [
            'ip_failed_logins',
            'ip_unique_users_attempted',
            'ip_failed_to_success_ratio',
            'ip_avg_inter_attempt_seconds',
            'ip_auth_method_variance',
            'user_login_time_std_devs',
            'user_new_ip_detected',
            'user_first_sudo_usage',
            'user_failed_sudo_attempts',
            'user_login_from_new_asn',
            'session_login_to_privesc_seconds',
            'session_post_login_command_rate',
            'session_lolbin_executed',
            'session_account_changes',
        ]
        self.scaler_params = None
    
    def train(self, feature_matrix: np.ndarray) -> None:
        """Train model on baseline data"""
        if feature_matrix.shape[0] < 10:
            logger.warning("Very small training set, model may not generalize")
        
        # Normalize features
        feature_matrix = self._normalize_features(feature_matrix, fit=True)
        
        # Train Isolation Forest
        self.model.fit(feature_matrix)
        logger.info(f"Model trained on {feature_matrix.shape[0]} samples")
    
    def predict(self, feature_matrix: np.ndarray) -> List[Tuple[float, bool]]:
        """
        Predict anomaly scores.
        Returns list of (score, is_anomaly) tuples.
        Score ranges from -1 (anomaly) to 1 (normal).
        """
        feature_matrix = self._normalize_features(feature_matrix)
        
        # Get anomaly scores (-1 for anomalies, 1 for normal)
        predictions = self.model.predict(feature_matrix)
        
        # Get decision function scores (negative means anomaly)
        decision_scores = self.model.score_samples(feature_matrix)
        
        results = []
        for pred, score in zip(predictions, decision_scores):
            is_anomaly = (pred == -1)
            # Normalize score to 0-1 (0 = normal, 1 = anomaly)
            normalized_score = 1 / (1 + np.exp(score))
            results.append((float(normalized_score), is_anomaly))
        
        return results
    
    def _normalize_features(self, X: np.ndarray, fit: bool = False) -> np.ndarray:
        """Normalize features using z-score normalization"""
        X = np.array(X, dtype=np.float64)
        
        if fit:
            self.scaler_params = {
                'mean': np.mean(X, axis=0),
                'std': np.std(X, axis=0),
            }
        
        if self.scaler_params is None:
            logger.warning("Model not trained, using feature normalization")
            self.scaler_params = {
                'mean': np.mean(X, axis=0),
                'std': np.std(X, axis=0),
            }
        
        # Avoid division by zero
        std = self.scaler_params['std'].copy()
        std[std == 0] = 1
        
        X_normalized = (X - self.scaler_params['mean']) / std
        return X_normalized
    
    def save(self, model_path: str) -> None:
        """Save model to disk"""
        data = {
            'model': self.model,
            'feature_names': self.feature_names,
            'scaler_params': self.scaler_params,
        }
        with open(model_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"Model saved to {model_path}")
    
    @staticmethod
    def load(model_path: str) -> "IsolationForestModel":
        """Load model from disk"""
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
        
        instance = IsolationForestModel()
        instance.model = data['model']
        instance.feature_names = data['feature_names']
        instance.scaler_params = data['scaler_params']
        
        logger.info(f"Model loaded from {model_path}")
        return instance


class AnomalyDetector:
    """
    Coordinates ML-based anomaly detection with explainability.
    Maps scores to risk levels and generates explanations.
    """
    
    def __init__(
        self,
        model: IsolationForestModel,
        low_threshold: float = 0.4,
        medium_threshold: float = 0.6,
        high_threshold: float = 0.8,
        critical_threshold: float = 0.9,
    ):
        self.model = model
        self.low_threshold = low_threshold
        self.medium_threshold = medium_threshold
        self.high_threshold = high_threshold
        self.critical_threshold = critical_threshold
        
        # Feature importance cache
        self.feature_importance = None
    
    def detect_anomalies(
        self,
        feature_vectors: List,
        metadata: List[Dict],
    ) -> List[AnomalyScore]:
        """Detect anomalies in feature vectors"""
        if not feature_vectors:
            return []
        
        # Convert to ML matrix
        X = np.array([v.to_ml_vector() for v in feature_vectors])
        
        # Get predictions
        predictions = self.model.predict(X)
        
        results = []
        for i, (score, is_anomaly) in enumerate(predictions):
            meta = metadata[i] if i < len(metadata) else {}
            vector = feature_vectors[i] if i < len(feature_vectors) else None
            
            # Classify risk level
            risk_level = self._score_to_risk_level(score)
            
            # Calculate confidence
            confidence = min(score * 1.5, 1.0)  # Normalize to 0-1
            
            # Generate explanation
            explanation = self._generate_explanation(vector, score, is_anomaly)
            
            # Get contributing features
            contributing_features = self._get_contributing_features(vector, score)
            
            result = AnomalyScore(
                event_id=meta.get('event_id', ''),
                timestamp=meta.get('timestamp', datetime.now().isoformat()),
                anomaly_score=float(score),
                is_anomaly=bool(is_anomaly),
                risk_level=risk_level,
                confidence=float(confidence),
                contributing_features=contributing_features,
                explanation=explanation,
            )
            results.append(result)
        
        return results
    
    def _score_to_risk_level(self, score: float) -> str:
        """Convert anomaly score to risk level"""
        if score >= self.critical_threshold:
            return "CRITICAL"
        elif score >= self.high_threshold:
            return "HIGH"
        elif score >= self.medium_threshold:
            return "MEDIUM"
        elif score >= self.low_threshold:
            return "LOW"
        else:
            return "NORMAL"
    
    def _generate_explanation(self, vector, score: float, is_anomaly: bool) -> str:
        """Generate human-readable explanation of anomaly"""
        if not is_anomaly:
            return "Event appears normal"
        
        if vector is None:
            return "Unable to generate explanation"
        
        # Identify contributing factors
        factors = []
        
        if vector.ip_failed_logins > 5:
            factors.append(f"High failed login attempts ({vector.ip_failed_logins})")
        
        if vector.ip_unique_users_attempted > 5:
            factors.append(f"Scanning multiple users ({vector.ip_unique_users_attempted})")
        
        if vector.ip_failed_to_success_ratio > 0.7:
            factors.append(f"High failure rate ({vector.ip_failed_to_success_ratio:.1%})")
        
        if vector.user_new_ip_detected:
            factors.append("Login from new IP address")
        
        if vector.user_first_sudo_usage:
            factors.append("First sudo usage for user")
        
        if vector.user_failed_sudo_attempts > 3:
            factors.append(f"Multiple failed sudo attempts ({vector.user_failed_sudo_attempts})")
        
        if vector.session_login_to_privesc_seconds > 0 and vector.session_login_to_privesc_seconds < 60:
            factors.append(f"Rapid privilege escalation ({int(vector.session_login_to_privesc_seconds)}s after login)")
        
        if vector.session_lolbin_executed:
            factors.append("Potential LOLBin execution detected")
        
        if not factors:
            return "Anomaly detected but specific factors unclear"
        
        return "Possible attack detected: " + "; ".join(factors)
    
    def _get_contributing_features(self, vector, score: float) -> Dict[str, float]:
        """Identify which features contributed most to anomaly score"""
        if vector is None:
            return {}
        
        # Normalize feature values to 0-1 for comparison
        features = vector.to_ml_vector()
        
        # Feature importance heuristic: features with high absolute values
        contributions = {}
        feature_names = self.model.feature_names
        
        for name, value in zip(feature_names, features):
            # Normalize contribution
            contribution = min(abs(value), 1.0)
            if contribution > 0.1:  # Only include significant features
                contributions[name] = float(contribution)
        
        # Sort by contribution
        return dict(sorted(contributions.items(), key=lambda x: x[1], reverse=True))


class MLPipeline:
    """Orchestrates the full ML training and inference pipeline"""
    
    def __init__(
        self,
        model_path: str = "/var/lib/devilnet/isolation_forest.pkl",
        contamination: float = 0.1,
        n_estimators: int = 100,
    ):
        self.model_path = model_path
        self.model = IsolationForestModel(contamination=contamination, n_estimators=n_estimators)
        self.detector = AnomalyDetector(self.model)
        self.is_trained = False
    
    def train_from_baseline(self, feature_vectors: List) -> None:
        """Train model on baseline normal behavior"""
        if len(feature_vectors) < 100:
            logger.warning("Small training dataset - model may overfit")
        
        X = np.array([v.to_ml_vector() for v in feature_vectors])
        self.model.train(X)
        self.is_trained = True
        self.save_model()
    
    def infer(
        self,
        feature_vectors: List,
        metadata: List[Dict],
    ) -> List[AnomalyScore]:
        """Run inference on new data"""
        if not self.is_trained:
            logger.warning("Model not trained, loading from disk...")
            if not self.load_model():
                raise RuntimeError("Model not trained and cannot load from disk")
        
        return self.detector.detect_anomalies(feature_vectors, metadata)
    
    def save_model(self) -> None:
        """Save trained model to disk"""
        self.model.save(self.model_path)
    
    def load_model(self) -> bool:
        """Load model from disk"""
        try:
            self.model = IsolationForestModel.load(self.model_path)
            self.detector.model = self.model
            self.is_trained = True
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False
