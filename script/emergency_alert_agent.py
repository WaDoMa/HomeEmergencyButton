#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Emergency alert agent

Collects events from Wifi IoT-buttons and sends them over Telegram.
Also collects filesystem check results, kernel warnings, and dmesg errors
related to the SD card,and sends a summary to a Telegram channel.

Created on YYYY-MM-DD
Author: Your Name
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

# Constants
APP_NAME = "Emergency Alerting Agent"
PROJECT_DIR = pth.Path(__file__).parents[1]    # Top level directory of this py-file
CONFIG_PATH = PROJECT_DIR.joinpath('config', 'buttons.ini')  # Construct absolut path to the config-file
SD_DEVICE = "mmcblk0"
# Example keywords for fsck issues
FSCK_KEYWORDS = ["repaired", "error", "corrupt", "lost"]


# ------------------- Helper Functions ------------------- #
def get_config(config_path: str | pth.Path, section: str) -> tpg.Dict[str, str]:
    """
    Parse config file and return key-value pairs of a section.

    Parameters
    ----------
    config_path : str or pathlib.Path
        Path to the config file.
    section : str
        Section name to extract.

    Returns
    -------
    dict
        Key-value pairs from the section.

    Raises
    ------
    ValueError
        If the section is not found.
    """
    # Create a ConfigParser object using '=' as the only delimiter;
    # ':' would conflict with colons in MAC addresses.
    parser = cfg.ConfigParser(delimiters=('='))
    parser.optionxform = str
    parser.read(config_path)
    if not parser.has_section(section):
        raise ValueError(f"Section '{section}' not found in {config_path}")
    return dict(parser.items(section))


def filter_sd_lines(output: str) -> list[str]:
    """
    Filter lines containing the SD device identifier (case-insensitive).

    Parameters
    ----------
    output : str
        Multi-line string, typically output from a command like `dmesg` or `journalctl`.

    Returns
    -------
    list[str]
        A list of lines from `output` that mention the SD device specified by `SD_DEVICE`.

    Notes
    -----
    The search is case-insensitive. `SD_DEVICE` should be defined globally
    (e.g., "mmcblk0") for this function to work correctly.

    Examples
    --------
    >>> SD_DEVICE = "mmcblk0"
    >>> log = "mmcblk0: error detected\nmmcblk1: ok"
    >>> filter_sd_lines(log)
    ['mmcblk0: error detected']
    """
    sd_lower = SD_DEVICE.lower()
    return [line for line in output.splitlines() if sd_lower in line.lower()]


def filter_keywords(lines: list[str], keywords: list[str]) -> list[str]:
    """
    Return lines that contain any of the specified keywords (case-insensitive).

    Parameters
    ----------
    lines : list of str
        List of text lines to search.
    keywords : list of str
        List of keywords to search for in each line.

    Returns
    -------
    list of str
        Lines from `lines` that contain at least one of the keywords.

    Notes
    -----
    Matching is case-insensitive. The order of the returned lines
    is the same as in the input `lines`.

    Examples
    --------
    >>> lines = ["Disk error detected", "All good", "File system lost blocks"]
    >>> filter_keywords(lines, ["error", "lost"])
    ['Disk error detected', 'File system lost blocks']
    """
    kw_lower = [k.lower() for k in keywords]
    return [line for line in lines if any(k in line.lower() for k in kw_lower)]


def run_cmd(cmd: list[str]) -> str:
    """
    Run a shell command and return its output as a string.

    Parameters
    ----------
    cmd : list of str
        Command and arguments to execute.

    Returns
    -------
    str
        Output of the command.
    """
    try:
        return subprocess.check_output(cmd, text=True)
    except subprocess.CalledProcessError:
        return ""


# ------------------- Reporting Functions ------------------- #
# === 1️⃣ Collect fsck results from systemd journal ===
def get_fsck_report() -> str:
    """
    Collect fsck results from the systemd journal.

    Returns
    -------
    str
        Meaningful fsck lines or a message if none found.
    """
    output = run_cmd(["journalctl", "-b", "-u", "systemd-fsck@*", "--no-pager"])
    sd_lines = filter_sd_lines(output)
    meaningful = filter_keywords(sd_lines, FSCK_KEYWORDS)
    return "\n".join(meaningful) or "No fsck repairs/errors detected."



# === 2️⃣ Collect kernel warnings/errors from journalctl ===
def get_kernel_report() -> str:
    """
    Collect kernel warnings/errors related to the SD card in the last 7 days.

    Returns
    -------
    str
        Relevant kernel log lines or a message if none found.
    """
    output = run_cmd(["journalctl", "-k", "-p", "warning..alert", "--since", "7 days ago"])
    sd_lines = filter_sd_lines(output)
    # optional: filter for specific kernel keywords if needed
    return "\n".join(sd_lines) or "No SD card kernel warnings/errors in last 7 days."


# === 3️⃣ Collect current boot dmesg errors (optional) ===
def get_dmesg_report() -> str:
    """
    Collect current boot dmesg errors related to the SD card.

    Returns
    -------
    str
        Relevant dmesg lines or a message if none found.
    """
    output = run_cmd(["dmesg"])
    sd_lines = filter_sd_lines(output)
    error_lines = filter_keywords(sd_lines, ["error"])
    return "\n".join(error_lines) or "No current boot dmesg errors for SD card."


# ------------------- Main Logic ------------------- #
async def main():
    """Main logic of the script."""
    print(f"Starting {APP_NAME}...")

     # Read ini-file with MAC-addresses and button_names of buttons:
    try:
        buttons = get_config(CONFIG_PATH, 'Buttons')
    except ValueError as e:
        print(e)
        buttons = {}

    if buttons:
        for mac_address, button_name in buttons.items():
            print(f"MAC Address: {mac_address} -> Button Name: {button_name}")
    else:
        print("No buttons found.")

    # Load environment variables from .env file into the environment, if not
    # already set in the environment:
    dt.load_dotenv()
    # Access variables using os.getenv
    telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    channel_id_tech_stats = os.getenv('CHANNEL_ID_TechStats')
    debug = os.getenv('DEBUG')

    print(f'TELEGRAM_BOT_TOKEN: {telegram_bot_token}')
    print(f'CHANNEL_ID_TechStats: {channel_id_tech_stats}')
    print(f'DEBUG: {debug}')
    
    fsck_report = get_fsck_report()
    kernel_report = get_kernel_report()
    dmesg_report = get_dmesg_report()

    message = (
        f"📦 SD Card Health Report ({SD_DEVICE}):\n\n"
        f"🛠 fsck results:\n{fsck_report}\n\n"
        f"⚠ Kernel warnings/errors (last 7 days):\n{kernel_report}\n\n"
        f"💻 Current boot dmesg errors:\n{dmesg_report}"
    )

    bot = telegram.Bot(token=telegram_bot_token)
    await bot.send_message(chat_id=channel_id_tech_stats, text=message)


if __name__ == "__main__":
    try:
        nest_asyncio.apply()
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
