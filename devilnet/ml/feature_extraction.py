"""
Feature Extraction Engine

Generates behavioral features from authentication events for ML anomaly detection.
Computes sliding-window aggregations per IP, user, and session.
"""

import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """Machine learning feature vector"""
    timestamp: str
    event_id: str
    
    # Per-IP features
    ip_failed_logins: int = 0
    ip_unique_users_attempted: int = 0
    ip_failed_to_success_ratio: float = 0.0
    ip_avg_inter_attempt_seconds: float = 0.0
    ip_auth_method_variance: float = 0.0
    
    # Per-user features
    user_login_time_std_devs: float = 0.0
    user_new_ip_detected: bool = False
    user_first_sudo_usage: bool = False
    user_failed_sudo_attempts: int = 0
    user_login_from_new_asn: bool = False
    
    # Per-session features
    session_login_to_privesc_seconds: float = 0.0
    session_post_login_command_rate: float = 0.0
    session_lolbin_executed: bool = False
    session_account_changes: int = 0
    
    # Context
    source_ip: Optional[str] = None
    username: Optional[str] = None
    event_type: str = ""
    
    def to_ml_vector(self) -> List[float]:
        """Convert to feature vector for ML model"""
        return [
            float(self.ip_failed_logins),
            float(self.ip_unique_users_attempted),
            self.ip_failed_to_success_ratio,
            self.ip_avg_inter_attempt_seconds,
            self.ip_auth_method_variance,
            self.user_login_time_std_devs,
            float(self.user_new_ip_detected),
            float(self.user_first_sudo_usage),
            float(self.user_failed_sudo_attempts),
            float(self.user_login_from_new_asn),
            self.session_login_to_privesc_seconds,
            self.session_post_login_command_rate,
            float(self.session_lolbin_executed),
            float(self.session_account_changes),
        ]


