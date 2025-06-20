#!/bin/bash

# AIOps Enterprise Installation Script
# Automated installer for the Autonomous Incident Management System
# Supports Linux, macOS, and Windows (WSL)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
AIOPS_VERSION="1.0.0"
AIOPS_HOME="${INSTALL_DIR:-/opt/aiops}"
AIOPS_USER="${AIOPS_USER:-aiops}"
PYTHON_VERSION="3.11"
REPO_URL="https://github.com/aiops-platform/aiops-system.git"

# Flags
INSTALL_DEMO_DATA=true
ENABLE_SYSTEMD=true
CONFIGURE_FIREWALL=false
SETUP_SSL=false
INTERACTIVE_MODE=true

# Print functions
print_header() {
    echo -e "${PURPLE}"
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                    AIOps Enterprise Installation                     ║"
    echo "║                 Autonomous Incident Management System                ║"
    echo "║                            Version $AIOPS_VERSION                            ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Helper functions
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

get_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*)    echo "windows";;
        MINGW*)     echo "windows";;
        *)          echo "unknown";;
    esac
}

get_distro() {
    if [[ "$(get_os)" == "linux" ]]; then
        if command_exists lsb_release; then
            lsb_release -si | tr '[:upper:]' '[:lower:]'
        elif [[ -f /etc/os-release ]]; then
            . /etc/os-release
            echo "$ID"
        elif [[ -f /etc/redhat-release ]]; then
            echo "rhel"
        else
            echo "unknown"
        fi
    fi
}

check_requirements() {
    log_step "Checking system requirements..."
    
    local os=$(get_os)
    local distro=$(get_distro)
    
    log_info "Operating System: $os"
    [[ "$os" == "linux" ]] && log_info "Distribution: $distro"
    
    # Check architecture
    local arch=$(uname -m)
    log_info "Architecture: $arch"
    
    if [[ "$arch" != "x86_64" && "$arch" != "aarch64" && "$arch" != "arm64" ]]; then
        log_error "Unsupported architecture: $arch"
        exit 1
    fi
    
    # Check available memory
    local memory_gb
    case "$os" in
        "linux")
            memory_gb=$(free -g | awk '/^Mem:/{print $2}')
            ;;
        "macos")
            memory_gb=$(($(sysctl -n hw.memsize) / 1024 / 1024 / 1024))
            ;;
    esac
    
    log_info "Available Memory: ${memory_gb}GB"
    
    if [[ $memory_gb -lt 8 ]]; then
        log_warning "Minimum 8GB RAM recommended. Current: ${memory_gb}GB"
        if [[ $INTERACTIVE_MODE == true ]]; then
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
    
    # Check disk space
    local available_space_gb
    case "$os" in
        "linux"|"macos")
            available_space_gb=$(df -BG "${AIOPS_HOME%/*}" 2>/dev/null | awk 'NR==2 {print $4}' | sed 's/G//' || echo "0")
            ;;
    esac
    
    log_info "Available Disk Space: ${available_space_gb}GB"
    
    if [[ $available_space_gb -lt 50 ]]; then
        log_warning "Minimum 50GB disk space recommended. Current: ${available_space_gb}GB"
        if [[ $INTERACTIVE_MODE == true ]]; then
            read -p "Continue anyway? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                exit 1
            fi
        fi
    fi
    
    log_success "System requirements check completed"
}

install_dependencies() {
    log_step "Installing system dependencies..."
    
    local os=$(get_os)
    local distro=$(get_distro)
    
    case "$os" in
        "linux")
            case "$distro" in
                "ubuntu"|"debian")
                    sudo apt update
                    sudo apt install -y \
                        python${PYTHON_VERSION} \
                        python${PYTHON_VERSION}-venv \
                        python${PYTHON_VERSION}-dev \
                        python3-pip \
                        git \
                        curl \
                        wget \
                        build-essential \
                        libpq-dev \
                        redis-server \
                        postgresql \
                        postgresql-contrib \
                        nginx \
                        systemd \
                        ufw \
                        jq \
                        htop \
                        screen
                    ;;
                "centos"|"rhel"|"fedora")
                    if command_exists dnf; then
                        sudo dnf install -y \
                            python${PYTHON_VERSION} \
                            python${PYTHON_VERSION}-devel \
                            python3-pip \
                            git \
                            curl \
                            wget \
                            gcc \
                            gcc-c++ \
                            postgresql-devel \
                            redis \
                            postgresql-server \
                            nginx \
                            systemd \
                            firewalld \
                            jq \
                            htop \
                            screen
                    else
                        sudo yum install -y \
                            python${PYTHON_VERSION} \
                            python${PYTHON_VERSION}-devel \
                            python3-pip \
                            git \
                            curl \
                            wget \
                            gcc \
                            gcc-c++ \
                            postgresql-devel \
                            redis \
                            postgresql-server \
                            nginx \
                            systemd \
                            firewalld \
                            jq \
                            htop \
                            screen
                    fi
                    ;;
                "arch")
                    sudo pacman -Sy --noconfirm \
                        python \
                        python-pip \
                        git \
                        curl \
                        wget \
                        base-devel \
                        postgresql \
                        redis \
                        nginx \
                        systemd \
                        ufw \
                        jq \
                        htop \
                        screen
                    ;;
            esac
            ;;
        "macos")
            if ! command_exists brew; then
                log_info "Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            fi
            
            brew update
            brew install \
                python@${PYTHON_VERSION} \
                git \
                postgresql \
                redis \
                nginx \
                jq \
                htop \
                screen
            ;;
    esac
    
    log_success "System dependencies installed"
}

