# Devilnet - Interactive Terminal UI & Resilience Features

## Overview

This update introduces:
1. **Interactive Terminal Dashboard** - Easy-to-navigate menu system
2. **Non-Blocking Alert System** - Notifications don't interrupt monitoring
3. **Error Recovery** - Script continues running despite errors
4. **Performance Monitoring** - Track and optimize system efficiency

## Quick Start

### Launch Interactive Dashboard
```bash
python3 -m devilnet --ui
```

### Navigation (Interactive Mode)
- **↑ / ↓** : Navigate menu items
- **Enter** : Select menu item
- **q** : Quit application
- **Ctrl+C** : Emergency exit

### Other Modes
```bash
# Train ML model
python3 -m devilnet --train

# Run single detection cycle
python3 -m devilnet --once

# Continuous monitoring (headless)
python3 -m devilnet --monitor

# System status
python3 -m devilnet --status

# Demonstration
python3 -m devilnet --demo

# Verbose logging
python3 -m devilnet --ui --verbose
```

## Architecture

### Resilient Engine (`devilnet/core/resilient_engine.py`)

**Non-Blocking Architecture**
```
Main Thread (UI)
    ↓ sends commands to
Monitoring Thread (Inference)
    ↓ produces
Alert Queue (Thread-Safe)
    ↓ consumed by
Alert Handler Thread (Background Processing)
```

**Error Recovery**
- Maximum 5 consecutive errors before graceful pause
- Exponential backoff (2s after error vs 5s normal)
- Circuit breaker pattern prevents cascading failures
- All errors logged but don't stop execution

### Terminal UI (`devilnet/ui/terminal_ui.py`)

**Components:**
- `AlertLevel` - Alert severity (INFO, WARNING, CRITICAL, SUCCESS)
- `AlertQueue` - Thread-safe queue for non-blocking notifications
- `InteractiveUI` - Menu state management
- `TerminalRenderer` - Curses-based rendering with colors
- `MonitoringThread` - Background inference with error recovery
- `NonBlockingAlertHandler` - Background alert processing

**Features:**
- Non-blocking input (100ms timeout)
- Real-time metrics (alerts, anomalies, actions, uptime)
- Menu-driven navigation
- Color-coded alert levels (green/yellow/red/cyan)

### Performance Monitoring (`devilnet/core/performance.py`)

**Metrics Tracked:**
- Component response times (min/max/avg)
- Error rates per component
- Success rates
- Bottleneck identification
- Optimization recommendations

**Usage:**
```python
from devilnet.core.performance import get_performance_monitor, TimerContext

monitor = get_performance_monitor()

# Record metrics
with TimerContext(monitor, 'ingestion', 'parse_auth_log'):
    # Your code here
    pass

# Get stats
stats = monitor.get_stats()
recommendations = monitor.get_recommendations()
```

## Non-Blocking Design

### Why Non-Blocking?

**Problem**: Traditional blocking I/O freezes the UI when:
- Reading large log files
- Processing anomalies
- Generating reports
- Receiving alerts

**Solution**: Threading + Queues
```
Alert arrives
    ↓ (non-blocking)
Added to queue
    ↓ (queue callback)
Handler processes asynchronously
    ↓ (display when ready)
Shown in UI without interruption
```

### Key Guarantees

✓ **Never Blocks**: Input never waits for processing
✓ **Always Recovers**: Errors trigger pause, not crash
✓ **Non-Destructive**: No data loss on errors
✓ **Auditable**: All errors logged with recovery info

## Error Recovery Pattern

### Circuit Breaker Pattern

```
CLOSED (Normal Operation)
    ↓ (5 consecutive failures)
OPEN (Blocking Calls)
    ↓ (60 second timeout)
HALF-OPEN (Testing Recovery)
    ↓ (success)
CLOSED (Resume Normal)
```

### Component Recovery

```python
# Each component can fail independently
for component in ['ingestion', 'ml_inference', 'response', 'reporting']:
    breaker = circuit_breakers[component]
    try:
        result = breaker.call(operation)
    except Exception:
        # Component fails, others continue
        recovery_manager.record_error(component)
        # System continues without this component
```

## Performance Optimization

### Benchmarks

Target performance:
- Log parsing: <50ms per 1000 events
- Feature extraction: <20ms per vector
- ML inference: <100ms per batch
- Report generation: <500ms

### Identifying Bottlenecks

```bash
# Enable performance monitoring
python3 -m devilnet --ui --verbose

# Check bottlenecks in logs
tail -f /var/log/devilnet/devilnet.log | grep "bottleneck"
```

### Optimization Tips

1. **Batch Processing**: Process multiple events together
2. **Caching**: Cache ML models and feature statistics
3. **Async I/O**: Use threading for log reading
4. **Vectorization**: Use NumPy for feature extraction
5. **Lazy Loading**: Load models only when needed

## Configuration

### Main Configuration (`/etc/devilnet/devilnet.json`)

Key settings:
- `poll_interval_seconds`: How often to check logs (default: 5)
- `batch_size`: Events per batch (default: 100)
- `alert_queue_size`: Max alerts in queue (default: 1000)
- `error_recovery_max_retries`: Max retry attempts (default: 3)
- `circuit_breaker_timeout`: Recovery time in seconds (default: 60)

