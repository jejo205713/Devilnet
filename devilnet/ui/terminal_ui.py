"""
Interactive Terminal UI with Menu System

Provides a non-blocking, interactive CLI experience with real-time notifications.
Uses threading to handle alerts independently from user input/menu navigation.
"""

import curses
import threading
import time
import queue
import logging
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    SUCCESS = "SUCCESS"


@dataclass
class Alert:
    """Alert notification"""
    message: str
    level: AlertLevel
    timestamp: datetime
    
    def __str__(self) -> str:
        time_str = self.timestamp.strftime("%H:%M:%S")
        level_icon = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🔴",
            AlertLevel.SUCCESS: "✅",
        }.get(self.level, "•")
        return f"[{time_str}] {level_icon} {self.message}"


class MenuItem:
    """Menu item with associated action"""
    
    def __init__(self, label: str, action: Optional[Callable] = None, submenu: Optional['Menu'] = None):
        self.label = label
        self.action = action
        self.submenu = submenu
        self.is_separator = (action is None and submenu is None)


class Menu:
    """Interactive menu system"""
    
    def __init__(self, title: str, items: List[MenuItem]):
        self.title = title
        self.items = items
        self.current_selection = 0
    
    def get_selectable_items(self) -> List[MenuItem]:
        """Get non-separator items"""
        return [item for item in self.items if not item.is_separator]
    
    def move_up(self) -> None:
        """Move selection up"""
        selectable = self.get_selectable_items()
        if not selectable:
            return
        
        current_idx = 0
        for i, item in enumerate(selectable):
            if item == self.items[self.current_selection]:
                current_idx = i
                break
        
        current_idx = (current_idx - 1) % len(selectable)
        self.current_selection = self.items.index(selectable[current_idx])
    
    def move_down(self) -> None:
        """Move selection down"""
        selectable = self.get_selectable_items()
        if not selectable:
            return
        
        current_idx = 0
        for i, item in enumerate(selectable):
            if item == self.items[self.current_selection]:
                current_idx = i
                break
        
        current_idx = (current_idx + 1) % len(selectable)
        self.current_selection = self.items.index(selectable[current_idx])
    
    def get_current_item(self) -> Optional[MenuItem]:
        """Get currently selected item"""
        if 0 <= self.current_selection < len(self.items):
            return self.items[self.current_selection]
        return None


class AlertQueue:
    """Thread-safe alert queue"""
    
    def __init__(self, max_size: int = 100):
        self.queue: queue.Queue = queue.Queue(maxsize=max_size)
        self.lock = threading.Lock()
    
    def put(self, alert: Alert) -> None:
        """Add alert to queue (non-blocking)"""
        try:
            self.queue.put_nowait(alert)
        except queue.Full:
            # Remove oldest alert if queue full
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(alert)
            except queue.Empty:
                pass
    
    def get_all(self) -> List[Alert]:
        """Get all pending alerts"""
        alerts = []
        while True:
            try:
                alerts.append(self.queue.get_nowait())
            except queue.Empty:
                break
        return alerts
    
    def get_recent(self, count: int = 10) -> List[Alert]:
        """Get recent alerts (without removing)"""
        alerts = []
        temp_alerts = []
        
        while len(alerts) < count:
            try:
                alert = self.queue.get_nowait()
                alerts.append(alert)
                temp_alerts.append(alert)
            except queue.Empty:
                break
        
        # Put alerts back
        for alert in reversed(temp_alerts):
            try:
                self.queue.put_nowait(alert)
            except queue.Full:
                pass
        
        return alerts


