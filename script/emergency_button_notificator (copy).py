#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Emergency Alert Notificator

This agent monitors system logs related to SD card health, kernel warnings,
and power/thermal events. It also monitors Amazon Dash buttons for emergency
alerts. All information is sent to Telegram channels for real-time monitoring.

Modules:
- asyncio: Asynchronous execution
- subprocess: Running shell commands
- pathlib: File system paths
- configparser: Reading configuration files
- dotenv: Loading environment variables
- telegram: Sending messages via Telegram API
- scapy: Network packet sniffing for Dash button detection

Author: Your Name
Created on: YYYY-MM-DD
"""

# Standard library
import asyncio
import subprocess
import os
import sys
import pathlib as pth
import typing as typ
import dataclasses as dc
import configparser as cfg
import datetime as dt_lib
import signal
import threading

# Third-party
import dotenv as dt
import telegram as tg
import telegram.error as tg_error
import scapy.all as scapy


# ------------------- Configuration ------------------- #
APP_NAME = "Emergency Alerting Notificator"
PROJECT_DIR = pth.Path(__file__).parents[1]
CONFIG_PATH = PROJECT_DIR / 'config' / 'buttons.ini'

# Monitoring configuration
SD_DEVICE = "mmcblk0"
SD_KEYWORDS = ["mmc", "mmcblk", "blk_update_request", "Buffer I/O error", 
               "end_request: I/O error"]
FSCK_KEYWORDS = ["repaired", "error", "corrupt", "lost"]
POWER_KEYWORDS = ["under-voltage", "over-temp", "throttl", "thermal"]
POWER_IGNORE_PATTERNS = [
    "thermal_sys: Registered thermal governor",
    "systemd-pstore.service"
]

# Default time ranges
DEFAULT_LOOKBACK_DAYS = 7

# Button detection settings
BUTTON_DEBOUNCE_SECONDS = 5  # Ignore repeated presses within this time


# ------------------- Global State ------------------- #
class GlobalState:
    """Shared state for the application."""
    def __init__(self):
        self.running = True
        self.last_button_press = {}  # MAC -> timestamp for debouncing
        self.telegram_bot = None
        self.channel_id_alerts = None
        self.channel_id_tech_stats = None
        self.buttons_config = {}
        self.debug = False
        self.loop = None

STATE = GlobalState()


@dc.dataclass
class SystemReport:
    """Container for all system health reports."""
    disk_usage: str
    fsck: str
    kernel_errors: str
    sd_warnings: str
    power_thermal: str

    def format_message(self) -> str:
        """Format all reports into a single Telegram message."""
        sections = [
            ("📊 System Health Report", None),
            ("💾 Disk Usage", self.disk_usage),
            ("🛠 FSCK Results (since boot)", self.fsck),
            ("⚠ Kernel Errors (last 7 days)", self.kernel_errors),
            ("💿 SD Card Warnings (last 7 days)", self.sd_warnings),
            ("⚡ Power & Thermal Alerts (last 7 days)", self.power_thermal),
        ]

        message_parts = []
        for title, content in sections:
            if content is None:
                message_parts.append(f"{title}:\n")
            else:
                message_parts.append(f"{title}:\n{content}\n")

        return "\n".join(message_parts).strip()


# ------------------- Helper Functions ------------------- #
def load_config_section(config_path: pth.Path, section: str) -> dict[str, str]:
    """
    Read a section from an INI configuration file.

    Parameters
    ----------
    config_path : pathlib.Path
        Path to the configuration file.
    section : str
        Section name in the INI file.

    Returns
    -------
    dict[str, str]
        Dictionary of key-value pairs from the section.

    Raises
    ------
    ValueError
        If the section does not exist in the file.
    """
    parser = cfg.ConfigParser(delimiters=('=',))
    parser.optionxform = str  # preserve case
    parser.read(config_path)

    if not parser.has_section(section):
        raise ValueError(f"Section '{section}' not found in {config_path}")

    return dict(parser.items(section))


def run_command(cmd: list[str], max_lines: typ.Optional[int] = None) -> str:
    """
    Execute a shell command and return its output.

    Parameters
    ----------
    cmd : list[str]
        Command and arguments as a list.
    max_lines : int | None
        Maximum number of lines to return (for limiting large outputs).

    Returns
    -------
    str
        Command output as string. Returns empty string if command fails.
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )
        
        if result.returncode != 0:
            return ""
        
        output = result.stdout
        if max_lines:
            lines = output.splitlines()[:max_lines]
            output = "\n".join(lines)
            if len(result.stdout.splitlines()) > max_lines:
                output += f"\n... (truncated, {len(result.stdout.splitlines()) - max_lines} more lines)"
        
        return output
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        return ""


