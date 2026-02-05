# DEVILNET QUICK START & COMMAND REFERENCE

## Installation (1 minute)

```bash
# Clone/navigate to directory
cd devilnet_system

# Run quickstart script
sudo bash deploy/quickstart.sh

# Verify
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 --version
```

## Usage

### Run Demonstration
```bash
# Shows 3 attack scenarios + reports
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine --demo
```

### Single Inference Cycle
```bash
# Run once and exit (check for alerts)
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine --once
```

### Continuous Monitoring
```bash
# Run forever (Ctrl+C to stop)
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine
```

### Train Model
```bash
# Train on baseline data (1000+ normal events)
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine \
    --train /path/to/baseline_events.jsonl
```

### Check Status
```bash
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine --status
```

### Verbose Logging
```bash
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine \
    --once --verbose
```

---

## File Locations

| File | Purpose |
|------|---------|
| `/var/lib/devilnet/isolation_forest.pkl` | Trained ML model |
| `/var/lib/devilnet/venv/` | Python environment |
| `/var/log/devilnet/alerts/stream.jsonl` | Real-time alert stream |
| `/var/log/devilnet/reports/` | Incident reports (JSON + TXT) |
| `/var/log/devilnet/responses_*.jsonl` | Response action audit log |
| `/opt/devilnet/config/devilnet.json` | Configuration |
| `/etc/apparmor.d/devilnet-ml` | AppArmor profile |

---

## Configuration Quick Tune

Edit `/opt/devilnet/config/devilnet.json`:

### Reduce False Positives
```json
{
  "ml_pipeline": {
    "contamination": 0.15    // Increase to 0.15 (15% anomalies)
  },
  "alert_levels": {
    "low_threshold": 0.5,    // Raise to 0.5
    "medium_threshold": 0.7  // Raise to 0.7
  }
}
```

### Increase Detection Sensitivity
```json
{
  "ml_pipeline": {
    "contamination": 0.05    // Lower to 0.05 (5% anomalies)
  },
  "alert_levels": {
    "low_threshold": 0.3,    // Lower to 0.3
    "medium_threshold": 0.5  // Lower to 0.5
  }
}
```

### Enable Automated Response (AFTER TESTING)
```json
{
  "incident_response": {
    "enable_automated_actions": true
  }
}
```

---

## Monitoring

### Watch Real-Time Alerts
```bash
tail -f /var/log/devilnet/alerts/stream.jsonl | jq .
```

### View Incident Reports
```bash
# List recent incidents
ls -lrt /var/log/devilnet/reports/ | tail -5

# View specific report
cat /var/log/devilnet/reports/INC-20250115-000001.txt

# Parse JSON report
jq . /var/log/devilnet/reports/INC-20250115-000001.json
```

### Check Response Actions
```bash
# View all response actions
cat /var/log/devilnet/responses_*.jsonl | jq .

# View only failed actions
cat /var/log/devilnet/responses_*.jsonl | jq 'select(.success == false)'

# Get reversal commands (if needed to undo)
cat /var/log/devilnet/responses_*.jsonl | jq '.reversal_command'
```

### Engine Logs
```bash
# Systemd service logs
sudo journalctl -u devilnet.service -f

# Or file logs
tail -f /var/log/devilnet/engine.log
```

---

## Troubleshooting

### "User devilnet not found"
```bash
sudo useradd -r -s /bin/false devilnet
```

### "Permission denied" reading logs
```bash
sudo usermod -a -G adm devilnet
sudo setfacl -m u:devilnet:r /var/log/auth.log /var/log/syslog
```

### "Model not trained"
```bash
# Collect 1000+ normal events to baseline file
# Then train:
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine \
    --train baseline_events.jsonl
```

### No alerts after running
```bash
# Check if events are being ingested
sudo -u devilnet tail -n 5 /var/log/auth.log

# Run verbose to debug
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine \
    --once --verbose

# Check alert stream
tail -f /var/log/devilnet/alerts/stream.jsonl
```

---

## Attack Scenario Examples

### Simulate Brute Force
```bash
# Generate 50 failed SSH attempts from single IP
for i in {1..50}; do
  sshlog="Failed password for root from 203.0.113.99 port $((50000+i))"
  echo "Jan 15 14:32:10 server sshd[1234]: $sshlog" >> /tmp/test_auth.log
done
```

