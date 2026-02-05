# Devilnet Interactive UI - Quick Reference

## Startup Commands

```bash
# Interactive dashboard (RECOMMENDED)
python3 -m devilnet --ui

# Single cycle (test/verify)
python3 -m devilnet --once

# Continuous monitoring (headless)
python3 -m devilnet --monitor

# Train ML model
python3 -m devilnet --train

# System status check
python3 -m devilnet --status

# Run demo with simulated attacks
python3 -m devilnet --demo

# Verbose logging (debug)
python3 -m devilnet --ui --verbose
```

## Interactive UI Controls

| Key | Action |
|-----|--------|
| `↑` / `↓` | Navigate menu items |
| `Enter` | Select highlighted item |
| `q` | Quit application gracefully |
| `Ctrl+C` | Emergency exit (unsafe) |

## UI Menu Items

### Dashboard
- View real-time metrics
- See current anomalies
- Monitor system health

### Alerts
- View recent alerts
- Filter by severity
- Acknowledge/dismiss

### Reports
- List incident reports
- View report details
- Export reports

### Settings
- Change thresholds
- Toggle features
- View configuration

### Monitoring
- Start/pause monitoring
- View monitoring status
- Adjust poll interval

### Exit
- Gracefully shutdown
- Save state
- Clean up resources

## Real-Time Metrics (Dashboard)

```
├─ Alerts Total: 42
├─ Anomalies Detected: 12
├─ Actions Taken: 3
├─ Success Rate: 99.2%
└─ Uptime: 2d 5h 23m
```

## Alert Levels

| Level | Color | Meaning |
|-------|-------|---------|
| INFO | Green | Informational |
| WARNING | Yellow | Needs attention |
| CRITICAL | Red | Immediate action needed |
| SUCCESS | Cyan | Operation succeeded |

## Troubleshooting Shortcuts

### Script keeps stopping
1. Check logs: `tail /var/log/devilnet/devilnet.log`
2. Look for: `exceeded max retries`
3. Fix root cause (e.g., missing logs)
4. Restart: `python3 -m devilnet --ui`

### UI freezes
1. Press `Ctrl+C` to exit
2. Check system resources: `free -h`
3. Try single cycle: `python3 -m devilnet --once`
4. Restart UI

### No anomalies detected
1. Check if model trained: `python3 -m devilnet --status`
2. Train if needed: `python3 -m devilnet --train`
3. Verify log access: `ls -la /var/log/auth.log`
4. Enable verbose: `--verbose`

### Performance issues
1. Check bottlenecks: `grep "bottleneck" /var/log/devilnet/devilnet.log`
2. Increase poll interval in config
3. Run: `python3 -m devilnet --once --verbose`
4. Look for slow components

## Configuration Files

```
/etc/devilnet/devilnet.json    - Main configuration
/var/log/devilnet/devilnet.log - Main log file
/var/lib/devilnet/model.pkl    - Trained ML model
/var/log/devilnet/reports/     - Incident reports
```

## Key Features

✓ **Non-Blocking UI** - Doesn't freeze on alerts or processing
✓ **Error Recovery** - Script continues despite errors (max 5 consecutive)
✓ **Real-Time Dashboard** - Live metrics and alerts
✓ **Multiple Modes** - UI, headless, demo, training
✓ **Performance Monitoring** - Track system efficiency
✓ **Graceful Shutdown** - Clean exit on Ctrl+C or signal

## Architecture

```
┌─────────────────────────────────────┐
│  Interactive Terminal UI (Main)     │
│  - Menu navigation                  │
│  - Real-time display                │
│  - Non-blocking input               │
└─────────────────────────────────────┘
         │
         ├─→ Monitoring Thread (Background)
         │   - Continuous inference
         │   - Error recovery
         │   - Max 5 consecutive errors
         │
         └─→ Alert Handler Thread (Background)
             - Process queue
             - Display notifications
             - Never blocks UI

Error Handling:
- Each component isolated
- Circuit breaker pattern
- Exponential backoff
- Graceful pause on max errors
```

## Performance Targets

- **Inference cycle**: < 5 seconds
- **Alert display**: < 100ms
- **UI refresh**: < 100ms
- **Log processing**: < 50ms per 1000 events
- **Report generation**: < 500ms

## Security Notes

⚠️ **Always run as non-root user:**
```bash
sudo useradd -r -s /bin/false devilnet
sudo -u devilnet python3 -m devilnet --ui
```

⚠️ **Log files are read-only:**
- Devilnet cannot modify logs
- Only authorized users can delete
- Actions are simulated by default

⚠️ **No network exposure:**
- No listening ports
- No outbound connections
- Completely isolated

## Examples

### Monitor continuously for 1 hour then analyze
```bash
timeout 3600 python3 -m devilnet --monitor
# Then check reports
ls -lh /var/log/devilnet/reports/
```

### Test detection on single cycle with verbose output
```bash
python3 -m devilnet --once --verbose
# Look for anomaly scores in output
```

### Train model on clean baseline (no attacks)
```bash
python3 -m devilnet --train
# Takes 1-2 minutes
# Creates /var/lib/devilnet/model.pkl
```

### View recent anomalies
```bash
tail -f /var/log/devilnet/alerts/stream.jsonl
# Real-time JSON alert stream
```

### Generate performance report
```bash
python3 -c "
from devilnet.core.performance import get_performance_monitor
monitor = get_performance_monitor()
print(monitor.print_report())
"
```

## Support Resources

| Resource | Location |
|----------|----------|
| Full Guide | `INTERACTIVE_UI_GUIDE.md` |
| Technical Ref | `REFERENCE.md` |
| Hardening | `deploy/HARDENING_GUIDE.md` |
| Quick Start | `QUICK_START.md` |
| Main README | `README.md` |

---

**Version**: 2.0 (Interactive + Resilience)
**Last Updated**: 2024
**Status**: Production Ready
