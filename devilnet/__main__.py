#!/usr/bin/env python3
"""
Devilnet Main Entry Point - Interactive Mode with Non-Blocking Alerts

Supports multiple operational modes:
- --ui: Interactive terminal dashboard (recommended)
- --demo: Run demonstration with simulated attacks
- --train: Train ML model on baseline logs
- --once: Single detection cycle
- --monitor: Continuous monitoring (background mode)
"""

import sys
import os
import argparse
import logging
from pathlib import Path
from typing import Optional

# Ensure we're running as non-root
if os.getuid() == 0:
    print("ERROR: This engine must NOT run as root")
    print("Create a dedicated user and run as that user:")
    print("  sudo useradd -r -s /bin/false devilnet")
    print("  sudo -u devilnet python3 -m devilnet")
    sys.exit(1)

# Setup logging before imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/devilnet/devilnet.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def initialize_environment():
    """Validate and initialize runtime environment"""
    try:
        # Check Python version
        if sys.version_info < (3, 7):
            print("ERROR: Python 3.7+ required")
            sys.exit(1)
        
        # Create required directories
        required_dirs = [
            '/var/log/devilnet/reports',
            '/var/log/devilnet/alerts',
            '/var/lib/devilnet',
        ]
        
        for dir_path in required_dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True, mode=0o755)
        
        logger.info("Environment initialized successfully")
        return True
    
    except Exception as e:
        logger.error(f"Environment initialization failed: {e}")
        return False


def run_interactive_ui():
    """Run interactive terminal UI"""
    try:
        from devilnet.engine import DevilnetEngine
        from devilnet.core.resilient_engine import create_resilient_engine
        from devilnet.ui.terminal_ui import run_interactive_ui as start_ui
        
        logger.info("Initializing Devilnet Engine...")
        base_engine = DevilnetEngine()
        
        logger.info("Creating resilient engine wrapper...")
        engine = create_resilient_engine(base_engine)
        
        logger.info("Starting interactive UI...")
        start_ui(engine)
    
    except Exception as e:
        logger.error(f"UI initialization failed: {e}", exc_info=True)
        print(f"\nERROR: {e}\n")
        sys.exit(1)


def run_demo_mode():
    """Run demonstration with simulated attacks"""
    try:
        from examples.demo_scenarios import run_demo
        logger.info("Running Devilnet demonstration...")
        run_demo()
    
    except Exception as e:
        logger.error(f"Demo execution failed: {e}", exc_info=True)
        sys.exit(1)


def run_training():
    """Train ML model on baseline logs"""
    try:
        from devilnet.engine import DevilnetEngine
        logger.info("Initializing engine for training...")
        engine = DevilnetEngine()
        
        logger.info("Starting ML model training...")
        engine.ml_pipeline.train()
        
        logger.info("Training completed successfully")
    
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        sys.exit(1)


def run_single_cycle():
    """Execute single detection cycle"""
    try:
        from devilnet.engine import DevilnetEngine
        from devilnet.core.resilient_engine import create_resilient_engine
        
        logger.info("Initializing engine...")
        base_engine = DevilnetEngine()
        engine = create_resilient_engine(base_engine)
        
        logger.info("Running single inference cycle...")
        anomalies = engine.run_inference_cycle_resilient()
        
        if anomalies:
            logger.info(f"Detected {len(anomalies)} anomalies")
            for anomaly in anomalies:
                logger.info(
                    f"  - {anomaly.event_type} ({anomaly.risk_level}): "
                    f"{anomaly.source_ip or 'unknown'} -> "
                    f"{anomaly.username or 'unknown'}"
                )
        else:
            logger.info("No anomalies detected")
    
    except Exception as e:
        logger.error(f"Cycle execution failed: {e}", exc_info=True)
        sys.exit(1)


def run_continuous_monitoring():
    """Run continuous monitoring (headless)"""
    try:
        from devilnet.engine import DevilnetEngine
        from devilnet.core.resilient_engine import create_resilient_engine, SignalHandler
        import time
        
        logger.info("Initializing engine for continuous monitoring...")
        base_engine = DevilnetEngine()
        engine = create_resilient_engine(base_engine)
        signal_handler = SignalHandler()
        
        logger.info("Starting continuous monitoring (press Ctrl+C to stop)...")
        cycle_count = 0
        
        while signal_handler.running:
            try:
                cycle_count += 1
                anomalies = engine.run_inference_cycle_resilient()
                
                if cycle_count % 10 == 0:  # Log stats every 10 cycles
                    stats = engine.get_stats()
                    logger.info(
                        f"Stats - Cycles: {stats['cycles_completed']}, "
                        f"Anomalies: {stats['anomalies_detected']}, "
                        f"Success Rate: {stats['success_rate']:.1%}, "
                        f"Uptime: {stats['uptime_seconds']}s"
                    )
                
                time.sleep(5)  # Poll every 5 seconds
            
            except KeyboardInterrupt:
                logger.info("Monitoring interrupted by user")
                break
            except Exception as e:
                logger.error(f"Cycle error (continuing): {e}")
                time.sleep(2)  # Backoff on error
        
        logger.info("Continuous monitoring completed")
        stats = engine.get_stats()
        logger.info(f"Final stats: {stats}")
    
    except Exception as e:
        logger.error(f"Continuous monitoring failed: {e}", exc_info=True)
        sys.exit(1)


