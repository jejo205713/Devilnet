"""
Comprehensive Testing & Validation Suite

Tests detection pipeline, ML model, incident response, and security constraints.
"""

import unittest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

# Test data generators
def create_normal_auth_event(timestamp=None):
    """Create a normal authentication event"""
    from devilnet.ingestion.log_parser import AuthEvent
    return AuthEvent(
        timestamp=(timestamp or datetime.now()).isoformat(),
        host='webserver',
        source_ip='192.168.1.100',
        source_port=22000,
        username='alice',
        auth_method='publickey',
        event_type='login_success',
        service='sshd',
        message='Accepted publickey for alice from 192.168.1.100',
        raw_line='...',
    )


def create_brute_force_event(ip='203.0.113.99', timestamp=None):
    """Create a brute force attack event"""
    from devilnet.ingestion.log_parser import AuthEvent
    return AuthEvent(
        timestamp=(timestamp or datetime.now()).isoformat(),
        host='webserver',
        source_ip=ip,
        source_port=50000,
        username='admin',
        auth_method='password',
        event_type='login_failed',
        service='sshd',
        message=f'Failed password for admin from {ip}',
        raw_line='...',
    )


class TestLogParsing(unittest.TestCase):
    """Test log parsing and event extraction"""
    
    def test_parse_ssh_failed_login(self):
        """Test SSH failed login parsing"""
        from devilnet.ingestion.log_parser import LogParser
        
        line = 'Jan 15 14:32:10 server sshd[1234]: Failed password for root from 203.0.113.99 port 54321 ssh2'
        event = LogParser.parse_auth_log_line(line)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, 'login_failed')
        self.assertEqual(event.source_ip, '203.0.113.99')
        self.assertEqual(event.username, 'root')
    
    def test_parse_ssh_successful_login(self):
        """Test SSH successful login parsing"""
        from devilnet.ingestion.log_parser import LogParser
        
        line = 'Jan 15 14:32:10 server sshd[1234]: Accepted publickey for alice from 192.168.1.100 port 22000 ssh2'
        event = LogParser.parse_auth_log_line(line)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, 'login_success')
        self.assertEqual(event.auth_method, 'publickey')
    
    def test_parse_sudo_success(self):
        """Test sudo command parsing"""
        from devilnet.ingestion.log_parser import LogParser
        
        line = 'Jan 15 14:32:10 server sudo: alice : TTY=pts/0 ; PWD=/home/alice ; USER=root ; COMMAND=/bin/systemctl restart nginx'
        event = LogParser.parse_auth_log_line(line)
        
        self.assertIsNotNone(event)
        self.assertIn('sudo', event.event_type)


class TestFeatureExtraction(unittest.TestCase):
    """Test feature engineering"""
    
    def test_extract_features(self):
        """Test basic feature extraction"""
        from devilnet.ml.feature_extraction import FeatureExtractor
        
        extractor = FeatureExtractor()
        event = create_normal_auth_event()
        vector = extractor.extract_features(event)
        
        self.assertIsNotNone(vector)
        self.assertEqual(vector.username, 'alice')
        self.assertEqual(vector.source_ip, '192.168.1.100')
    
    def test_per_ip_features(self):
        """Test per-IP feature aggregation"""
        from devilnet.ml.feature_extraction import FeatureExtractor
        
        extractor = FeatureExtractor()
        ip = '203.0.113.99'
        
        # Simulate 10 failed attempts from same IP
        for i in range(10):
            event = create_brute_force_event(ip=ip, timestamp=datetime.now() - timedelta(seconds=i*10))
            vector = extractor.extract_features(event)
        
        # Last vector should show aggregated features
        self.assertGreater(vector.ip_failed_logins, 0)
    
    def test_user_new_ip_detection(self):
        """Test detection of login from new IP"""
        from devilnet.ml.feature_extraction import FeatureExtractor
        
        extractor = FeatureExtractor()
        
        # First login from IP1
        event1 = create_normal_auth_event()
        event1.source_ip = '192.168.1.100'
        event1.username = 'bob'
        vector1 = extractor.extract_features(event1)
        
        # Second login from different IP
        event2 = create_normal_auth_event()
        event2.source_ip = '198.51.100.45'
        event2.username = 'bob'
        vector2 = extractor.extract_features(event2)
        
        # Should detect new IP
        self.assertTrue(vector2.user_new_ip_detected)


