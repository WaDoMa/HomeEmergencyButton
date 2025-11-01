#!/usr/bin/env python3
"""
Amazon Dash Button Detector
Detects when Dash buttons are pressed by monitoring ARP packets
"""

import scapy.all
import datetime

# Add your Dash Button MAC addresses here (find them by monitoring network first)
DASH_BUTTONS = {
    'ac:63:be:xx:xx:xx': 'Kitchen Button',
    '50:f5:da:xx:xx:xx': 'Living Room Button',
    # Add more buttons here
}

def button_pressed(mac_address, button_name):
    """Called when a button press is detected"""
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {button_name} pressed! (MAC: {mac_address})")
    
    # Add your custom actions here
    # Examples:
    # - Send notification
    # - Control smart home devices
    # - Run shell commands
    # - Make API calls

def packet_handler(packet):
    """Process each ARP packet"""
    if packet.haslayer(scapy.all.ARP):
        mac = packet[scapy.all.ARP].hwsrc.lower()
        
        if mac in DASH_BUTTONS:
            button_name = DASH_BUTTONS[mac]
            button_pressed(mac, button_name)

def find_dash_buttons(duration=60):
    """
    Discovery mode: Monitor network for specified duration to find button MACs
    Press your buttons during this time to identify their MAC addresses
    """
    print(f"Discovery mode: Monitoring for {duration} seconds...")
    print("Press your Dash buttons now to identify their MAC addresses\n")
    
    detected = {}
    
    def discover_handler(packet):
        if packet.haslayer(scapy.all.ARP):
            mac = packet[scapy.all.ARP].hwsrc.lower()
            if mac not in detected:
                # Filter for likely Dash button MACs (Amazon OUI prefixes)
                if mac.startswith(('ac:63:be', '50:f5:da', '74:75:48', 
                                  '18:74:2e', '00:fc:8b', '68:54:fd',
                                  'a0:02:dc', '74:c2:46', '84:d6:d0')):
                    detected[mac] = datetime.datetime.now()
                    print(f"Found potential Dash button: {mac}")
    
    scapy.all.sniff(prn=discover_handler, filter="arp", timeout=duration, store=False)
    
    print("\n=== Discovered Devices ===")
    for mac, timestamp in detected.items():
        print(f"MAC: {mac} (detected at {timestamp.strftime('%H:%M:%S')})")
    print("\nAdd these MACs to the DASH_BUTTONS dictionary")

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'discover':
        # Discovery mode
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        find_dash_buttons(duration)
    else:
        # Normal monitoring mode
        print("Amazon Dash Button Monitor Started")
        print("Monitoring for button presses... (Ctrl+C to stop)\n")
        
        if not DASH_BUTTONS:
            print("WARNING: No buttons configured!")
            print("Run with 'discover' argument to find button MAC addresses:")
            print("  sudo python3 dash_detector.py discover\n")
        
        try:
            # Sniff ARP packets (requires root/sudo)
            scapy.all.sniff(prn=packet_handler, filter="arp", store=False)
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped")
        except PermissionError:
            print("ERROR: This script requires root privileges")
            print("Run with: sudo python3 dash_detector.py")

if __name__ == '__main__':
    main()