def filter_lines(
    lines: list[str],
    include_keywords: typ.Optional[list[str]] = None,
    exclude_patterns: typ.Optional[list[str]] = None
) -> list[str]:
    """
    Filter lines by inclusion and exclusion patterns.

    Parameters
    ----------
    lines : list[str]
        List of lines to filter.
    include_keywords : list[str] | None
        Only include lines containing any of these keywords (case-insensitive).
    exclude_patterns : list[str] | None
        Exclude lines containing any of these patterns (case-insensitive).

    Returns
    -------
    list[str]
        Filtered lines.
    """
    filtered = lines

    if include_keywords:
        filtered = [
            line for line in filtered
            if any(keyword.lower() in line.lower() for keyword in include_keywords)
        ]

    if exclude_patterns:
        filtered = [
            line for line in filtered
            if not any(pattern.lower() in line.lower() for pattern in exclude_patterns)
        ]

    return filtered


# ------------------- Journal Query Functions ------------------- #
def query_journal(
    include_keywords: typ.Optional[list[str]] = None,
    exclude_patterns: typ.Optional[list[str]] = None,
    priorities: typ.Optional[str] = None,
    since: str = "7 days ago",
    boot: typ.Optional[str] = None,
    max_lines: int = 1000
) -> list[str]:
    """
    Query systemd journal with filters.

    Parameters
    ----------
    include_keywords : list[str] | None
        Include lines containing these keywords.
    exclude_patterns : list[str] | None
        Exclude lines containing these patterns.
    priorities : str | None
        Kernel log priorities (e.g., 'err', 'warning').
    since : str
        Start date for log collection.
    boot : str | None
        Specific boot ID or offset.
    max_lines : int
        Maximum number of lines to process.

    Returns
    -------
    list[str]
        Filtered log lines.
    """
    cmd = ["journalctl", "-k", "--no-pager", "--since", since, f"--lines={max_lines}"]
    
    if priorities:
        cmd.extend(["-p", priorities])
    if boot:
        cmd.extend(["-b", boot])

    output = run_command(cmd)
    if not output:
        return []

    lines = output.splitlines()
    return filter_lines(lines, include_keywords, exclude_patterns)


# ------------------- Specific Report Functions ------------------- #
def get_disk_usage_report(all_fs: bool = True) -> str:
    """
    Get disk usage statistics using `df -h`.

    Parameters
    ----------
    all_fs : bool
        If True, report all filesystems; if False, report only root '/'.

    Returns
    -------
    str
        Formatted disk usage output.
    """
    cmd = ["df", "-h"]
    if not all_fs:
        cmd.append("/")

    output = run_command(cmd)
    return output if output else "Unable to retrieve disk usage."


def get_sd_fsck_report() -> str:
    """Return SD card filesystem check results since boot."""
    lines = query_journal(
        include_keywords=[SD_DEVICE] + FSCK_KEYWORDS,
        since="boot"
    )
    return "\n".join(lines) if lines else "No FSCK issues found."


def get_kernel_errors() -> str:
    """
    Return all kernel errors (priority err and above) from last 7 days.
    This replaces the old dmesg error check and provides persistent logs.
    """
    lines = query_journal(
        priorities="err",
        since=f"{DEFAULT_LOOKBACK_DAYS} days ago"
    )
    return "\n".join(lines) if lines else "No kernel errors found."


def get_sd_warnings() -> str:
    """
    Return SD card related warnings and issues from last 7 days.
    Includes both priority warnings and keyword-based detection.
    """
    # Get priority warnings
    priority_lines = query_journal(
        include_keywords=SD_KEYWORDS,
        priorities="warning",
        since=f"{DEFAULT_LOOKBACK_DAYS} days ago"
    )
    
    # Get all logs with SD-related error keywords
    keyword_lines = query_journal(
        include_keywords=SD_KEYWORDS + FSCK_KEYWORDS,
        since=f"{DEFAULT_LOOKBACK_DAYS} days ago"
    )
    
    # Combine and deduplicate
    all_lines = list(dict.fromkeys(priority_lines + keyword_lines))
    
    return "\n".join(all_lines) if all_lines else "No SD card warnings found."


