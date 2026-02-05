# Devilnet System Reference & Architecture Guide

## Table of Contents
1. [System Overview](#system-overview)
2. [Component Architecture](#component-architecture)
3. [Data Flow](#data-flow)
4. [Detection Pipeline](#detection-pipeline)
5. [ML Model Details](#ml-model-details)
6. [Security Architecture](#security-architecture)
7. [API Reference](#api-reference)
8. [Configuration Reference](#configuration-reference)
9. [Incident Response Details](#incident-response-details)
10. [Troubleshooting Guide](#troubleshooting-guide)

---

## System Overview

### Purpose

Devilnet is a real-time, machine learning-powered anomaly detection system designed for Blue Team operations in cybersecurity environments. It continuously monitors Linux authentication and system logs to identify:

- **Credential-based attacks**: Brute force, password guessing, credential stuffing
- **Account abuse**: Unauthorized access via compromised accounts
- **Privilege escalation**: Suspicious sudo usage and elevation patterns
- **Post-compromise activity**: Tool execution, log tampering, persistence mechanisms

### Design Philosophy

**Security-First**: The detection engine itself must not become an attack surface. Therefore:
- Runs as non-privileged user
- No network exposure
- Read-only log access
- No shell execution capability
- Sandboxed via AppArmor/SELinux
- Fully auditable action history

**Explainability**: ML models must be trustworthy for security decisions:
- Feature importance visible for each detection
- MITRE ATT&CK mapping for threat context
- Human-readable reports alongside machine scores
- Low false positive rate through domain-specific features

---

## Component Architecture

### High-Level Module Structure

```
┌─────────────────────────────────────────────────────────────┐
│                    DEVILNET ENGINE (engine.py)              │
│ Orchestrates all subsystems, manages lifecycle              │
└─────────────────────────────────────────────────────────────┘
              ↓           ↓           ↓           ↓
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ INGESTION   │ │ ML PIPELINE │ │  RESPONSE   │ │  REPORTING  │
    │ (logs)      │ │ (detection) │ │ (actions)   │ │ (alerts)    │
    └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
         ↓                ↓                ↓                ↓
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ Log Parser  │ │ Features    │ │ Response    │ │ Reporter    │
    │ Log Tailer  │ │ Extraction  │ │ Executor    │ │ Alert Stream│
    └─────────────┘ │ ML Training │ │ Decision    │ │ MITRE Map   │
                    │ ML Inference│ │ Engine      │ │             │
                    └─────────────┘ └─────────────┘ └─────────────┘
```

### Package Hierarchy

```
devilnet/
├── core/                          # Core functionality
│   ├── security.py               # Privilege management, sandboxing
│   ├── config.py                 # Configuration management
│   └── mitre_mapping.py          # MITRE ATT&CK mappings
│
├── ingestion/                     # Log data sources
│   └── log_parser.py             # Parsing, event extraction, tailing
│
├── ml/                           # Machine learning pipeline
│   ├── feature_extraction.py     # Feature engineering
│   └── pipeline.py               # Isolation Forest, inference
│
├── response/                      # Automated response layer
│   └── incident_response.py      # Response actions, policies
│
├── reporting/                     # Output generation
│   └── reporter.py               # Reports, alerts, SIEM export
│
└── engine.py                      # Main orchestration engine
```

---

## Data Flow

### Event Ingestion Pipeline

```
┌──────────────────────────────────────────────────────────────┐
│ RAW LOG FILES (read-only)                                    │
│ /var/log/auth.log (SSH events)                               │
│ /var/log/syslog (system events)                              │
│ /var/log/audit/audit.log (auditd events)                     │
│ /var/log/fail2ban.log (fail2ban blocks)                      │
└──────────────────────────────────────────────────────────────┘
                         ↓
              TAIL STATE TRACKING
            (/tmp/devilnet_tail_*.state)
                         ↓
         ┌───────────────────────────────────┐
         │ LOG PARSER (log_parser.py)        │
         │ - Regex-based log format parsing  │
         │ - SSH/sudo event extraction       │
         │ - Audit log interpretation        │
         └───────────────────────────────────┘
                         ↓
         ┌───────────────────────────────────┐
         │ EVENT NORMALIZATION               │
         │ AuthEvent dataclass instances     │
         │ Standardized fields:              │
         │ - timestamp, source_ip, username  │
         │ - auth_method, event_type         │
         └───────────────────────────────────┘
                         ↓
         ┌───────────────────────────────────┐
         │ BATCH PROCESSING                  │
         │ (batch_size = 100 by default)     │
         │ Group events for efficiency       │
         └───────────────────────────────────┘
                         ↓
         ┌───────────────────────────────────┐
         │ FEATURE EXTRACTION                │
         │ (feature_extraction.py)           │
         │ Generate FeatureVector instances  │
         └───────────────────────────────────┘
```

### Feature Vector Generation

For each event, features are aggregated over sliding window (default 5 min):

```
AuthEvent
├─ timestamp
├─ source_ip
├─ username
├─ auth_method
└─ event_type

                    ↓

    FeatureExtractor maintains:
    - ip_events[IP] = list of events from IP
    - user_events[USER] = list of events for user
    - user_known_ips[USER] = set of IPs seen
    - user_login_times[USER] = list of login hours

                    ↓

         Computes FeatureVector:
    ┌──────────────────────────────┐
    │ Per-IP Features              │
    ├──────────────────────────────┤
    │ ip_failed_logins             │
    │ ip_unique_users_attempted    │
    │ ip_failed_to_success_ratio   │
    │ ip_avg_inter_attempt_seconds │
    │ ip_auth_method_variance      │
    ├──────────────────────────────┤
    │ Per-User Features            │
    ├──────────────────────────────┤
    │ user_login_time_std_devs     │
    │ user_new_ip_detected         │
    │ user_first_sudo_usage        │
    │ user_failed_sudo_attempts    │
    │ user_login_from_new_asn      │
    ├──────────────────────────────┤
    │ Per-Session Features         │
    ├──────────────────────────────┤
    │ session_login_to_privesc_seconds
    │ session_post_login_command_rate
    │ session_lolbin_executed      │
    │ session_account_changes      │
    └──────────────────────────────┘
```

### ML Inference Pipeline

```
         FeatureVector batch
         (14-dimensional)
                ↓
         [Normalization]
    (z-score: (X - mean) / std)
                ↓
         ┌─────────────────────────────┐
         │ Isolation Forest Model      │
         │ (trained on normal behavior)│
         │ n_estimators=100            │
         │ max_samples=256             │
         └─────────────────────────────┘
                ↓
         score_samples() → decision scores
         predict() → -1 (anomaly) or 1 (normal)
                ↓
         ┌─────────────────────────────┐
         │ Anomaly Scoring             │
         │ normalized_score = 1/(1+exp(score))
         │ is_anomaly = (score < threshold)
         └─────────────────────────────┘
                ↓
         ┌─────────────────────────────┐
         │ Risk Classification         │
         │ NORMAL (< 0.4)              │
         │ LOW    (0.4 - 0.6)          │
         │ MEDIUM (0.6 - 0.8)          │
         │ HIGH   (0.8 - 0.9)          │
         │ CRITICAL (> 0.9)            │
         └─────────────────────────────┘
                ↓
         AnomalyScore instance with:
         - anomaly_score (0-1)
         - risk_level
         - confidence
         - contributing_features
         - explanation
```

---

## Detection Pipeline

### Event Processing Sequence

```python
# Simplified pseudocode
while True:
    # 1. INGESTION
    raw_events = ingestion_pipeline.ingest_all()
    
    # 2. FEATURE EXTRACTION
    feature_vectors = []
    metadata = []
    for event in raw_events:
        vector = feature_extractor.extract_features(event)
        feature_vectors.append(vector)
        metadata.append(event.metadata)
    
    # 3. ML INFERENCE
    anomaly_scores = ml_pipeline.infer(feature_vectors, metadata)
    
    # 4. FILTER ANOMALIES
    anomalies = [a for a in anomaly_scores if a.is_anomaly]
    
    # 5. FOR EACH ANOMALY
    for anomaly in anomalies:
        # Generate report
        report = report_generator.generate_report(anomaly)
        
        # Write to streams
        alert_stream.write_alert(anomaly)
        reporter.save_report(report)
        
        # Determine response
        response_actions = response_decision_engine.determine_response(
            risk_level=anomaly.risk_level,
            event_type=anomaly.event_type,
            source_ip=anomaly.source_ip,
            username=anomaly.username,
        )
        
        # Execute response (with cooldowns)
        for action in response_actions:
            response_executor.execute_response(action)
    
    # 6. SLEEP & REPEAT
    time.sleep(5)  # Poll interval
```

---

## ML Model Details

### Isolation Forest Algorithm

**What it does**: Identifies anomalies by isolating them in decision trees

**How it works**:
1. Randomly selects features
2. Randomly selects split values
3. Builds trees that partition normal points further from anomalies
4. Anomalies isolated quickly (shallow trees)
5. Anomaly score = average path length / expected path length

**Why Isolation Forest?**
- ✅ Unsupervised (no labeled attack data needed)
- ✅ Scalable (O(n) complexity)
- ✅ Effective for high-dimensional data
- ✅ Robust to irrelevant features
- ✅ Low false positive rate on normal variants
- ✅ Interpretable (feature importance)

### Model Lifecycle

```
[Training Phase]
Generate baseline events → Feature extraction → Normalize → Train IF model
                                                                     ↓
                                                         /var/lib/devilnet/
                                                         isolation_forest.pkl

                                                                     ↓

[Inference Phase]
Stream logs → Parse events → Extract features → Normalize → Load model
                                                                ↓
                                                          Score events
                                                                ↓
                                                    Generate alerts/reports
                                                                ↓
                                                       (Maybe) Execute response
```

### Hyperparameter Tuning

```json
{
  "contamination": 0.1,      // Range: 0.01 - 0.5
                             // Start at 0.1, adjust based on observed anomaly rate
                             // Higher = more alerts but better detection of rare attacks
  
  "n_estimators": 100,       // Range: 50 - 500
                             // 100 balances accuracy & speed
                             // Increase if high false negatives
  
  "max_samples": 256,        // Range: 128 - 512
                             // Samples per tree
                             // Larger = better for low-dimensional problems
  
  "random_state": 42         // For reproducibility
}
```

---

## Security Architecture

### Privilege Model

```
System Boot
      ↓
devilnet service starts (as root via systemd)
      ↓
[IF running as root]
  security.py:initialize_security()
      ↓
  Check: getuid() == 0?
  Yes → Drop privileges
      ↓
  setgid(devilnet_gid)
  setuid(devilnet_uid)
      ↓
  Verify: getuid() != 0
      ↓
  Continue as 'devilnet' (unprivileged user)

[Engine operations]
- Read logs as 'devilnet' (via adm group or ACL)
- Write to /var/lib/devilnet and /var/log/devilnet
- No capability escalation
- No root operations
```

### Filesystem Isolation

```
READ-ONLY (via AppArmor/SELinux)
├── /var/log/auth.log         [AuthEvent ingestion]
├── /var/log/syslog           [System event ingestion]
├── /var/log/audit/           [Auditd events]
└── /var/log/fail2ban.log     [Fail2Ban events]

READ-WRITE (controlled via permissions)
├── /var/lib/devilnet/        [ML state, models]
│   ├── isolation_forest.pkl  [Trained model]
│   ├── venv/                 [Python environment]
│   └── baseline_events.jsonl [Training data]
│
└── /var/log/devilnet/        [Outputs]
    ├── alerts/
    │   ├── stream.jsonl      [Alert stream (JSONL)]
    │   └── responses_*.jsonl [Response audit log]
    └── reports/
        ├── INC-*.json        [Incident reports (JSON)]
        └── INC-*.txt         [Human-readable reports]

DENIED (via AppArmor/SELinux)
├── Network access (all protocols)
├── /bin/bash, /bin/sh        [No shell execution]
├── /usr/bin/sudo             [No privilege escalation]
├── ptrace                     [No process tracing]
└── Capability changes        [No cap_* operations]
```

### Python Safety

```
✓ No subprocess.run() or shell execution
✓ No exec() or eval()
✓ No __import__() of untrusted modules
✓ No pickle.loads() of untrusted data
✓ Dependencies frozen (no pip at runtime)
✓ site-packages read-only (chmod 555)

Safety mechanisms:
- scikit-learn (model inference) - trusted, stable
- numpy (numerical ops) - trusted, stable
- Avoid: requests, urllib, socket (network)
- Avoid: os.system(), subprocess (shell)
```

---

## API Reference

### Core Classes

#### `DevilnetEngine`

Main orchestration class.

```python
from devilnet.engine import DevilnetEngine, create_engine

# Create engine
engine = create_engine(config_path='/etc/devilnet/config.json')

# Methods
engine.run_inference_cycle()      # → List[AnomalyScore]
engine.train_on_baseline(path)    # Train on baseline JSONL
engine.print_status()              # Print engine configuration

# Attributes
engine.security_context            # SecurityContext
engine.ml_pipeline                 # MLPipeline
engine.response_executor           # SafeResponseExecutor
engine.report_generator            # IncidentReportGenerator
```

#### `AuthEvent`

Raw authentication event.

```python
from devilnet.ingestion.log_parser import AuthEvent

event = AuthEvent(
    timestamp='2025-01-15T14:32:10Z',
    host='webserver',
    source_ip='203.0.113.99',
    source_port=54321,
    username='admin',
    auth_method='password',
    event_type='login_failed',
    service='sshd',
    message='Failed password for admin...',
    raw_line='...'
)
```

#### `FeatureVector`

ML feature vector (14-dimensional).

```python
from devilnet.ml.feature_extraction import FeatureVector

vector.to_ml_vector()    # → List[float] of 14 features
```

#### `AnomalyScore`

ML inference result.

```python
from devilnet.ml.pipeline import AnomalyScore

score.event_id                  # Unique event ID
score.anomaly_score             # 0.0 (normal) - 1.0 (anomaly)
score.risk_level                # "LOW", "MEDIUM", "HIGH", "CRITICAL"
score.confidence                # 0.0 - 1.0
score.is_anomaly                # bool
score.contributing_features     # Dict[str, float] feature importance
score.explanation               # str human-readable explanation
```

#### `IncidentReport`

Complete incident report.

```python
from devilnet.reporting.reporter import IncidentReport

report.incident_id               # Unique incident ID
report.severity                  # Risk level
report.event_type                # Type of event
report.source_ip                 # Attacker IP
report.username                  # Target user
report.mitre_tactics             # List[str] tactics
report.mitre_techniques          # List[Dict] techniques
report.kill_chain_events         # List[Dict] timeline
report.contributing_features     # Dict[str, float]

# Export
report.to_json()                 # Machine-readable
report.to_human_readable()       # Human-readable
```

---

## Configuration Reference

### Full Config Structure

```json
{
  "feature_thresholds": {
    "failed_login_threshold": 5,
    "unique_users_threshold": 10,
    "failed_to_success_ratio_threshold": 0.8,
    "min_inter_attempt_seconds": 2,
    "login_time_std_devs": 3.0,
    "new_ip_risk_boost": 0.3,
    "first_sudo_risk_boost": 0.25,
    "failed_sudo_threshold": 3
  },
  "alert_levels": {
    "low_threshold": 0.4,
    "medium_threshold": 0.6,
    "high_threshold": 0.8,
    "critical_threshold": 0.9
  },
  "incident_response": {
    "lock_account_at_risk_level": "HIGH",
    "block_ip_at_risk_level": "HIGH",
    "terminate_session_at_risk_level": "CRITICAL",
    "lock_account_cooldown": 300,
    "block_ip_cooldown": 600,
    "terminate_session_cooldown": 180,
    "enable_automated_actions": false
  },
  "log_sources": {
    "auth_log": "/var/log/auth.log",
    "syslog": "/var/log/syslog",
    "audit_log": "/var/log/audit/audit.log",
    "fail2ban_log": "/var/log/fail2ban.log",
    "read_mode": "file",
    "tail_poll_interval_seconds": 5,
    "tail_batch_size": 1000,
    "state_dir": "/var/lib/devilnet",
    "alert_dir": "/var/log/devilnet/alerts",
    "report_dir": "/var/log/devilnet/reports"
  },
  "ml_pipeline": {
    "contamination": 0.1,
    "n_estimators": 100,
    "max_samples": 256,
    "random_state": 42,
    "feature_window_minutes": 5,
    "min_samples_for_training": 1000,
    "training_data_file": "baseline_events.jsonl",
    "model_file": "isolation_forest.pkl",
    "batch_size": 100
  },
  "security_policy": {
    "execution_user": "devilnet",
    "enforce_non_root": true,
    "allow_network": false,
    "allow_eval": false,
    "allow_shell_exec": false,
    "readonly_paths": [...],
    "writable_paths": [...]
  }
}
```

---

## Incident Response Details

### Response Action Types

```python
from devilnet.response.incident_response import ResponseAction

ResponseAction.LOCK_ACCOUNT      # → usermod -L <user>
ResponseAction.UNLOCK_ACCOUNT    # → usermod -U <user>
ResponseAction.BLOCK_IP          # → iptables -A INPUT -s <ip> -j DROP
ResponseAction.UNBLOCK_IP        # → iptables -D INPUT -s <ip> -j DROP
ResponseAction.TERMINATE_SESSION # → pkill -u <user> sshd
ResponseAction.ALERT_ONLY        # → Generate alert (no action)
```

### Response Decision Logic

```python
from devilnet.response.incident_response import ResponseDecisionEngine

engine = ResponseDecisionEngine()

# Determine actions based on risk level
actions = engine.determine_response(
    risk_level="HIGH",              # NORMAL, LOW, MEDIUM, HIGH, CRITICAL
    event_type="login_failed",
    anomaly_score=0.85,
    source_ip="203.0.113.99",
    username="admin"
)

# Returns: List[IncidentResponseAction]
# Each action:
# - Has reversible execution (logged with reversal command)
# - Respects cooldown periods
# - Only executes if enable_automated_actions=true
```

### Response Audit Log Format

```json
{
  "action": {
    "action_type": "lock_account",
    "target": "admin",
    "reason": "Brute force SSH attack detected",
    "severity": "HIGH",
    "timestamp": "2025-01-15T14:32:10Z",
    "event_id": "203.0.113.99_admin_1234567890.0"
  },
  "success": true,
  "result_message": "Account locked successfully",
  "executed_at": "2025-01-15T14:32:11Z",
  "executed_by": "devilnet_engine",
  "reversal_command": "usermod -U admin"
}
```

---

## Troubleshooting Guide

### Common Issues

#### Issue: "ERROR: ML engine running as root"

**Cause**: Engine started with `sudo` directly

**Solution**: 
```bash
# Create dedicated user first
sudo useradd -r -s /bin/false devilnet

# Run as that user
sudo -u devilnet python3 -m devilnet.engine
```

#### Issue: "Dedicated user 'devilnet' not found"

**Cause**: System user not created

**Solution**:
```bash
sudo useradd -r -s /bin/false devilnet
```

#### Issue: "Failed to read log file /var/log/auth.log: Permission denied"

**Cause**: `devilnet` user doesn't have read access to logs

**Solution**:
```bash
# Add to adm group
sudo usermod -a -G adm devilnet

# Or use ACL
sudo setfacl -m u:devilnet:r /var/log/auth.log
sudo setfacl -m u:devilnet:r /var/log/syslog
```

#### Issue: "Model not trained" on first run

**Cause**: ML model hasn't been trained on baseline data

**Solution**:
```bash
# Collect baseline events (normal traffic) for 1-2 hours, then:
python3 -m devilnet.engine --train /path/to/baseline_events.jsonl
```

#### Issue: Too many false positives

**Cause**: Thresholds set too low or model needs retraining

**Solutions**:
1. Increase contamination ratio:
   ```json
   {"ml_pipeline": {"contamination": 0.15}}
   ```

2. Increase anomaly thresholds:
   ```json
   {"alert_levels": {"low_threshold": 0.5, "medium_threshold": 0.7}}
   ```

3. Retrain model on more baseline data

#### Issue: No alerts being generated

**Cause**: 
- Model not trained
- No new events being ingested
- Anomaly score thresholds too high

**Debug steps**:
```bash
# 1. Check if events are being ingested
tail -f /tmp/devilnet_tail_auth.log.state

# 2. Run single cycle with verbose logging
python3 -m devilnet.engine --once --verbose

# 3. Check alert stream
tail -f /var/log/devilnet/alerts/stream.jsonl

# 4. Verify model exists
ls -la /var/lib/devilnet/isolation_forest.pkl
```

---

## Performance Tuning

### Memory Optimization

```python
# Reduce feature window for faster memory cleanup
"ml_pipeline": {
    "feature_window_minutes": 3,  # Shorter window
    "batch_size": 50              # Smaller batches
}
```

### Latency Optimization

```python
# Reduce inference latency
"ml_pipeline": {
    "n_estimators": 50,           # Fewer trees (faster)
    "max_samples": 128            # Fewer samples per tree
}
```

### Throughput Optimization

```python
# Increase ingestion throughput
"log_sources": {
    "tail_batch_size": 2000,      # Larger batches
    "tail_poll_interval_seconds": 2  # More frequent polling
}
```

---

## References

- MITRE ATT&CK: https://attack.mitre.org/
- scikit-learn Isolation Forest: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- AppArmor: https://gitlab.com/apparmor/apparmor/-/wikis/home
- SELinux: https://github.com/SELinuxProject/selinux

