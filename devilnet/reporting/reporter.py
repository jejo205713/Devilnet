"""
Incident Reporting

Generates machine-readable and human-readable incident reports.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime
import json
import logging
from pathlib import Path

from devilnet.core.mitre_mapping import MitreATTACKMapping, get_tactic_string

logger = logging.getLogger(__name__)


@dataclass
class IncidentReport:
    """Complete incident report"""
    incident_id: str
    timestamp: str
    severity: str
    event_type: str
    source_ip: Optional[str]
    username: Optional[str]
    anomaly_score: float
    confidence: float
    
    # MITRE ATT&CK
    mitre_tactics: List[str]
    mitre_techniques: List[Dict]
    
    # Timeline
    kill_chain_events: List[Dict]
    
    # ML explainability
    contributing_features: Dict[str, float]
    explanation: str
    
    # Response actions taken
    response_actions: List[Dict]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def to_human_readable(self) -> str:
        """Generate human-readable report"""
        lines = []
        lines.append("=" * 80)
        lines.append("SECURITY INCIDENT REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Header
        lines.append(f"Incident ID: {self.incident_id}")
        lines.append(f"Timestamp: {self.timestamp}")
        lines.append(f"Severity: {self.severity}")
        lines.append("")
        
        # Event summary
        lines.append("INCIDENT SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Event Type: {self.event_type}")
        if self.source_ip:
            lines.append(f"Source IP: {self.source_ip}")
        if self.username:
            lines.append(f"Target User: {self.username}")
        lines.append(f"Anomaly Score: {self.anomaly_score:.3f}")
        lines.append(f"ML Confidence: {self.confidence:.1%}")
        lines.append("")
        
        # MITRE ATT&CK
        lines.append("MITRE ATT&CK COVERAGE")
        lines.append("-" * 80)
        lines.append(f"Tactics: {', '.join(self.mitre_tactics)}")
        lines.append("")
        lines.append("Techniques:")
        for tech in self.mitre_techniques:
            lines.append(f"  - {tech['id']}: {tech['name']} ({tech['tactic']})")
        lines.append("")
        
        # Kill Chain
        if self.kill_chain_events:
            lines.append("KILL CHAIN TIMELINE")
            lines.append("-" * 80)
            for i, event in enumerate(self.kill_chain_events, 1):
                lines.append(f"{i}. [{event['timestamp']}] {event['description']}")
            lines.append("")
        
        # ML Explanation
        lines.append("MACHINE LEARNING ANALYSIS")
        lines.append("-" * 80)
        lines.append(f"Explanation: {self.explanation}")
        lines.append("")
        lines.append("Contributing Features:")
        for feature, value in sorted(self.contributing_features.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  - {feature}: {value:.3f}")
        lines.append("")
        
        # Response
        if self.response_actions:
            lines.append("RESPONSE ACTIONS")
            lines.append("-" * 80)
            for action in self.response_actions:
                lines.append(f"  - {action['action_type']}: {action['target']} ({action['result_message']})")
            lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)


class IncidentReportGenerator:
    """Generates incident reports from anomaly detections"""
    
    def __init__(self, report_dir: str = "/var/log/devilnet/reports"):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.incident_counter = 0
    
    def generate_report(
        self,
        anomaly_score,
        event_type: str,
        source_ip: Optional[str],
        username: Optional[str],
        feature_vector,
        response_actions: List = None,
    ) -> IncidentReport:
        """Generate incident report from anomaly detection"""
        
        self.incident_counter += 1
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d')}-{self.incident_counter:06d}"
        
        # Map to MITRE ATT&CK
        feature_dict = {
            'ip_failed_logins': feature_vector.ip_failed_logins if feature_vector else 0,
            'ip_unique_users_attempted': feature_vector.ip_unique_users_attempted if feature_vector else 0,
            'ip_failed_to_success_ratio': feature_vector.ip_failed_to_success_ratio if feature_vector else 0.0,
            'user_new_ip_detected': feature_vector.user_new_ip_detected if feature_vector else False,
            'user_first_sudo_usage': feature_vector.user_first_sudo_usage if feature_vector else False,
            'user_failed_sudo_attempts': feature_vector.user_failed_sudo_attempts if feature_vector else 0,
            'session_login_to_privesc_seconds': feature_vector.session_login_to_privesc_seconds if feature_vector else 0,
            'session_lolbin_executed': feature_vector.session_lolbin_executed if feature_vector else False,
        }
        
        mitre_techniques = MitreATTACKMapping.get_techniques_for_event(event_type, feature_dict)
        
        mitre_tactics = list(set(get_tactic_string(t.tactic) for t in mitre_techniques))
        mitre_techniques_dict = [
            {
                'id': t.technique_id,
                'name': t.name,
                'tactic': get_tactic_string(t.tactic),
                'description': t.description,
            }
            for t in mitre_techniques
        ]
        
        # Build kill chain
        kill_chain_events = [
            {
                'timestamp': datetime.now().isoformat(),
                'description': f"{event_type}: {source_ip or 'unknown'} -> {username or 'unknown'}",
            }
        ]
        
        # Determine severity
        severity = anomaly_score.risk_level if hasattr(anomaly_score, 'risk_level') else "UNKNOWN"
        score_value = anomaly_score.anomaly_score if hasattr(anomaly_score, 'anomaly_score') else anomaly_score
        confidence = anomaly_score.confidence if hasattr(anomaly_score, 'confidence') else 0.5
        
        # Extract explanation and features
        explanation = anomaly_score.explanation if hasattr(anomaly_score, 'explanation') else "Unknown anomaly"
        contributing_features = anomaly_score.contributing_features if hasattr(anomaly_score, 'contributing_features') else {}
        
        # Response actions
        response_actions_dict = []
        if response_actions:
            response_actions_dict = [
                {
                    'action_type': str(a.action_type),
                    'target': a.target,
                    'reason': a.reason,
                    'result_message': getattr(a, 'result_message', 'pending'),
                }
                for a in response_actions
            ]
        
        report = IncidentReport(
            incident_id=incident_id,
            timestamp=datetime.now().isoformat(),
            severity=severity,
            event_type=event_type,
            source_ip=source_ip,
            username=username,
            anomaly_score=float(score_value),
            confidence=float(confidence),
            mitre_tactics=mitre_tactics,
            mitre_techniques=mitre_techniques_dict,
            kill_chain_events=kill_chain_events,
            contributing_features=contributing_features,
            explanation=explanation,
            response_actions=response_actions_dict,
        )
        
        return report
    
    def save_json_report(self, report: IncidentReport) -> str:
        """Save report as JSON"""
        report_file = self.report_dir / f"{report.incident_id}.json"
        
        with open(report_file, 'w') as f:
            f.write(report.to_json())
        
        logger.info(f"JSON report saved: {report_file}")
        return str(report_file)
    
    def save_text_report(self, report: IncidentReport) -> str:
        """Save report as human-readable text"""
        report_file = self.report_dir / f"{report.incident_id}.txt"
        
        with open(report_file, 'w') as f:
            f.write(report.to_human_readable())
        
        logger.info(f"Text report saved: {report_file}")
        return str(report_file)
    
    def save_report(self, report: IncidentReport, format: str = "both") -> Dict[str, str]:
        """Save report in specified format"""
        files = {}
        
        if format in ("json", "both"):
            files['json'] = self.save_json_report(report)
        
        if format in ("text", "both"):
            files['text'] = self.save_text_report(report)
        
        return files


class AlertStream:
    """Streams alerts in real-time (JSONL format)"""
    
    def __init__(self, alert_file: str = "/var/log/devilnet/alerts/stream.jsonl"):
        self.alert_file = Path(alert_file)
        self.alert_file.parent.mkdir(parents=True, exist_ok=True)
    
    def write_alert(
        self,
        incident_id: str,
        severity: str,
        event_type: str,
        source_ip: Optional[str],
        username: Optional[str],
        anomaly_score: float,
        explanation: str,
    ) -> None:
        """Write alert to stream"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'incident_id': incident_id,
            'severity': severity,
            'event_type': event_type,
            'source_ip': source_ip,
            'username': username,
            'anomaly_score': float(anomaly_score),
            'explanation': explanation,
        }
        
        with open(self.alert_file, 'a') as f:
            f.write(json.dumps(alert) + '\n')