create_user() {
    log_step "Creating AIOps system user..."
    
    if ! id "$AIOPS_USER" &>/dev/null; then
        case "$(get_os)" in
            "linux")
                sudo useradd -r -m -d "$AIOPS_HOME" -s /bin/bash "$AIOPS_USER"
                ;;
            "macos")
                # On macOS, we'll use the current user
                AIOPS_USER=$(whoami)
                ;;
        esac
        log_success "Created user: $AIOPS_USER"
    else
        log_info "User $AIOPS_USER already exists"
    fi
}

setup_directories() {
    log_step "Setting up directories..."
    
    sudo mkdir -p "$AIOPS_HOME"
    sudo mkdir -p "$AIOPS_HOME"/{config,logs,data,backups,scripts,models}
    sudo mkdir -p /var/log/aiops
    sudo mkdir -p /etc/aiops
    
    # Set ownership
    sudo chown -R "$AIOPS_USER:$AIOPS_USER" "$AIOPS_HOME"
    sudo chown -R "$AIOPS_USER:$AIOPS_USER" /var/log/aiops
    sudo chown -R "$AIOPS_USER:$AIOPS_USER" /etc/aiops
    
    log_success "Directories created and configured"
}

install_aiops() {
    log_step "Installing AIOps application..."
    
    # Switch to AIOps user for installation
    sudo -u "$AIOPS_USER" bash << EOF
set -euo pipefail

cd "$AIOPS_HOME"

# Clone repository or copy current files
if [[ -d ".git" ]]; then
    log_info "Using existing repository..."
    git pull origin main || true
else
    log_info "Setting up AIOps files..."
    # Copy files from current directory if we're in the source
    if [[ -f "$(pwd)/test_aiops.py" ]]; then
        cp -r . "$AIOPS_HOME/"
    else
        log_error "AIOps source files not found. Please run this script from the AIOps directory."
        exit 1
    fi
fi

# Create Python virtual environment
log_info "Creating Python virtual environment..."
python${PYTHON_VERSION} -m venv venv
source venv/bin/activate

# Upgrade pip and install requirements
log_info "Installing Python dependencies..."
pip install --upgrade pip setuptools wheel

# Install core packages
pip install \
    scikit-learn==1.7.0 \
    pandas==2.3.0 \
    numpy==2.3.0 \
    matplotlib==3.10.3 \
    seaborn==0.13.2 \
    prophet==1.1.7 \
    openai==1.88.0 \
    click==8.2.1 \
    rich==14.0.0 \
    pydantic==2.11.7 \
    asyncio-mqtt==0.16.2 \
    prometheus-client==0.22.1 \
    elasticsearch==9.0.2 \
    redis==6.2.0 \
    psutil==7.0.0 \
    watchdog==6.0.0 \
    schedule==1.2.2 \
    flask==3.1.1 \
    flask-cors==6.0.1 \
    requests==2.32.4 \
    python-dotenv==1.1.0 \
    jsonschema==4.24.0

log_success "Python dependencies installed"
EOF

    log_success "AIOps application installed"
}

