# Home Emergency Button

A Raspberry Pi-based emergency alert system that monitors system health and IoT button events, providing reliable notifications via Telegram.

## Project Overview

This project implements a resilient emergency alerting system designed for continuous operation on Raspberry Pi hardware. The system focuses on two key functions:

1. **System Health Monitoring**: Continuous monitoring of SD card health, kernel errors, and power/thermal events with persistent logs across reboots
2. **Emergency Button Integration**: Detection and notification of IoT button press events (in development)

### Design Philosophy

The project prioritizes **reliability and early failure detection** through:

- Proactive SD card health monitoring to prevent system failures
- Weekly automated reboots with filesystem checks to repair errors before they escalate
- Persistent logging via systemd journal for tracking issues across boot cycles
- Automated reporting for remote system observation

## Features

### Current Capabilities

- **Persistent Kernel Error Monitoring**: Tracks all kernel errors (priority "err" and above) from the last 7 days using journalctl, surviving reboots
- **SD Card Health Monitoring**: Detects filesystem errors, read/write issues, block corruption, and MMC/block device failures
- **Power/Thermal Monitoring**: Tracks undervoltage events, overtemperature conditions, and throttling
- **FSCK Integration**: Monitors filesystem check results since last boot
- **Disk Usage Reporting**: Regular filesystem capacity monitoring
- **Automated Telegram Notifications**: Sends consolidated health reports to designated channels
- **Service Management**: Runs as a systemd service with automatic restart on failure

### Planned Features

- **IoT Button Event Detection**: Monitor and respond to WiFi-based emergency button presses
- **Button Event Notifications**: Send immediate alerts when emergency buttons are triggered

## System Architecture

### Monitoring Workflow
```
Weekly cron → Reboot → Force fsck on all partitions → 
Emergency Alert Agent starts → Collects logs from journalctl (last 7 days) → 
Filters relevant issues → Sends report via Telegram
```

### Log Sources

The system aggregates information from multiple sources:

- **journalctl**: System journal entries (kernel messages from last 7 days, persistent across reboots)
- **systemd-fsck**: Filesystem check service logs (since current boot)
- **df**: Disk usage statistics

### Key Design Decision: journalctl vs dmesg

This system exclusively uses `journalctl -k` (kernel messages from systemd journal) instead of `dmesg` because:

- **Persistence**: journalctl maintains logs across reboots, while dmesg only shows current boot session
- **Time range**: Can query logs from the last 7 days, even if multiple reboots occurred
- **Priority filtering**: Native support for kernel log levels (err, warning, etc.)
- **Reliability**: Survives kernel ring buffer overflows

## Prerequisites

### Hardware

- Raspberry Pi (any model with SD card storage)
- Stable power supply (recommended: official Raspberry Pi power supply)
- Network connectivity (WiFi or Ethernet)

### Software