### Generate Valid Account Abuse
```bash
# Add successful login from new IP
echo "Jan 15 14:33:00 server sshd[1234]: Accepted publickey for alice from 198.51.100.45" >> /var/log/auth.log
```

### Run Demo Scenarios
```bash
sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine --demo
```

---

## Configuration Defaults

```json
{
  "failed_login_threshold": 5,           // Alerts on 5+ failed logins
  "unique_users_threshold": 10,          // Alerts on 10+ different users tried
  "low_threshold": 0.4,                  // ML score for LOW severity
  "medium_threshold": 0.6,               // ML score for MEDIUM severity
  "high_threshold": 0.8,                 // ML score for HIGH severity
  "critical_threshold": 0.9,             // ML score for CRITICAL severity
  "lock_account_at_risk_level": "HIGH",  // Lock accounts on HIGH alerts
  "block_ip_at_risk_level": "HIGH",      // Block IPs on HIGH alerts
  "enable_automated_actions": false,     // Start in dry-run mode
  "feature_window_minutes": 5,           // Aggregate events over 5 min
  "tail_poll_interval_seconds": 5       // Check for new logs every 5 sec
}
```

---

## Detection Examples

### Brute Force (T1110)
- **Trigger**: 5+ failed logins from same IP
- **Features**: `ip_failed_logins > 5`, `ip_failed_to_success_ratio > 0.8`
- **Risk**: HIGH
- **Action**: Block IP

### Credential Stuffing (T1110.004)
- **Trigger**: Successful login after multiple failures, new IP
- **Features**: `ip_failed_to_success_ratio > 0.5`, `user_new_ip_detected`
- **Risk**: MEDIUM
- **Action**: Alert

### Privilege Escalation (T1548)
- **Trigger**: Sudo within 60 sec of login
- **Features**: `session_login_to_privesc_seconds < 60`
- **Risk**: HIGH
- **Action**: Lock account, block IP

### Post-Compromise Activity (T1059.004)
- **Trigger**: Shell/LOLBin execution detected
- **Features**: `session_lolbin_executed = true`
- **Risk**: HIGH
- **Action**: Terminate session, alert

---

## Key Features

✓ Real-time log monitoring (sub-100ms latency)  
✓ 14-dimensional behavioral features  
✓ Unsupervised ML (Isolation Forest)  
✓ 15+ MITRE ATT&CK technique mappings  
✓ Automated incident response (controlled)  
✓ Dry-run mode (test before enabling)  
✓ Fully auditable (all actions logged)  
✓ Non-privileged execution  
✓ AppArmor/SELinux sandboxed  
✓ JSON + human-readable reports  

---

## Important Security Notes

⚠️ **Never run as root** - Engine explicitly prevents it  
⚠️ **Always start in dry-run mode** - Test responses first  
⚠️ **Train on clean baseline** - Use known-good traffic  
⚠️ **Monitor cooldowns** - Prevent response spam  
⚠️ **Review false positives** - Tune thresholds as needed  
⚠️ **Maintain baseline** - Retrain monthly  

---

## Quick Deployment Checklist

- [ ] Create `devilnet` user
- [ ] Create `/var/lib/devilnet` and `/var/log/devilnet`
- [ ] Setup Python venv
- [ ] Load AppArmor profile
- [ ] Configure log access (ACL or adm group)
- [ ] Copy application code
- [ ] Copy configuration file
- [ ] Collect baseline data (1000+ events)
- [ ] Train model: `--train baseline.jsonl`
- [ ] Run demo: `--demo`
- [ ] Test single cycle: `--once --verbose`
- [ ] Verify alert generation
- [ ] Setup SystemD service
- [ ] Enable automated actions (after validation)

---

## Support & References

- **Main Docs**: See `README.md`
- **Technical Details**: See `REFERENCE.md`
- **Deployment Guide**: See `deploy/HARDENING_GUIDE.md`
- **Examples**: See `examples/demo_scenarios.py`
- **Tests**: See `tests/test_suite.py`
- **MITRE ATT&CK**: https://attack.mitre.org/
- **scikit-learn**: https://scikit-learn.org/