### UI Configuration

Automatic:
- Menu refreshes every 100ms
- Alerts display immediately
- Metrics update in real-time
- No user configuration needed

## Troubleshooting

### Script Stops During Monitoring

**Cause**: Too many consecutive errors (>5)

**Solution**:
1. Check logs: `tail /var/log/devilnet/devilnet.log`
2. Fix root issue (e.g., missing log files)
3. Restart: `python3 -m devilnet --ui`

### UI Freezes

**Cause**: Blocking operation in monitoring thread

**Solution**:
1. Press Ctrl+C (emergency exit)
2. Check if log files are corrupted
3. Run training: `python3 -m devilnet --train`
4. Restart UI

### Slow Performance

**Cause**: Too many events or complex features

**Solution**:
1. Check bottlenecks: `python3 -m devilnet --ui --verbose`
2. Increase batch size in config
3. Reduce log file polling frequency
4. Disable non-essential features

### Alerts Not Appearing

**Cause**: Alert queue overflow or handler thread stopped

**Solution**:
1. Reduce monitoring frequency (longer poll intervals)
2. Check if max alerts in queue reached
3. Restart script: `python3 -m devilnet --ui`

## Implementation Details

### Thread Safety

All shared data protected by locks:
```python
# UI metrics (shared between threads)
self.stats_lock = threading.Lock()
with self.stats_lock:
    self.stats['anomalies_detected'] += 1

# Alert queue (thread-safe)
self.alert_queue = queue.Queue(maxsize=1000)
self.alert_queue.put(alert)  # Thread-safe
alert = self.alert_queue.get()  # Thread-safe
```

### Signal Handling

Graceful shutdown on SIGTERM/SIGINT:
```python
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)
# Script exits cleanly without data loss
```

### Resource Cleanup

Automatic cleanup:
- Closes file handles on exit
- Flushes pending alerts
- Saves monitoring state
- Releases memory

## API Reference

### ResilientDevilnetEngine

```python
class ResilientDevilnetEngine:
    # Run inference with full error recovery
    def run_inference_cycle_resilient(self) -> List:
        """Never raises - returns [] on errors"""
    
    # Get engine statistics
    def get_stats(self) -> Dict[str, Any]:
        """Returns cycles, anomalies, success rate, uptime"""

# Create resilient wrapper
engine = create_resilient_engine(base_engine, ui=None)
```

### InteractiveUI

```python
class InteractiveUI:
    # Add alert for display
    def add_alert(self, message: str, level: AlertLevel) -> None:
        """Non-blocking - returns immediately"""
    
    # Update metrics display
    def update_metrics(self, anomalies_detected: int = None, 
                      actions_taken: int = None, ...) -> None:
        """Updates real-time dashboard"""

# Create UI instance
ui = InteractiveUI()
```

### PerformanceMonitor

```python
from devilnet.core.performance import get_performance_monitor, TimerContext

monitor = get_performance_monitor()

# Record metrics with context manager
with TimerContext(monitor, 'ml_inference', 'predict'):
    predictions = model.predict(features)

# Get statistics
stats = monitor.get_stats('ingestion')
recommendations = monitor.get_recommendations()
```

## Files Changed/Created

**New Files:**
- `devilnet/core/resilient_engine.py` - Error recovery & resilience
- `devilnet/core/performance.py` - Performance monitoring
- `devilnet/ui/terminal_ui.py` - Interactive terminal UI
- `devilnet/ui/__init__.py` - UI package initialization

**Modified Files:**
- `devilnet/__main__.py` - New entry point with multiple modes

**No Changes to:**
- `devilnet/engine.py` - Core ML/security untouched
- `devilnet/core/security.py` - Security constraints unchanged
- Log parsing, feature extraction, response systems - Fully compatible

## Testing

### Unit Tests (Existing)
```bash
python3 tests/test_suite.py
```

### Manual Testing

1. **UI Navigation**
   ```bash
   python3 -m devilnet --ui
   # Test arrow keys, Enter, q
   ```

2. **Error Recovery**
   ```bash
   # Simulate error by corrupting log file
   # UI should pause, then allow recovery
   ```

3. **Non-Blocking Alerts**
   ```bash
   # Monitor alert queue size doesn't exceed limit
   tail -f /var/log/devilnet/devilnet.log | grep AlertQueue
   ```

4. **Performance**
   ```bash
   python3 -m devilnet --once --verbose
   # Check timing for each component
   ```

## Roadmap

**Future Enhancements:**
- Web UI dashboard (HTTP REST API)
- Distributed monitoring (multiple hosts)
- Machine learning model export/import
- Automated tuning of thresholds
- Database backend for reports
- Real-time collaboration features

## Support

**Documentation:**
- [README.md](README.md) - System overview
- [REFERENCE.md](REFERENCE.md) - Technical deep dive
- [HARDENING_GUIDE.md](deploy/HARDENING_GUIDE.md) - Deployment guide
- [QUICK_START.md](QUICK_START.md) - Command reference

**Issues:**
- Check logs: `/var/log/devilnet/devilnet.log`
- Run status: `python3 -m devilnet --status`
- Enable verbose: `python3 -m devilnet --ui --verbose`

## License & Security

See parent project documentation.
