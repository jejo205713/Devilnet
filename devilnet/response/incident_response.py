"""
Incident Response Layer

Performs controlled, logged, reversible automated responses to HIGH/CRITICAL incidents.
No direct shell execution - only safe IPC-based actions with audit trails.
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Callable
from enum import Enum
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class ResponseAction(Enum):
    """Automated response actions"""
    LOCK_ACCOUNT = "lock_account"
    UNLOCK_ACCOUNT = "unlock_account"
    BLOCK_IP = "block_ip"
    UNBLOCK_IP = "unblock_ip"
    TERMINATE_SESSION = "terminate_session"
    ALERT_ONLY = "alert_only"


@dataclass
class IncidentResponseAction:
    """Describes a response action to be taken"""
    action_type: ResponseAction
    target: str  # username or IP address
    reason: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    timestamp: str
    event_id: str
    is_reversible: bool = True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        result = asdict(self)
        result['action_type'] = self.action_type.value
        return result


@dataclass
class ResponseLog:
    """Log entry for response action"""
    action: IncidentResponseAction
    success: bool
    result_message: str
    executed_at: str
    executed_by: str = "devilnet_engine"
    reversal_command: Optional[str] = None


class CooldownManager:
    """Prevents action spam with configurable cooldowns"""
    
    def __init__(self):
        # Track last action per target
        self.last_actions: Dict[str, Dict] = {}
    
    def should_allow_action(
        self,
        action_type: ResponseAction,
        target: str,
        cooldown_seconds: int,
    ) -> bool:
        """Check if action is allowed given cooldown policy"""
        key = f"{action_type.value}:{target}"
        
        if key not in self.last_actions:
            return True
        
        last_action_time = datetime.fromisoformat(self.last_actions[key]['timestamp'])
        elapsed = (datetime.now() - last_action_time).total_seconds()
        
        return elapsed >= cooldown_seconds
    
    def record_action(self, action_type: ResponseAction, target: str) -> None:
        """Record that an action was performed"""
        key = f"{action_type.value}:{target}"
        self.last_actions[key] = {
            'timestamp': datetime.now().isoformat(),
            'target': target,
        }


class SafeResponseExecutor:
    """
    Executes response actions safely via IPC, not shell exec.
    All actions logged, auditable, and reversible where possible.
    """
    
    def __init__(
        self,
        response_log_dir: str = "/var/log/devilnet/responses",
        enable_actions: bool = False,
    ):
        self.response_log_dir = Path(response_log_dir)
        self.response_log_dir.mkdir(parents=True, exist_ok=True)
        self.enable_actions = enable_actions
        self.cooldown_manager = CooldownManager()
        
        # Action handlers - can be overridden in testing
        self.handlers: Dict[ResponseAction, Callable] = {
            ResponseAction.LOCK_ACCOUNT: self._handle_lock_account,
            ResponseAction.UNLOCK_ACCOUNT: self._handle_unlock_account,
            ResponseAction.BLOCK_IP: self._handle_block_ip,
            ResponseAction.UNBLOCK_IP: self._handle_unblock_ip,
            ResponseAction.TERMINATE_SESSION: self._handle_terminate_session,
            ResponseAction.ALERT_ONLY: self._handle_alert_only,
        }
    
    def execute_response(
        self,
        action: IncidentResponseAction,
        cooldown_seconds: int = 300,
    ) -> ResponseLog:
        """Execute a response action with safety checks"""
        
        # Check cooldown
        if not self.cooldown_manager.should_allow_action(
            action.action_type,
            action.target,
            cooldown_seconds
        ):
            return ResponseLog(
                action=action,
                success=False,
                result_message=f"Action blocked by cooldown (cooldown: {cooldown_seconds}s)",
                executed_at=datetime.now().isoformat(),
            )
        
        # Check if actions are enabled
        if not self.enable_actions and action.action_type != ResponseAction.ALERT_ONLY:
            logger.warning(
                f"Response action {action.action_type.value} blocked (actions disabled in config)"
            )
            return ResponseLog(
                action=action,
                success=False,
                result_message="Automated actions disabled (dry-run mode)",
                executed_at=datetime.now().isoformat(),
            )
        
        # Execute handler
        try:
            handler = self.handlers[action.action_type]
            result_message, reversal_cmd = handler(action)
            
            # Record in audit log
            log_entry = ResponseLog(
                action=action,
                success=True,
                result_message=result_message,
                executed_at=datetime.now().isoformat(),
                reversal_command=reversal_cmd,
            )
            
            self._write_response_log(log_entry)
            self.cooldown_manager.record_action(action.action_type, action.target)
            
            logger.info(f"Response action executed: {action.action_type.value} on {action.target}")
            return log_entry
        
        except Exception as e:
            logger.error(f"Response action failed: {e}")
            log_entry = ResponseLog(
                action=action,
                success=False,
                result_message=f"Action failed: {str(e)}",
                executed_at=datetime.now().isoformat(),
            )
            self._write_response_log(log_entry)
            return log_entry
    
    def _handle_lock_account(self, action: IncidentResponseAction) -> tuple[str, Optional[str]]:
        """Lock a user account (disable login)"""
        username = action.target
        
        # In production, this would call into PAM or useradd
        # For now, we simulate and return commands that would be executed
        
        lock_cmd = f"usermod -L {username}"
        unlock_cmd = f"usermod -U {username}"
        
        result = f"Account {username} locked (simulated)"
        logger.info(result)
        
        return result, unlock_cmd
    
    def _handle_unlock_account(self, action: IncidentResponseAction) -> tuple[str, Optional[str]]:
        """Unlock a user account"""
        username = action.target
        
        lock_cmd = f"usermod -L {username}"
        
        result = f"Account {username} unlocked (simulated)"
        logger.info(result)
        
        return result, lock_cmd
    
    def _handle_block_ip(self, action: IncidentResponseAction) -> tuple[str, Optional[str]]:
        """Block an IP address via firewall rules"""
        ip_address = action.target
        
        # In production, would add iptables/firewalld rules
        block_cmd = f"iptables -A INPUT -s {ip_address} -j DROP"
        unblock_cmd = f"iptables -D INPUT -s {ip_address} -j DROP"
        
        result = f"IP {ip_address} blocked (simulated)"
        logger.info(result)
        
        return result, unblock_cmd
    
    def _handle_unblock_ip(self, action: IncidentResponseAction) -> tuple[str, Optional[str]]:
        """Unblock an IP address"""
        ip_address = action.target
        
        block_cmd = f"iptables -A INPUT -s {ip_address} -j DROP"
        
        result = f"IP {ip_address} unblocked (simulated)"
        logger.info(result)
        
        return result, block_cmd
    
    def _handle_terminate_session(self, action: IncidentResponseAction) -> tuple[str, Optional[str]]:
        """Terminate active sessions for a user"""
        username = action.target
        
        # In production, would use pkill with careful filtering
        term_cmd = f"pkill -u {username} sshd"
        
        result = f"Sessions for {username} terminated (simulated)"
        logger.info(result)
        
        return result, None
    
    def _handle_alert_only(self, action: IncidentResponseAction) -> tuple[str, Optional[str]]:
        """Generate alert without taking action"""
        result = f"Alert: {action.reason}"
        logger.warning(result)
        return result, None
    
    def _write_response_log(self, log_entry: ResponseLog) -> None:
        """Write response action to audit log"""
        log_file = self.response_log_dir / f"responses_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        
        try:
            with open(log_file, 'a') as f:
                data = {
                    'action': log_entry.action.to_dict(),
                    'success': log_entry.success,
                    'result_message': log_entry.result_message,
                    'executed_at': log_entry.executed_at,
                    'executed_by': log_entry.executed_by,
                    'reversal_command': log_entry.reversal_command,
                }
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            logger.error(f"Failed to write response log: {e}")


class ResponseDecisionEngine:
    """Determines appropriate response actions based on incident severity"""
    
    def __init__(
        self,
        lock_account_threshold: str = "HIGH",
        block_ip_threshold: str = "HIGH",
        terminate_threshold: str = "CRITICAL",
    ):
        self.lock_account_threshold = lock_account_threshold
        self.block_ip_threshold = block_ip_threshold
        self.terminate_threshold = terminate_threshold
        
        # Risk level hierarchy
        self.severity_levels = ["NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    
    def determine_response(
        self,
        risk_level: str,
        event_type: str,
        anomaly_score: float,
        source_ip: str,
        username: str,
    ) -> List[IncidentResponseAction]:
        """Determine appropriate response actions"""
        actions = []
        timestamp = datetime.now().isoformat()
        event_id = f"{source_ip}_{username}_{timestamp}"
        
        # Always generate alert
        actions.append(IncidentResponseAction(
            action_type=ResponseAction.ALERT_ONLY,
            target=username,
            reason=f"Anomaly detected: {event_type} (score: {anomaly_score:.2f})",
            severity=risk_level,
            timestamp=timestamp,
            event_id=event_id,
        ))
        
        # Block IP for HIGH or CRITICAL
        if self._meets_threshold(risk_level, self.block_ip_threshold):
            actions.append(IncidentResponseAction(
                action_type=ResponseAction.BLOCK_IP,
                target=source_ip,
                reason=f"Blocking IP after {event_type}",
                severity=risk_level,
                timestamp=timestamp,
                event_id=event_id,
            ))
        
        # Lock account for HIGH or CRITICAL
        if self._meets_threshold(risk_level, self.lock_account_threshold):
            actions.append(IncidentResponseAction(
                action_type=ResponseAction.LOCK_ACCOUNT,
                target=username,
                reason=f"Locking account after {event_type}",
                severity=risk_level,
                timestamp=timestamp,
                event_id=event_id,
            ))
        
        # Terminate session for CRITICAL
        if self._meets_threshold(risk_level, self.terminate_threshold):
            actions.append(IncidentResponseAction(
                action_type=ResponseAction.TERMINATE_SESSION,
                target=username,
                reason=f"Terminating sessions for {username} (CRITICAL)",
                severity=risk_level,
                timestamp=timestamp,
                event_id=event_id,
            ))
        
        return actions
    
    def _meets_threshold(self, current_level: str, threshold_level: str) -> bool:
        """Check if current level meets or exceeds threshold"""
        try:
            current_idx = self.severity_levels.index(current_level)
            threshold_idx = self.severity_levels.index(threshold_level)
            return current_idx >= threshold_idx
        except ValueError:
            return False
