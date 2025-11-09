#!/bin/sh
# OpenWRT Configuration Script for TP-Link Archer C7 v2
# Purpose: Create isolated WLAN for Amazon Dash Button with local access but no internet
# 
# EDIT THESE VARIABLES BEFORE RUNNING:
DASH_SSID="DashButton"           # SSID for the Dash Button WLAN
DASH_PASSWORD="YourSecurePass"   # WPA2 password (min 8 characters)
DASH_MAC_1="AA:BB:CC:DD:EE:FF"   # MAC address of first Amazon Dash Button
DASH_MAC_2=""                    # MAC address of second Dash Button (optional, leave empty if not used)
DASH_MAC_3=""                    # MAC address of third Dash Button (optional)
MAIN_SSID="YourMainWiFi"         # Your main WiFi SSID (optional, for reference)

# Network configuration
DASH_NETWORK="192.168.2.1"       # IP for the dash network gateway
DASH_NETMASK="255.255.255.0"
DASH_DHCP_START="100"
DASH_DHCP_LIMIT="50"

echo "=== Starting OpenWRT Configuration ==="
echo "This script will:"
echo "1. Create a new WLAN interface for Dash Button"
echo "2. Set up a separate network zone with local access"
echo "3. Block internet access for the Dash Button MAC"
echo "4. Allow LAN devices to discover the Dash Button"
echo ""

# ============================================================================
# STEP 1: Create new network interface for Dash Button WLAN
# ============================================================================
echo "[1/6] Creating network interface 'dash'..."

# Create new interface called 'dash' with static IP
uci set network.dash=interface
uci set network.dash.proto='static'
uci set network.dash.ipaddr="$DASH_NETWORK"
uci set network.dash.netmask="$DASH_NETMASK"
uci set network.dash.type='bridge'

# Enable DHCP server for dash network
uci set dhcp.dash=dhcp
uci set dhcp.dash.interface='dash'
uci set dhcp.dash.start="$DASH_DHCP_START"
uci set dhcp.dash.limit="$DASH_DHCP_LIMIT"
uci set dhcp.dash.leasetime='12h'

uci commit network
uci commit dhcp

# ============================================================================
# STEP 2: Create separate WLAN for Dash Button
# ============================================================================
echo "[2/6] Creating separate WLAN interface..."

# Find the 2.4GHz radio (usually radio0 on Archer C7 v2)
# The Dash Button only supports 2.4GHz
RADIO_24GHZ="radio0"

# Create new wireless interface
uci add wireless wifi-iface
uci set wireless.@wifi-iface[-1].device="$RADIO_24GHZ"
uci set wireless.@wifi-iface[-1].network='dash'
uci set wireless.@wifi-iface[-1].mode='ap'
uci set wireless.@wifi-iface[-1].ssid="$DASH_SSID"
uci set wireless.@wifi-iface[-1].encryption='psk2'
uci set wireless.@wifi-iface[-1].key="$DASH_PASSWORD"
uci set wireless.@wifi-iface[-1].isolate='0'  # Allow clients to see each other

# Ensure radio is enabled
uci set wireless.${RADIO_24GHZ}.disabled='0'

uci commit wireless

# ============================================================================
# STEP 3: Configure firewall zones
# ============================================================================
echo "[3/6] Configuring firewall zones..."

# Create firewall zone for dash network
uci add firewall zone
uci set firewall.@zone[-1].name='dash'
uci set firewall.@zone[-1].network='dash'
uci set firewall.@zone[-1].input='ACCEPT'
uci set firewall.@zone[-1].output='ACCEPT'
uci set firewall.@zone[-1].forward='REJECT'  # Default reject forwarding

# Allow dash zone to communicate with LAN (for local discovery)
uci add firewall forwarding
uci set firewall.@forwarding[-1].src='dash'
uci set firewall.@forwarding[-1].dest='lan'

# Allow LAN to communicate with dash zone (for ARP scans from Linux machine)
uci add firewall forwarding
uci set firewall.@forwarding[-1].src='lan'
uci set firewall.@forwarding[-1].dest='dash'