def print_status():
    """Print system status"""
    try:
        from pathlib import Path
        from devilnet.core.config import DevilnetConfig
        import json
        
        print("\n" + "="*60)
        print("DEVILNET STATUS")
        print("="*60)
        
        # Configuration status
        config_path = Path("/etc/devilnet/devilnet.json")
        if config_path.exists():
            print("\n✓ Configuration: Found")
            config = DevilnetConfig.from_json(str(config_path))
            print(f"  - Feature thresholds: Loaded")
            print(f"  - Alert levels: Loaded")
        else:
            print("\n✗ Configuration: Not found at /etc/devilnet/devilnet.json")
        
        # Log files status
        log_paths = [
            "/var/log/auth.log",
            "/var/log/syslog",
            "/var/log/audit/audit.log",
        ]
        
        print("\n Log Files:")
        for log_path in log_paths:
            path = Path(log_path)
            if path.exists():
                size_mb = path.stat().st_size / (1024*1024)
                print(f"  ✓ {log_path} ({size_mb:.1f}MB)")
            else:
                print(f"  - {log_path} (not available)")
        
        # Model status
        model_path = Path("/var/lib/devilnet/model.pkl")
        if model_path.exists():
            size_mb = model_path.stat().st_size / (1024*1024)
            print(f"\n✓ ML Model: Trained ({size_mb:.2f}MB)")
        else:
            print("\n✗ ML Model: Not trained. Run: devilnet --train")
        
        # Reports status
        reports_dir = Path("/var/log/devilnet/reports")
        if reports_dir.exists():
            report_count = len(list(reports_dir.glob("INC-*.json")))
            print(f"\n✓ Reports: {report_count} incidents documented")
        else:
            print("\n✗ Reports directory: Not found")
        
        print("\n" + "="*60 + "\n")
    
    except Exception as e:
        print(f"Status check failed: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Devilnet - Blue Team ML Anomaly Detection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
USAGE EXAMPLES:
  # Interactive dashboard (recommended)
  %(prog)s --ui
  
  # Demonstration with simulated attacks
  %(prog)s --demo
  
  # Train ML model on baseline logs
  %(prog)s --train
  
  # Single detection cycle
  %(prog)s --once
  
  # Continuous monitoring (background)
  %(prog)s --monitor
  
  # Check system status
  %(prog)s --status

KEYBOARD SHORTCUTS (Interactive Mode):
  ↑↓         Navigate menu
  Enter      Select option
  q          Quit application
  Ctrl+C     Emergency exit

For documentation: see README.md, REFERENCE.md, HARDENING_GUIDE.md
        '''
    )
    
    mode_group = parser.add_mutually_exclusive_group(required=False)
    mode_group.add_argument(
        '--ui',
        action='store_true',
        help='Run interactive terminal UI (default, recommended)'
    )
    mode_group.add_argument(
        '--demo',
        action='store_true',
        help='Run demonstration with simulated attacks'
    )
    mode_group.add_argument(
        '--train',
        action='store_true',
        help='Train ML model on baseline logs'
    )
    mode_group.add_argument(
        '--once',
        action='store_true',
        help='Run single detection cycle and exit'
    )
    mode_group.add_argument(
        '--monitor',
        action='store_true',
        help='Continuous monitoring mode (headless)'
    )
    mode_group.add_argument(
        '--status',
        action='store_true',
        help='Print system status and requirements'
    )
    
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize environment
    if not initialize_environment():
        sys.exit(1)
    
    # Determine mode (default to UI)
    if args.status:
        print_status()
    elif args.demo:
        run_demo_mode()
    elif args.train:
        run_training()
    elif args.once:
        run_single_cycle()
    elif args.monitor:
        run_continuous_monitoring()
    else:  # Default to UI
        run_interactive_ui()
    
    parser.add_argument(
        '--once',
        action='store_true',
        help='Run inference cycle once and exit (default: continuous)'
    )
    
    parser.add_argument(
        '--train',
        type=str,
        help='Train model on baseline data (JSONL file path) and exit'
    )
    
    parser.add_argument(
        '--demo',
        action='store_true',
        help='Run demonstration with simulated attack scenarios'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='Print engine status and exit'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Demo mode
        if args.demo:
            logger.info("Running demonstration mode...")
            from examples.demo_scenarios import demonstrate_detection, generate_example_report
            demonstrate_detection()
            generate_example_report()
            return 0
        
        # Load configuration
        try:
            config = DevilnetConfig.load_from_file(args.config)
            logger.info(f"Configuration loaded from {args.config}")
        except FileNotFoundError:
            logger.warning(f"Config not found at {args.config}, using defaults")
            config = None
        
        # Create engine
        engine = create_engine(args.config)
        
        # Status mode
        if args.status:
            engine.print_status()
            return 0
        
        # Training mode
        if args.train:
            logger.info(f"Training model on {args.train}")
            engine.train_on_baseline(args.train)
            logger.info("Training completed")
            return 0
        
        # Inference modes
        engine.print_status()
        
        if args.once:
            logger.info("Running single inference cycle...")
            anomalies = engine.run_inference_cycle()
            logger.info(f"Cycle complete: {len(anomalies)} anomalies detected")
            return 0
        else:
            logger.info("Starting continuous inference loop (Ctrl+C to stop)...")
            import time
            cycle = 0
            try:
                while True:
                    cycle += 1
                    logger.debug(f"Inference cycle {cycle}")
                    anomalies = engine.run_inference_cycle()
                    
                    if anomalies:
                        logger.warning(f"Cycle {cycle}: {len(anomalies)} anomalies detected")
                    
                    # Wait for next cycle
                    time.sleep(5)  # Poll interval from config
            
            except KeyboardInterrupt:
                logger.info("Shutting down gracefully...")
                return 0
    
    except Exception as e:
        logger.error(f"Engine failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
