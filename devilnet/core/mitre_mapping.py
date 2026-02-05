"""
MITRE ATT&CK Mapping

Maps detected anomalies to MITRE ATT&CK techniques for standardized threat classification.
"""

from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from enum import Enum


class Tactic(Enum):
    """MITRE ATT&CK Tactics"""
    INITIAL_ACCESS = "Initial Access"
    EXECUTION = "Execution"
    PERSISTENCE = "Persistence"
    PRIVILEGE_ESCALATION = "Privilege Escalation"
    DEFENSE_EVASION = "Defense Evasion"
    CREDENTIAL_ACCESS = "Credential Access"
    DISCOVERY = "Discovery"
    LATERAL_MOVEMENT = "Lateral Movement"
    COLLECTION = "Collection"
    COMMAND_AND_CONTROL = "Command and Control"
    EXFILTRATION = "Exfiltration"
    IMPACT = "Impact"


@dataclass
class MitreATTACKTechnique:
    """MITRE ATT&CK Technique with metadata"""
    technique_id: str
    name: str
    tactic: Tactic
    description: str
    detection_indicators: List[str]


class MitreATTACKMapping:
    """Maps security events to MITRE ATT&CK framework"""
    
    TECHNIQUES = {
        # Credential Access
        'T1110': MitreATTACKTechnique(
            technique_id='T1110',
            name='Brute Force',
            tactic=Tactic.CREDENTIAL_ACCESS,
            description='Attacker uses brute force techniques to guess credentials',
            detection_indicators=[
                'Multiple failed login attempts from single IP',
                'Rapid sequential login attempts',
                'Invalid user enumeration',
                'High failure-to-success ratio',
            ]
        ),
        
        'T1110.001': MitreATTACKTechnique(
            technique_id='T1110.001',
            name='Brute Force: Password Guessing',
            tactic=Tactic.CREDENTIAL_ACCESS,
            description='Attacker guesses passwords through repeated attempts',
            detection_indicators=[
                'Repeated failed password attempts',
                'Failed logins followed by success',
                'Failed authentication within seconds of success',
            ]
        ),
        
        'T1110.004': MitreATTACKTechnique(
            technique_id='T1110.004',
            name='Brute Force: Credential Stuffing',
            tactic=Tactic.CREDENTIAL_ACCESS,
            description='Attacker uses previously compromised credentials',
            detection_indicators=[
                'Login from unusual geographic location',
                'Login from new IP address',
                'Login at unusual time of day',
            ]
        ),
        
        # Valid Accounts
        'T1078': MitreATTACKTechnique(
            technique_id='T1078',
            name='Valid Accounts',
            tactic=Tactic.DEFENSE_EVASION,
            description='Attacker uses legitimate credentials for access',
            detection_indicators=[
                'Successful login from new IP',
                'Login at unusual time',
                'Unusual geographic location',
                'Successful login after failed attempts',
            ]
        ),
        
        'T1078.001': MitreATTACKTechnique(
            technique_id='T1078.001',
            name='Valid Accounts: Local Accounts',
            tactic=Tactic.DEFENSE_EVASION,
            description='Attacker uses local system accounts',
            detection_indicators=[
                'Successful login for system user',
                'Sudo usage by system account',
                'Permission changes by system account',
            ]
        ),
        
        # Privilege Escalation
        'T1548': MitreATTACKTechnique(
            technique_id='T1548',
            name='Abuse Elevation Control Mechanism',
            tactic=Tactic.PRIVILEGE_ESCALATION,
            description='Attacker abuses elevation mechanisms like sudo',
            detection_indicators=[
                'Sudo usage immediately after login',
                'Failed sudo attempts',
                'Sudo usage for non-standard commands',
                'Sudo usage outside normal user pattern',
            ]
        ),
        
        'T1548.003': MitreATTACKTechnique(
            technique_id='T1548.003',
            name='Abuse Elevation Control Mechanism: Sudo and Sudo Caching',
            tactic=Tactic.PRIVILEGE_ESCALATION,
            description='Attacker abuses sudo to escalate privileges',
            detection_indicators=[
                'Rapid sudo invocations',
                'Failed sudo attempts followed by success',
                'Sudo usage outside normal TTY',
            ]
        ),
        
        # Persistence
        'T1098': MitreATTACKTechnique(
            technique_id='T1098',
            name='Account Manipulation',
            tactic=Tactic.PERSISTENCE,
            description='Attacker modifies account properties for persistence',
            detection_indicators=[
                'SSH key addition',
                'Account password change',
                'Group membership modification',
                'User account creation',
            ]
        ),
        
        'T1547': MitreATTACKTechnique(
            technique_id='T1547',
            name='Boot or Logon Autostart Execution',
            tactic=Tactic.PERSISTENCE,
            description='Attacker modifies startup mechanisms for persistence',
            detection_indicators=[
                'Modification of rc scripts',
                'Modification of crontab',
                'Addition of systemd services',
            ]
        ),
        
        # Execution
        'T1059': MitreATTACKTechnique(
            technique_id='T1059',
            name='Command and Scripting Interpreter',
            tactic=Tactic.EXECUTION,
            description='Attacker executes commands through shell',
            detection_indicators=[
                'Shell command execution',
                'Script execution',
                'Interactive shell access',
                'Command chaining',
            ]
        ),
        
        'T1059.004': MitreATTACKTechnique(
            technique_id='T1059.004',
            name='Command and Scripting Interpreter: Unix Shell',
            tactic=Tactic.EXECUTION,
            description='Attacker uses Unix shell for command execution',
            detection_indicators=[
                'Bash invocation',
                'Shell script execution',
                'Interactive SSH shell usage',
            ]
        ),
        
        # Ingress Tool Transfer
        'T1105': MitreATTACKTechnique(
            technique_id='T1105',
            name='Ingress Tool Transfer',
            tactic=Tactic.COMMAND_AND_CONTROL,
            description='Attacker transfers tools to target system',
            detection_indicators=[
                'curl/wget execution',
                'File transfer tool usage',
                'Downloaded tool execution',
            ]
        ),
        
        # Log Tampering
        'T1070': MitreATTACKTechnique(
            technique_id='T1070',
            name='Indicator Removal on Host: Clear Linux/Mac History',
            tactic=Tactic.DEFENSE_EVASION,
            description='Attacker clears audit logs to hide activity',
            detection_indicators=[
                'Log file truncation',
                'Audit log clearing',
                'History file deletion',
                'Suspicious rm commands on log files',
            ]
        ),
        
        # Post-Compromise Discovery
        'T1087': MitreATTACKTechnique(
            technique_id='T1087',
            name='Account Discovery',
            tactic=Tactic.DISCOVERY,
            description='Attacker enumerates user accounts',
            detection_indicators=[
                'getent/cat of passwd file',
                'Enumeration of sudoers',
                'User enumeration commands',
            ]
        ),
        
        'T1217': MitreATTACKTechnique(
            technique_id='T1217',
            name='Browser Bookmark Discovery',
            tactic=Tactic.DISCOVERY,
            description='Attacker searches for sensitive files',
            detection_indicators=[
                'Recursive directory searches',
                'Find command for sensitive patterns',
                'Grep for credentials in files',
            ]
        ),
    }
    
    @staticmethod
    def get_techniques_for_event(event_type: str, anomaly_features: Dict) -> List[MitreATTACKTechnique]:
        """Map an event to applicable MITRE techniques"""
        techniques = []
        
        # Brute force detection
        if event_type == 'login_failed' and anomaly_features.get('ip_failed_logins', 0) > 5:
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1110'])
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1110.001'])
        
        # Invalid user enumeration
        if event_type == 'invalid_user_attempt':
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1110'])
        
        # Successful login after failures (credential stuffing)
        if event_type == 'login_success' and anomaly_features.get('ip_failed_to_success_ratio', 0) > 0.5:
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1110.004'])
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1078'])
        
        # Valid account abuse - new IP or unusual time
        if event_type == 'login_success' and anomaly_features.get('user_new_ip_detected', False):
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1078'])
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1078.001'])
        
        # Privilege escalation via sudo
        if 'sudo' in event_type:
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1548'])
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1548.003'])
        
        # First sudo usage
        if event_type == 'sudo_success' and anomaly_features.get('user_first_sudo_usage', False):
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1548'])
        
        # Failed sudo
        if event_type == 'sudo_failure' and anomaly_features.get('user_failed_sudo_attempts', 0) > 3:
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1548.003'])
        
        # Rapid privesc (login to sudo)
        if anomaly_features.get('session_login_to_privesc_seconds', 0) > 0 and \
           anomaly_features.get('session_login_to_privesc_seconds', 0) < 60:
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1548'])
        
        # LOLBin execution
        if anomaly_features.get('session_lolbin_executed', False):
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1059.004'])
            techniques.append(MitreATTACKMapping.TECHNIQUES['T1105'])
        
        return techniques
    
    @staticmethod
    def get_technique(technique_id: str) -> Optional[MitreATTACKTechnique]:
        """Get specific technique by ID"""
        return MitreATTACKMapping.TECHNIQUES.get(technique_id)
    
    @staticmethod
    def get_all_techniques() -> List[MitreATTACKTechnique]:
        """Get all mapped techniques"""
        return list(MitreATTACKMapping.TECHNIQUES.values())


def get_tactic_string(tactic: Tactic) -> str:
    """Get human-readable tactic string"""
    return tactic.value