class InteractiveUI:
    """Interactive terminal UI with menu navigation"""
    
    def __init__(self):
        self.current_menu: Optional[Menu] = None
        self.running = True
        self.alert_queue = AlertQueue()
        self.screen = None
        self.lock = threading.Lock()
        
        # Performance metrics
        self.metrics = {
            'alerts_total': 0,
            'anomalies_detected': 0,
            'actions_taken': 0,
            'errors': 0,
            'uptime_seconds': 0,
        }
        self.start_time = datetime.now()
    
    def initialize_menu(self) -> Menu:
        """Create main menu"""
        return Menu("DEVILNET - ML ANOMALY DETECTION", [
            MenuItem("▶ START MONITORING", action=self._menu_start),
            MenuItem("⏸ PAUSE MONITORING", action=self._menu_pause),
            MenuItem("", None),  # Separator
            MenuItem("📊 VIEW STATUS", action=self._menu_status),
            MenuItem("🚨 VIEW RECENT ALERTS", action=self._menu_alerts),
            MenuItem("📋 VIEW REPORTS", action=self._menu_reports),
            MenuItem("", None),  # Separator
            MenuItem("⚙️  CONFIGURATION", action=self._menu_config),
            MenuItem("🧠 ML MODEL INFO", action=self._menu_model),
            MenuItem("", None),  # Separator
            MenuItem("❌ EXIT", action=self._menu_exit),
        ])
    
    def _menu_start(self) -> None:
        """Start monitoring action"""
        self.add_alert("Starting continuous monitoring...", AlertLevel.INFO)
    
    def _menu_pause(self) -> None:
        """Pause monitoring action"""
        self.add_alert("Monitoring paused", AlertLevel.WARNING)
    
    def _menu_status(self) -> None:
        """Show status"""
        self.add_alert(f"Status: {json.dumps(self.metrics, indent=2)}", AlertLevel.INFO)
    
    def _menu_alerts(self) -> None:
        """Show recent alerts"""
        alerts = self.alert_queue.get_recent(10)
        if alerts:
            msg = f"Recent alerts: {len(alerts)} found"
            self.add_alert(msg, AlertLevel.INFO)
        else:
            self.add_alert("No recent alerts", AlertLevel.INFO)
    
    def _menu_reports(self) -> None:
        """Show reports"""
        self.add_alert("Viewing incident reports...", AlertLevel.INFO)
    
    def _menu_config(self) -> None:
        """Show configuration"""
        self.add_alert("Opening configuration...", AlertLevel.INFO)
    
    def _menu_model(self) -> None:
        """Show ML model info"""
        self.add_alert("Model: Isolation Forest | Status: Trained", AlertLevel.INFO)
    
    def _menu_exit(self) -> None:
        """Exit application"""
        self.running = False
        self.add_alert("Shutting down gracefully...", AlertLevel.WARNING)
    
    def add_alert(self, message: str, level: AlertLevel = AlertLevel.INFO) -> None:
        """Add alert to queue (thread-safe)"""
        alert = Alert(message=message, level=level, timestamp=datetime.now())
        self.alert_queue.put(alert)
        self.metrics['alerts_total'] += 1
        logger.debug(f"Alert queued: {message}")
    
    def update_metrics(self, **kwargs) -> None:
        """Update performance metrics (thread-safe)"""
        with self.lock:
            for key, value in kwargs.items():
                if key in self.metrics:
                    if isinstance(self.metrics[key], int):
                        self.metrics[key] += value if isinstance(value, int) else 1
                    else:
                        self.metrics[key] = value
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        with self.lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            return {**self.metrics, 'uptime_seconds': int(uptime)}


