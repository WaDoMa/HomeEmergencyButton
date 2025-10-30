# Home Emergency Button
A Raspberry Pi-based emergency alert agent.


## SD Card Health Monitoring Workflow 

To maximize reliabilty and detect early signs of SD card degradation, the Raspberry Pi emergency button project
implements a weekly filesystem check combined with automated monitoring and reporting:

### 1. Weekly Filesystem System
- A forced filesystem check (fsck) runs on all partitions during a weekly reboot.
- It is triggered by a cron job.
- This ensures that minor filesystem errors are repaired before they escalate, increasing the operational availibilty.

### 2. Kernel and Systems Logs Monitoring
- Kernel warnings and errors related to the SD card are monitored to detect read/write retries, coorupted blocks, or other anomalies that *fsck* may not catch.
- Relevant logs are collected from:
    - *journalctl* (last 7 days)
    - *dmesg* (current boot)
    - *system-fsck* service logs

### 3. Automated Reportimg via Telegram
- A Python service runs after boot and aggregates the reports.
- Only relevant lines related to SD card issues are included:
    - *fsck* repair or corruption messages
    - Kernel warnings/errors
    - dmesg error lines
- The summary is sent via Telegram to a designated channel, providing eraly warning of SD card wear or filesystem problems.

### 4. Benefits
- Continuous monitoring of SD card health without manual intervention.
- Early detection of failing SD cards before critical data loss or failing of alerting system occurs.
- Centralized reporting allows remote observation of system reliabitly.

### Compact Workflow
Weekly cron → reboot → force fsck on all partitions → Python monitoring service collects fsck/journalctl/dmesg logs → filter SD card issues → send report via Telegram


## System Configuration

## 1. Increase Filesystem Robustness on the Raspberry Pi

### Edit the kernel command line
Open the boot configuration file for editing:
```shell
sudo nano /boot/firmware/cmdline.txt
```
Add the following parameters (append on the same line) to force filesystem checks and automatic repairs on every boot:
```text
fsck.mode=force fsck.repair=yes
```
Save and exit the editor.

### Schedule Weekly Reboots to Trigger Filesystem Checks
Edit the root user's crontab:
```shell
sudo crontab -e
```
Add a cron job to reboot every Saturday at 3:00 AM:
```text
# Weekly reboot to trigger filesystem check, part of Home Emergency Button project maintenance
0 3 * * Saturday /usr/bin/touch /forcefsck && /sbin/shutdown -r now

```
This schedule ensures a regular reboot that triggers the filesystem check, increasing system stability.

## 2. Create a System Service to Launch `emergency_button_notificator.py` on Startup

### Copy the Service Definition File
Copy the service file to the systemd directory:
```shell
sudo cp ./system_configuration/emergency_button_notificator.service /etc/systemd/system/emergency_button_notificator.service
```
### Make the Python Script Executable
Set the script as executable:
```shell
sudo chmod +x ./script/emergency_button_notificator.py
```
### Enable and Start the Service
Reload systemd, enable the service to start on boot, and start it immediately:
```shell
sudo systemctl daemon-reload
sudo systemctl enable emergency_button_notificator.service
sudo systemctl start emergency_button_notificator.service
```

## 3. Install Dependencies

```shell
pip install scapy dotenv configparser python-telegram-bot
```
## 4. Create Telegram Ressources

Create Telegram bot by @BotFather and create environment variable with its' TELEGRAM_BOT_TOKEN.
Search Bot by its' username '@mybotname' and start it by pressing start button or by sending '/start'.
Create Telegram Channel for technical stats, search bot and add it as adminstrator. Create environment variable with its' CANNEL_ID.
Create Telegram Channel for the alert messages and create environment variable with its' CANNEL_ID.

