# Devilnet ML Anomaly Detection Engine - Deployment Hardening Guide

## Overview

Devilnet is a secure, sandboxed Blue Team machine learning system for detecting anomalies in Linux authentication and system logs. This guide ensures secure deployment that doesn't weaken host security.

---

## Security Architecture

### Design Principles

1. **Principle of Least Privilege**: Engine runs as dedicated non-privileged system user
2. **Read-Only Access**: Log ingestion is strictly read-only
3. **No Network Exposure**: Zero network listeners or external connectivity
4. **Sandbox Isolation**: Constrained via AppArmor/SELinux
5. **No Dynamic Execution**: No shell execution, eval, or unsafe dynamic code
6. **Immutable Dependencies**: Frozen dependencies in isolated venv

---

## Pre-Deployment Setup

### 1. Create Dedicated System User

```bash
# Create non-login system user for ML engine
sudo useradd -r -s /bin/false devilnet

# Verify
id devilnet
# uid=XXX(devilnet) gid=XXX(devilnet) groups=XXX(devilnet)
```

### 2. Create Directory Structure

```bash
# Create state and log directories
sudo mkdir -p /var/lib/devilnet
sudo mkdir -p /var/log/devilnet/{alerts,reports}

# Set permissions (devilnet user only)
sudo chown -R devilnet:devilnet /var/lib/devilnet /var/log/devilnet
sudo chmod -R 750 /var/lib/devilnet /var/log/devilnet

# Make readable by devilnet (but read-only for logs)
sudo setfacl -R -m u:devilnet:r /var/log/auth.log /var/log/syslog /var/log/audit/ /var/log/fail2ban.log
```

### 3. Grant Log Read Access

```bash
# Add devilnet to adm group for log access
sudo usermod -a -G adm devilnet

# Alternative: Use ACL for precise access
sudo setfacl -m u:devilnet:r /var/log/auth.log
sudo setfacl -m u:devilnet:r /var/log/syslog
sudo setfacl -m u:devilnet:r /var/log/audit/
sudo setfacl -m u:devilnet:r /var/log/fail2ban.log

# Verify read access
sudo -u devilnet tail -n 1 /var/log/auth.log
```

### 4. Setup Python Virtual Environment

```bash
# Install system Python (minimal)
sudo apt-get install -y python3-minimal python3-venv python3-pip

# Create venv as devilnet
sudo -u devilnet python3 -m venv /var/lib/devilnet/venv

# Activate and install dependencies
sudo -u devilnet /var/lib/devilnet/venv/bin/pip install --upgrade pip
sudo -u devilnet /var/lib/devilnet/venv/bin/pip install \
    scikit-learn==1.3.2 \
    numpy==1.24.3 \
    pandas==2.0.3

# Lock venv permissions (read-only)
sudo chmod -R 555 /var/lib/devilnet/venv/lib/python*/site-packages
```

### 5. Deploy Devilnet Code

```bash
# Copy application to standard location
sudo cp -r devilnet_system/devilnet /opt/devilnet/

# Set ownership
sudo chown -R devilnet:devilnet /opt/devilnet
sudo chmod -R 755 /opt/devilnet

# Create symlink for easy access
sudo ln -s /opt/devilnet /var/lib/devilnet/app
```

### 6. Configure AppArmor Profile

```bash
# Copy AppArmor profile
sudo cp deploy/apparmor/devilnet-ml /etc/apparmor.d/

# Load and enable
sudo apparmor_parser -r /etc/apparmor.d/devilnet-ml
sudo aa-enforce devilnet-ml

# Verify
sudo aa-status | grep devilnet-ml
```

Alternatively, if using SELinux:

```bash
# Create and load SELinux policy
sudo semodule -i deploy/selinux/devilnet_ml.pp
```

### 7. Configure Logging

```bash
# Create rsyslog config for devilnet
sudo tee /etc/rsyslog.d/50-devilnet.conf > /dev/null <<EOF
# Devilnet ML Engine Logs
:programname, isequal, "devilnet" /var/log/devilnet/engine.log
& stop
EOF

# Restart rsyslog
sudo systemctl restart rsyslog
```

