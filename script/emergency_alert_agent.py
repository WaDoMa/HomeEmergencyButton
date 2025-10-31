#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Emergency Alert Agent

This agent monitors IoT buttons (e.g., WiFi-based triggers) and system logs 
related to SD card health, kernel warnings, and power/thermal events. It sends
collected information to a Telegram channel for real-time monitoring.

Modules:
- asyncio, nest_asyncio: Asynchronous execution
- subprocess: Running shell commands
- pathlib: File system paths
- configparser: Reading configuration files
- dotenv: Loading environment variables
- telegram: Sending messages via Telegram API

Author: Your Name
Created on: YYYY-MM-DD
"""

import asyncio
import subprocess
import nest_asyncio
import os
import sys
import pathlib as pth
import typing as tpg
import dotenv as dt
import configparser as cfg
import telegram

# ------------------- Constants ------------------- #
APP_NAME = "Emergency Alerting Agent"

# Project directory (two levels up from this file)
PROJECT_DIR = pth.Path(__file__).parents[1]

# Path to configuration file storing IoT button MAC addresses
CONFIG_PATH = PROJECT_DIR.joinpath('config', 'buttons.ini')

# SD card device to monitor (used in dmesg/journal filtering)
SD_DEVICE = "mmcblk0"

# Keywords to identify filesystem check issues
FSCK_KEYWORDS = ["repaired", "error", "corrupt", "lost"]


# ------------------- Helper Functions ------------------- #
def get_config(config_path: str | pth.Path, section: str) -> tpg.Dict[str, str]:
    """
    Read a section from an INI configuration file.

    Parameters
    ----------
    config_path : str | pathlib.Path
        Path to the configuration file.
    section : str
        Section name in the INI file.

    Returns
    -------
    dict
        Dictionary of key-value pairs from the section.

    Raises
    ------
    ValueError
        If the section does not exist in the file.
    """
    parser = cfg.ConfigParser(delimiters=('='))
    parser.optionxform = str  # preserve case
    parser.read(config_path)

    if not parser.has_section(section):
        raise ValueError(f"Section '{section}' not found in {config_path}")

    return dict(parser.items(section))


def run_cmd(cmd: list[str]) -> str:
    """
    Execute a shell command and return its output.

    Parameters
    ----------
    cmd : list[str]
        Command and arguments as a list.

    Returns
    -------
    str
        Command output as string. Returns empty string if command fails.
    """
    try:
        return subprocess.check_output(cmd, text=True)
    except subprocess.CalledProcessError:
        return ""


def filter_lines(
    text_or_lines: str | list[str],
    keywords: list[str] | None = None,
    ignore_patterns: list[str] | None = None
) -> list[str]:
    """
    Filter a set of lines by inclusion and exclusion patterns.

    Parameters
    ----------
    text_or_lines : str | list[str]
        Input text (multi-line string) or list of lines.
    keywords : list[str] | None
        Only include lines containing any of these keywords (case-insensitive).
    ignore_patterns : list[str] | None
        Exclude lines containing any of these patterns (case-insensitive).

    Returns
    -------
    list[str]
        Filtered lines as a list.
    """
    # Convert string to list of lines if necessary
    lines = text_or_lines.splitlines() if isinstance(text_or_lines, str) else text_or_lines

    # Include lines matching any keyword
    if keywords:
        lines = [line for line in lines if any(k.lower() in line.lower() for k in keywords)]

    # Exclude lines matching any ignore pattern
    if ignore_patterns:
        lines = [line for line in lines if not any(ig.lower() in line.lower() for ig in ignore_patterns)]

    return lines


def filter_sd_lines(output: str) -> list[str]:
    """
    Filter lines that reference the SD card device.

    Parameters
    ----------
    output : str
        Text output from logs or commands.

    Returns
    -------
    list[str]
        Lines mentioning the SD_DEVICE.
    """
    return filter_lines(output, [SD_DEVICE])


# ------------------- Reporting Functions ------------------- #
def get_journal_report(
    keywords: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
    priorities: str | None = None,
    since: str = "7 days ago",
    boot: str | None = None,
    device_filter: bool = False
) -> list[str]:
    """
    Collect and filter kernel log messages using journalctl.

    Parameters
    ----------
    keywords : list[str] | None
        Include lines containing these keywords.
    ignore_patterns : list[str] | None
        Exclude lines containing these patterns.
    priorities : str | None
        Kernel log priorities (e.g., 'warning..alert').
    since : str
        Start date for log collection (e.g., "7 days ago").
    boot : str | None
        Specific boot ID or "-b" offset.
    device_filter : bool
        If True, include only lines related to SD_DEVICE.

    Returns
    -------
    list[str]
        Filtered log lines.
    """
    cmd = ["journalctl", "-k", "--no-pager", "--since", since]
    if priorities:
        cmd.extend(["-p", priorities])
    if boot:
        cmd.extend(["-b", boot])

    output = run_cmd(cmd)

    # Filter by SD device if requested
    if device_filter:
        output = "\n".join(filter_sd_lines(output))

    # Apply keyword and ignore filters
    return filter_lines(output, keywords, ignore_patterns)


def get_device_report(
    source: str = "journalctl",
    device: str | None = None,
    keywords: list[str] | None = None,
    ignore_patterns: list[str] | None = None,
    priorities: str | None = None,
    since: str = "7 days ago",
    boot: str | None = None
) -> str:
    """
    Generic function to collect logs from journalctl or dmesg and filter them.

    Parameters
    ----------
    source : str
        Log source ("journalctl" or "dmesg").
    device : str | None
        Device identifier to filter logs (e.g., SD card).
    keywords : list[str] | None
        Lines must contain at least one keyword.
    ignore_patterns : list[str] | None
        Lines containing these patterns are excluded.
    priorities : str | None
        Kernel log priorities (for journalctl).
    since : str
        Start date for journal logs.
    boot : str | None
        Boot offset or ID for journalctl.

    Returns
    -------
    str
        Filtered logs as a single string or default message if empty.
    """
    if source == "journalctl":
        lines = get_journal_report(
            keywords=keywords,
            ignore_patterns=ignore_patterns,
            priorities=priorities,
            since=since,
            boot=boot,
            device_filter=bool(device)
        )
    elif source == "dmesg":
        output = run_cmd(["dmesg"])
        if device:
            output = "\n".join(filter_lines(output, [device]))
        lines = filter_lines(output, keywords, ignore_patterns)
    else:
        return f"Unknown log source: {source}"

    return "\n".join(lines) if lines else "No matching log entries found."


# ------------------- Specific Report Functions ------------------- #
def get_sd_fsck_report() -> str:
    """Return SD card filesystem check results since boot."""
    return get_device_report(
        source="journalctl",
        device=SD_DEVICE,
        keywords=FSCK_KEYWORDS,
        since="boot"
    )

def get_sd_dmesg_errors() -> str:
    """Return dmesg errors related to SD card."""
    return get_device_report(
        source="dmesg",
        device=SD_DEVICE,
        keywords=["error"]
    )

def get_sd_card_kernel_warnings() -> str:
    """Return kernel warnings/errors for SD card."""
    return get_device_report(
        source="journalctl",
        device=SD_DEVICE,
        priorities="warning..alert"
    )

def get_power_thermal_undervolt_events(days: int = 7) -> str:
    """
    Return power, thermal, and undervoltage events over the last N days.

    Parameters
    ----------
    days : int
        Number of days to look back.

    Returns
    -------
    str
        Formatted report.
    """
    keywords = ["under-volt", "over-temp", "thrott", "thermal"]
    ignore_patterns = [
        "thermal_sys: Registered thermal governor",
        "systemd-pstore.service"
    ]
    return get_device_report(
        source="journalctl",
        keywords=keywords,
        ignore_patterns=ignore_patterns,
        since=f"{days} days ago"
    )


def get_disk_usage_report(all_fs: bool = True) -> str:
    """
    Get disk usage statistics for all mounted filesystems using `df -h`.
    Uses the existing `run_cmd` and `filter_lines` helpers for consistency.

    Parameters
    ----------
    all_fs : bool
        If True, report all filesystems; if False, report only root '/'.

    Returns
    -------
    str
        Formatted disk usage lines suitable for Telegram message, including
        the header line.
    """
    cmd = ["df", "-h"]
    if not all_fs:
        cmd.append("/")  # Only check root if all_fs is False

    output = run_cmd(cmd)
    if not output:
        return "Unable to retrieve df output."

    lines = filter_lines(output.splitlines(), ignore_patterns=["^$"])  # remove empty lines
    if not lines:
        return "No usable output from df."

    # Preserve header line
    header, *data_lines = lines
    formatted = "\n".join([header] + data_lines)

    return f"{formatted}"




# ------------------- Main Logic ------------------- #
async def main():
    """Collect all reports and send to Telegram channel."""
    print(f"Starting {APP_NAME}...")

    # Load button configuration
    try:
        buttons = get_config(CONFIG_PATH, 'Buttons')
    except ValueError as e:
        print(e)
        buttons = {}

    # Print loaded buttons
    if buttons:
        for mac_address, button_name in buttons.items():
            print(f"MAC Address: {mac_address} -> Button Name: {button_name}")
    else:
        print("No buttons found.")

    # Load environment variables
    dt.load_dotenv()
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id_tech_stats = os.getenv('CHANNEL_ID_TechStats')
    debug = os.getenv('DEBUG')

    print(f'TELEGRAM_BOT_TOKEN: {telegram_bot_token}')
    print(f'CHANNEL_ID_TechStats: {channel_id_tech_stats}')
    print(f'DEBUG: {debug}')

    # Collect system reports
    fsck_report = get_sd_fsck_report()
    kernel_report = get_sd_card_kernel_warnings()
    dmesg_report = get_sd_dmesg_errors()
    power_thermal_undervolt_report = get_power_thermal_undervolt_events(days=7)
    disk_usage_report = get_disk_usage_report(all_fs=True)
    
    # Combine all reports into one message


    message = (
    f"📊 System Health Report:\n\n"
    f"💾 Disk Usage Report:\n{disk_usage_report}\n\n"
    f"🛠 FSCK results:\n{fsck_report}\n\n"
    f"⚠ Kernel warnings/errors (last 7 days):\n{kernel_report}\n\n"
    f"💻 Current boot dmesg errors:\n{dmesg_report}\n\n"
    f"⚡ Power & Thermal / Undervoltage Alerts:\n{power_thermal_undervolt_report}"
    )

    # Send message via Telegram
    bot = telegram.Bot(token=telegram_bot_token)
    await bot.send_message(chat_id=channel_id_tech_stats, text=message)


if __name__ == "__main__":
    try:
        nest_asyncio.apply()  # allow nested event loops (required in Jupyter, etc.)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