configure_services() {
    log_step "Configuring system services..."
    
    # Create systemd service files
    if [[ "$ENABLE_SYSTEMD" == true && "$(get_os)" == "linux" ]]; then
        
        # AIOps Engine Service
        sudo tee /etc/systemd/system/aiops-engine.service > /dev/null << EOF
[Unit]
Description=AIOps ML Engine
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

[Service]
Type=simple
User=$AIOPS_USER
Group=$AIOPS_USER
WorkingDirectory=$AIOPS_HOME
Environment=PATH=$AIOPS_HOME/venv/bin
ExecStart=$AIOPS_HOME/venv/bin/python test_aiops.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=aiops-engine

[Install]
WantedBy=multi-user.target
EOF

        # AIOps Dashboard Service
        sudo tee /etc/systemd/system/aiops-dashboard.service > /dev/null << EOF
[Unit]
Description=AIOps Web Dashboard
After=network.target aiops-engine.service
Wants=aiops-engine.service

[Service]
Type=simple
User=$AIOPS_USER
Group=$AIOPS_USER
WorkingDirectory=$AIOPS_HOME
Environment=PATH=$AIOPS_HOME/venv/bin
ExecStart=$AIOPS_HOME/venv/bin/python web_dashboard.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=aiops-dashboard

[Install]
WantedBy=multi-user.target
EOF

        # Reload systemd and enable services
        sudo systemctl daemon-reload
        sudo systemctl enable aiops-engine aiops-dashboard
        
        log_success "Systemd services configured"
    fi
}

setup_database() {
    log_step "Setting up database..."
    
    case "$(get_os)" in
        "linux")
            # Start and enable PostgreSQL
            sudo systemctl start postgresql
            sudo systemctl enable postgresql
            
            # Start and enable Redis
            sudo systemctl start redis
            sudo systemctl enable redis
            ;;
        "macos")
            # Start services with brew
            brew services start postgresql
            brew services start redis
            ;;
    esac
    
    # Setup PostgreSQL database
    sudo -u postgres bash << EOF || true
createuser $AIOPS_USER
createdb aiops_db -O $AIOPS_USER
psql -c "ALTER USER $AIOPS_USER PASSWORD 'aiops_secure_password';"
EOF

    log_success "Database configured"
}

create_configuration() {
    log_step "Creating configuration files..."
    
    # Create main environment file
    sudo -u "$AIOPS_USER" tee "$AIOPS_HOME/.env" > /dev/null << EOF
# AIOps Configuration
AIOPS_ENV=production
AIOPS_SECRET_KEY=$(openssl rand -hex 32)
AIOPS_DEBUG=false

# Database Configuration
DATABASE_URL=postgresql://$AIOPS_USER:aiops_secure_password@localhost:5432/aiops_db
REDIS_URL=redis://localhost:6379/0

# ML/AI Configuration (Add your OpenAI API key)
OPENAI_API_KEY=
ML_MODEL_PATH=$AIOPS_HOME/models
ENABLE_PREDICTIONS=true

# Monitoring Configuration
PROMETHEUS_URL=http://localhost:9090
ELASTICSEARCH_URL=http://localhost:9200

# Security Configuration
JWT_SECRET=$(openssl rand -hex 32)
API_RATE_LIMIT=1000
ENABLE_CORS=true
ALLOWED_HOSTS=localhost,127.0.0.1

# Performance Configuration
WORKER_CONCURRENCY=4
MAX_MEMORY_USAGE=4GB
CACHE_TTL=3600

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=$AIOPS_HOME/logs/aiops.log
EOF

    # Create logging configuration
    sudo -u "$AIOPS_USER" tee "$AIOPS_HOME/config/logging.conf" > /dev/null << EOF
[loggers]
keys=root,aiops

[handlers]
keys=consoleHandler,fileHandler

[formatters]
keys=simpleFormatter

[logger_root]
level=INFO
handlers=consoleHandler

[logger_aiops]
level=INFO
handlers=consoleHandler,fileHandler
qualname=aiops
propagate=0

[handler_consoleHandler]
class=StreamHandler
level=INFO
formatter=simpleFormatter
args=(sys.stdout,)

[handler_fileHandler]
class=FileHandler
level=INFO
formatter=simpleFormatter
args=('$AIOPS_HOME/logs/aiops.log',)

[formatter_simpleFormatter]
format=%(asctime)s - %(name)s - %(levelname)s - %(message)s
EOF

    log_success "Configuration files created"
}

setup_demo_data() {
    if [[ "$INSTALL_DEMO_DATA" == true ]]; then
        log_step "Setting up demo data..."
        
        sudo -u "$AIOPS_USER" bash << EOF
cd "$AIOPS_HOME"
source venv/bin/activate

# Generate demo data
if [[ -f "demo_data_generator.py" ]]; then
    python demo_data_generator.py
    log_success "Demo data generated"
else
    log_warning "Demo data generator not found"
fi
EOF
    fi
}