class FeatureExtractor:
    """Extracts features from authentication events"""
    
    # Common LOLBins (Living Off the Land Binaries)
    LOLBINS = {
        'bash', 'sh', 'python', 'perl', 'ruby', 'php',
        'curl', 'wget', 'nc', 'netcat', 'telnet',
        'find', 'grep', 'awk', 'sed',
        'tar', 'zip', 'gzip',
        'dd', 'cp', 'mv', 'chmod',
        'gcc', 'make',
        'git', 'svn',
    }
    
    def __init__(self, window_minutes: int = 5):
        self.window_minutes = window_minutes
        
        # Per-IP event history
        self.ip_events: Dict[str, List] = defaultdict(list)
        
        # Per-user event history
        self.user_events: Dict[str, List] = defaultdict(list)
        
        # Per-user baseline login times
        self.user_login_times: Dict[str, List[float]] = defaultdict(list)
        
        # Known IPs per user
        self.user_known_ips: Dict[str, set] = defaultdict(set)
        
        # Session tracking
        self.user_sessions: Dict[Tuple[str, str], Dict] = defaultdict(dict)
    
    def extract_features(self, event) -> FeatureVector:
        """Extract feature vector from an authentication event"""
        timestamp = datetime.fromisoformat(event.timestamp) if isinstance(event.timestamp, str) else event.timestamp
        source_ip = event.source_ip or "unknown"
        username = event.username or "unknown"
        
        # Update event history
        self._update_event_history(event)
        
        # Extract features
        vector = FeatureVector(
            timestamp=timestamp.isoformat(),
            event_id=f"{source_ip}_{username}_{timestamp.timestamp()}",
            source_ip=source_ip,
            username=username,
            event_type=event.event_type,
        )
        
        # Per-IP features
        vector.ip_failed_logins = self._get_ip_failed_logins(source_ip)
        vector.ip_unique_users_attempted = self._get_ip_unique_users(source_ip)
        vector.ip_failed_to_success_ratio = self._get_ip_failure_ratio(source_ip)
        vector.ip_avg_inter_attempt_seconds = self._get_ip_inter_attempt_time(source_ip)
        vector.ip_auth_method_variance = self._get_ip_auth_method_variance(source_ip)
        
        # Per-user features
        vector.user_login_time_std_devs = self._get_user_login_time_deviation(username, timestamp)
        vector.user_new_ip_detected = self._is_new_ip_for_user(username, source_ip)
        vector.user_first_sudo_usage = self._is_first_sudo(username, event)
        vector.user_failed_sudo_attempts = self._get_user_failed_sudo_count(username)
        
        # Per-session features (simplified for this example)
        vector.session_login_to_privesc_seconds = self._get_session_login_to_privesc_time(username, event)
        vector.session_lolbin_executed = self._check_lolbin_in_message(event.message)
        
        return vector
    
    def _update_event_history(self, event) -> None:
        """Update event history for feature computation"""
        timestamp = datetime.fromisoformat(event.timestamp) if isinstance(event.timestamp, str) else datetime.now()
        
        if event.source_ip:
            self.ip_events[event.source_ip].append({
                'timestamp': timestamp,
                'username': event.username,
                'event_type': event.event_type,
                'auth_method': event.auth_method,
            })
        
        if event.username:
            self.user_events[event.username].append({
                'timestamp': timestamp,
                'source_ip': event.source_ip,
                'event_type': event.event_type,
            })
            
            if event.event_type == 'login_success':
                self.user_login_times[event.username].append(timestamp.hour + timestamp.minute / 60)
            
            if event.source_ip:
                self.user_known_ips[event.username].add(event.source_ip)
        
        # Cleanup old entries (outside window)
        self._cleanup_old_events()
    
    def _cleanup_old_events(self) -> None:
        """Remove events outside the feature window"""
        cutoff = datetime.now() - timedelta(minutes=self.window_minutes)
        
        for ip in list(self.ip_events.keys()):
            self.ip_events[ip] = [
                e for e in self.ip_events[ip]
                if e['timestamp'] > cutoff
            ]
            if not self.ip_events[ip]:
                del self.ip_events[ip]
        
        for user in list(self.user_events.keys()):
            self.user_events[user] = [
                e for e in self.user_events[user]
                if e['timestamp'] > cutoff
            ]
            if not self.user_events[user]:
                del self.user_events[user]
    
    def _get_ip_failed_logins(self, ip: str) -> int:
        """Count failed login attempts from IP in window"""
        if ip not in self.ip_events:
            return 0
        return sum(
            1 for e in self.ip_events[ip]
            if 'failed' in e['event_type']
        )
    
    def _get_ip_unique_users(self, ip: str) -> int:
        """Count unique usernames attempted from IP"""
        if ip not in self.ip_events:
            return 0
        return len(set(
            e['username'] for e in self.ip_events[ip]
            if e['username']
        ))
    
    def _get_ip_failure_ratio(self, ip: str) -> float:
        """Calculate failed-to-total login ratio from IP"""
        if ip not in self.ip_events:
            return 0.0
        
        events = self.ip_events[ip]
        if not events:
            return 0.0
        
        failed = sum(1 for e in events if 'failed' in e['event_type'])
        return failed / len(events) if events else 0.0
    
    def _get_ip_inter_attempt_time(self, ip: str) -> float:
        """Calculate average time between login attempts from IP"""
        if ip not in self.ip_events:
            return 0.0
        
        events = sorted(self.ip_events[ip], key=lambda e: e['timestamp'])
        if len(events) < 2:
            return 0.0
        
        intervals = [
            (events[i+1]['timestamp'] - events[i]['timestamp']).total_seconds()
            for i in range(len(events) - 1)
        ]
        return statistics.mean(intervals) if intervals else 0.0
    
    def _get_ip_auth_method_variance(self, ip: str) -> float:
        """Measure variance in authentication methods from IP"""
        if ip not in self.ip_events:
            return 0.0
        
        methods = [e['auth_method'] for e in self.ip_events[ip]]
        if not methods:
            return 0.0
        
        # Diversity metric: unique methods / total methods
        unique_methods = len(set(methods))
        return unique_methods / len(methods) if methods else 0.0
    
    def _get_user_login_time_deviation(self, user: str, current_time: datetime) -> float:
        """Calculate standard deviation of login times from baseline"""
        if user not in self.user_login_times or len(self.user_login_times[user]) < 2:
            return 0.0
        
        baseline_hours = self.user_login_times[user]
        try:
            std_dev = statistics.stdev(baseline_hours)
            # Normalize to hours
            return std_dev
        except:
            return 0.0
    
    def _is_new_ip_for_user(self, user: str, ip: str) -> bool:
        """Check if IP is new for this user"""
        return ip not in self.user_known_ips[user]
    
    def _is_first_sudo(self, user: str, event) -> bool:
        """Check if this is first sudo usage for user"""
        if event.event_type != 'sudo_success':
            return False
        
        # Check if any previous sudo usage exists
        for e in self.user_events.get(user, []):
            if 'sudo' in e['event_type']:
                return False
        return True
    
    def _get_user_failed_sudo_count(self, user: str) -> int:
        """Count failed sudo attempts for user in window"""
        return sum(
            1 for e in self.user_events.get(user, [])
            if e['event_type'] == 'sudo_failure'
        )
    
    def _get_session_login_to_privesc_time(self, user: str, event) -> float:
        """Calculate time from login to privilege escalation"""
        if event.event_type != 'sudo_success':
            return 0.0
        
        session_events = self.user_events.get(user, [])
        login_events = [e for e in session_events if e['event_type'] == 'login_success']
        
        if not login_events:
            return 0.0
        
        last_login = login_events[-1]['timestamp']
        current_timestamp = datetime.fromisoformat(event.timestamp) if isinstance(event.timestamp, str) else datetime.now()
        
        return (current_timestamp - last_login).total_seconds()
    
    def _check_lolbin_in_message(self, message: str) -> bool:
        """Check if message contains LOLBin execution"""
        message_lower = message.lower()
        return any(lolbin in message_lower for lolbin in self.LOLBINS)


class FeatureVectorBatch:
    """Batch of feature vectors for ML inference"""
    
    def __init__(self, vectors: List[FeatureVector]):
        self.vectors = vectors
    
    def to_ml_matrix(self) -> List[List[float]]:
        """Convert batch to 2D feature matrix for ML model"""
        return [v.to_ml_vector() for v in self.vectors]
    
    def get_metadata(self) -> List[Dict]:
        """Get metadata for each vector (for mapping predictions back)"""
        return [
            {
                'event_id': v.event_id,
                'timestamp': v.timestamp,
                'source_ip': v.source_ip,
                'username': v.username,
                'event_type': v.event_type,
            }
            for v in self.vectors
        ]
