"""
Resilient Engine with Error Recovery

Implements graceful error handling, automatic recovery, and script stability.
Ensures the script never crashes and continues monitoring despite errors.
"""

import logging
import sys
import time
import threading
import signal
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class ErrorRecoveryManager:
    """Manages error recovery and resilience"""
    
    def __init__(self, max_retries: int = 3, backoff_multiplier: float = 2.0):
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier
        self.error_counts: Dict[str, int] = {}
        self.lock = threading.Lock()
    
    def reset_error_count(self, component: str) -> None:
        """Reset error counter for component"""
        with self.lock:
            self.error_counts[component] = 0
    
    def record_error(self, component: str) -> int:
        """Record an error and return current count"""
        with self.lock:
            self.error_counts[component] = self.error_counts.get(component, 0) + 1
            return self.error_counts[component]
    
    def get_backoff_time(self, component: str) -> float:
        """Get backoff time in seconds"""
        with self.lock:
            error_count = self.error_counts.get(component, 0)
        
        if error_count == 0:
            return 0
        
        backoff = min(
            (self.backoff_multiplier ** (error_count - 1)),
            300  # Max 5 minutes
        )
        return backoff
    
    def should_retry(self, component: str) -> bool:
        """Check if component should retry"""
        with self.lock:
            error_count = self.error_counts.get(component, 0)
        
        return error_count < self.max_retries


