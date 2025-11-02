#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# Installation script for Home Emergency Button Notification systemd service
#
# This script installs and configures the emergency button service as a
# system-level service (requires root for packet sniffing).
#
# Usage:
#   ./install_service.sh [OPTIONS]
#
# Options:
#   --uninstall    Remove the service
#   --help         Show this help message
#
# Author: Your Name
# Created: YYYY-MM-DD

set -e  # Exit on error

# ------------------- Configuration ------------------- #
SERVICE_NAME="emergency_button.service"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_FILE="${PROJECT_DIR}/systemd/${SERVICE_NAME}"
SYSTEM_SYSTEMD_DIR="/etc/systemd/system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ------------------- Helper Functions ------------------- #
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1" >&2
}

show_help() {
    cat << EOF
Home Emergency Button Service Installer

Usage: sudo $0 [OPTIONS]

Options:
    --uninstall    Remove the service and disable it
    --help         Show this help message

Installation:
    The service is installed as a system-level service that:
      - Runs as root (required for packet sniffing with scapy)
      - Starts automatically at boot
      - Monitors for Dash button presses via ARP packets
      - Sends system health reports and emergency alerts via Telegram

    Note: Root privileges are required because packet sniffing (scapy)
          needs raw network access to detect Dash button ARP packets.

Examples:
    sudo $0                Install the service
    sudo $0 --uninstall    Remove the service

EOF
    exit 0
}

check_prerequisites() {
    print_info "Checking prerequisites..."
    
    # Check for sudo/root
    if [[ $EUID -ne 0 ]]; then
        print_error "This script must be run as root (requires packet sniffing capabilities)."
        print_info "Please run: sudo $0"
        exit 1
    fi
    
    # Check if systemd is available
    if ! command -v systemctl &> /dev/null; then
        print_error "systemctl not found. This script requires systemd."
        exit 1
    fi
    
    # Check if service file exists
    if [[ ! -f "${SERVICE_FILE}" ]]; then
        print_error "Service file not found: ${SERVICE_FILE}"
        print_info "Expected project structure:"
        print_info "  HomeEmergencyButton/"
        print_info "  ├── script/"
        print_info "  │   └── install_service.sh"
        print_info "  └── systemd/"
        print_info "      └── ${SERVICE_NAME}"
        exit 1
    fi
    
    # Check if Python script exists
    PYTHON_SCRIPT="${PROJECT_DIR}/script/emergency_button_notificator.py"
    if [[ ! -f "${PYTHON_SCRIPT}" ]]; then
        print_warning "Python script not found: ${PYTHON_SCRIPT}"
        print_warning "Service may not start correctly."
    fi
    
    # Check if virtual environment exists
    VENV_PYTHON="${PROJECT_DIR}/.venv/bin/python3"
    if [[ ! -f "${VENV_PYTHON}" ]]; then
        print_warning "Virtual environment not found: ${PROJECT_DIR}/.venv"
        print_warning "Please create it with: python3 -m venv ${PROJECT_DIR}/.venv"
        print_warning "And install dependencies: ${VENV_PYTHON} -m pip install -r ${PROJECT_DIR}/requirements.txt"
    fi
    
    # Check if .env file exists
    if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
        print_warning ".env file not found: ${PROJECT_DIR}/.env"
        print_warning "Service requires:"
        print_warning "  - TELEGRAM_BOT_TOKEN"
        print_warning "  - CHANNEL_ID_TechStats"
        print_warning "  - CHANNEL_ID_Alerts"
    fi
    
    # Check if buttons.ini exists
    if [[ ! -f "${PROJECT_DIR}/config/buttons.ini" ]]; then
        print_warning "Button configuration not found: ${PROJECT_DIR}/config/buttons.ini"
        print_info "Run discovery mode to find button MAC addresses:"
        print_info "  sudo ${PYTHON_SCRIPT} discover"
    fi
    
    print_success "Prerequisites check completed"
}

install_service() {
    print_info "Installing ${SERVICE_NAME} as system service..."
    
    # Create a temporary service file with substituted paths
    TEMP_SERVICE_FILE=$(mktemp)
    
    # Replace %h with the actual project directory's parent (to avoid /root path issue)
    # Since User=root and %h would resolve to /root, we need absolute paths
    sed "s|%h/HomeEmergencyButton|${PROJECT_DIR}|g" "${SERVICE_FILE}" > "${TEMP_SERVICE_FILE}"
    
    # Copy service file
    cp "${TEMP_SERVICE_FILE}" "${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}"
    rm "${TEMP_SERVICE_FILE}"
    print_success "Installed service file to ${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}"
    
    # Show the actual paths being used
    print_info "Service configuration:"
    print_info "  Project directory: ${PROJECT_DIR}"
    print_info "  Python script: ${PROJECT_DIR}/script/emergency_button_notificator.py"
    print_info "  Virtual environment: ${PROJECT_DIR}/.venv"
    
    # Reload systemd daemon
    systemctl daemon-reload
    print_success "Reloaded systemd daemon"
    
    # Enable service
    systemctl enable "${SERVICE_NAME}"
    print_success "Enabled ${SERVICE_NAME}"
    
    # Start service
    systemctl start "${SERVICE_NAME}"
    print_success "Started ${SERVICE_NAME}"
    
    echo ""
    print_success "Installation completed successfully!"
    print_info "Service will start automatically at boot"
    echo ""
    
    # Wait a moment for service to start
    sleep 2
    
    print_info "Service status:"
    systemctl status "${SERVICE_NAME}" --no-pager || true
    
    echo ""
    print_info "Useful commands:"
    echo "  Check status:    sudo systemctl status ${SERVICE_NAME}"
    echo "  View logs:       sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  Stop service:    sudo systemctl stop ${SERVICE_NAME}"
    echo "  Restart service: sudo systemctl restart ${SERVICE_NAME}"
    echo "  Disable service: sudo systemctl disable ${SERVICE_NAME}"
    echo ""
    print_info "Check recent logs:"
    echo "  sudo journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
}

uninstall_service() {
    print_info "Uninstalling ${SERVICE_NAME}..."
    
    # Check for sudo/root
    if [[ $EUID -ne 0 ]]; then
        print_error "Service removal requires root privileges."
        print_info "Please run: sudo $0 --uninstall"
        exit 1
    fi
    
    # Check if service is installed
    if [[ ! -f "${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}" ]]; then
        print_warning "Service is not installed"
        exit 0
    fi
    
    # Stop service if running
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        systemctl stop "${SERVICE_NAME}"
        print_success "Stopped service"
    fi
    
    # Disable service if enabled
    if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
        systemctl disable "${SERVICE_NAME}"
        print_success "Disabled service"
    fi
    
    # Remove service file
    rm "${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}"
    systemctl daemon-reload
    print_success "Removed service file"
    
    echo ""
    print_success "Uninstallation completed successfully!"
}

# ------------------- Main Script ------------------- #
main() {
    # Parse arguments
    case "${1:-}" in
        --help|-h)
            show_help
            ;;
        --uninstall)
            check_prerequisites
            uninstall_service
            ;;
        "")
            # Default: install
            check_prerequisites
            install_service
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
}

main "$@"