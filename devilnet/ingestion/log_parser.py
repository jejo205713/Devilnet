"""
Log Ingestion & Event Parsing

Safely parses authentication and system logs into structured events.
Handles auth.log, syslog, auditd, and fail2ban logs.
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Generator
from dataclasses import dataclass, asdict
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuthEvent:
    """Structured authentication event"""
    timestamp: str
    host: str
    source_ip: Optional[str]
    source_port: Optional[int]
    username: Optional[str]
    auth_method: str
    event_type: str  # "login_success", "login_failed", "sudo_attempt", etc.
    service: str  # "sshd", "sudo", etc.
    message: str
    raw_line: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class LogParser:
    """Parses various Linux log formats into structured events"""
    
    # Regex patterns for common log formats
    SSH_PATTERNS = {
        'failed': re.compile(
            r'(\w+ +\d+ [\d:]+) .+ sshd\[\d+\]: .*Failed password for (.*) from ([\d.]+) port (\d+)'
        ),
        'success': re.compile(
            r'(\w+ +\d+ [\d:]+) .+ sshd\[\d+\]: .*[Aa]ccepted (\w+) for (\w+) from ([\d.]+) port (\d+)'
        ),
        'invalid_user': re.compile(
            r'(\w+ +\d+ [\d:]+) .+ sshd\[\d+\]: .*Invalid user (\w+) from ([\d.]+) port (\d+)'
        ),
        'disconnect': re.compile(
            r'(\w+ +\d+ [\d:]+) .+ sshd\[\d+\]: .*Disconnected from (\w+ )?([\d.]+) port (\d+)'
        ),
    }
    
    SUDO_PATTERNS = {
        'success': re.compile(
            r'(\w+ +\d+ [\d:]+) .+ sudo: (\w+) : TTY=(\S+) ; PWD=(\S+) ; USER=(\w+) ; COMMAND=(.+)'
        ),
        'failure': re.compile(
            r'(\w+ +\d+ [\d:]+) .+ sudo: (\w+) : command not allowed'
        ),
    }
    
    AUDIT_PATTERNS = {
        'execve': re.compile(
            r'type=EXECVE msg=audit\(\d+\.\d+:\d+\): .*exe="([^"]+)"'
        ),
    }
    
    @staticmethod
    def parse_auth_log_line(line: str) -> Optional[AuthEvent]:
        """Parse a single line from /var/log/auth.log"""
        if not line.strip():
            return None
        
        try:
            # Try SSH patterns first
            for event_type, pattern in LogParser.SSH_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    groups = match.groups()
                    timestamp = groups[0]
                    
                    if event_type == 'failed':
                        return AuthEvent(
                            timestamp=timestamp,
                            host='localhost',
                            source_ip=groups[2],
                            source_port=int(groups[3]),
                            username=groups[1],
                            auth_method='password',
                            event_type='login_failed',
                            service='sshd',
                            message=line,
                            raw_line=line,
                        )
                    
                    elif event_type == 'success':
                        return AuthEvent(
                            timestamp=timestamp,
                            host='localhost',
                            source_ip=groups[3],
                            source_port=int(groups[4]),
                            username=groups[2],
                            auth_method=groups[1],
                            event_type='login_success',
                            service='sshd',
                            message=line,
                            raw_line=line,
                        )
                    
                    elif event_type == 'invalid_user':
                        return AuthEvent(
                            timestamp=timestamp,
                            host='localhost',
                            source_ip=groups[2],
                            source_port=int(groups[3]),
                            username=groups[1],
                            auth_method='password',
                            event_type='invalid_user_attempt',
                            service='sshd',
                            message=line,
                            raw_line=line,
                        )
            
            # Try sudo patterns
            for event_type, pattern in LogParser.SUDO_PATTERNS.items():
                match = pattern.search(line)
                if match:
                    groups = match.groups()
                    timestamp = groups[0]
                    username = groups[1]
                    
                    return AuthEvent(
                        timestamp=timestamp,
                        host='localhost',
                        source_ip=None,
                        source_port=None,
                        username=username,
                        auth_method='sudo',
                        event_type=f'sudo_{event_type}',
                        service='sudo',
                        message=line,
                        raw_line=line,
                    )
            
            # If no patterns matched, return generic event
            return AuthEvent(
                timestamp=datetime.now().isoformat(),
                host='localhost',
                source_ip=None,
                source_port=None,
                username=None,
                auth_method='unknown',
                event_type='unknown',
                service='unknown',
                message=line,
                raw_line=line,
            )
        
        except Exception as e:
            logger.debug(f"Failed to parse line: {line}: {e}")
            return None
    
    @staticmethod
    def parse_syslog_line(line: str) -> Optional[AuthEvent]:
        """Parse a single line from /var/log/syslog"""
        # Syslog may contain auth events too
        return LogParser.parse_auth_log_line(line)
    
    @staticmethod
    def parse_audit_line(line: str) -> Optional[AuthEvent]:
        """Parse a single line from audit log"""
        if not line.strip() or 'type=' not in line:
            return None
        
        try:
            timestamp = datetime.now().isoformat()
            
            # Extract exec command
            match = LogParser.AUDIT_PATTERNS['execve'].search(line)
            if match:
                exe = match.group(1)
                return AuthEvent(
                    timestamp=timestamp,
                    host='localhost',
                    source_ip=None,
                    source_port=None,
                    username=None,
                    auth_method='exec',
                    event_type='process_execution',
                    service='auditd',
                    message=f"Executed: {exe}",
                    raw_line=line,
                )
            
            return None
        
        except Exception as e:
            logger.debug(f"Failed to parse audit line: {e}")
            return None


class LogTailer:
    """Tails log files with read-only access, yielding new lines"""
    
    def __init__(self, log_path: str):
        self.log_path = Path(log_path)
        self.current_position = 0
        self._load_state()
    
    def _load_state(self) -> None:
        """Load saved file position from state file"""
        state_file = Path(f"/tmp/devilnet_tail_{self.log_path.name}.state")
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    self.current_position = int(f.read().strip())
            except Exception as e:
                logger.warning(f"Failed to load tail state: {e}")
    
    def _save_state(self) -> None:
        """Save current file position to state file"""
        state_file = Path(f"/tmp/devilnet_tail_{self.log_path.name}.state")
        try:
            with open(state_file, 'w') as f:
                f.write(str(self.current_position))
        except Exception as e:
            logger.warning(f"Failed to save tail state: {e}")
    
    def tail(self, batch_size: int = 1000) -> Generator[str, None, None]:
        """
        Yield new lines from log file since last read.
        Read-only access, safe for concurrent access.
        """
        if not self.log_path.exists():
            logger.warning(f"Log file not found: {self.log_path}")
            return
        
        try:
            with open(self.log_path, 'r') as f:
                # Seek to last known position
                f.seek(self.current_position)
                
                lines_read = 0
                for line in f:
                    yield line.rstrip('\n')
                    lines_read += 1
                    
                    if lines_read >= batch_size:
                        break
                
                # Update position
                self.current_position = f.tell()
                self._save_state()
        
        except IOError as e:
            logger.error(f"Failed to read log file {self.log_path}: {e}")


class LogIngestionPipeline:
    """Coordinates log tailing, parsing, and event generation"""
    
    def __init__(self, log_sources: Dict[str, str]):
        self.log_sources = log_sources
        self.tailers = {
            name: LogTailer(path)
            for name, path in log_sources.items()
        }
        self.parser = LogParser()
    
    def ingest_all(self, batch_size: int = 1000) -> List[AuthEvent]:
        """Ingest events from all log sources"""
        events = []
        
        # Auth log
        if 'auth_log' in self.tailers:
            for line in self.tailers['auth_log'].tail(batch_size):
                event = self.parser.parse_auth_log_line(line)
                if event:
                    events.append(event)
        
        # Syslog
        if 'syslog' in self.tailers:
            for line in self.tailers['syslog'].tail(batch_size):
                event = self.parser.parse_syslog_line(line)
                if event:
                    events.append(event)
        
        # Audit log
        if 'audit_log' in self.tailers:
            for line in self.tailers['audit_log'].tail(batch_size):
                event = self.parser.parse_audit_line(line)
                if event:
                    events.append(event)
        
        return events