def get_power_thermal_events(days: int = DEFAULT_LOOKBACK_DAYS) -> str:
    """
    Return power, thermal, and undervoltage events.

    Parameters
    ----------
    days : int
        Number of days to look back.

    Returns
    -------
    str
        Formatted report.
    """
    lines = query_journal(
        include_keywords=POWER_KEYWORDS,
        exclude_patterns=POWER_IGNORE_PATTERNS,
        since=f"{days} days ago"
    )
    return "\n".join(lines) if lines else "No power/thermal events found."


# ------------------- System Report Logic ------------------- #
def collect_system_reports() -> SystemReport:
    """Collect all system health reports."""
    print("Collecting system reports...")
    
    return SystemReport(
        disk_usage=get_disk_usage_report(all_fs=True),
        fsck=get_sd_fsck_report(),
        kernel_errors=get_kernel_errors(),
        sd_warnings=get_sd_warnings(),
        power_thermal=get_power_thermal_events()
    )


# ------------------- Telegram Functions ------------------- #
async def send_telegram_message(bot_token: str, chat_id: str, message: str) -> bool:
    """
    Send a message via Telegram with error handling.

    Parameters
    ----------
    bot_token : str
        Telegram bot token.
    chat_id : str
        Target chat/channel ID.
    message : str
        Message to send.

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    try:
        bot = tg.Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message)
        print("✓ Message sent successfully to Telegram")
        return True
    except tg_error.TelegramError as e:
        print(f"✗ Failed to send Telegram message: {e}", file=sys.stderr)
        return False


def send_telegram_sync(chat_id: str, message: str):
    """
    Synchronous wrapper to send Telegram message from non-async context.
    
    Parameters
    ----------
    chat_id : str
        Target chat/channel ID.
    message : str
        Message to send.
    """
    if not STATE.telegram_bot or not STATE.loop:
        print("Error: Telegram bot not initialized", file=sys.stderr)
        return
    
    async def _send():
        try:
            await STATE.telegram_bot.send_message(chat_id=chat_id, text=message)
            if STATE.debug:
                print(f"✓ Alert sent to {chat_id}")
        except tg_error.TelegramError as e:
            print(f"✗ Failed to send alert: {e}", file=sys.stderr)
    
    # Schedule coroutine in the event loop
    asyncio.run_coroutine_threadsafe(_send(), STATE.loop)


# ------------------- Dash Button Detection ------------------- #
def is_debounced(mac_address: str) -> bool:
    """
    Check if button press should be debounced.
    
    Parameters
    ----------
    mac_address : str
        MAC address of the button.
    
    Returns
    -------
    bool
        True if press should be ignored (too soon after last press).
    """
    now = dt_lib.datetime.now()
    
    if mac_address in STATE.last_button_press:
        time_since_last = (now - STATE.last_button_press[mac_address]).total_seconds()
        if time_since_last < BUTTON_DEBOUNCE_SECONDS:
            return True
    
    STATE.last_button_press[mac_address] = now
    return False


def handle_button_press(mac_address: str, button_name: str):
    """
    Handle emergency button press event.
    
    Parameters
    ----------
    mac_address : str
        MAC address of the pressed button.
    button_name : str
        Human-readable name of the button.
    """
    if is_debounced(mac_address):
        if STATE.debug:
            print(f"Debounced: {button_name} ({mac_address})")
        return
    
    timestamp = dt_lib.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n🚨 [{timestamp}] EMERGENCY: {button_name} pressed! (MAC: {mac_address})")
    
    # Format alert message
    alert_message = (
        f"🚨 EMERGENCY ALERT 🚨\n\n"
        f"Button: {button_name}\n"
        f"MAC: {mac_address}\n"
        f"Time: {timestamp}\n\n"
        f"⚠️ Immediate attention required!"
    )
    
    # Send to alerts channel
    if STATE.channel_id_alerts:
        send_telegram_sync(STATE.channel_id_alerts, alert_message)
    else:
        print("Warning: No alerts channel configured", file=sys.stderr)


def packet_handler(packet):
    """
    Process each ARP packet to detect button presses.
    
    Parameters
    ----------
    packet : scapy.Packet
        Network packet to analyze.
    """
    if not STATE.running:
        return
    
    if packet.haslayer(scapy.ARP):
        mac = packet[scapy.ARP].hwsrc.lower()
        
        if mac in STATE.buttons_config:
            button_name = STATE.buttons_config[mac]
            handle_button_press(mac, button_name)


def discover_dash_buttons(duration: int = 60):
    """
    Discovery mode: Monitor network for specified duration to find button MACs.
    
    Parameters
    ----------
    duration : int
        Duration in seconds to monitor for button presses.
    """
    print(f"\n{'='*60}")
    print(f"DISCOVERY MODE: Monitoring for {duration} seconds...")
    print("Press your Dash buttons now to identify their MAC addresses")
    print(f"{'='*60}\n")
    
    detected = {}
    
    def discover_handler(packet):
        if packet.haslayer(scapy.ARP):
            mac = packet[scapy.ARP].hwsrc.lower()
            if mac not in detected:
                # Filter for likely Dash button MACs (Amazon OUI prefixes)
                if mac.startswith(('ac:63:be', '50:f5:da', '74:75:48', 
                                  '18:74:2e', '00:fc:8b', '68:54:fd',
                                  'a0:02:dc', '74:c2:46', '84:d6:d0')):
                    detected[mac] = dt_lib.datetime.now()
                    print(f"✓ Found potential Dash button: {mac}")
    
    try:
        scapy.sniff(prn=discover_handler, filter="arp", timeout=duration, store=False)
    except PermissionError:
        print("\nERROR: This script requires root privileges")
        print("Run with: sudo python3 emergency_alert_notificator.py discover")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print("DISCOVERED DEVICES")
    print(f"{'='*60}")
    
    if detected:
        for mac, timestamp in detected.items():
            print(f"MAC: {mac} (detected at {timestamp.strftime('%H:%M:%S')})")
        
        print(f"\n{'='*60}")
        print("Add these to your config/buttons.ini file:")
        print(f"{'='*60}")
        print("[Buttons]")
        for i, mac in enumerate(detected.keys(), 1):
            print(f"{mac} = Button {i}")
    else:
        print("No Dash buttons detected.")
        print("Make sure you pressed the buttons during the monitoring period.")
    
    print(f"{'='*60}\n")


def start_button_monitoring():
    """Start monitoring for Dash button presses in a separate thread."""
    def monitor():
        print("\n📡 Starting Dash button monitoring...")
        print("Waiting for button presses... (Ctrl+C to stop)\n")
        
        try:
            scapy.sniff(prn=packet_handler, filter="arp", store=False)
        except PermissionError:
            print("\nERROR: This script requires root privileges for button monitoring")
            print("Run with: sudo python3 emergency_alert_notificator.py")
            STATE.running = False
        except Exception as e:
            if STATE.running:  # Only print if not intentionally stopped
                print(f"\nButton monitoring error: {e}", file=sys.stderr)
    
    # Run scapy in a separate thread to avoid blocking asyncio
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    return monitor_thread


# ------------------- Main Logic ------------------- #
async def send_system_report():
    """Collect and send system health report."""
    report = collect_system_reports()
    message = report.format_message()

    if STATE.debug:
        print("\n" + "="*50)
        print("System Report Message:")
        print("="*50)
        print(message)
        print("="*50 + "\n")

    success = await send_telegram_message(
        os.getenv('TELEGRAM_BOT_TOKEN'),
        STATE.channel_id_tech_stats,
        message
    )
    return success


async def keep_alive():
    """
    Keep the event loop running while monitoring for button presses.
    Simply waits until STATE.running becomes False.
    """
    try:
        while STATE.running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    print("\n\n🛑 Shutdown signal received...")
    STATE.running = False


async def main(mode: str = "monitor"):
    """
    Main execution function.
    
    Parameters
    ----------
    mode : str
        Operation mode: "monitor", "discover", or "report-only"
    """
    print(f"Starting {APP_NAME}...\n")

    # Load environment variables
    dt.load_dotenv()
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    STATE.channel_id_tech_stats = os.getenv('CHANNEL_ID_TechStats')
    STATE.channel_id_alerts = os.getenv('CHANNEL_ID_Alerts')
    STATE.debug = os.getenv('DEBUG', 'false').lower() == 'true'

    # Discovery mode - no Telegram needed
    if mode == "discover":
        duration = 60
        discover_dash_buttons(duration)
        return 0

    # Validate configuration for monitoring modes
    if not telegram_bot_token or not STATE.channel_id_tech_stats:
        print("Error: Missing TELEGRAM_BOT_TOKEN or CHANNEL_ID_TechStats", file=sys.stderr)
        return 1

    if mode == "monitor" and not STATE.channel_id_alerts:
        print("Warning: CHANNEL_ID_Alerts not set. Button alerts will not be sent.", file=sys.stderr)

    if STATE.debug:
        print("Debug mode enabled")
        print(f"Channel ID for technical stats: {STATE.channel_id_tech_stats}")
        print(f"Channel ID for alerts: {STATE.channel_id_alerts}\n")

    # Initialize Telegram bot
    STATE.telegram_bot = tg.Bot(token=telegram_bot_token)
    STATE.loop = asyncio.get_event_loop()

    # Load button configuration
    try:
        STATE.buttons_config = load_config_section(CONFIG_PATH, 'Buttons')
        if STATE.buttons_config:
            print(f"Loaded {len(STATE.buttons_config)} button(s):")
            for mac, name in STATE.buttons_config.items():
                print(f"  • {name} ({mac})")
            print()
        else:
            print("Warning: No buttons configured in buttons.ini")
            if mode == "monitor":
                print("Run in discovery mode to find button MAC addresses:")
                print("  sudo python3 emergency_alert_notificator.py discover\n")
    except (ValueError, FileNotFoundError) as e:
        print(f"Note: {e}")
        if mode == "monitor":
            print("Button monitoring will not be available.\n")

    # Report-only mode: send one report and exit
    if mode == "report-only":
        success = await send_system_report()
        return 0 if success else 1

    # Full monitoring mode: system reports + button monitoring
    if mode == "monitor":
        # Set up signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Send initial system report (only once at startup)
        print("📊 Sending initial system health report...\n")
        await send_system_report()

        # Start button monitoring in background thread
        if STATE.buttons_config:
            monitor_thread = start_button_monitoring()
            print("✅ System initialized. Monitoring for emergency button presses...\n")
        else:
            print("⚠️  Skipping button monitoring (no buttons configured)")
            monitor_thread = None

        try:
            # Keep running until interrupted (just monitor buttons)
            await keep_alive()
        except asyncio.CancelledError:
            pass
        finally:
            STATE.running = False
            if monitor_thread:
                print("Stopping button monitoring...")

        print("✓ Agent stopped gracefully\n")
        return 0

    return 1


if __name__ == "__main__":
    # Parse command line arguments
    mode = "monitor"  # Default mode
    
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == "discover":
            mode = "discover"
        elif arg == "report":
            mode = "report-only"
        elif arg in ["help", "-h", "--help"]:
            print(f"""
{APP_NAME}