class TestMLPipeline(unittest.TestCase):
    """Test machine learning pipeline"""
    
    def test_model_training(self):
        """Test model training on normal data"""
        from devilnet.ml.pipeline import MLPipeline
        from devilnet.ml.feature_extraction import FeatureExtractor
        
        # Generate baseline vectors
        extractor = FeatureExtractor()
        vectors = []
        for i in range(100):
            event = create_normal_auth_event(timestamp=datetime.now() - timedelta(hours=i))
            vector = extractor.extract_features(event)
            vectors.append(vector)
        
        # Train model
        pipeline = MLPipeline()
        pipeline.train_from_baseline(vectors)
        
        self.assertTrue(pipeline.is_trained)
    
    def test_anomaly_detection(self):
        """Test anomaly detection on attack data"""
        from devilnet.ml.pipeline import MLPipeline
        from devilnet.ml.feature_extraction import FeatureExtractor
        
        # Train on normal data
        extractor = FeatureExtractor()
        baseline_vectors = []
        for i in range(100):
            event = create_normal_auth_event(timestamp=datetime.now() - timedelta(hours=i))
            vector = extractor.extract_features(event)
            baseline_vectors.append(vector)
        
        pipeline = MLPipeline()
        pipeline.train_from_baseline(baseline_vectors)
        
        # Test with attack data
        attack_vectors = []
        metadata = []
        for i in range(10):
            event = create_brute_force_event()
            vector = extractor.extract_features(event)
            attack_vectors.append(vector)
            metadata.append({
                'event_id': vector.event_id,
                'timestamp': vector.timestamp,
                'source_ip': vector.source_ip,
                'username': vector.username,
                'event_type': vector.event_type,
            })
        
        # Inference should detect anomalies
        anomalies = pipeline.infer(attack_vectors, metadata)
        
        # Some should be anomalous
        is_anomalous = [a.is_anomaly for a in anomalies]
        self.assertTrue(any(is_anomalous))


class TestMitreMapping(unittest.TestCase):
    """Test MITRE ATT&CK mapping"""
    
    def test_brute_force_mapping(self):
        """Test brute force technique mapping"""
        from devilnet.core.mitre_mapping import MitreATTACKMapping
        
        techniques = MitreATTACKMapping.get_techniques_for_event(
            'login_failed',
            {'ip_failed_logins': 10, 'ip_unique_users_attempted': 5}
        )
        
        technique_ids = [t.technique_id for t in techniques]
        self.assertIn('T1110', technique_ids)
    
    def test_privilege_escalation_mapping(self):
        """Test privilege escalation technique mapping"""
        from devilnet.core.mitre_mapping import MitreATTACKMapping
        
        techniques = MitreATTACKMapping.get_techniques_for_event(
            'sudo_success',
            {}
        )
        
        technique_ids = [t.technique_id for t in techniques]
        self.assertIn('T1548', technique_ids)
    
    def test_get_specific_technique(self):
        """Test retrieving specific technique"""
        from devilnet.core.mitre_mapping import MitreATTACKMapping
        
        technique = MitreATTACKMapping.get_technique('T1110')
        
        self.assertIsNotNone(technique)
        self.assertEqual(technique.name, 'Brute Force')