---

## Runtime Execution

### Manual Execution

```bash
# Run as devilnet user (engine will verify)
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 \
    -m devilnet.engine \
    --config /opt/devilnet/config/devilnet.json

# The engine will:
# 1. Verify non-root execution
# 2. Verify AppArmor/SELinux confinement
# 3. Initialize security context
# 4. Load and run ML pipeline
```

### Systemd Service

Create `/etc/systemd/system/devilnet.service`:

```ini
[Unit]
Description=Devilnet ML Anomaly Detection Engine
After=network.target syslog.target
PartOf=multi-user.target

[Service]
Type=simple
User=devilnet
Group=devilnet

# Security hardening
PrivateTmp=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/var/lib/devilnet /var/log/devilnet
ReadOnlyPaths=/var/log/auth.log /var/log/syslog /var/log/audit /var/log/fail2ban.log

# Execution
ExecStart=/var/lib/devilnet/venv/bin/python3 -m devilnet.engine \
          --config /opt/devilnet/config/devilnet.json

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=600
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable devilnet.service
sudo systemctl start devilnet.service

# Check status
sudo systemctl status devilnet.service
sudo journalctl -u devilnet.service -f
```

---

## Security Verification

### 1. Verify Non-Root Execution

```bash
# Check running process
ps aux | grep devilnet

# Should show:
# devilnet ... /var/lib/devilnet/venv/bin/python3 ...
# NOT root
```

### 2. Verify AppArmor Confinement

```bash
# Check AppArmor profile
sudo aa-status | grep devilnet-ml

# Verify in enforce mode
sudo aa-enforce devilnet-ml
```

### 3. Verify Network Access Disabled

```bash
# Check for network listeners (should be empty)
sudo netstat -tlnup | grep devilnet
sudo ss -tlnup | grep devilnet

# Should return nothing
```

### 4. Verify Filesystem Access

```bash
# Verify read-only access to logs
sudo -u devilnet cat /var/log/auth.log | head -n 1

# Verify write access to state
sudo -u devilnet touch /var/lib/devilnet/test_write.txt
ls -la /var/lib/devilnet/test_write.txt
sudo -u devilnet rm /var/lib/devilnet/test_write.txt

# Verify NO write access to logs
sudo -u devilnet tee /var/log/auth.log < /dev/null
# Should fail: Permission denied
```

### 5. Verify Python Isolation

```bash
# Check venv is active
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -c "import sys; print(sys.prefix)"
# Should show: /var/lib/devilnet/venv

# Verify no dangerous modules available
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -c "import subprocess; print(subprocess.run(['id']))"
# Should work but restricted by AppArmor
```

---

## Monitoring & Maintenance

### 1. Monitor Engine Health

```bash
# Check recent alerts
tail -f /var/log/devilnet/alerts/stream.jsonl

# Check incident reports
ls -lrt /var/log/devilnet/reports/ | tail -10

# Check engine logs
journalctl -u devilnet.service -n 100
```

### 2. Training on Baseline Data

```bash
# Before first deployment, train on baseline (normal) traffic
# This requires collecting 1000+ events from normal operations

# Create baseline file (JSONL format of feature vectors)
# Then train:
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 << 'EOF'
from devilnet.ml.pipeline import MLPipeline
from devilnet.ml.feature_extraction import FeatureVector
import json

pipeline = MLPipeline()
# Load feature vectors from baseline JSONL
vectors = []
with open('/var/lib/devilnet/baseline_events.jsonl', 'r') as f:
    for line in f:
        data = json.loads(line)
        # Reconstruct FeatureVector from JSON
        # (simplified)

pipeline.train_from_baseline(vectors)
print("Model trained successfully")
EOF
```

### 3. Rotating Logs

```bash
# Configure logrotate for devilnet logs
sudo tee /etc/logrotate.d/devilnet > /dev/null <<EOF
/var/log/devilnet/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 750 devilnet devilnet
    sharedscripts
    postrotate
        systemctl reload-or-restart devilnet.service > /dev/null 2>&1 || true
    endscript
}
EOF
```