configure_firewall() {
    if [[ "$CONFIGURE_FIREWALL" == true ]]; then
        log_step "Configuring firewall..."
        
        case "$(get_distro)" in
            "ubuntu"|"debian")
                sudo ufw --force enable
                sudo ufw allow ssh
                sudo ufw allow 80/tcp
                sudo ufw allow 443/tcp
                sudo ufw allow 5000/tcp  # AIOps Dashboard
                sudo ufw allow 8000/tcp  # AIOps API
                ;;
            "centos"|"rhel"|"fedora")
                sudo systemctl start firewalld
                sudo systemctl enable firewalld
                sudo firewall-cmd --permanent --add-service=ssh
                sudo firewall-cmd --permanent --add-service=http
                sudo firewall-cmd --permanent --add-service=https
                sudo firewall-cmd --permanent --add-port=5000/tcp
                sudo firewall-cmd --permanent --add-port=8000/tcp
                sudo firewall-cmd --reload
                ;;
        esac
        
        log_success "Firewall configured"
    fi
}

create_startup_script() {
    log_step "Creating startup script..."
    
    sudo -u "$AIOPS_USER" tee "$AIOPS_HOME/scripts/start_aiops.sh" > /dev/null << 'EOF'
#!/bin/bash

# AIOps Startup Script
set -euo pipefail

AIOPS_HOME="${AIOPS_HOME:-/opt/aiops}"
cd "$AIOPS_HOME"

echo "Starting AIOps system..."

# Activate virtual environment
source venv/bin/activate

# Check if configuration exists
if [[ ! -f ".env" ]]; then
    echo "Error: Configuration file .env not found"
    exit 1
fi

# Load environment variables
source .env

# Start services
echo "Starting AIOps components..."

# Run system health check
if [[ -f "test_aiops.py" ]]; then
    echo "Running system health check..."
    python test_aiops.py > /dev/null 2>&1 && echo "✓ System health check passed" || echo "⚠ System health check failed"
fi

# Start web dashboard in background
if [[ -f "web_dashboard.py" ]]; then
    echo "Starting web dashboard on port 5000..."
    nohup python web_dashboard.py > logs/dashboard.log 2>&1 &
    echo $! > logs/dashboard.pid
fi

echo "AIOps system started successfully!"
echo "Web interface: http://localhost:5000"
echo "View logs: tail -f logs/*.log"
EOF

    chmod +x "$AIOPS_HOME/scripts/start_aiops.sh"
    
    # Create stop script
    sudo -u "$AIOPS_USER" tee "$AIOPS_HOME/scripts/stop_aiops.sh" > /dev/null << 'EOF'
#!/bin/bash

# AIOps Stop Script
set -euo pipefail

AIOPS_HOME="${AIOPS_HOME:-/opt/aiops}"
cd "$AIOPS_HOME"

echo "Stopping AIOps system..."

# Stop web dashboard
if [[ -f "logs/dashboard.pid" ]]; then
    PID=$(cat logs/dashboard.pid)
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Stopped web dashboard (PID: $PID)"
    fi
    rm -f logs/dashboard.pid
fi

# Kill any remaining Python processes
pkill -f "python.*aiops" || true

echo "AIOps system stopped"
EOF

    chmod +x "$AIOPS_HOME/scripts/stop_aiops.sh"
    
    log_success "Startup scripts created"
}

run_tests() {
    log_step "Running initial tests..."
    
    sudo -u "$AIOPS_USER" bash << EOF
cd "$AIOPS_HOME"
source venv/bin/activate

# Test basic functionality
if [[ -f "test_aiops.py" ]]; then
    echo "Running AIOps functionality test..."
    timeout 60 python test_aiops.py > logs/test_output.log 2>&1 && echo "✓ Basic functionality test passed" || echo "⚠ Basic functionality test had issues"
fi

# Test high-level enhancements
if [[ -f "high_level_aiops_enhancements.py" ]]; then
    echo "Running enhancement capabilities test..."
    timeout 30 python high_level_aiops_enhancements.py > logs/enhancement_test.log 2>&1 && echo "✓ Enhancement test passed" || echo "⚠ Enhancement test had issues"
fi
EOF

    log_success "Initial tests completed"
}

