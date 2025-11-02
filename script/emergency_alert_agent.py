#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Emergency Alert Agent

This agent monitors system logs related to SD card health, kernel warnings,
and power/thermal events. It sends collected information to a Telegram channel
for real-time monitoring.

Modules:
- asyncio: Asynchronous execution
- subprocess: Running shell commands
- pathlib: File system paths
- configparser: Reading configuration files
- dotenv: Loading environment variables
- telegram: Sending messages via Telegram API

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

# Third-party
import dotenv as dt
import telegram as tg
import telegram.error as tg_error


# ------------------- Configuration ------------------- #
APP_NAME = "Emergency Alerting Agent"
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


# ------------------- Main Logic ------------------- #
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


async def main():
    """Main execution function."""
    print(f"Starting {APP_NAME}...\n")

    # Load environment variables
    dt.load_dotenv()
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id = os.getenv('CHANNEL_ID_TechStats')
    debug = os.getenv('DEBUG', 'false').lower() == 'true'

    # Validate configuration
    if not telegram_bot_token or not channel_id:
        print("Error: Missing TELEGRAM_BOT_TOKEN or CHANNEL_ID_TechStats", file=sys.stderr)
        sys.exit(1)

    if debug:
        print("Debug mode enabled")
        print(f"Channel ID: {channel_id}\n")

    # Load button configuration (if needed for future features)
    try:
        buttons = load_config_section(CONFIG_PATH, 'Buttons')
        if debug and buttons:
            print("Loaded buttons:")
            for mac, name in buttons.items():
                print(f"  {mac} -> {name}")
            print()
    except (ValueError, FileNotFoundError) as e:
        if debug:
            print(f"Note: {e}\n")

    # Collect and send reports
    report = collect_system_reports()
    message = report.format_message()

    if debug:
        print("\n" + "="*50)
        print("Message to send:")
        print("="*50)
        print(message)
        print("="*50 + "\n")

    success = await send_telegram_message(telegram_bot_token, channel_id, message)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        # Check if there's already a running event loop (e.g., in Spyder, Jupyter)
        try:
            loop = asyncio.get_running_loop()
            # We're in an existing event loop, use it directly
            import nest_asyncio  # Special case for Spyder compatibility
            nest_asyncio.apply()
            loop.run_until_complete(main())
        except RuntimeError:
            # No running loop, use asyncio.run() (standard approach)
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)