Usage:
  sudo python3 emergency_alert_notificator.py [mode]

Modes:
  (none)    - Full monitoring: send system report at startup, then monitor buttons (default)
  discover  - Discovery mode: find Dash button MAC addresses
  report    - Send one system report and exit
  help      - Show this help message

Examples:
  # Full monitoring (requires root for button detection)
  # Sends tech stats once at startup, then monitors buttons indefinitely
  sudo python3 emergency_alert_notificator.py

  # Find button MAC addresses
  sudo python3 emergency_alert_notificator.py discover

  # Send system report only (can run without root)
  python3 emergency_alert_notificator.py report

Configuration:
  .env file must contain:
    - TELEGRAM_BOT_TOKEN
    - CHANNEL_ID_TechStats (for system reports)
    - CHANNEL_ID_Alerts (for emergency alerts)
    - DEBUG=true/false (optional)

  config/buttons.ini must contain:
    [Buttons]
    aa:bb:cc:dd:ee:ff = Button Name

Note: System reboots every 7 days, so system reports are sent once per boot cycle.
""")
            sys.exit(0)

    try:
        # Check if there's already a running event loop (e.g., in Spyder, Jupyter)
        try:
            loop = asyncio.get_running_loop()
            # We're in an existing event loop, use it directly
            import nest_asyncio  # Special case for Spyder compatibility
            nest_asyncio.apply()
            exit_code = loop.run_until_complete(main(mode))
            sys.exit(exit_code)
        except RuntimeError:
            # No running loop, use asyncio.run() (standard approach)
            exit_code = asyncio.run(main(mode))
            sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n✓ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)