### 4. Incident Response Review

```bash
# Review executed response actions
cat /var/log/devilnet/responses_*.jsonl | jq .

# Rollback (reversal) of response actions if needed
# Each action logs its reversal command:
# "reversal_command": "usermod -U compromised_user"
```

---

## Troubleshooting

### Engine Won't Start

```bash
# Check security context
sudo systemctl status devilnet.service
sudo journalctl -u devilnet.service -n 20

# Common issues:
# 1. User "devilnet" doesn't exist -> create it
# 2. Log files not readable -> verify ACLs/permissions
# 3. Directory doesn't exist -> create /var/lib/devilnet
```

### No Events Being Detected

```bash
# Verify log ingestion
sudo -u devilnet tail -n 10 /var/log/auth.log

# Check tail state file
ls -la /tmp/devilnet_tail_*.state

# Verify ML model is trained
ls -la /var/lib/devilnet/isolation_forest.pkl

# Check alert stream
tail -f /var/log/devilnet/alerts/stream.jsonl
```

### AppArmor Denials

```bash
# Check for AppArmor denials
sudo dmesg | grep apparmor | tail -20

# Check audit log
grep "apparmor" /var/log/audit/audit.log | tail -20

# If legitimate access needed, update profile:
sudo nano /etc/apparmor.d/devilnet-ml
sudo apparmor_parser -r /etc/apparmor.d/devilnet-ml
```

---

## Security Checklist

- [ ] Dedicated non-privileged user created
- [ ] Log directories created with correct permissions
- [ ] Python venv configured with frozen dependencies
- [ ] AppArmor/SELinux profile loaded and enforced
- [ ] Service runs as correct user (verified)
- [ ] No network listeners active
- [ ] Logs are read-only
- [ ] State directories are writable
- [ ] venv site-packages are read-only
- [ ] SystemD service with security hardening configured
- [ ] Logging configured and rotating
- [ ] Baseline training data collected and model trained
- [ ] Alert stream monitored
- [ ] Incident response tested (dry-run mode first)

---

## Production Deployment Tips

1. **Start in Dry-Run Mode**: Set `enable_automated_actions: false` initially
2. **Monitor Baseline Period**: Run for 1-2 weeks to tune thresholds
3. **Tune Contamination**: Adjust `ml_pipeline.contamination` based on observed anomaly rate
4. **Review False Positives**: Adjust feature thresholds if too many alerts
5. **Test Response Actions**: Verify incident response in staging before production
6. **Backup Model**: Store trained models in version control
7. **Monitor Performance**: Track inference latency and memory usage
8. **Update Baseline**: Retrain model monthly on latest normal data
9. **Audit Logs**: Regularly review response audit logs for effectiveness
10. **Security Updates**: Keep scikit-learn and Python updated

---

## Incident Response Procedures

When HIGH or CRITICAL anomalies are detected:

1. **Automatic Alert**: Alert sent to /var/log/devilnet/alerts/stream.jsonl
2. **Report Generation**: JSON and text reports saved to /var/log/devilnet/reports/
3. **Dry-Run by Default**: Actions logged but not executed (enable in config)
4. **Manual Verification**: Blue team reviews report and decides on response
5. **Execute Response**: Either manually or enable automated actions after validation
6. **Audit Trail**: All actions logged in /var/log/devilnet/responses_*.jsonl
7. **Reversible**: All actions include reversal commands for rollback

---

## Performance Considerations

- **Feature Window**: Shorter windows (1-2 min) for responsiveness, longer (5-10 min) for stability
- **Batch Size**: Increase for higher throughput, decrease for lower latency
- **Contamination**: Default 0.1 (10% anomalies) - adjust based on expected anomaly rate
- **Model Size**: n_estimators=100 is lightweight, increase only if needed
- **Poll Interval**: 5 seconds default balances latency vs. system load

---

## References

- MITRE ATT&CK: https://attack.mitre.org/
- AppArmor Wiki: https://gitlab.com/apparmor/apparmor/-/wikis/home
- scikit-learn Isolation Forest: https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html
- Linux Security: https://wiki.debian.org/Hardening

