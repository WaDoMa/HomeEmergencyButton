# Home Emergency Button

A Raspberry Pi-based emergency alert system that monitors system health and Amazon Dash button events, providing reliable notifications via Telegram.

## Project Overview

This project implements a resilient emergency alerting system designed for continuous operation on Raspberry Pi hardware. The system focuses on two key functions:

1. **System Health Monitoring**: Continuous monitoring of SD card health, kernel errors, and power/thermal events with persistent logs across reboots
2. **Emergency Button Detection**: Real-time detection and notification of Amazon Dash button press events via ARP packet monitoring

### Design Philosophy

The project prioritizes **reliability and early failure detection** through:

- Proactive SD card health monitoring to prevent system failures
- Weekly automated reboots with filesystem checks to repair errors before they escalate
- Persistent logging via systemd journal for tracking issues across boot cycles
- Automated reporting for remote system observation
- Real-time emergency button monitoring for immediate alerts

## Features

### Current Capabilities

- **Persistent Kernel Error Monitoring**: Tracks all kernel errors (priority "err" and above) from the last 7 days using journalctl, surviving reboots
- **SD Card Health Monitoring**: Detects filesystem errors, read/write issues, block corruption, and MMC/block device failures
- **Power/Thermal Monitoring**: Tracks undervoltage events, overtemperature conditions, and throttling
- **FSCK Integration**: Monitors filesystem check results since last boot
- **Disk Usage Reporting**: Regular filesystem capacity monitoring
- **Amazon Dash Button Detection**: Real-time monitoring of emergency button presses via ARP packet sniffing
- **Dual Telegram Channels**: Separate channels for system health reports and emergency alerts
- **Button Discovery Mode**: Built-in tool to identify Dash button MAC addresses
- **Debouncing**: Prevents duplicate alerts from repeated button presses
- **Automated Telegram Notifications**: Sends consolidated health reports and emergency alerts to designated channels
- **Service Management**: Runs as a systemd service with automatic restart on failure

## System Architecture

### Monitoring Workflow
```
Weekly cron → Reboot → Force fsck on all partitions → 
Emergency Alert Agent starts → Sends system health report (once) →
Monitors for button presses (continuous) →
Sends emergency alerts on button events
```

### Dual Channel Strategy

The system uses two separate Telegram channels for different purposes:

1. **Technical Stats Channel** (📊): Receives system health reports once per boot cycle
   - Disk usage statistics
   - Filesystem check results
   - Kernel errors from last 7 days
   - SD card warnings
   - Power/thermal events

2. **Emergency Alerts Channel** (🚨): Receives immediate notifications when emergency buttons are pressed
   - Button identification
   - Timestamp
   - MAC address
   - Instant alert delivery

### Log Sources

The system aggregates information from multiple sources:

- **journalctl**: System journal entries (kernel messages from last 7 days, persistent across reboots)
- **systemd-fsck**: Filesystem check service logs (since current boot)
- **df**: Disk usage statistics
- **ARP packets**: Network traffic for Dash button detection (via scapy)

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
- Amazon Dash buttons (one or more)

### Software

- Raspberry Pi OS (or compatible Linux distribution with systemd)
- Python 3.9 or higher
- systemd with persistent journal enabled (standard on Raspberry Pi OS)
- Internet access for Telegram API
- Root privileges for packet sniffing (required for button detection)

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
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Required Python packages:**
- `python-telegram-bot` - Telegram Bot API wrapper
- `python-dotenv` - Environment variable management
- `scapy` - Network packet sniffing for button detection
- `nest-asyncio` - Asyncio compatibility for interactive environments

**System dependencies for Scapy (if not already installed):**
```bash
# Debian/Ubuntu/Raspberry Pi OS
sudo apt-get install python3-dev libpcap-dev
```

### 4. Configure Telegram

#### Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts to create your bot
3. Save the bot token provided by BotFather

#### Create Telegram Channels

Create two channels for different notification types:

1. **Technical Stats Channel** (📊): For system health reports
   - Create a new Telegram channel (e.g., "Emergency System - Tech Stats")
   - Add your bot as an administrator
   - Get the channel ID (see below)