# ============================================================================
# STEP 4: Block Dash Button MAC addresses from accessing internet
# ============================================================================
echo "[4/6] Creating firewall rules to block Dash Button internet access..."

# Block traffic from first Dash Button MAC to WAN
if [ -n "$DASH_MAC_1" ]; then
    uci add firewall rule
    uci set firewall.@rule[-1].name='Block Dash Button 1 Internet'
    uci set firewall.@rule[-1].src='dash'
    uci set firewall.@rule[-1].dest='wan'
    uci set firewall.@rule[-1].src_mac="$DASH_MAC_1"
    uci set firewall.@rule[-1].target='REJECT'
    uci set firewall.@rule[-1].enabled='1'
    echo "  → Blocked MAC: $DASH_MAC_1"
fi

# Block traffic from second Dash Button MAC to WAN (if configured)
if [ -n "$DASH_MAC_2" ]; then
    uci add firewall rule
    uci set firewall.@rule[-1].name='Block Dash Button 2 Internet'
    uci set firewall.@rule[-1].src='dash'
    uci set firewall.@rule[-1].dest='wan'
    uci set firewall.@rule[-1].src_mac="$DASH_MAC_2"
    uci set firewall.@rule[-1].target='REJECT'
    uci set firewall.@rule[-1].enabled='1'
    echo "  → Blocked MAC: $DASH_MAC_2"
fi

# Block traffic from third Dash Button MAC to WAN (if configured)
if [ -n "$DASH_MAC_3" ]; then
    uci add firewall rule
    uci set firewall.@rule[-1].name='Block Dash Button 3 Internet'
    uci set firewall.@rule[-1].src='dash'
    uci set firewall.@rule[-1].dest='wan'
    uci set firewall.@rule[-1].src_mac="$DASH_MAC_3"
    uci set firewall.@rule[-1].target='REJECT'
    uci set firewall.@rule[-1].enabled='1'
    echo "  → Blocked MAC: $DASH_MAC_3"
fi

uci commit firewall

# ============================================================================
# STEP 5: Enable IP forwarding between LAN and dash network
# ============================================================================
echo "[5/6] Configuring routing..."

# This ensures packets can be routed between LAN and dash networks
# Already handled by firewall forwarding rules above

# ============================================================================
# STEP 6: Apply all changes and restart services
# ============================================================================
echo "[6/6] Applying configuration and restarting services..."

# Restart network service
/etc/init.d/network restart

# Wait a moment for network to stabilize
sleep 3

# Restart wireless
wifi reload

# Restart firewall
/etc/init.d/firewall restart

# Restart dnsmasq (DHCP server)
/etc/init.d/dnsmasq restart

echo ""
echo "=== Configuration Complete ==="
echo ""
echo "Summary:"
echo "- New WLAN SSID: $DASH_SSID"
echo "- Dash network: $DASH_NETWORK/$DASH_NETMASK"
[ -n "$DASH_MAC_1" ] && echo "- Blocked MAC 1: $DASH_MAC_1"
[ -n "$DASH_MAC_2" ] && echo "- Blocked MAC 2: $DASH_MAC_2"
[ -n "$DASH_MAC_3" ] && echo "- Blocked MAC 3: $DASH_MAC_3"
echo ""
echo "What you can do now:"
echo "1. Connect your Amazon Dash Button to SSID: $DASH_SSID"
echo "2. From your LAN machine, scan with: sudo arp-scan --interface=eth0 --localnet"
echo "   Or scan dash network: sudo arp-scan 192.168.2.0/24"
echo "3. The Dash Button can be discovered by devices in LAN and dash networks"
echo "4. The Dash Button CANNOT access the internet"
echo ""
echo "To verify configuration:"
echo "  uci show network | grep dash"
echo "  uci show wireless | grep -A 10 wifi-iface"
echo "  uci show firewall | grep -A 5 'dash\|Dash'"
echo ""