- Raspberry Pi OS (or compatible Linux distribution with systemd)
- Python 3.9 or higher
- systemd with persistent journal enabled (standard on Raspberry Pi OS)
- Internet access for Telegram API

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/WaDoMa/HomeEmergencyButton.git
cd HomeEmergencyButton
```

### 2. Create Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# Or: .venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Required Python packages:**
- `python-telegram-bot` - Telegram Bot API wrapper
- `python-dotenv` - Environment variable management
- `nest-asyncio` - Asyncio compatibility for interactive environments

### 4. Configure Telegram

#### Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts to create your bot
3. Save the bot token provided by BotFather

#### Create Telegram Channels

Create two channels for different notification types:

1. **Technical Stats Channel**: For system health reports
   - Create a new Telegram channel
   - Add your bot as an administrator
   - Get the channel ID (e.g., `-1001234567890`)

2. **Emergency Alerts Channel**: For emergency button events (future use)
   - Create another Telegram channel
   - Add your bot as an administrator
   - Get the channel ID

**To find a channel ID:**
- Forward a message from the channel to `@userinfobot`
- Or use the Telegram API to get updates after adding the bot

#### Set Up Environment Variables

Create a `.env` file in the project root directory:
```bash
# .env file
TELEGRAM_BOT_TOKEN=your_bot_token_here
CHANNEL_ID_TechStats=-1001234567890
CHANNEL_ID_EmergencyAlerts=-1009876543210
DEBUG=false
```

**Security note**: Never commit the `.env` file to version control. It's already included in `.gitignore`.

### 5. Configure System for Enhanced Reliability

#### Enable Persistent Journal (Verify)

Most Raspberry Pi OS installations have persistent journaling enabled by default. Verify with:
```bash
ls -la /var/log/journal/
```

If the directory doesn't exist, enable persistent logging:
```bash
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo systemctl restart systemd-journald
```

#### Schedule Weekly Reboots

Configure a weekly reboot to trigger filesystem checks:
```bash
sudo crontab -e
```

Add the following line:
```cron
# Weekly reboot for filesystem maintenance (Home Emergency Button project)
0 3 * * 0 /sbin/shutdown -r now
```

This schedules a reboot every Sunday at 3:00 AM.

### 6. Install the System Service

The project includes an automated installation script that supports two modes:

#### Option A: User-Level Service (Recommended)

Installs the service under your user account with automatic boot startup:
```bash
chmod +x script/install_service.sh
./script/install_service.sh
```

This automatically:
- Creates the systemd user service
- Enables the service to start at boot
- Configures lingering so the service runs even when not logged in
- Starts the service immediately

#### Option B: System-Level Service

For production deployments requiring system-wide service:
```bash
sudo ./script/install_service.sh --system
```

### 7. Verify Installation

Check the service status:
```bash
# For user-level service
systemctl --user status emergency_button.service

# For system-level service
sudo systemctl status emergency_button.service
```

View real-time logs:
```bash
# For user-level service
journalctl --user -u emergency_button.service -f

# For system-level service
sudo journalctl -u emergency_button.service -f
```

## Usage

### Service Management

#### User-Level Service Commands
```bash
# Check service status
systemctl --user status emergency_button.service

# View logs
journalctl --user -u emergency_button.service -f

# Stop the service
systemctl --user stop emergency_button.service

# Restart the service
systemctl --user restart emergency_button.service

# Disable auto-start
systemctl --user disable emergency_button.service

# Re-enable auto-start
systemctl --user enable emergency_button.service
```

#### System-Level Service Commands
```bash
# Check service status
sudo systemctl status emergency_button.service

# View logs
sudo journalctl -u emergency_button.service -f

# Stop the service
sudo systemctl stop emergency_button.service