class TerminalRenderer:
    """Renders UI to terminal using curses"""
    
    def __init__(self, ui: InteractiveUI):
        self.ui = ui
        self.max_alert_lines = 10
    
    def render(self, stdscr: Any) -> None:
        """Main render loop"""
        curses.curs_set(0)  # Hide cursor
        stdscr.nodelay(1)   # Non-blocking input
        stdscr.timeout(100) # 100ms timeout
        
        # Color pairs
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_WHITE, curses.COLOR_BLACK)
        
        menu = self.ui.initialize_menu()
        
        while self.ui.running:
            stdscr.clear()
            height, width = stdscr.getmaxyx()
            
            # Get input (non-blocking)
            try:
                key = stdscr.getch()
            except:
                key = -1
            
            # Handle input
            if key == ord('q'):
                self.ui.running = False
            elif key == curses.KEY_UP:
                menu.move_up()
            elif key == curses.KEY_DOWN:
                menu.move_down()
            elif key == ord('\n'):
                item = menu.get_current_item()
                if item and item.action:
                    item.action()
            
            # Render components
            self._render_header(stdscr, width)
            self._render_menu(stdscr, menu, width, height)
            self._render_alerts(stdscr, width, height)
            self._render_metrics(stdscr, width, height)
            self._render_footer(stdscr, width, height)
            
            stdscr.refresh()
            time.sleep(0.1)
    
    def _render_header(self, stdscr: Any, width: int) -> None:
        """Render header"""
        header = "═" * width
        stdscr.addstr(0, 0, header, curses.COLOR_CYAN)
        
        title = "DEVILNET - ML ANOMALY DETECTION ENGINE"
        x = (width - len(title)) // 2
        stdscr.addstr(1, x, title, curses.color_pair(1) | curses.A_BOLD)
        
        status = "● RUNNING" if self.ui.running else "● STOPPED"
        stdscr.addstr(1, width - 15, status, curses.color_pair(1))
        
        stdscr.addstr(2, 0, "═" * width, curses.COLOR_CYAN)
    
    def _render_menu(self, stdscr: Any, menu: Menu, width: int, height: int) -> None:
        """Render menu items"""
        y = 4
        
        for i, item in enumerate(menu.items):
            if y >= height - 10:
                break
            
            if item.is_separator:
                stdscr.addstr(y, 0, "─" * width, curses.COLOR_WHITE)
            else:
                is_selected = (i == menu.current_selection)
                
                if is_selected:
                    attr = curses.A_REVERSE | curses.A_BOLD
                    color = curses.color_pair(4)
                else:
                    attr = curses.A_NORMAL
                    color = curses.color_pair(5)
                
                line = f"  {item.label}"
                stdscr.addstr(y, 0, line[:width], attr | color)
            
            y += 1
    
    def _render_alerts(self, stdscr: Any, width: int, height: int) -> None:
        """Render recent alerts"""
        alerts = self.ui.alert_queue.get_recent(self.max_alert_lines)
        
        alert_y = height - 15
        if alert_y > 0:
            stdscr.addstr(alert_y - 1, 0, "─" * width, curses.COLOR_WHITE)
            stdscr.addstr(alert_y - 1, 2, "ALERTS", curses.color_pair(4) | curses.A_BOLD)
            
            for i, alert in enumerate(alerts[-self.max_alert_lines:]):
                y = alert_y + i
                if y >= height - 2:
                    break
                
                color = {
                    AlertLevel.INFO: curses.color_pair(4),
                    AlertLevel.WARNING: curses.color_pair(2),
                    AlertLevel.CRITICAL: curses.color_pair(3),
                    AlertLevel.SUCCESS: curses.color_pair(1),
                }.get(alert.level, curses.COLOR_WHITE)
                
                alert_str = str(alert)[:width-2]
                stdscr.addstr(y, 2, alert_str, color)
    
    def _render_metrics(self, stdscr: Any, width: int, height: int) -> None:
        """Render metrics"""
        metrics = self.ui.get_metrics()
        metrics_y = height - 4
        
        if metrics_y > 0:
            metrics_line = (
                f"Alerts: {metrics['alerts_total']} | "
                f"Anomalies: {metrics['anomalies_detected']} | "
                f"Actions: {metrics['actions_taken']} | "
                f"Uptime: {metrics['uptime_seconds']}s"
            )[:width-2]
            stdscr.addstr(metrics_y, 2, metrics_line, curses.color_pair(4))
    
    def _render_footer(self, stdscr: Any, width: int, height: int) -> None:
        """Render footer"""
        footer_y = height - 1
        footer = "UP/DOWN: Navigate | ENTER: Select | Q: Quit"
        footer_line = footer[:width-2]
        stdscr.addstr(footer_y, 2, footer_line, curses.color_pair(2))