class CircuitBreaker:
    """Prevents cascading failures (circuit breaker pattern)"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self.lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        with self.lock:
            if self.state == "open":
                # Check if recovery timeout has passed
                if self._should_attempt_recovery():
                    self.state = "half-open"
                else:
                    raise Exception(f"Circuit breaker open (recovery in {self._time_until_recovery()}s)")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed for recovery"""
        if self.last_failure_time is None:
            return True
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout
    
    def _time_until_recovery(self) -> int:
        """Time until circuit can be half-open"""
        if self.last_failure_time is None:
            return 0
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        remaining = self.recovery_timeout - int(elapsed)
        return max(0, remaining)
    
    def _on_success(self) -> None:
        """Handle successful call"""
        with self.lock:
            self.failure_count = 0
            self.state = "closed"
            self.last_failure_time = None
    
    def _on_failure(self) -> None:
        """Handle failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"


class ResilientDevilnetEngine:
    """Enhanced Devilnet engine with error recovery"""
    
    def __init__(self, base_engine, ui=None):
        self.base_engine = base_engine
        self.ui = ui
        self.recovery_manager = ErrorRecoveryManager()
        self.circuit_breakers = {
            'ingestion': CircuitBreaker(),
            'ml_inference': CircuitBreaker(),
            'response': CircuitBreaker(),
            'reporting': CircuitBreaker(),
        }
        self.running = True
        self.stats = {
            'cycles_completed': 0,
            'cycles_failed': 0,
            'anomalies_detected': 0,
            'errors_recovered': 0,
            'uptime_seconds': 0,
        }
        self.start_time = datetime.now()
    
    def run_inference_cycle_resilient(self) -> List:
        """
        Run inference cycle with full error recovery.
        Never raises exceptions - always returns result or empty list.
        """
        try:
            # 1. INGESTION (with circuit breaker)
            events = []
            try:
                events = self.circuit_breakers['ingestion'].call(
                    self._safe_ingest_logs
                )
            except Exception as e:
                logger.warning(f"Ingestion failed: {e}")
                self._handle_error('ingestion', e)
            
            if not events:
                self.stats['cycles_completed'] += 1
                return []
            
            # 2. FEATURE EXTRACTION (with error handling)
            try:
                feature_vectors, metadata = self._safe_extract_features(events)
            except Exception as e:
                logger.warning(f"Feature extraction failed: {e}")
                self._log_ui_alert(f"Feature extraction error: {e}")
                self.stats['cycles_completed'] += 1
                return []
            
            if not feature_vectors:
                self.stats['cycles_completed'] += 1
                return []
            
            # 3. ML INFERENCE (with circuit breaker)
            anomaly_scores = []
            try:
                anomaly_scores = self.circuit_breakers['ml_inference'].call(
                    self._safe_ml_inference,
                    feature_vectors,
                    metadata
                )
            except Exception as e:
                logger.warning(f"ML inference failed: {e}")
                self._handle_error('ml_inference', e)
            
            # 4. PROCESS ANOMALIES (with error handling)
            anomalies = [a for a in anomaly_scores if a.is_anomaly]
            
            if anomalies:
                self.stats['anomalies_detected'] += len(anomalies)
                
                try:
                    self.circuit_breakers['response'].call(
                        self._safe_process_anomalies,
                        anomalies,
                        feature_vectors,
                        anomaly_scores
                    )
                except Exception as e:
                    logger.warning(f"Anomaly processing failed: {e}")
                    self._handle_error('response', e)
            
            self.stats['cycles_completed'] += 1
            self.recovery_manager.reset_error_count('main_loop')
            return anomalies
        
        except Exception as e:
            logger.error(f"Unexpected error in inference cycle: {e}", exc_info=True)
            self.stats['cycles_failed'] += 1
            self.stats['errors_recovered'] += 1
            self._log_ui_alert(f"Cycle error (recovered): {e}")
            return []
    
    def _safe_ingest_logs(self) -> List:
        """Safely ingest logs with error handling"""
        try:
            return self.base_engine.ingestion_pipeline.ingest_all()
        except Exception as e:
            logger.error(f"Log ingestion error: {e}")
            raise
    
    def _safe_extract_features(self, events) -> tuple:
        """Safely extract features with error handling"""
        feature_vectors = []
        metadata = []
        
        for event in events:
            try:
                vector = self.base_engine.feature_extractor.extract_features(event)
                feature_vectors.append(vector)
                metadata.append({
                    'event_id': vector.event_id,
                    'timestamp': vector.timestamp,
                    'source_ip': vector.source_ip,
                    'username': vector.username,
                    'event_type': vector.event_type,
                })
            except Exception as e:
                logger.debug(f"Feature extraction failed for event: {e}")
                continue
        
        return feature_vectors, metadata
    
    def _safe_ml_inference(self, feature_vectors, metadata) -> List:
        """Safely run ML inference with error handling"""
        try:
            return self.base_engine.ml_pipeline.infer(feature_vectors, metadata)
        except Exception as e:
            logger.error(f"ML inference error: {e}")
            raise
    
    def _safe_process_anomalies(self, anomalies, feature_vectors, anomaly_scores) -> None:
        """Safely process anomalies with error handling"""
        for anomaly in anomalies:
            try:
                # Find corresponding feature vector
                feature_vector = None
                for i, score in enumerate(anomaly_scores):
                    if score == anomaly:
                        feature_vector = feature_vectors[i] if i < len(feature_vectors) else None
                        break
                
                # Generate report
                report = self.base_engine.report_generator.generate_report(
                    anomaly_score=anomaly,
                    event_type=anomaly.event_type,
                    source_ip=anomaly.source_ip,
                    username=anomaly.username,
                    feature_vector=feature_vector,
                )
                
                # Save report
                self.base_engine.report_generator.save_report(report, format="both")
                
                # Write to alert stream
                self.base_engine.alert_stream.write_alert(
                    incident_id=report.incident_id,
                    severity=anomaly.risk_level,
                    event_type=anomaly.event_type,
                    source_ip=anomaly.source_ip,
                    username=anomaly.username,
                    anomaly_score=anomaly.anomaly_score,
                    explanation=anomaly.explanation,
                )
                
                # Determine response
                response_actions = self.base_engine.response_decision_engine.determine_response(
                    risk_level=anomaly.risk_level,
                    event_type=anomaly.event_type,
                    anomaly_score=anomaly.anomaly_score,
                    source_ip=anomaly.source_ip or "unknown",
                    username=anomaly.username or "unknown",
                )
                
                # Execute response
                for action in response_actions:
                    try:
                        self.base_engine.response_executor.execute_response(action)
                    except Exception as action_error:
                        logger.warning(f"Response execution error: {action_error}")
                
            except Exception as e:
                logger.error(f"Error processing anomaly: {e}")
    
    def _handle_error(self, component: str, error: Exception) -> None:
        """Handle component error with recovery"""
        error_count = self.recovery_manager.record_error(component)
        should_retry = self.recovery_manager.should_retry(component)
        backoff = self.recovery_manager.get_backoff_time(component)
        
        logger.warning(
            f"Component '{component}' error #{error_count}: {error} "
            f"(will retry: {should_retry}, backoff: {backoff}s)"
        )
        
        if not should_retry:
            logger.error(f"Component '{component}' exceeded max retries")
            self._log_ui_alert(f"Component {component} failed max retries", "CRITICAL")
    
    def _log_ui_alert(self, message: str, level: str = "WARNING") -> None:
        """Log alert to UI if available"""
        if self.ui:
            from devilnet.ui.terminal_ui import AlertLevel
            try:
                alert_level = getattr(AlertLevel, level, AlertLevel.INFO)
                self.ui.add_alert(message, alert_level)
            except Exception as e:
                logger.debug(f"Failed to log UI alert: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            **self.stats,
            'uptime_seconds': int(uptime),
            'success_rate': (
                self.stats['cycles_completed'] - self.stats['cycles_failed']
            ) / max(self.stats['cycles_completed'], 1),
        }


class SignalHandler:
    """Graceful shutdown on signals"""
    
    def __init__(self):
        self.running = True
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
    
    def _handle_signal(self, signum, frame) -> None:
        """Handle shutdown signal"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False


def create_resilient_engine(base_engine, ui=None) -> ResilientDevilnetEngine:
    """Factory to create resilient engine"""
    return ResilientDevilnetEngine(base_engine, ui)
