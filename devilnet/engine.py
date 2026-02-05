"""
Devilnet ML Detection Engine

Main orchestration layer coordinating all subsystems.
Secure, sandboxed anomaly detection and incident response.
"""

import logging
import sys
from typing import List, Optional
from pathlib import Path

from devilnet.core.security import initialize_security, SecurityException
from devilnet.core.config import get_default_config, DevilnetConfig
from devilnet.ingestion.log_parser import LogIngestionPipeline, AuthEvent
from devilnet.ml.feature_extraction import FeatureExtractor, FeatureVectorBatch
from devilnet.ml.pipeline import MLPipeline, AnomalyScore
from devilnet.response.incident_response import SafeResponseExecutor, ResponseDecisionEngine
from devilnet.reporting.reporter import IncidentReportGenerator, AlertStream

logger = logging.getLogger(__name__)


class DevilnetEngine:
    """Main anomaly detection and incident response engine"""
    
    def __init__(self, config: Optional[DevilnetConfig] = None):
        self.config = config or get_default_config()
        
        # Initialize security
        try:
            self.security_context = initialize_security(
                self.config.security_policy.execution_user
            )
        except SecurityException as e:
            logger.error(f"Security initialization failed: {e}")
            raise
        
        # Initialize subsystems
        self.ingestion_pipeline = LogIngestionPipeline({
            'auth_log': self.config.log_sources.auth_log,
            'syslog': self.config.log_sources.syslog,
            'audit_log': self.config.log_sources.audit_log,
        })
        
        self.feature_extractor = FeatureExtractor(
            window_minutes=self.config.ml_pipeline.feature_window_minutes
        )
        
        self.ml_pipeline = MLPipeline(
            model_path=f"{self.config.log_sources.state_dir}/isolation_forest.pkl",
            contamination=self.config.ml_pipeline.contamination,
            n_estimators=self.config.ml_pipeline.n_estimators,
        )
        
        self.response_executor = SafeResponseExecutor(
            response_log_dir=self.config.log_sources.alert_dir,
            enable_actions=self.config.incident_response.enable_automated_actions,
        )
        
        self.response_decision_engine = ResponseDecisionEngine(
            lock_account_threshold=self.config.incident_response.lock_account_at_risk_level,
            block_ip_threshold=self.config.incident_response.block_ip_at_risk_level,
            terminate_threshold=self.config.incident_response.terminate_session_at_risk_level,
        )
        
        self.report_generator = IncidentReportGenerator(
            report_dir=self.config.log_sources.report_dir
        )
        
        self.alert_stream = AlertStream(
            alert_file=f"{self.config.log_sources.alert_dir}/stream.jsonl"
        )
        
        logger.info("Devilnet Engine initialized successfully")
    
    def run_inference_cycle(self) -> List[AnomalyScore]:
        """Execute single inference cycle"""
        logger.debug("Starting inference cycle")
        
        # 1. Ingest logs
        events = self.ingestion_pipeline.ingest_all(
            batch_size=self.config.ml_pipeline.batch_size
        )
        
        if not events:
            logger.debug("No new events")
            return []
        
        logger.info(f"Ingested {len(events)} events")
        
        # 2. Extract features
        feature_vectors = []
        metadata = []
        
        for event in events:
            try:
                vector = self.feature_extractor.extract_features(event)
                feature_vectors.append(vector)
                metadata.append({
                    'event_id': vector.event_id,
                    'timestamp': vector.timestamp,
                    'source_ip': vector.source_ip,
                    'username': vector.username,
                    'event_type': vector.event_type,
                })
            except Exception as e:
                logger.warning(f"Feature extraction failed for event: {e}")
                continue
        
        if not feature_vectors:
            logger.warning("No features extracted")
            return []
        
        logger.debug(f"Extracted {len(feature_vectors)} feature vectors")
        
        # 3. Run ML inference
        try:
            anomaly_scores = self.ml_pipeline.infer(feature_vectors, metadata)
        except Exception as e:
            logger.error(f"ML inference failed: {e}")
            return []
        
        # 4. Filter to anomalies only
        anomalies = [a for a in anomaly_scores if a.is_anomaly]
        logger.info(f"Detected {len(anomalies)} anomalies")
        
        # 5. Generate reports and responses
        for anomaly in anomalies:
            try:
                self._process_anomaly(anomaly, feature_vectors[anomaly_scores.index(anomaly)] if anomaly in anomaly_scores else None)
            except Exception as e:
                logger.error(f"Anomaly processing failed: {e}")
        
        return anomalies
    
    def _process_anomaly(self, anomaly_score: AnomalyScore, feature_vector) -> None:
        """Process single anomaly: generate report, execute response"""
        
        logger.warning(
            f"ANOMALY DETECTED: {anomaly_score.event_type} from "
            f"{anomaly_score.contributing_features} (score: {anomaly_score.anomaly_score:.3f})"
        )
        
        # Generate report
        report = self.report_generator.generate_report(
            anomaly_score=anomaly_score,
            event_type=anomaly_score.event_type,
            source_ip=anomaly_score.source_ip,
            username=anomaly_score.username,
            feature_vector=feature_vector,
        )
        
        # Save reports
        self.report_generator.save_report(report, format="both")
        
        # Write to alert stream
        self.alert_stream.write_alert(
            incident_id=report.incident_id,
            severity=anomaly_score.risk_level,
            event_type=anomaly_score.event_type,
            source_ip=anomaly_score.source_ip,
            username=anomaly_score.username,
            anomaly_score=anomaly_score.anomaly_score,
            explanation=anomaly_score.explanation,
        )
        
        # Determine and execute response
        response_actions = self.response_decision_engine.determine_response(
            risk_level=anomaly_score.risk_level,
            event_type=anomaly_score.event_type,
            anomaly_score=anomaly_score.anomaly_score,
            source_ip=anomaly_score.source_ip or "unknown",
            username=anomaly_score.username or "unknown",
        )
        
        for action in response_actions:
            cooldown = self.config.incident_response.__dict__.get(
                f"{action.action_type.value}_cooldown", 300
            )
            self.response_executor.execute_response(action, cooldown_seconds=cooldown)
    
    def train_on_baseline(self, baseline_file: str) -> None:
        """Train ML model on baseline data"""
        logger.info(f"Training model on baseline: {baseline_file}")
        
        feature_vectors = []
        with open(baseline_file, 'r') as f:
            for line in f:
                # Load feature vectors from JSONL baseline
                # This is simplified; production would parse full format
                pass
        
        if len(feature_vectors) < self.config.ml_pipeline.min_samples_for_training:
            raise ValueError(
                f"Insufficient baseline data: {len(feature_vectors)} < "
                f"{self.config.ml_pipeline.min_samples_for_training}"
            )
        
        self.ml_pipeline.train_from_baseline(feature_vectors)
        logger.info("Model training completed")
    
    def print_status(self) -> None:
        """Print current engine status"""
        print("\n=== DEVILNET ENGINE STATUS ===")
        print(f"Security Context: {self.security_context.user} (UID:{self.security_context.uid})")
        print(f"ML Model Trained: {self.ml_pipeline.is_trained}")
        print(f"Automated Response Enabled: {self.config.incident_response.enable_automated_actions}")
        print(f"Config - Feature Window: {self.config.ml_pipeline.feature_window_minutes} min")
        print(f"Config - Alert Thresholds: LOW={self.config.alert_levels.low_threshold}, "
              f"MED={self.config.alert_levels.medium_threshold}, "
              f"HIGH={self.config.alert_levels.high_threshold}")
        print("==============================\n")


def create_engine(config_path: Optional[str] = None) -> DevilnetEngine:
    """Factory function to create engine with optional config"""
    if config_path:
        config = DevilnetConfig.load_from_file(config_path)
    else:
        config = get_default_config()
    
    return DevilnetEngine(config)