class NonBlockingAlertHandler:
    """Handles alerts in background thread"""
    
    def __init__(self, ui: InteractiveUI, engine):
        self.ui = ui
        self.engine = engine
        self.running = True
        self.thread = None
        self.lock = threading.Lock()
    
    def start(self) -> None:
        """Start alert handler thread"""
        self.thread = threading.Thread(target=self._alert_loop, daemon=True)
        self.thread.start()
        logger.info("Alert handler started")
    
    def stop(self) -> None:
        """Stop alert handler thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        logger.info("Alert handler stopped")
    
    def _alert_loop(self) -> None:
        """Background alert processing loop"""
        while self.running:
            try:
                # Check for new anomalies
                # This would be called from the main engine loop
                # and won't block the UI
                time.sleep(1)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")
                self.ui.add_alert(f"Alert error: {e}", AlertLevel.WARNING)


class MonitoringThread:
    """Runs continuous monitoring in background"""
    
    def __init__(self, ui: InteractiveUI, engine):
        self.ui = ui
        self.engine = engine
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
    
    def start(self) -> None:
        """Start monitoring thread"""
        with self.lock:
            if self.running:
                return
            
            self.running = True
            self.thread = threading.Thread(target=self._monitoring_loop, daemon=True)
            self.thread.start()
            self.ui.add_alert("Monitoring started", AlertLevel.SUCCESS)
            logger.info("Monitoring thread started")
    
    def stop(self) -> None:
        """Stop monitoring thread"""
        with self.lock:
            if not self.running:
                return
            
            self.running = False
        
        if self.thread:
            self.thread.join(timeout=5)
        
        self.ui.add_alert("Monitoring stopped", AlertLevel.WARNING)
        logger.info("Monitoring thread stopped")
    
    def _monitoring_loop(self) -> None:
        """Continuous monitoring loop (non-blocking)"""
        error_count = 0
        max_consecutive_errors = 5
        
        while self.running:
            try:
                # Run inference cycle
                anomalies = self.engine.run_inference_cycle()
                
                if anomalies:
                    self.ui.update_metrics(anomalies_detected=len(anomalies))
                    for anomaly in anomalies:
                        self.ui.add_alert(
                            f"Anomaly detected: {anomaly.event_type} ({anomaly.risk_level})",
                            AlertLevel.CRITICAL
                        )
                        self.ui.update_metrics(actions_taken=1)
                
                error_count = 0  # Reset on success
                time.sleep(5)  # Poll interval
            
            except Exception as e:
                error_count += 1
                logger.error(f"Monitoring cycle error: {e}")
                self.ui.add_alert(f"Monitoring error: {e}", AlertLevel.WARNING)
                self.ui.update_metrics(errors=1)
                
                if error_count >= max_consecutive_errors:
                    logger.error(f"Too many errors ({error_count}), pausing monitoring")
                    self.ui.add_alert(
                        "Monitoring paused due to repeated errors",
                        AlertLevel.CRITICAL
                    )
                    self.stop()
                    break
                
                time.sleep(2)  # Back-off before retry


def run_interactive_ui(engine) -> None:
    """Run the interactive UI"""
    ui = InteractiveUI()
    
    # Start monitoring thread
    monitoring = MonitoringThread(ui, engine)
    
    # Start alert handler
    alert_handler = NonBlockingAlertHandler(ui, engine)
    alert_handler.start()
    
    ui.add_alert("Devilnet started - Ready to monitor", AlertLevel.SUCCESS)
    
    # Render UI
    try:
        renderer = TerminalRenderer(ui)
        curses.wrapper(renderer.render)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        ui.add_alert("Shutdown requested", AlertLevel.WARNING)
    finally:
        # Cleanup
        monitoring.stop()
        alert_handler.stop()
        ui.add_alert("Devilnet shutdown complete", AlertLevel.INFO)
        logger.info("UI shutdown complete")