2. **Emergency Alerts Channel** (🚨): For emergency button events
   - Create another Telegram channel (e.g., "Emergency System - Alerts")
   - Add your bot as an administrator
   - Get the channel ID

**To find a channel ID:**
1. Add your bot as administrator to the channel
2. Forward any message from the channel to `@userinfobot` or `@RawDataBot`
3. The bot will reply with the channel information including the ID
4. Channel IDs are negative numbers starting with `-100` (e.g., `-1001234567890`)

#### Set Up Environment Variables

Create a `.env` file in the project root directory:
```bash
# .env file
TELEGRAM_BOT_TOKEN=your_bot_token_here
CHANNEL_ID_TechStats=-1001234567890
CHANNEL_ID_Alerts=-1009876543210
DEBUG=false
```

**Security note**: Never commit the `.env` file to version control. It's already included in `.gitignore`.

### 5. Configure Emergency Buttons

#### Discover Your Dash Button MAC Addresses

Run the script in discovery mode to find your button MAC addresses:

```bash
sudo python3 script/emergency_alert_agent.py discover
```

This will monitor your network for 60 seconds. Press your Dash buttons during this time, and the script will display their MAC addresses.

Example output:
```
Discovery mode: Monitoring for 60 seconds...
Press your Dash buttons now to identify their MAC addresses

✓ Found potential Dash button: ac:63:be:12:34:56
✓ Found potential Dash button: 50:f5:da:78:90:ab

=== Discovered Devices ===
MAC: ac:63:be:12:34:56 (detected at 14:23:15)
MAC: 50:f5:da:78:90:ab (detected at 14:23:42)

Add these to your config/buttons.ini file:
[Buttons]
ac:63:be:12:34:56 = Button 1
50:f5:da:78:90:ab = Button 2
```

#### Configure Buttons

Create or edit `config/buttons.ini`:

```ini
[Buttons]
ac:63:be:12:34:56 = Kitchen Emergency Button
50:f5:da:78:90:ab = Bedroom Emergency Button
```

Replace the MAC addresses with your actual button MACs, and give each button a descriptive name.

### 6. Configure System for Enhanced Reliability

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

### 7. Install the System Service

The project includes an automated installation script. Since button monitoring requires root privileges for packet sniffing, install as a system service:

```bash
chmod +x script/install_service.sh
sudo ./script/install_service.sh
```

This automatically:
- Creates the systemd service with root privileges (required for packet sniffing)
- Enables the service to start at boot
- Starts the service immediately
- Configures absolute paths for your project location

### 8. Verify Installation

Check the service status:
```bash
sudo systemctl status emergency_button.service
```

View real-time logs:
```bash
sudo journalctl -u emergency_button.service -f
```

You should see:
1. Initial system health report being sent
2. Button monitoring starting
3. "Monitoring for emergency button presses..." message

## Usage

### Operating Modes

The script supports three operating modes:

#### 1. Monitor Mode (Default - Continuous Operation)
```bash
sudo python3 script/emergency_alert_agent.py
```

This is the primary mode for production use:
- Sends system health report once at startup
- Monitors for emergency button presses continuously
- Sends alerts immediately when buttons are pressed
- Runs until interrupted or system shutdown

#### 2. Discovery Mode (Find Button MAC Addresses)
```bash
sudo python3 script/emergency_alert_agent.py discover
```

Use this mode to identify your Dash button MAC addresses:
- Monitors network for 60 seconds
- Displays MAC addresses of detected Dash buttons
- No Telegram configuration required for this mode

#### 3. Report-Only Mode (Single Report)
```bash
python3 script/emergency_alert_agent.py report
```

Sends a single system health report and exits:
- Useful for manual health checks
- Does not require root privileges
- Does not monitor buttons

### Service Management

#### System-Level Service Commands
```bash
# Check service status
sudo systemctl status emergency_button.service

# View logs (real-time)
sudo journalctl -u emergency_button.service -f

# View all logs
sudo journalctl -u emergency_button.service --no-pager

# Stop the service
sudo systemctl stop emergency_button.service

# Restart the service
sudo systemctl restart emergency_button.service

# Disable auto-start
sudo systemctl disable emergency_button.service

# Re-enable auto-start
sudo systemctl enable emergency_button.service
```

