"""
Security Foundation: Privilege Management & Sandboxing

Enforces secure execution under dedicated non-privileged user.
Handles privilege dropping, resource constraints, and audit logging.
"""

import os
import sys
import logging
import pwd
import grp
from typing import Optional
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SecurityContext:
    """Immutable security execution context"""
    user: str
    uid: int
    gid: int
    home_dir: Path
    is_privileged: bool
    
    def validate(self) -> bool:
        """Validate that we're running as expected non-privileged user"""
        actual_uid = os.getuid()
        if actual_uid != self.uid:
            raise SecurityException(
                f"UID mismatch: expected {self.uid}, got {actual_uid}"
            )
        if actual_uid == 0:
            raise SecurityException(
                "CRITICAL: ML engine running as root - this violates security policy"
            )
        return True


class SecurityException(Exception):
    """Raised when security constraints are violated"""
    pass


class PrivilegeManager:
    """Manages privilege dropping and execution context"""
    
    def __init__(self, dedicated_user: str = "devilnet"):
        self.dedicated_user = dedicated_user
        self.context: Optional[SecurityContext] = None
    
    def get_or_create_context(self) -> SecurityContext:
        """Get or establish security context for non-privileged user"""
        if self.context is not None:
            return self.context
        
        try:
            pwd_entry = pwd.getpwnam(self.dedicated_user)
            grp_entry = grp.getgrgid(pwd_entry.pw_gid)
            
            self.context = SecurityContext(
                user=pwd_entry.pw_name,
                uid=pwd_entry.pw_uid,
                gid=pwd_entry.pw_gid,
                home_dir=Path(pwd_entry.pw_dir),
                is_privileged=(os.getuid() == 0)
            )
            
            logger.info(
                f"Security context established: {self.dedicated_user} "
                f"(UID:{self.context.uid}, GID:{self.context.gid})"
            )
            return self.context
        
        except KeyError:
            raise SecurityException(
                f"Dedicated user '{self.dedicated_user}' not found. "
                f"Create with: sudo useradd -r -s /bin/false {self.dedicated_user}"
            )
    
    def drop_privileges(self) -> None:
        """Drop root privileges if running as root"""
        current_uid = os.getuid()
        
        if current_uid != 0:
            logger.debug(f"Already running as non-root (UID {current_uid})")
            return
        
        context = self.get_or_create_context()
        
        try:
            # Set process group
            os.setgid(context.gid)
            os.setuid(context.uid)
            
            # Verify privilege drop
            if os.getuid() == 0 or os.getgid() == 0:
                raise SecurityException("Failed to drop privileges")
            
            logger.info(f"Privileges dropped to {self.dedicated_user}")
        
        except OSError as e:
            raise SecurityException(f"Failed to drop privileges: {e}")
    
    def validate_execution_context(self) -> None:
        """Verify we're in secure execution environment"""
        context = self.get_or_create_context()
        context.validate()
        
        # Verify running with correct UID
        current_uid = os.getuid()
        if current_uid == 0:
            raise SecurityException(
                "CRITICAL: Anomaly detection engine must not run as root"
            )
        
        logger.debug(f"Execution context validated: UID={current_uid}")


class IsolationPolicy:
    """Defines filesystem and network isolation constraints"""
    
    # Read-only log paths
    READONLY_PATHS = {
        "/var/log/auth.log",
        "/var/log/syslog",
        "/var/log/audit/",
        "/var/log/fail2ban.log",
    }
    
    # Allowed write paths (ML state, reports)
    WRITABLE_PATHS = {
        "/var/lib/devilnet/",
        "/var/log/devilnet/",
    }
    
    # Blocked network access
    BLOCK_NETWORK = True
    
    # Blocked dynamic code execution
    BLOCK_EVAL = True
    
    @staticmethod
    def get_apparmor_profile() -> str:
        """Return AppArmor profile for the ML engine"""
        return """
#include <tunables/global>

profile devilnet-ml flags=(attach_disconnected,mediate_deleted) {
    #include <abstractions/base>
    #include <abstractions/nameservice>
    
    # Read-only log access
    /var/log/auth.log r,
    /var/log/syslog r,
    /var/log/audit/** r,
    /var/log/fail2ban.log r,
    
    # ML state and outputs
    /var/lib/devilnet/ rw,
    /var/lib/devilnet/** rw,
    /var/log/devilnet/ rw,
    /var/log/devilnet/** rw,
    
    # Python runtime
    /usr/bin/python3 ix,
    /usr/lib/python3** r,
    /usr/lib/x86_64-linux-gnu/ r,
    
    # Deny network
    deny network,
    
    # Deny shell execution
    deny /bin/bash rwix,
    deny /bin/sh rwix,
    deny /usr/bin/sudo rwix,
}
"""
    
    @staticmethod
    def get_selinux_policy() -> str:
        """Return SELinux policy for the ML engine"""
        return """
# Devilnet ML Engine SELinux Policy
policy_module(devilnet_ml, 1.0.0)

type devilnet_ml_t;
type devilnet_ml_exec_t;
type devilnet_log_t;

# Allow read of log files
allow devilnet_ml_t devilnet_log_t:file { read open };

# Deny network access
dontaudit devilnet_ml_t port_t:tcp_socket { bind listen connect };
dontaudit devilnet_ml_t port_t:udp_socket { bind listen };

# Deny privilege escalation
dontaudit devilnet_ml_t self:process { setcap setfcap };
dontaudit devilnet_ml_t self:process { ptrace };
"""


def initialize_security(user: str = "devilnet") -> SecurityContext:
    """
    Initialize security framework.
    
    Must be called at application startup.
    Enforces privilege constraints and validates execution environment.
    """
    manager = PrivilegeManager(user)
    
    # Drop privileges if running as root
    manager.drop_privileges()
    
    # Validate execution context
    manager.validate_execution_context()
    
    context = manager.get_or_create_context()
    logger.info(f"Security framework initialized: {context}")
    
    return context
