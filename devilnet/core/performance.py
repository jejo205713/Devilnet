"""
Performance Monitoring and Optimization

Tracks metrics and identifies bottlenecks for efficiency improvements.
"""

import time
import threading
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance measurement"""
    component: str
    operation: str
    duration_ms: float
    timestamp: datetime = field(default_factory=datetime.now)
    success: bool = True
    error_msg: Optional[str] = None


@dataclass
class ComponentStats:
    """Aggregated statistics for a component"""
    component: str
    total_calls: int = 0
    total_time_ms: float = 0.0
    min_time_ms: float = float('inf')
    max_time_ms: float = 0.0
    avg_time_ms: float = 0.0
    errors: int = 0
    success_rate: float = 1.0
    
    def update(self, metric: PerformanceMetric) -> None:
        """Update stats with new metric"""
        self.total_calls += 1
        self.total_time_ms += metric.duration_ms
        self.min_time_ms = min(self.min_time_ms, metric.duration_ms)
        self.max_time_ms = max(self.max_time_ms, metric.duration_ms)
        self.avg_time_ms = self.total_time_ms / self.total_calls
        
        if not metric.success:
            self.errors += 1
        
        if self.total_calls > 0:
            self.success_rate = (self.total_calls - self.errors) / self.total_calls


class PerformanceMonitor:
    """Tracks system performance metrics"""
    
    def __init__(self, max_metrics: int = 10000, retention_seconds: int = 3600):
        self.max_metrics = max_metrics
        self.retention_seconds = retention_seconds
        self.metrics: deque = deque(maxlen=max_metrics)
        self.component_stats: Dict[str, ComponentStats] = {}
        self.lock = threading.Lock()
    
    def record_metric(self, component: str, operation: str, duration_ms: float,
                     success: bool = True, error_msg: Optional[str] = None) -> None:
        """Record a performance metric"""
        metric = PerformanceMetric(
            component=component,
            operation=operation,
            duration_ms=duration_ms,
            success=success,
            error_msg=error_msg
        )
        
        with self.lock:
            self.metrics.append(metric)
            
            if component not in self.component_stats:
                self.component_stats[component] = ComponentStats(component)
            
            self.component_stats[component].update(metric)
    
    def get_stats(self, component: Optional[str] = None) -> Dict[str, Any]:
        """Get performance statistics"""
        with self.lock:
            if component:
                stats = self.component_stats.get(component)
                return {
                    'component': component,
                    'total_calls': stats.total_calls if stats else 0,
                    'avg_time_ms': stats.avg_time_ms if stats else 0,
                    'min_time_ms': stats.min_time_ms if stats else 0,
                    'max_time_ms': stats.max_time_ms if stats else 0,
                    'errors': stats.errors if stats else 0,
                    'success_rate': stats.success_rate if stats else 1.0,
                } if stats else {}
            else:
                return {
                    component: {
                        'total_calls': stats.total_calls,
                        'avg_time_ms': f"{stats.avg_time_ms:.2f}",
                        'min_time_ms': f"{stats.min_time_ms:.2f}",
                        'max_time_ms': f"{stats.max_time_ms:.2f}",
                        'errors': stats.errors,
                        'success_rate': f"{stats.success_rate:.1%}",
                    }
                    for component, stats in self.component_stats.items()
                }
    
    def get_bottlenecks(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get slowest operations (potential bottlenecks)"""
        with self.lock:
            slow_ops = []
            for metric in list(self.metrics):
                if metric.success:
                    slow_ops.append({
                        'component': metric.component,
                        'operation': metric.operation,
                        'duration_ms': metric.duration_ms,
                        'timestamp': metric.timestamp,
                    })
            
            # Sort by duration descending
            slow_ops.sort(key=lambda x: x['duration_ms'], reverse=True)
            return slow_ops[:limit]
    
    def cleanup_old_metrics(self) -> None:
        """Remove metrics older than retention period"""
        cutoff = datetime.now() - timedelta(seconds=self.retention_seconds)
        
        with self.lock:
            while self.metrics and self.metrics[0].timestamp < cutoff:
                self.metrics.popleft()
    
    def print_report(self) -> str:
        """Generate performance report"""
        with self.lock:
            lines = [
                "\n" + "="*70,
                "PERFORMANCE METRICS REPORT",
                "="*70,
            ]
            
            # Component statistics
            lines.append("\nCOMPONENT STATISTICS:")
            lines.append("-" * 70)
            for component, stats in sorted(self.component_stats.items()):
                lines.append(
                    f"{component:20} | Calls: {stats.total_calls:6} | "
                    f"Avg: {stats.avg_time_ms:8.2f}ms | "
                    f"Min: {stats.min_time_ms:8.2f}ms | "
                    f"Max: {stats.max_time_ms:8.2f}ms | "
                    f"Success: {stats.success_rate:.1%}"
                )
            
            # Bottlenecks
            lines.append("\nTOP BOTTLENECKS:")
            lines.append("-" * 70)
            bottlenecks = self.get_bottlenecks(limit=10)
            for i, op in enumerate(bottlenecks, 1):
                lines.append(
                    f"{i}. {op['component']}.{op['operation']}: "
                    f"{op['duration_ms']:.2f}ms"
                )
            
            lines.append("="*70 + "\n")
            return "\n".join(lines)


class TimerContext:
    """Context manager for measuring operation time"""
    
    def __init__(self, monitor: PerformanceMonitor, component: str, 
                operation: str):
        self.monitor = monitor
        self.component = component
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        success = exc_type is None
        error_msg = str(exc_val) if exc_val else None
        
        self.monitor.record_metric(
            self.component,
            self.operation,
            duration_ms,
            success=success,
            error_msg=error_msg
        )
        
        return False  # Don't suppress exceptions


class OptimizationRecommender:
    """Provides optimization recommendations based on metrics"""
    
    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
    
    def get_recommendations(self) -> List[str]:
        """Get optimization recommendations"""
        recommendations = []
        stats = self.monitor.get_stats()
        
        for component, comp_stats in stats.items():
            if isinstance(comp_stats, dict):
                # Check for high error rates
                if comp_stats.get('success_rate', 1.0) < 0.95:
                    recommendations.append(
                        f"Component '{component}' has error rate "
                        f"{(1-comp_stats.get('success_rate', 1.0))*100:.1f}%. "
                        f"Review error logs for issues."
                    )
                
                # Check for slow operations
                if comp_stats.get('avg_time_ms', 0) > 100:
                    recommendations.append(
                        f"Component '{component}' has high latency "
                        f"({comp_stats.get('avg_time_ms', 0):.0f}ms avg). "
                        f"Consider optimization."
                    )
        
        return recommendations or ["System performing normally."]


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor


def reset_performance_monitor() -> None:
    """Reset global performance monitor"""
    global _performance_monitor
    _performance_monitor = None