### Testing Emergency Buttons

Once the service is running, simply press your configured Dash buttons. You should receive:

1. An immediate alert in your Emergency Alerts Telegram channel
2. Button identification and timestamp
3. Console log entry (visible via `journalctl`)

**Note**: Buttons have built-in debouncing (5 seconds) to prevent duplicate alerts from repeated presses.

### Uninstalling the Service
```bash
sudo ./script/install_service.sh --uninstall
```

This automatically removes the system service.

## Development

### Project Structure
```
HomeEmergencyButton/
├── script/
│   ├── emergency_alert_agent.py           # Main monitoring agent
│   └── install_service.sh                 # Service installation script
├── systemd/
│   └── emergency_button.service           # Systemd service definition
├── config/
│   └── buttons.ini                        # Dash button configuration
├── .venv/                                 # Python virtual environment
├── .env                                   # Environment variables (not in git)
├── .gitignore                             # Git ignore rules
├── requirements.txt                       # Python dependencies
└── README.md                              # This file
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
# Discovery mode (find buttons)
sudo python3 script/emergency_alert_agent.py discover

# Report-only mode (no root needed)
python3 script/emergency_alert_agent.py report

# Full monitoring mode (requires root)
sudo python3 script/emergency_alert_agent.py
```

### Code Style and Philosophy

The codebase follows these principles:

- **Explicit imports**: Uses module-level imports with prefixes (e.g., `pathlib as pth`) for namespace clarity
- **Type hints**: Comprehensive type annotations for better code documentation
- **Error handling**: Graceful degradation - functions return empty strings/lists on failure
- **Modular design**: Separated concerns for logging, filtering, reporting, and button detection
- **Thread safety**: Proper async/threaded integration for packet sniffing
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

### Button Detection Architecture

The button detection system uses:

1. **Scapy ARP monitoring**: Detects when Dash buttons send ARP packets (happens on button press)
2. **Thread-based sniffing**: Runs packet capture in a separate thread to not block asyncio
3. **Debouncing**: 5-second window to prevent duplicate alerts
4. **Async messaging**: Thread-safe integration with Telegram bot using `asyncio.run_coroutine_threadsafe()`

### Contributing

When developing new features:

1. **Test filesystem operations** thoroughly - the system monitors critical storage
2. **Handle errors gracefully** - functions should return empty results rather than crash
3. **Use journalctl for kernel monitoring** - don't add dmesg dependencies
4. **Test button detection** - verify ARP packet handling and debouncing
5. **Maintain thread safety** - ensure proper async/thread integration
6. **Update documentation** - keep README and docstrings current
7. **Test service behavior** - verify restart and recovery mechanisms

### Debugging

Enable debug mode by setting the environment variable:
```bash
DEBUG=true
```

This provides additional output including:
- Configuration values (sanitized)
- Report contents before sending
- Button press events (including debounced ones)
- Detailed execution flow

## Monitoring and Maintenance

### Expected Behavior

After installation and startup:

1. Service starts automatically after boot (typically within 30-60 seconds)
2. Sends initial system health report to Technical Stats channel
3. Begins monitoring for button presses
4. Sends immediate alerts to Emergency Alerts channel when buttons are pressed
5. System health reports are sent once per boot cycle (weekly with scheduled reboots)
6. Service restarts automatically if it crashes (30-second delay)

### System Health Report Contents

Each report includes:

1. **💾 Disk Usage**: Current filesystem capacity (all mounted filesystems)
2. **🛠 FSCK Results**: Filesystem check findings since current boot
3. **⚠ Kernel Errors**: All kernel errors (priority "err" and above) from last 7 days
4. **💿 SD Card Warnings**: SD card specific issues from last 7 days
5. **⚡ Power & Thermal Alerts**: Undervoltage, overtemperature, and throttling events from last 7 days

### Emergency Alert Format

When a button is pressed, you receive:

```
🚨 EMERGENCY ALERT 🚨

Button: Kitchen Emergency Button
MAC: ac:63:be:12:34:56
Time: 2024-11-02 14:23:15

⚠️ Immediate attention required!
```