print_completion_info() {
    log_success "AIOps installation completed successfully!"
    
    echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    Installation Summary                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════════════╝${NC}"
    
    echo -e "\n${CYAN}Installation Directory:${NC} $AIOPS_HOME"
    echo -e "${CYAN}AIOps User:${NC} $AIOPS_USER"
    echo -e "${CYAN}Configuration:${NC} $AIOPS_HOME/.env"
    echo -e "${CYAN}Logs:${NC} $AIOPS_HOME/logs/"
    
    echo -e "\n${YELLOW}Quick Start Commands:${NC}"
    echo -e "  Start AIOps:     ${GREEN}$AIOPS_HOME/scripts/start_aiops.sh${NC}"
    echo -e "  Stop AIOps:      ${GREEN}$AIOPS_HOME/scripts/stop_aiops.sh${NC}"
    echo -e "  View logs:       ${GREEN}tail -f $AIOPS_HOME/logs/*.log${NC}"
    echo -e "  Run demo:        ${GREEN}cd $AIOPS_HOME && source venv/bin/activate && python test_aiops.py${NC}"
    
    if [[ "$ENABLE_SYSTEMD" == true && "$(get_os)" == "linux" ]]; then
        echo -e "\n${YELLOW}Systemd Service Commands:${NC}"
        echo -e "  Start services:  ${GREEN}sudo systemctl start aiops-engine aiops-dashboard${NC}"
        echo -e "  Stop services:   ${GREEN}sudo systemctl stop aiops-engine aiops-dashboard${NC}"
        echo -e "  Check status:    ${GREEN}sudo systemctl status aiops-engine${NC}"
        echo -e "  View logs:       ${GREEN}sudo journalctl -u aiops-engine -f${NC}"
    fi
    
    echo -e "\n${YELLOW}Web Interfaces:${NC}"
    echo -e "  Dashboard:       ${GREEN}http://localhost:5000${NC}"
    echo -e "  API:             ${GREEN}http://localhost:8000${NC}"
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo -e "  1. ${BLUE}Configure OpenAI API key in $AIOPS_HOME/.env${NC}"
    echo -e "  2. ${BLUE}Review configuration settings${NC}"
    echo -e "  3. ${BLUE}Start the AIOps system${NC}"
    echo -e "  4. ${BLUE}Access the web dashboard${NC}"
    echo -e "  5. ${BLUE}Read the documentation: FEATURES_GUIDE.md${NC}"
    
    echo -e "\n${GREEN}Support:${NC}"
    echo -e "  Documentation:   INSTALLATION_GUIDE.md"
    echo -e "  Features Guide:  FEATURES_GUIDE.md"
    echo -e "  Deployment:      DEPLOYMENT_GUIDE.md"
    
    if [[ ! -f "$AIOPS_HOME/.env" ]] || ! grep -q "OPENAI_API_KEY=sk-" "$AIOPS_HOME/.env" 2>/dev/null; then
        echo -e "\n${RED}⚠ Important:${NC} Set your OpenAI API key in $AIOPS_HOME/.env for full AI capabilities"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --install-dir)
            AIOPS_HOME="$2"
            shift 2
            ;;
        --user)
            AIOPS_USER="$2"
            shift 2
            ;;
        --no-demo-data)
            INSTALL_DEMO_DATA=false
            shift
            ;;
        --no-systemd)
            ENABLE_SYSTEMD=false
            shift
            ;;
        --configure-firewall)
            CONFIGURE_FIREWALL=true
            shift
            ;;
        --setup-ssl)
            SETUP_SSL=true
            shift
            ;;
        --non-interactive)
            INTERACTIVE_MODE=false
            shift
            ;;
        --help)
            echo "AIOps Installation Script"
            echo ""
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --install-dir DIR     Installation directory (default: /opt/aiops)"
            echo "  --user USER           System user for AIOps (default: aiops)"
            echo "  --no-demo-data        Skip demo data generation"
            echo "  --no-systemd          Skip systemd service creation"
            echo "  --configure-firewall  Configure firewall rules"
            echo "  --setup-ssl           Setup SSL certificates"
            echo "  --non-interactive     Run without user prompts"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main installation flow
main() {
    print_header
    
    # Pre-installation checks
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root. Please run as a regular user with sudo privileges."
        exit 1
    fi
    
    if ! command_exists sudo; then
        log_error "sudo is required but not installed. Please install sudo first."
        exit 1
    fi
    
    # Installation steps
    check_requirements
    install_dependencies
    create_user
    setup_directories
    install_aiops
    setup_database
    create_configuration
    configure_services
    setup_demo_data
    configure_firewall
    create_startup_script
    run_tests
    print_completion_info
    
    log_success "AIOps installation completed successfully!"
}

# Error handling
trap 'log_error "Installation failed at line $LINENO. Check the logs for details."' ERR

# Run main installation
main "$@"