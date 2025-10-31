#!/usr/bin/env bash
# -*- coding: utf-8 -*-
#
# Installation script for Home Emergency Button Agent systemd service
#
# This script installs and configures the emergency button service as a
# user-level systemd service. It automatically detects the project directory
# and sets up the service without requiring manual path configuration.
#
# Usage:
#   ./install_service.sh [OPTIONS]
#
# Options:
#   --system       Install as system-level service (requires sudo, runs at boot)
#   --user         Install as user-level service (default, requires lingering for boot)
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
USER_SYSTEMD_DIR="${HOME}/.config/systemd/user"
SYSTEM_SYSTEMD_DIR="/etc/systemd/system"
INSTALL_MODE="user"  # Default to user-level service

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

Usage: $0 [OPTIONS]

Options:
    --user         Install as user-level service (default, requires lingering)
    --system       Install as system-level service (requires sudo, auto-starts at boot)
    --uninstall    Remove the service and disable it
    --help         Show this help message

Installation Modes:
    User-level (--user):
      - Service runs under your user account
      - Requires 'loginctl enable-linger' to start at boot
      - Does not require sudo for installation
      - Service file: ~/.config/systemd/user/emergency_button.service

    System-level (--system):
      - Service runs at system boot automatically
      - Requires sudo for installation
      - Service file: /etc/systemd/system/emergency_button.service
      - Recommended for production deployments

Examples:
    $0                    Install as user service (default)
    $0 --user             Install as user service (explicit)
    $0 --system           Install as system service (requires sudo)
    $0 --uninstall        Remove the service

EOF
    exit 0
}

check_prerequisites() {
    print_info "Checking prerequisites..."
    
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
        print_warning "And install dependencies: ${VENV_PYTHON} -m pip install -r requirements.txt"
    fi
    
    print_success "Prerequisites check completed"
}

install_service() {
    print_info "Installing ${SERVICE_NAME} in ${INSTALL_MODE} mode..."
    
    if [[ "${INSTALL_MODE}" == "system" ]]; then
        install_system_service
    else
        install_user_service
    fi
}

install_user_service() {
    # Create user systemd directory if it doesn't exist
    if [[ ! -d "${USER_SYSTEMD_DIR}" ]]; then
        mkdir -p "${USER_SYSTEMD_DIR}"
        print_success "Created directory: ${USER_SYSTEMD_DIR}"
    fi
    
    # Copy service file
    cp "${SERVICE_FILE}" "${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
    print_success "Copied service file to ${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
    
    # Reload systemd daemon
    systemctl --user daemon-reload
    print_success "Reloaded systemd daemon"
    
    # Enable service
    systemctl --user enable "${SERVICE_NAME}"
    print_success "Enabled ${SERVICE_NAME}"
    
    # Start service
    systemctl --user start "${SERVICE_NAME}"
    print_success "Started ${SERVICE_NAME}"
    
    # Enable lingering (allows service to run even when user is not logged in)
    if loginctl enable-linger "${USER}" 2>/dev/null; then
        print_success "Enabled lingering for user ${USER}"
        print_info "Service will now start automatically at boot"
    else
        print_warning "Could not enable lingering. Service will stop when you log out."
        print_info "To enable it manually, run: sudo loginctl enable-linger ${USER}"
    fi
    
    echo ""
    print_success "Installation completed successfully!"
    echo ""
    print_info "Service status:"
    systemctl --user status "${SERVICE_NAME}" --no-pager || true
    
    echo ""
    print_info "Useful commands:"
    echo "  Check status:    systemctl --user status ${SERVICE_NAME}"
    echo "  View logs:       journalctl --user -u ${SERVICE_NAME} -f"
    echo "  Stop service:    systemctl --user stop ${SERVICE_NAME}"
    echo "  Restart service: systemctl --user restart ${SERVICE_NAME}"
    echo "  Disable service: systemctl --user disable ${SERVICE_NAME}"
}

install_system_service() {
    # Check for sudo
    if [[ $EUID -ne 0 ]]; then
        print_error "System-level installation requires root privileges."
        print_info "Please run: sudo $0 --system"
        exit 1
    fi
    
    # Create a temporary service file with substituted paths
    TEMP_SERVICE_FILE=$(mktemp)
    sed "s|USER_TO_RUN_AS|${SUDO_USER:-${USER}}|g" "${SERVICE_FILE}" > "${TEMP_SERVICE_FILE}"
    
    # Copy service file
    cp "${TEMP_SERVICE_FILE}" "${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}"
    rm "${TEMP_SERVICE_FILE}"
    print_success "Copied service file to ${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}"
    
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
    print_info "Service status:"
    systemctl status "${SERVICE_NAME}" --no-pager || true
    
    echo ""
    print_info "Useful commands:"
    echo "  Check status:    sudo systemctl status ${SERVICE_NAME}"
    echo "  View logs:       sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  Stop service:    sudo systemctl stop ${SERVICE_NAME}"
    echo "  Restart service: sudo systemctl restart ${SERVICE_NAME}"
    echo "  Disable service: sudo systemctl disable ${SERVICE_NAME}"
}

uninstall_service() {
    print_info "Uninstalling ${SERVICE_NAME}..."
    
    # Detect which mode is installed
    USER_INSTALLED=false
    SYSTEM_INSTALLED=false
    
    if [[ -f "${USER_SYSTEMD_DIR}/${SERVICE_NAME}" ]]; then
        USER_INSTALLED=true
    fi
    
    if [[ -f "${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}" ]]; then
        SYSTEM_INSTALLED=true
    fi
    
    if [[ "${USER_INSTALLED}" == false ]] && [[ "${SYSTEM_INSTALLED}" == false ]]; then
        print_warning "Service is not installed"
        exit 0
    fi
    
    # Uninstall user service
    if [[ "${USER_INSTALLED}" == true ]]; then
        print_info "Removing user-level service..."
        
        if systemctl --user is-active --quiet "${SERVICE_NAME}"; then
            systemctl --user stop "${SERVICE_NAME}"
            print_success "Stopped user service"
        fi
        
        if systemctl --user is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
            systemctl --user disable "${SERVICE_NAME}"
            print_success "Disabled user service"
        fi
        
        rm "${USER_SYSTEMD_DIR}/${SERVICE_NAME}"
        systemctl --user daemon-reload
        print_success "Removed user service file"
    fi
    
    # Uninstall system service
    if [[ "${SYSTEM_INSTALLED}" == true ]]; then
        if [[ $EUID -ne 0 ]]; then
            print_error "System-level service removal requires root privileges."
            print_info "Please run: sudo $0 --uninstall"
            exit 1
        fi
        
        print_info "Removing system-level service..."
        
        if systemctl is-active --quiet "${SERVICE_NAME}"; then
            systemctl stop "${SERVICE_NAME}"
            print_success "Stopped system service"
        fi
        
        if systemctl is-enabled --quiet "${SERVICE_NAME}" 2>/dev/null; then
            systemctl disable "${SERVICE_NAME}"
            print_success "Disabled system service"
        fi
        
        rm "${SYSTEM_SYSTEMD_DIR}/${SERVICE_NAME}"
        systemctl daemon-reload
        print_success "Removed system service file"
    fi
    
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
        --system)
            INSTALL_MODE="system"
            check_prerequisites
            install_service
            ;;
        --user)
            INSTALL_MODE="user"
            check_prerequisites
            install_service
            ;;
        --uninstall)
            check_prerequisites
            uninstall_service
            ;;
        "")
            # Default to user mode
            INSTALL_MODE="user"
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