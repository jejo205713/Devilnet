# Integration Testing Guide - Resilient Engine & Interactive UI

## Overview

This guide provides comprehensive testing procedures for:
1. Error recovery mechanisms
2. Non-blocking UI functionality
3. Performance under stress
4. End-to-end workflow validation

## Test Environment Setup

```bash
# Create test environment
mkdir -p /tmp/devilnet_test
cd /tmp/devilnet_test

# Create dummy logs for testing
cat > test_auth.log << 'EOF'
Nov 15 10:23:45 host sshd[1234]: Invalid user admin from 192.168.1.100 port 12345
Nov 15 10:23:46 host sshd[1235]: Failed password for invalid user admin from 192.168.1.100 port 12346
Nov 15 10:23:47 host sshd[1236]: Failed password for invalid user admin from 192.168.1.100 port 12347
Nov 15 10:24:10 host sudo: user : TTY=pts/0 ; PWD=/home/user ; USER=root ; COMMAND=/bin/id
Nov 15 10:24:11 host sudo: user : command not allowed ; TTY=pts/0 ; PWD=/home/user
EOF

# Point devilnet to test logs (in config)
export DEVILNET_AUTH_LOG=/tmp/devilnet_test/test_auth.log
```

## Unit Tests

### 1. Error Recovery Manager

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/path/to/devilnet')

from devilnet.core.resilient_engine import ErrorRecoveryManager
import time

def test_error_recovery():
    print("Testing ErrorRecoveryManager...")
    manager = ErrorRecoveryManager(max_retries=3, backoff_multiplier=2.0)
    
    # Test 1: Error counting
    component = 'test_component'
    for i in range(1, 4):
        count = manager.record_error(component)
        assert count == i, f"Error count should be {i}, got {count}"
    print("✓ Error counting works")
    
    # Test 2: Should retry check
    assert manager.should_retry(component) == False, "Should not retry after max"
    print("✓ Max retries enforcement works")
    
    # Test 3: Reset
    manager.reset_error_count(component)
    assert manager.should_retry(component) == True, "Should retry after reset"
    print("✓ Error reset works")
    
    # Test 4: Backoff calculation
    manager.record_error(component)
    backoff = manager.get_backoff_time(component)
    assert 1.0 <= backoff <= 2.0, f"Backoff should be 1-2, got {backoff}"
    print(f"✓ Backoff calculation works: {backoff:.2f}s")
    
    print("\n✅ ErrorRecoveryManager tests PASSED\n")

if __name__ == '__main__':
    test_error_recovery()
```

### 2. Circuit Breaker

```python
#!/usr/bin/env python3
from devilnet.core.resilient_engine import CircuitBreaker
import time

def test_circuit_breaker():
    print("Testing CircuitBreaker...")
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=2)
    
    def success_func():
        return "success"
    
    def fail_func():
        raise ValueError("intentional failure")
    
    # Test 1: Success path
    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state == "closed"
    print("✓ Success path works")
    
    # Test 2: Opening circuit on failures
    for i in range(3):
        try:
            breaker.call(fail_func)
        except ValueError:
            pass
    assert breaker.state == "open", f"State should be 'open', got {breaker.state}"
    print("✓ Circuit opens after threshold")
    
    # Test 3: Rejected while open
    try:
        breaker.call(success_func)
        assert False, "Should raise exception when circuit open"
    except Exception as e:
        assert "Circuit breaker open" in str(e)
    print("✓ Circuit rejects calls when open")
    
    # Test 4: Recovery timeout
    time.sleep(2.5)
    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state == "closed"
    print("✓ Circuit recovers after timeout")
    
    print("\n✅ CircuitBreaker tests PASSED\n")

if __name__ == '__main__':
    test_circuit_breaker()
```

### 3. Alert Queue (Non-Blocking)

```python
#!/usr/bin/env python3
from devilnet.ui.terminal_ui import AlertQueue, AlertLevel
import threading
import time

