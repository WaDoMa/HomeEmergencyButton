# Home Emergency Button

A Raspberry Pi-based emergency alert system that monitors system health and IoT button events, providing reliable notifications via Telegram.

## Project Overview

This project implements a resilient emergency alerting system designed for continuous operation on Raspberry Pi hardware. The system focuses on two key functions:

1. **System Health Monitoring**: Continuous monitoring of SD card health, kernel warnings, and power/thermal events
2. **Emergency Button Integration**: Detection and notification of IoT button press events (in development)

### Design Philosophy

The project prioritizes **reliability and early failure detection** through:

- Proactive SD card health monitoring to prevent system failures
- Weekly filesystem checks to repair errors before they escalate
- Automated logging and reporting for remote system observation
- Graceful error handling and recovery mechanisms
- Minimal dependencies to reduce failure points

## Features

### Current Capabilities

- **SD Card Health Monitoring**: Detects filesystem errors, read/write issues, and block corruption
- **Kernel Log Analysis**: Monitors kernel warnings and errors related to storage devices
- **Power/Thermal Monitoring**: Tracks undervoltage events, overtemperature conditions, and throttling
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
Emergency Alert Agent starts → Collects logs from journalctl/dmesg/fsck → 
Filters relevant issues → Sends report via Telegram
```

### Log Sources

The system aggregates information from multiple sources:

- **journalctl**: System journal entries (configurable time range, default 7 days)
- **dmesg**: Kernel ring buffer (current boot)
- **systemd-fsck**: Filesystem check service logs
- **df**: Disk usage statistics

## Prerequisites

### Hardware

- Raspberry Pi (any model with SD card storage)
- Stable power supply (recommended: official Raspberry Pi power supply)
- Network connectivity (WiFi or Ethernet)

### Software

- Raspberry Pi OS (or compatible Linux distribution)
- Python 3.9 or higher
- systemd (standard on Raspberry Pi OS)
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

#### Schedule Weekly Reboots

Configure a weekly reboot to trigger filesystem checks:
```bash
sudo crontab -e
```

Add the following line:
```cron
# Weekly reboot for filesystem maintenance (Home Emergency Button project)
0 3 * * Saturday /sbin/shutdown -r now
```

This schedules a reboot every Saturday at 3:00 AM.

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
- **Error handling**: Graceful degradation with informative error messages
- **Modular design**: Separated concerns for logging, filtering, and reporting
- **Documentation**: Detailed docstrings following NumPy style

### Contributing

When developing new features:

1. **Test filesystem operations** thoroughly - the system monitors critical storage
2. **Handle errors gracefully** - the service must continue running despite failures
3. **Log appropriately** - use proper logging levels (info, warning, error)
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
- Monitors system continuously for new events
- Restarts automatically if it crashes (30-second delay)

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

#### No Telegram Messages

Verify:
- Bot token is correct in `.env`
- Channel IDs are correct (include the minus sign for channels)
- Bot has been added as administrator to channels
- Raspberry Pi has internet connectivity

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

## Security Considerations

- **Environment variables**: Never commit `.env` file to version control
- **Bot token**: Keep your Telegram bot token secret
- **Channel IDs**: Restrict channel access to authorized users only
- **File permissions**: Ensure service files are not world-writable
- **Network security**: Consider firewall rules if exposing services

## License

[Specify your license here]

## Acknowledgments

- Raspberry Pi Foundation for the hardware platform
- Telegram for the Bot API
- The Python community for excellent libraries

## Support

For issues, questions, or contributions:
- **GitHub Issues**: https://github.com/WaDoMa/HomeEmergencyButton/issues
- **Documentation**: https://github.com/WaDoMa/HomeEmergencyButton/README.md