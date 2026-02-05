"""
Configuration Management

Defines detection thresholds, alert levels, and system parameters.
"""

from dataclasses import dataclass, field
from typing import Dict, List
from pathlib import Path
import json


@dataclass
class FeatureThresholds:
    """Anomaly detection sensitivity thresholds"""
    # Per-IP thresholds
    failed_login_threshold: int = 5
    unique_users_threshold: int = 10
    failed_to_success_ratio_threshold: float = 0.8
    min_inter_attempt_seconds: int = 2
    
    # Per-user thresholds
    login_time_std_devs: float = 3.0
    new_ip_risk_boost: float = 0.3
    first_sudo_risk_boost: float = 0.25
    failed_sudo_threshold: int = 3
    
    # Per-session thresholds
    login_to_privesc_seconds: int = 60
    post_login_command_rate: float = 10.0  # commands per minute
    lolbin_execution_risk_boost: float = 0.4


@dataclass
class AlertLevels:
    """Risk scoring and alert classification"""
    low_threshold: float = 0.4
    medium_threshold: float = 0.6
    high_threshold: float = 0.8
    critical_threshold: float = 0.9


@dataclass
class IncidentResponse:
    """Automated response action thresholds"""
    lock_account_at_risk_level: str = "HIGH"
    block_ip_at_risk_level: str = "HIGH"
    terminate_session_at_risk_level: str = "CRITICAL"
    
    # Cooldown periods (seconds) to prevent action spam
    lock_account_cooldown: int = 300
    block_ip_cooldown: int = 600
    terminate_session_cooldown: int = 180
    
    # Enable/disable automated response (disable for testing)
    enable_automated_actions: bool = False


@dataclass
class LogSources:
    """Log file paths and ingestion settings"""
    auth_log: str = "/var/log/auth.log"
    syslog: str = "/var/log/syslog"
    audit_log: str = "/var/log/audit/audit.log"
    fail2ban_log: str = "/var/log/fail2ban.log"
    
    # Read mode: "file" for file tailing, "stdin" for piped input
    read_mode: str = "file"
    
    # Tail settings
    tail_poll_interval_seconds: int = 5
    tail_batch_size: int = 1000
    
    # Output paths (must be writable)
    state_dir: str = "/var/lib/devilnet"
    alert_dir: str = "/var/log/devilnet/alerts"
    report_dir: str = "/var/log/devilnet/reports"


@dataclass
class MLPipeline:
    """Machine learning configuration"""
    # Isolation Forest parameters
    contamination: float = 0.1  # Expected anomaly rate
    n_estimators: int = 100
    max_samples: int = 256
    random_state: int = 42
    
    # Feature window (minutes)
    feature_window_minutes: int = 5
    
    # Training data
    min_samples_for_training: int = 1000
    training_data_file: str = "baseline_events.jsonl"
    model_file: str = "isolation_forest.pkl"
    
    # Inference batch size
    batch_size: int = 100


@dataclass
class SecurityPolicy:
    """Security constraints enforcement"""
    # Execution user (non-root)
    execution_user: str = "devilnet"
    
    # Privilege enforcement
    enforce_non_root: bool = True
    
    # No network access
    allow_network: bool = False
    
    # No dynamic execution
    allow_eval: bool = False
    allow_shell_exec: bool = False
    
    # Filesystem isolation
    readonly_paths: List[str] = field(default_factory=lambda: [
        "/var/log/auth.log",
        "/var/log/syslog",
        "/var/log/audit/",
        "/var/log/fail2ban.log",
    ])
    
    writable_paths: List[str] = field(default_factory=lambda: [
        "/var/lib/devilnet/",
        "/var/log/devilnet/",
    ])


@dataclass
class DevilnetConfig:
    """Root configuration object"""
    feature_thresholds: FeatureThresholds = field(default_factory=FeatureThresholds)
    alert_levels: AlertLevels = field(default_factory=AlertLevels)
    incident_response: IncidentResponse = field(default_factory=IncidentResponse)
    log_sources: LogSources = field(default_factory=LogSources)
    ml_pipeline: MLPipeline = field(default_factory=MLPipeline)
    security_policy: SecurityPolicy = field(default_factory=SecurityPolicy)
    
    @staticmethod
    def load_from_file(config_path: str) -> "DevilnetConfig":
        """Load configuration from JSON file"""
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        return DevilnetConfig(
            feature_thresholds=FeatureThresholds(**data.get('feature_thresholds', {})),
            alert_levels=AlertLevels(**data.get('alert_levels', {})),
            incident_response=IncidentResponse(**data.get('incident_response', {})),
            log_sources=LogSources(**data.get('log_sources', {})),
            ml_pipeline=MLPipeline(**data.get('ml_pipeline', {})),
            security_policy=SecurityPolicy(**data.get('security_policy', {})),
        )
    
    def save_to_file(self, config_path: str) -> None:
        """Save configuration to JSON file"""
        data = {
            'feature_thresholds': self.feature_thresholds.__dict__,
            'alert_levels': self.alert_levels.__dict__,
            'incident_response': self.incident_response.__dict__,
            'log_sources': self.log_sources.__dict__,
            'ml_pipeline': self.ml_pipeline.__dict__,
            'security_policy': self.security_policy.__dict__,
        }
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)


def get_default_config() -> DevilnetConfig:
    """Get default configuration"""
    return DevilnetConfig()