# Restart the service
sudo systemctl restart emergency_button.service
```

### Uninstalling the Service
```bash
./script/install_service.sh --uninstall
```

This automatically detects and removes the installed service (user or system level).

## Development

### Project Structure
```
HomeEmergencyButton/
├── script/
│   ├── emergency_button_notificator.py    # Main monitoring agent
│   └── install_service.sh                 # Service installation script
├── systemd/
│   └── emergency_button.service           # Systemd service definition
├── config/
│   └── buttons.ini                        # IoT button configuration (optional)
├── .venv/                                 # Python virtual environment
├── .env                                   # Environment variables (not in git)
├── .gitignore                            # Git ignore rules
├── requirements.txt                       # Python dependencies
└── README.md                             # This file
```

### Setting Up Development Environment

1. **Clone and enter the repository:**
```bash
git clone https://github.com/WaDoMa/HomeEmergencyButton.git
cd HomeEmergencyButton
```

2. **Create and activate virtual environment:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables** as described in the installation section

5. **Run the script manually for testing:**
```bash
python script/emergency_button_notificator.py
```

### Code Style and Philosophy

The codebase follows these principles:

- **Explicit imports**: Uses module-level imports with prefixes (e.g., `pathlib as pth`) for namespace clarity
- **Type hints**: Comprehensive type annotations for better code documentation
- **Error handling**: Functions return empty strings/lists on failure rather than raising exceptions
- **Modular design**: Separated concerns for logging, filtering, and reporting
- **Documentation**: Detailed docstrings following NumPy style

### Monitoring Strategy

The system uses journalctl for all kernel monitoring because it provides:

1. **Persistent logs across reboots** - Essential for weekly monitoring cycles
2. **Priority-based filtering** - Direct access to kernel error levels (err, warning, etc.)
3. **Time-range queries** - Can request logs from specific time periods (e.g., "last 7 days")
4. **Reliability** - Survives kernel ring buffer overflows that can lose dmesg messages

Key monitoring patterns:
- `get_kernel_errors()`: All kernel errors (priority "err") from last 7 days
- `get_sd_warnings()`: SD card issues combining priority warnings and keyword detection
- `get_power_thermal_events()`: Power/thermal issues with pattern exclusions
- `get_sd_fsck_report()`: Filesystem check results since current boot

### Contributing

When developing new features:

1. **Test filesystem operations** thoroughly - the system monitors critical storage
2. **Handle errors gracefully** - functions should return empty results rather than crash
3. **Use journalctl for kernel monitoring** - don't add dmesg dependencies
4. **Update documentation** - keep README and docstrings current
5. **Test service behavior** - verify restart and recovery mechanisms

### Debugging

Enable debug mode by setting the environment variable:
```bash
DEBUG=true
```

This provides additional output including:
- Configuration values (sanitized)
- Report contents before sending
- Detailed execution flow

## Monitoring and Maintenance

### Expected Behavior

- Service starts automatically after boot (typically within 30-60 seconds)
- Sends initial health report to Telegram on startup
- Report includes logs from the last 7 days, even if multiple reboots occurred
- Service restarts automatically if it crashes (30-second delay)

### System Health Report Contents

Each report includes:

1. **💾 Disk Usage**: Current filesystem capacity (all mounted filesystems)
2. **🛠 FSCK Results**: Filesystem check findings since current boot
3. **⚠ Kernel Errors**: All kernel errors (priority "err" and above) from last 7 days
4. **💿 SD Card Warnings**: SD card specific issues from last 7 days
5. **⚡ Power & Thermal Alerts**: Undervoltage, overtemperature, and throttling events from last 7 days

### Troubleshooting

#### Service Not Starting

Check the service logs:
```bash
journalctl --user -u emergency_button.service --no-pager
```

Common issues:
- Missing `.env` file or incorrect environment variables
- Virtual environment not created or dependencies not installed
- Incorrect file paths in service definition
- Persistent journal not enabled

#### No Telegram Messages

Verify:
- Bot token is correct in `.env`
- Channel IDs are correct (include the minus sign for channels)
- Bot has been added as administrator to channels
- Raspberry Pi has internet connectivity

Test connectivity:
```bash
# Test if Telegram API is reachable
curl -I https://api.telegram.org
```

#### Lingering Not Enabled

If service stops when you log out:
```bash
sudo loginctl enable-linger $USER
```

Verify it's enabled:
```bash
loginctl show-user $USER | grep Linger
```

Should show: `Linger=yes`

#### Missing Historical Logs

If reports don't show logs from previous boots:

1. Verify persistent journal is enabled:
```bash
ls -la /var/log/journal/
journalctl --list-boots
```

2. Check journal configuration:
```bash
grep Storage /etc/systemd/journald.conf
```

Should show: `Storage=persistent` or `Storage=auto` (default)

3. If needed, enable persistent logging:
```bash
sudo mkdir -p /var/log/journal
sudo systemd-tmpfiles --create --prefix /var/log/journal
sudo systemctl restart systemd-journald
```

## Security Considerations

- **Environment variables**: Never commit `.env` file to version control
- **Bot token**: Keep your Telegram bot token secret
- **Channel IDs**: Restrict channel access to authorized users only
- **File permissions**: Ensure service files are not world-writable
- **Network security**: Consider firewall rules if exposing services
- **Log retention**: journalctl retains logs based on `/etc/systemd/journald.conf` settings (default: use up to 10% of disk space)

## License

[Specify your license here]

## Acknowledgments

- Raspberry Pi Foundation for the hardware platform
- Telegram for the Bot API
- The Python community for excellent libraries
- systemd project for robust logging infrastructure

## Support

For issues, questions, or contributions:
- **GitHub Issues**: https://github.com/WaDoMa/HomeEmergencyButton/issues
- **Documentation**: https://github.com/WaDoMa/HomeEmergencyButton/README.md