### Troubleshooting

#### Service Not Starting

Check the service logs:
```bash
sudo journalctl -u emergency_button.service --no-pager
```

Common issues:
- Missing `.env` file or incorrect environment variables
- Virtual environment not created or dependencies not installed
- Incorrect file paths in service definition
- Missing `config/buttons.ini` file
- Insufficient permissions (service needs root for packet sniffing)

#### Button Detection Not Working

Verify:
1. Service is running with root privileges:
   ```bash
   sudo systemctl status emergency_button.service
   ```

2. Buttons are configured in `config/buttons.ini`

3. MAC addresses are correct (use discovery mode to verify)

4. Buttons are on the same network as the Raspberry Pi

5. Check logs for permission errors:
   ```bash
   sudo journalctl -u emergency_button.service | grep -i permission
   ```

Common issues:
- Service not running as root (required for packet sniffing)
- Incorrect MAC addresses in configuration
- Buttons on different network/VLAN
- Scapy dependencies not installed

#### No Telegram Messages

Verify:
- Bot token is correct in `.env`
- Channel IDs are correct (include the minus sign for channels, e.g., `-1001234567890`)
- Bot has been added as administrator to both channels
- Raspberry Pi has internet connectivity

Test connectivity:
```bash
# Test if Telegram API is reachable
curl -I https://api.telegram.org
```

#### Duplicate Button Alerts

If you're receiving multiple alerts for single button presses:
- Check the debounce setting in the code (`BUTTON_DEBOUNCE_SECONDS`)
- Verify button press logs to see if multiple ARP packets are being sent
- Consider increasing debounce time if needed

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
- **Root privileges**: Service runs as root for packet sniffing - ensure code is trusted
- **File permissions**: Ensure service files are not world-writable
- **Network security**: Button detection monitors ARP traffic on local network only
- **Log retention**: journalctl retains logs based on `/etc/systemd/journald.conf` settings (default: use up to 10% of disk space)

## FAQ

### Q: Why do I need root privileges?
**A**: Packet sniffing (required for detecting Dash button presses via ARP packets) requires root privileges on Linux systems.

### Q: How often are system reports sent?
**A**: System health reports are sent once per boot cycle. With weekly reboots, you receive one report per week.

### Q: Can I use different types of buttons?
**A**: The system is designed for Amazon Dash buttons, which send ARP packets when pressed. Other IoT buttons that use ARP/network communication may work, but Amazon Dash buttons with specific MAC address prefixes are officially supported.

### Q: What happens if my internet connection drops?
**A**: The service continues monitoring. Telegram messages will fail to send but the service remains running. Once connectivity is restored, new alerts will be sent normally.

### Q: Can I add more buttons later?
**A**: Yes! Run discovery mode, add the new MAC addresses to `config/buttons.ini`, and restart the service.

### Q: How do I change the debounce time?
**A**: Edit `BUTTON_DEBOUNCE_SECONDS` in `emergency_alert_agent.py` and restart the service.

## License

[Specify your license here]

## Acknowledgments

- Raspberry Pi Foundation for the hardware platform
- Telegram for the Bot API
- Amazon for Dash buttons
- Scapy developers for packet sniffing capabilities
- The Python community for excellent libraries
- systemd project for robust logging infrastructure

## Support

For issues, questions, or contributions:
- **GitHub Issues**: https://github.com/WaDoMa/HomeEmergencyButton/issues
- **Documentation**: https://github.com/WaDoMa/HomeEmergencyButton/README.md

## Changelog

### Version 2.0 (Current)
- Added Amazon Dash button detection via ARP packet monitoring
- Implemented dual Telegram channel architecture (Tech Stats + Emergency Alerts)
- Added button discovery mode for MAC address identification
- Implemented debouncing for button presses
- Changed system reports to once-per-boot instead of periodic
- Added thread-safe async messaging for button events
- Enhanced error handling and logging
- Updated documentation with button configuration guide

### Version 1.0
- Initial release with system health monitoring
- Persistent journal-based logging
- Weekly reboot scheduling
- Telegram notifications for system health