class TestIncidentResponse(unittest.TestCase):
    """Test incident response system"""
    
    def test_response_decision_engine(self):
        """Test response action determination"""
        from devilnet.response.incident_response import ResponseDecisionEngine
        
        engine = ResponseDecisionEngine()
        
        actions = engine.determine_response(
            risk_level='HIGH',
            event_type='login_failed',
            anomaly_score=0.85,
            source_ip='203.0.113.99',
            username='admin',
        )
        
        # Should generate response actions
        self.assertGreater(len(actions), 0)
    
    def test_cooldown_manager(self):
        """Test cooldown policy enforcement"""
        from devilnet.response.incident_response import CooldownManager, ResponseAction
        
        manager = CooldownManager()
        
        # First action should be allowed
        should_allow = manager.should_allow_action(
            ResponseAction.LOCK_ACCOUNT,
            'alice',
            cooldown_seconds=10
        )
        self.assertTrue(should_allow)
        
        # Record it
        manager.record_action(ResponseAction.LOCK_ACCOUNT, 'alice')
        
        # Immediate second attempt should be blocked
        should_allow = manager.should_allow_action(
            ResponseAction.LOCK_ACCOUNT,
            'alice',
            cooldown_seconds=10
        )
        self.assertFalse(should_allow)


class TestReporting(unittest.TestCase):
    """Test report generation"""
    
    def test_incident_report_generation(self):
        """Test incident report creation"""
        from devilnet.reporting.reporter import IncidentReportGenerator
        
        generator = IncidentReportGenerator()
        
        class MockAnomaly:
            anomaly_score = 0.85
            risk_level = "HIGH"
            confidence = 0.92
            explanation = "Test anomaly"
            contributing_features = {'ip_failed_logins': 0.95}
        
        report = generator.generate_report(
            anomaly_score=MockAnomaly(),
            event_type='login_failed',
            source_ip='203.0.113.99',
            username='admin',
            feature_vector=None,
        )
        
        self.assertIsNotNone(report)
        self.assertEqual(report.severity, 'HIGH')
        self.assertIn('203.0.113.99', report.source_ip)
    
    def test_report_json_output(self):
        """Test JSON report output"""
        from devilnet.reporting.reporter import IncidentReportGenerator
        
        generator = IncidentReportGenerator()
        
        class MockAnomaly:
            anomaly_score = 0.85
            risk_level = "HIGH"
            confidence = 0.92
            explanation = "Test"
            contributing_features = {}
        
        report = generator.generate_report(
            anomaly_score=MockAnomaly(),
            event_type='login_failed',
            source_ip='203.0.113.99',
            username='admin',
            feature_vector=None,
        )
        
        json_str = report.to_json()
        data = json.loads(json_str)
        
        self.assertIn('incident_id', data)
        self.assertEqual(data['severity'], 'HIGH')


class TestSecurityConstraints(unittest.TestCase):
    """Test security framework constraints"""
    
    def test_non_root_requirement(self):
        """Test that engine requires non-root"""
        import os
        
        # This should run as non-root
        current_uid = os.getuid()
        
        # We can't directly test root check, but verify we're not root
        # (tests should run as user, not root)
        if current_uid == 0:
            self.skipTest("Tests should not run as root")
    
    def test_config_loading(self):
        """Test security configuration"""
        from devilnet.core.config import get_default_config
        
        config = get_default_config()
        
        # Verify security policies are set
        self.assertTrue(config.security_policy.enforce_non_root)
        self.assertFalse(config.security_policy.allow_network)
        self.assertFalse(config.security_policy.allow_eval)
        self.assertFalse(config.security_policy.allow_shell_exec)


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLogParsing))
    suite.addTests(loader.loadTestsFromTestCase(TestFeatureExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestMLPipeline))
    suite.addTests(loader.loadTestsFromTestCase(TestMitreMapping))
    suite.addTests(loader.loadTestsFromTestCase(TestIncidentResponse))
    suite.addTests(loader.loadTestsFromTestCase(TestReporting))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurityConstraints))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
