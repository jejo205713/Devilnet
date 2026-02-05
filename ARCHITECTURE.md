# Devilnet System Architecture - Version 2.0

## High-Level System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DEVILNET 2.0 ARCHITECTURE                   │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                      │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Interactive Terminal UI (Curses)               │ │
│  │  - Menu Navigation (↑↓ Enter)                          │ │
│  │  - Real-time Metrics Display                           │ │
│  │  - Color-Coded Alerts                                  │ │
│  │  - Non-Blocking Input (100ms timeout)                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                   │
│  ┌────────────────────────────────────────────────────────┐ │
│  │            Terminal Renderer (Curses Wrapper)          │ │
│  │  - Header (Title, Status)                              │ │
│  │  - Menu Section (Current Selection)                    │ │
│  │  - Alerts Section (Recent 5 Alerts)                    │ │
│  │  - Metrics Section (Live Stats)                        │ │
│  │  - Footer (Help, Clock)                                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                 CONCURRENCY & THREADING LAYER                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐               │
│  │  UI Main Thread  │  │ Monitoring Thread │ (Daemon)      │
│  │  - Input polling │→→→│ - Run inference  │               │
│  │  - Rendering     │   │ - Error recovery │               │
│  │  - Menu logic    │   │ - Max 5 errors   │               │
│  └──────────────────┘   └────────┬─────────┘               │
│                                   ↓                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │        Alert Handler Thread (Daemon)                │   │
│  │  - Get from AlertQueue                              │   │
│  │  - Process alerts (non-blocking)                    │   │
│  │  - Update UI display                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Thread-Safe Data Structures                  │  │
│  │  - AlertQueue (maxsize=1000, FIFO)                   │  │
│  │  - Metrics Lock (for stats updates)                  │  │
│  │  - Error Counter Lock (per component)                │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│            RESILIENCE & ERROR RECOVERY LAYER                 │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         ErrorRecoveryManager                           │ │
│  │  - Track errors per component                         │ │
│  │  - Max 3 retries per component                        │ │
│  │  - Exponential backoff (2.0x multiplier)             │ │
│  │  - Reset on success                                   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         CircuitBreaker Pattern                        │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │ │
│  │  │   CLOSED     │→→│    OPEN      │→→│ HALF-OPEN │  │ │
│  │  │  (Normal)    │  │ (Blocking)   │  │ (Testing) │  │ │
│  │  └──────────────┘  └──────────────┘  └────────────┘  │ │
│  │  - Threshold: 5 consecutive failures                  │ │
│  │  - Timeout: 60 seconds                                │ │
│  │  - Per-component isolation                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         ResilientDevilnetEngine                        │ │
│  │  - Wraps base engine with error handling              │ │
│  │  - run_inference_cycle_resilient()                    │ │
│  │    • Never raises exceptions                          │ │
│  │    • Returns [] on errors                             │ │
│  │    • Recovers gracefully                              │ │
│  │  - get_stats() for visibility                         │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│            PERFORMANCE MONITORING LAYER                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         PerformanceMonitor                             │ │
│  │  - Track latency per component                        │ │
│  │  - Record success/failure                             │ │
│  │  - Calculate min/max/avg times                        │ │
│  │  - Store up to 10K metrics                            │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         OptimizationRecommender                        │ │
│  │  - Analyze error rates                                │ │
│  │  - Identify slow components                           │ │
│  │  - Suggest optimizations                              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         TimerContext (Measurement)                    │ │
│  │  - Easy operation profiling                           │ │
│  │  - Automatic exception handling                       │ │
│  │  - Records all metrics                                │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                  ML/DETECTION ENGINE LAYER                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         DevilnetEngine (Unchanged)                    │ │
│  │  - Ingestion Pipeline                                │ │
│  │  - Feature Extraction (14-dim vectors)               │ │
│  │  - ML Inference (Isolation Forest)                   │ │
│  │  - MITRE Mapping                                     │ │
│  │  - Incident Response (Dry-run mode)                 │ │
│  │  - Report Generation                                 │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  COMPONENTS (All unchanged from v1.0):                       │
│  ├─ Log Parsing (auth.log, syslog, auditd)                 │
│  ├─ Feature Extraction (per-IP/user/session)              │
│  ├─ ML Pipeline (Isolation Forest training/inference)     │
│  ├─ MITRE Mapping (15+ techniques)                        │
│  ├─ Incident Response (lock, block, terminate)            │
│  └─ Report Generation (JSON, human-readable, JSONL)       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                  DATA & PERSISTENCE LAYER                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  INPUT:                           OUTPUT:                   │
│  ├─ /var/log/auth.log      →→→  ├─ /var/log/devilnet/*.log │
│  ├─ /var/log/syslog        →→→  ├─ /var/lib/devilnet/model │
│  ├─ /var/log/audit/audit   →→→  ├─ Reports: INC-*.json/.txt│
│  └─ /var/log/fail2ban      →→→  └─ Alerts: stream.jsonl    │
│                                                              │
│  All access is READ-ONLY for logs (enforced by security)    │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Threading Model Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                      THREADING LAYOUT                          │
└────────────────────────────────────────────────────────────────┘

TIMELINE SHOWING NON-BLOCKING BEHAVIOR:

Time:    0ms         100ms       200ms       300ms       400ms
         │           │           │           │           │
Main UI: ├─input─┬───render──┬───input───┬───render──┬───input
         │       │           │           │           │
Alert:   │       │ ALERT_NEW!│ ALERT_NEW!│           │ ALERT_NEW!
Handler: │       │ (queued)  │(displayed)│           │ (displayed)
         │       │           │           │           │
Monitor: ├─infer─(still running in bg, error recovery active)
         │       │           │           │           │
                  KEY: UI never waits, alerts processed async

WITHOUT OUR CHANGES (BLOCKING):
┌───────────────────────────────────────────────────────────┐
│ Time:    0ms         100ms       200ms       300ms        │
│          │           │           │           │            │
│ UI:      ├─input────BLOCKED────────────────BLOCKED       │
│          │           │           │           │            │
│ Alert:   │           └─generating(200ms)─────┘            │
│          │                                                 │
│ User Experience: FROZEN FOR 200ms DURING ALERT PROCESSING │
└───────────────────────────────────────────────────────────┘

WITH OUR CHANGES (NON-BLOCKING):
┌───────────────────────────────────────────────────────────┐
│ Time:    0ms         100ms       200ms       300ms        │
│          │           │           │           │            │
│ UI:      ├─input─┬───render──┬───input───┬───render     │
│ (Main):  │       │           │           │                │
│                                                            │
│ Alert    │       ├─processing──┤ (bg thread)             │
│ Handler: │                                                │
│                                                            │
│ Monitor  ├─(background inference, never blocks UI)       │
│ (Bg):    │                                                │
│                                                            │
│ User Experience: SMOOTH - No blocking                     │
└───────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                               │
└────────────────────────────────────────────────────────────────┘

LOG FILES
   │
   ├─→ LogTailer (read-only incremental)
   │
   └─→ AuthEventParser
        │
        └─→ Events (5-min batches)
            │
            ├─→ FeatureExtractor
            │   │
            │   └─→ FeatureVectors (14-dim)
            │       │
            │       └─→ MLPipeline (Isolation Forest)
            │           │
            │           └─→ AnomalyScores (0-1)
            │               │
            │               ├─→ MITRE Mapper
            │               │   │
            │               │   └─→ TechniqueList
            │               │
            │               └─→ ResponseDecisionEngine
            │                   │
            │                   ├─→ IncidentReportGenerator
            │                   │   │
            │                   │   └─→ IncidentReport
            │                   │       │
            │                   │       ├─→ JSON Report
            │                   │       ├─→ Text Report
            │                   │       └─→ JSONL Stream
            │                   │
            │                   └─→ UI AlertQueue
            │                       │
            │                       └─→ Terminal Display

ERROR HANDLING FLOW:
            
            Event ──error──→ ErrorRecoveryManager
                               │
                            record_error()
                               │
                          ┌─────┴─────┐
                          │           │
                      <5 errors   ≥5 errors
                          │           │
                       Continue    GracefulPause
                          │           │
                       Retry       User Alert
                          │           │
                        Backoff    Recovery Timeout
                                      │
                                   Retry
```

## Component Dependency Graph

```
┌────────────────────────────────────────────────────────────────┐
│                    COMPONENT DEPENDENCIES                      │
└────────────────────────────────────────────────────────────────┘

DevilnetEngine (unchanged core)
  │
  ├─ LogIngestionPipeline → LogTailer → AuthEventParser
  │
  ├─ FeatureExtractor → FeatureVector → FeatureVectorBatch
  │
  ├─ MLPipeline → IsolationForestModel → AnomalyDetector
  │
  ├─ MITREMapper → TechniqueSet
  │
  ├─ IncidentResponseEngine → SafeResponseExecutor → CooldownManager
  │
  └─ IncidentReportGenerator → IncidentReport → AlertStream

ResilientDevilnetEngine (new wrapper)
  │
  ├─ ErrorRecoveryManager (tracks errors per component)
  │
  ├─ CircuitBreaker (one per: ingestion, ml, response, reporting)
  │
  └─ DevilnetEngine (wrapped)

TerminalUI (new UI layer)
  │
  ├─ InteractiveUI → Menu → MenuItem
  │
  ├─ TerminalRenderer → curses
  │
  ├─ AlertQueue → threading.Queue
  │
  ├─ MonitoringThread → ResilientDevilnetEngine
  │
  └─ NonBlockingAlertHandler

PerformanceMonitor (new monitoring)
  │
  ├─ PerformanceMetric → ComponentStats
  │
  └─ OptimizationRecommender

SignalHandler (graceful shutdown)
  └─ signal.SIGTERM, signal.SIGINT
```

## Call Flow for Single Cycle

```
┌─────────────────────────────────────────────────────────────────┐
│           SINGLE INFERENCE CYCLE - DETAILED FLOW               │
└─────────────────────────────────────────────────────────────────┘

User calls: anomalies = engine.run_inference_cycle_resilient()

STEP 1: INGESTION (with circuit breaker)
  ├─ circuit_breaker['ingestion'].call(_safe_ingest_logs)
  │  ├─ IF OPEN: raise CircuitBreakerOpen
  │  └─ ELSE:
  │     ├─ call ingestion_pipeline.ingest_all()
  │     └─ get new events from logs
  │        └─ RETURNS: List[AuthEvent]
  │
  └─ error_count reset on success

STEP 2: FEATURE EXTRACTION (with exception handling)
  ├─ _safe_extract_features(events)
  │  ├─ FOR EACH event:
  │  │  ├─ TRY: feature_extractor.extract_features(event)
  │  │  │  └─ RETURNS: FeatureVector (14-dim)
  │  │  └─ EXCEPT: log warning, continue
  │  │
  │  └─ RETURNS: (List[FeatureVector], List[metadata])
  │
  └─ IF empty: return []

STEP 3: ML INFERENCE (with circuit breaker)
  ├─ circuit_breaker['ml_inference'].call(_safe_ml_inference, ...)
  │  ├─ ml_pipeline.infer(feature_vectors, metadata)
  │  │  ├─ Load model (or skip if loaded)
  │  │  ├─ Batch predict on all vectors
  │  │  └─ RETURNS: List[AnomalyScore]
  │  │
  │  └─ error_count reset on success
  │
  └─ IF empty: return []

STEP 4: PROCESS ANOMALIES
  ├─ anomalies = [score for score in anomaly_scores if is_anomaly]
  │
  └─ IF anomalies present:
     └─ FOR EACH anomaly:
        ├─ report_generator.generate_report(anomaly, ...)
        │
        ├─ report_generator.save_report(report, format="both")
        │  ├─ /var/log/devilnet/reports/INC-*.json
        │  └─ /var/log/devilnet/reports/INC-*.txt
        │
        ├─ alert_stream.write_alert(...)
        │  └─ /var/log/devilnet/alerts/stream.jsonl
        │
        ├─ response_decision_engine.determine_response(...)
        │  └─ RETURNS: List[ResponseAction]
        │
        └─ FOR EACH action:
           └─ response_executor.execute_response(action)
              ├─ Dry-run by default
              ├─ Log all actions
              └─ Emit response_actions

STEP 5: ERROR RECOVERY
  ├─ IF ANY step fails:
  │  ├─ recovery_manager.record_error(component)
  │  ├─ circuit_breaker[component]._on_failure()
  │  ├─ calculate backoff = 2^(error_count-1) seconds
  │  │  (max 300 seconds / 5 minutes)
  │  │
  │  └─ IF error_count >= 5:
  │     ├─ circuit_breaker opens
  │     ├─ monitoring thread pauses
  │     └─ UI alerts user: "Component failed max retries"
  │
  └─ ELSE: success_rate increments

STEP 6: RETURN RESULTS
  └─ RETURNS: List[AnomalyScore]
     (empty list on any error - never raises exception)

STEP 7: UPDATE STATS
  └─ stats['cycles_completed'] += 1
     stats['anomalies_detected'] += len(anomalies)
     stats['cycles_failed'] += (1 if had_error else 0)
     stats['errors_recovered'] += (1 if recovered_error else 0)
```

## Operational States

```
┌────────────────────────────────────────────────────────────────┐
│                     SYSTEM STATES                              │
└────────────────────────────────────────────────────────────────┘

ENGINE STATES:
  ├─ IDLE (waiting for input)
  ├─ INFERENCING (running ML cycle)
  ├─ PROCESSING (handling anomalies)
  ├─ PAUSED (error recovery pause)
  └─ SHUTDOWN (graceful exit)

CIRCUIT BREAKER STATES:
  ├─ CLOSED (normal, processing)
  ├─ OPEN (failure threshold exceeded)
  └─ HALF-OPEN (testing recovery)

MONITORING THREAD STATES:
  ├─ RUNNING (continuous cycles)
  ├─ PAUSED (after max errors)
  └─ STOPPED (user quit or signal)

UI STATES:
  ├─ ACTIVE (user interaction)
  ├─ WAITING (for input)
  └─ REFRESHING (screen redraw)

ERROR STATES:
  ├─ RECOVERING (error count < max)
  ├─ PAUSED (error count >= max)
  └─ MONITORING (60s timeout for recovery)

TRANSITIONS:
  IDLE ──→ INFERENCING ──→ PROCESSING ──error──→ PAUSED
           ↑                    ↓                      ↓
           └────success────────┘              recovery_timeout
                                                      ↓
                                                   IDLE (retry)
```

## Bottleneck Analysis

```
┌────────────────────────────────────────────────────────────────┐
│              TYPICAL CYCLE BREAKDOWN (ms)                      │
└────────────────────────────────────────────────────────────────┘

Total Cycle Time: ~100ms

Component Timing:
├─ Log Ingestion:        ~10ms (20 events from auth.log tail)
├─ Feature Extraction:   ~15ms (20 vectors × 0.75ms each)
├─ ML Inference:         ~50ms (batch prediction, Isolation Forest)
├─ Anomaly Processing:   ~20ms (report generation, mapping)
├─ UI Alert Queueing:    ~1ms (non-blocking queue operation)
└─ Overhead (GC, etc):   ~4ms

Typical Anomaly Cycle (with 5 anomalies):
├─ Same as above         ~100ms
├─ Report Generation:    ~50ms (×5 anomalies = 250ms)
├─ Response Actions:     ~20ms (lookup, no execution)
└─ Total                 ~150ms

Worst Case (with errors):
├─ Ingestion error:      → backoff 2s, retry cycle
├─ ML inference error:   → circuit opens after 5 retries
└─ All retry logic:      exponential backoff (max 5 minutes)
```

## Security Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                   SECURITY BOUNDARIES                          │
└────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    USER CONTEXT (devilnet)                 │
│  - Running as: devilnet (non-root)                         │
│  - UID: 1000+                                               │
│  - Groups: adm (for log access)                            │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │      APPARMOR/SELINUX SANDBOX                       │  │
│  │                                                      │  │
│  │  ALLOW:                                              │  │
│  │  ├─ Read: /var/log/, /etc/devilnet/                │  │
│  │  ├─ Write: /var/lib/devilnet/, /var/log/devilnet/ │  │
│  │  ├─ Capability: net_admin (blocked)                 │  │
│  │  └─ Exec: python3 only (no shell)                  │  │
│  │                                                      │  │
│  │  DENY:                                               │  │
│  │  ├─ Network: All (no bind, connect, recv, send)    │  │
│  │  ├─ Signals: ptrace, kill (safe)                   │  │
│  │  ├─ Exec: shell, eval, dynamic code                │  │
│  │  └─ Write to system files                           │  │
│  │                                                      │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
│  ISOLATION:                                                 │
│  ├─ No root escalation                                     │
│  ├─ No capability escalation                               │
│  ├─ No network exposure                                    │
│  ├─ No shell spawning                                      │
│  └─ No untrusted code execution                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘

THREAT MODEL:
├─ CANNOT attack host system (confined by AppArmor/SELinux)
├─ CANNOT exfiltrate data (no network)
├─ CANNOT escalate privileges (uid = devilnet)
├─ CANNOT read beyond /var/log (adm group only)
└─ CANNOT modify logs (read-only mode enforced)

AUDIT:
├─ All detections logged to /var/log/devilnet/alerts/stream.jsonl
├─ All responses logged with reversal commands
├─ Dry-run mode by default (no real actions)
└─ All errors logged (never hidden)
```

---

This architecture ensures:
✅ **Non-blocking** - All operations async where possible
✅ **Resilient** - Graceful error recovery
✅ **Observable** - Real-time metrics and visibility
✅ **Secure** - Sandboxed, non-root, read-only
✅ **Testable** - Modular components
✅ **Maintainable** - Clear separation of concerns