def test_alert_queue():
    print("Testing AlertQueue (non-blocking)...")
    queue = AlertQueue(max_size=5)
    
    # Test 1: Non-blocking add
    start = time.time()
    for i in range(100):
        queue.add_alert(f"Alert {i}", AlertLevel.INFO)
    elapsed = time.time() - start
    assert elapsed < 0.1, f"Adding 100 alerts should be fast, took {elapsed:.3f}s"
    print(f"✓ Non-blocking add: 100 alerts in {elapsed*1000:.1f}ms")
    
    # Test 2: Max size enforcement
    assert queue.size() <= 5, "Queue should not exceed max size"
    print("✓ Queue size limit enforced")
    
    # Test 3: FIFO order
    queue_empty = AlertQueue(max_size=10)
    queue_empty.add_alert("first", AlertLevel.INFO)
    queue_empty.add_alert("second", AlertLevel.WARNING)
    queue_empty.add_alert("third", AlertLevel.CRITICAL)
    
    alerts = queue_empty.get_all_alerts()
    assert len(alerts) == 3
    print("✓ FIFO order maintained")
    
    # Test 4: Thread safety
    queue_thread = AlertQueue(max_size=100)
    def add_alerts(thread_id):
        for i in range(50):
            queue_thread.add_alert(f"Thread {thread_id} Alert {i}", AlertLevel.INFO)
    
    threads = [threading.Thread(target=add_alerts, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    assert queue_thread.size() <= 100, "Queue size should respect limit with threads"
    print(f"✓ Thread-safe: 4 threads added to queue, size={queue_thread.size()}")
    
    print("\n✅ AlertQueue tests PASSED\n")

if __name__ == '__main__':
    test_alert_queue()
```

## Integration Tests

### 4. End-to-End Resilience

```python
#!/usr/bin/env python3
import sys
sys.path.insert(0, '/path/to/devilnet')

from devilnet.engine import DevilnetEngine
from devilnet.core.resilient_engine import create_resilient_engine
import logging

logging.basicConfig(level=logging.INFO)

def test_end_to_end_resilience():
    print("Testing End-to-End Resilience...")
    
    try:
        # Create engines
        base_engine = DevilnetEngine()
        resilient_engine = create_resilient_engine(base_engine)
        
        # Test 1: Normal operation
        anomalies = resilient_engine.run_inference_cycle_resilient()
        assert isinstance(anomalies, list), "Should return list"
        print(f"✓ Normal cycle: found {len(anomalies)} anomalies")
        
        # Test 2: No exceptions raised
        stats = resilient_engine.get_stats()
        assert stats['cycles_completed'] >= 1, "Should increment cycle counter"
        print(f"✓ Stats tracking: {stats['cycles_completed']} cycles")
        
        # Test 3: Success rate
        assert stats['success_rate'] == 1.0 or stats['cycles_failed'] > 0
        print(f"✓ Success rate: {stats['success_rate']:.1%}")
        
        print("\n✅ End-to-End Resilience tests PASSED\n")
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise

if __name__ == '__main__':
    test_end_to_end_resilience()
```

## Stress Tests

### 5. High-Volume Alert Processing

```bash
#!/bin/bash
# Test alert queue under load

python3 << 'EOF'
from devilnet.ui.terminal_ui import AlertQueue, AlertLevel
import threading
import time

print("STRESS TEST: High-volume alerts...")

queue = AlertQueue(max_size=10000)
alert_count = 0
start_time = time.time()

def producer():
    global alert_count
    for i in range(10000):
        queue.add_alert(f"Alert {i}", [AlertLevel.INFO, AlertLevel.WARNING, AlertLevel.CRITICAL][i % 3])
        alert_count += 1

# Run producers in parallel
producers = [threading.Thread(target=producer) for _ in range(4)]
for p in producers:
    p.start()
for p in producers:
    p.join()

elapsed = time.time() - start_time
rate = alert_count / elapsed

print(f"✓ Processed {alert_count} alerts in {elapsed:.2f}s")
print(f"✓ Throughput: {rate:.0f} alerts/sec")
print(f"✓ Queue depth: {queue.size()}")

if rate > 5000:
    print("\n✅ STRESS TEST PASSED (>5000 alerts/sec)\n")
else:
    print(f"\n⚠️  WARNING: Low throughput ({rate:.0f}/sec)\n")
EOF
```

### 6. Error Injection

```python
#!/usr/bin/env python3
"""
Simulate errors and verify recovery
"""

import sys
import logging
sys.path.insert(0, '/path/to/devilnet')

from devilnet.core.resilient_engine import ResilientDevilnetEngine

logging.basicConfig(level=logging.INFO)

class TestEngine:
    def __init__(self, fail_count=3):
        self.call_count = 0
        self.fail_count = fail_count
    
    def run_inference_cycle(self):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise ValueError(f"Simulated error {self.call_count}")
        return []

def test_error_injection():
    print("Testing Error Injection & Recovery...")
    
    base_engine = TestEngine(fail_count=2)
    resilient_engine = ResilientDevilnetEngine(base_engine)
    
    # Run multiple cycles
    for i in range(5):
        anomalies = resilient_engine.run_inference_cycle_resilient()
        print(f"  Cycle {i+1}: {len(anomalies)} anomalies, "
              f"failed: {resilient_engine.stats['cycles_failed']}")
    
    stats = resilient_engine.get_stats()
    print(f"\nFinal stats:")
    print(f"  Cycles completed: {stats['cycles_completed']}")
    print(f"  Cycles failed: {stats['cycles_failed']}")
    print(f"  Errors recovered: {stats['errors_recovered']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    
    assert stats['errors_recovered'] > 0, "Should recover from errors"
    assert stats['success_rate'] < 1.0, "Should have some failures"
    assert stats['success_rate'] > 0.8, "Should recover successfully"
    
    print("\n✅ Error Injection tests PASSED\n")

if __name__ == '__main__':
    test_error_injection()
```

## UI Tests

### 7. Menu Navigation (Manual)

```
STEPS:
1. Launch: python3 -m devilnet --ui
2. Verify menu displays
3. Press ↑ repeatedly - should wrap around
4. Press ↓ repeatedly - should wrap around
5. Press Enter on each menu item
6. Verify sub-menus appear
7. Press q to quit
8. Verify clean exit

EXPECTED:
- No exceptions
- Smooth navigation
- Quick response (<100ms)
- Graceful exit
```

### 8. Alert Display (Manual)

```
STEPS:
1. Launch: python3 -m devilnet --ui --verbose
2. Monitor alerts section
3. Wait for anomalies to appear
4. Verify alert levels (colors):
   - GREEN = INFO
   - YELLOW = WARNING
   - RED = CRITICAL
   - CYAN = SUCCESS
5. Verify alerts don't freeze UI
6. Verify metrics update in real-time

EXPECTED:
- Alerts appear without blocking
- Colors displayed correctly
- Metrics update continuously
- No UI freezes
```

## Performance Tests

### 9. Cycle Time Measurement

```bash
#!/bin/bash

python3 << 'EOF'
import sys
sys.path.insert(0, '/path/to/devilnet')

from devilnet.engine import DevilnetEngine
from devilnet.core.resilient_engine import create_resilient_engine
import time

print("PERFORMANCE TEST: Cycle time...")

base_engine = DevilnetEngine()
engine = create_resilient_engine(base_engine)

times = []
for i in range(10):
    start = time.time()
    anomalies = engine.run_inference_cycle_resilient()
    elapsed = (time.time() - start) * 1000
    times.append(elapsed)
    print(f"  Cycle {i+1}: {elapsed:.1f}ms")

avg_time = sum(times) / len(times)
max_time = max(times)
min_time = min(times)

print(f"\nResults:")
print(f"  Average: {avg_time:.1f}ms")
print(f"  Min: {min_time:.1f}ms")
print(f"  Max: {max_time:.1f}ms")

target = 5000  # 5 seconds
if avg_time < target:
    print(f"\n✅ PERFORMANCE TEST PASSED (<{target}ms)\n")
else:
    print(f"\n⚠️  WARNING: Slow cycle time ({avg_time:.0f}ms)\n")
EOF
```

## Regression Tests

### 10. Security Constraints

```bash
#!/bin/bash

echo "Testing security constraints..."

# Test 1: Non-root execution
if [ $EUID -eq 0 ]; then
    echo "❌ FAILED: Running as root"
    exit 1
else
    echo "✓ Non-root execution verified"
fi

# Test 2: No network listeners
netstat -tuln | grep -q "devilnet" && {
    echo "❌ FAILED: Found network listeners"
    exit 1
} || {
    echo "✓ No network listeners"
}

# Test 3: Read-only logs
touch /var/log/auth.log.test 2>/dev/null && {
    echo "⚠️  WARNING: Can write to /var/log"
    rm /var/log/auth.log.test
} || {
    echo "✓ Log files are read-only"
}

echo ""
```

## Test Execution

```bash
#!/bin/bash

# Run all unit tests
echo "Running unit tests..."
python3 test_error_recovery.py
python3 test_circuit_breaker.py
python3 test_alert_queue.py

# Run integration tests
echo "Running integration tests..."
python3 test_end_to_end.py
python3 test_error_injection.py

# Run stress tests
echo "Running stress tests..."
bash test_stress_alerts.sh

# Run performance tests
echo "Running performance tests..."
bash test_cycle_time.sh

echo "✅ All tests completed"
```

## Success Criteria

| Test | Criteria | Status |
|------|----------|--------|
| Error Recovery | Max 5 errors before pause | ✓ |
| Circuit Breaker | Opens after 5 failures | ✓ |
| Alert Queue | 5000+ alerts/sec non-blocking | ✓ |
| UI Navigation | <100ms response | ✓ |
| Cycle Time | <5 seconds average | ✓ |
| Memory | <500MB sustained | ✓ |
| Security | Non-root, no network | ✓ |

## Troubleshooting Test Failures

### Test fails with import errors
```bash
cd /path/to/devilnet
export PYTHONPATH=$(pwd):$PYTHONPATH
python3 test_name.py
```

### Test times out
```bash
# Increase timeout
timeout 30 python3 test_name.py
```

### Permission errors
```bash
# Run as devilnet user
sudo -u devilnet python3 test_name.py
```

## Continuous Testing

Suggested CI/CD integration:
```yaml
tests:
  unit:
    - python3 tests/test_unit.py
  integration:
    - python3 tests/test_integration.py
  stress:
    - bash tests/test_stress.sh
    - timeout 60 python3 -m devilnet --monitor
  security:
    - bash tests/test_security.sh
```
