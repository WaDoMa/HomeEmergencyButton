#!/bin/sh
# OpenWRT Configuration UNDO Script
# Purpose: Remove all Dash Button configurations created by the setup script
#
# WARNING: This will remove:
# - The 'dash' network interface
# - The Dash Button WLAN
# - All firewall rules and zones related to 'dash'
# - DHCP configuration for dash network

echo "=== OpenWRT Dash Button Configuration UNDO Script ==="
echo ""
echo "This script will remove ALL configurations created by the Dash Button setup."
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Undo cancelled."
    exit 0
fi

echo ""
echo "Starting removal process..."
echo ""

# ============================================================================
# STEP 1: Remove wireless interface for Dash Button WLAN
# ============================================================================
echo "[1/5] Removing Dash Button WLAN interface..."

# Find and remove all wifi-iface entries that use the 'dash' network
WIFI_IFACE_COUNT=0
while uci -q get wireless.@wifi-iface[$WIFI_IFACE_COUNT] > /dev/null 2>&1; do
    NETWORK=$(uci -q get wireless.@wifi-iface[$WIFI_IFACE_COUNT].network)
    if [ "$NETWORK" = "dash" ]; then
        echo "  → Removing wifi-iface #$WIFI_IFACE_COUNT (network=dash)"
        uci delete wireless.@wifi-iface[$WIFI_IFACE_COUNT]
        # Don't increment counter after deletion as indices shift
    else
        WIFI_IFACE_COUNT=$((WIFI_IFACE_COUNT + 1))
    fi
done

uci commit wireless

# ============================================================================
# STEP 2: Remove firewall rules for Dash Buttons
# ============================================================================
echo "[2/5] Removing firewall rules..."

# Remove all firewall rules related to Dash Buttons
RULE_COUNT=0
while uci -q get firewall.@rule[$RULE_COUNT] > /dev/null 2>&1; do
    RULE_NAME=$(uci -q get firewall.@rule[$RULE_COUNT].name)
    RULE_SRC=$(uci -q get firewall.@rule[$RULE_COUNT].src)
    
    # Check if rule is related to dash network or has "Dash Button" in name
    if [ "$RULE_SRC" = "dash" ] || echo "$RULE_NAME" | grep -qi "dash"; then
        echo "  → Removing rule: $RULE_NAME"
        uci delete firewall.@rule[$RULE_COUNT]
        # Don't increment counter after deletion
    else
        RULE_COUNT=$((RULE_COUNT + 1))
    fi
done

# ============================================================================
# STEP 3: Remove firewall forwarding rules
# ============================================================================
echo "[3/5] Removing firewall forwarding rules..."

# Remove forwarding rules for dash zone
FORWARD_COUNT=0
while uci -q get firewall.@forwarding[$FORWARD_COUNT] > /dev/null 2>&1; do
    FWD_SRC=$(uci -q get firewall.@forwarding[$FORWARD_COUNT].src)
    FWD_DEST=$(uci -q get firewall.@forwarding[$FORWARD_COUNT].dest)
    
    if [ "$FWD_SRC" = "dash" ] || [ "$FWD_DEST" = "dash" ]; then
        echo "  → Removing forwarding: $FWD_SRC → $FWD_DEST"
        uci delete firewall.@forwarding[$FORWARD_COUNT]
        # Don't increment counter after deletion
    else
        FORWARD_COUNT=$((FORWARD_COUNT + 1))
    fi
done

# ============================================================================
# STEP 4: Remove firewall zone
# ============================================================================
echo "[4/5] Removing firewall zone 'dash'..."

ZONE_COUNT=0
while uci -q get firewall.@zone[$ZONE_COUNT] > /dev/null 2>&1; do
    ZONE_NAME=$(uci -q get firewall.@zone[$ZONE_COUNT].name)
    
    if [ "$ZONE_NAME" = "dash" ]; then
        echo "  → Removing zone: dash"
        uci delete firewall.@zone[$ZONE_COUNT]
        # Don't increment counter after deletion
    else
        ZONE_COUNT=$((ZONE_COUNT + 1))
    fi
done

uci commit firewall

# ============================================================================
# STEP 5: Remove DHCP and network interface
# ============================================================================
echo "[5/5] Removing network interface and DHCP configuration..."

# Remove DHCP configuration for dash network
if uci -q get dhcp.dash > /dev/null 2>&1; then
    echo "  → Removing DHCP configuration for 'dash'"
    uci delete dhcp.dash
    uci commit dhcp
fi

# Remove network interface
if uci -q get network.dash > /dev/null 2>&1; then
    echo "  → Removing network interface 'dash'"
    uci delete network.dash
    uci commit network
fi

# ============================================================================
# Apply all changes and restart services
# ============================================================================
echo ""
echo "Applying changes and restarting services..."

# Restart services in correct order
/etc/init.d/network restart
sleep 2
wifi reload
/etc/init.d/firewall restart
/etc/init.d/dnsmasq restart

echo ""
echo "=== Removal Complete ==="
echo ""
echo "All Dash Button configurations have been removed."
echo "Your router has been restored to its previous state."
echo ""
echo "To verify removal:"
echo "  uci show network | grep dash        # Should return nothing"
echo "  uci show wireless | grep dash       # Should return nothing"
echo "  uci show firewall | grep -i dash    # Should return nothing"
echo "  uci show dhcp | grep dash           # Should return nothing"
echo ""