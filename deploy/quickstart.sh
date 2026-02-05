#!/bin/bash
# Quick deployment script for Devilnet on Ubuntu/Debian

set -e

echo "====== Devilnet Quick Deployment ======"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo "ERROR: This script must be run as root (sudo)"
    exit 1
fi

# 1. Create system user
echo "[1/6] Creating dedicated system user..."
if id "devilnet" &>/dev/null; then
    echo "  User 'devilnet' already exists"
else
    useradd -r -s /bin/false devilnet
    echo "  Created user 'devilnet' (UID: $(id -u devilnet))"
fi

# 2. Create directories
echo "[2/6] Creating directories..."
mkdir -p /var/lib/devilnet
mkdir -p /var/log/devilnet/{alerts,reports}
chown -R devilnet:devilnet /var/lib/devilnet /var/log/devilnet
chmod -R 750 /var/lib/devilnet /var/log/devilnet
echo "  Created: /var/lib/devilnet, /var/log/devilnet"

# 3. Grant log access
echo "[3/6] Configuring log access..."
usermod -a -G adm devilnet 2>/dev/null || true
setfacl -m u:devilnet:r /var/log/auth.log 2>/dev/null || true
setfacl -m u:devilnet:r /var/log/syslog 2>/dev/null || true
echo "  Granted read access to system logs"

# 4. Setup Python environment
echo "[4/6] Setting up Python virtual environment..."
if [ ! -d "/var/lib/devilnet/venv" ]; then
    sudo -u devilnet python3 -m venv /var/lib/devilnet/venv
    echo "  Created venv"
    
    sudo -u devilnet /var/lib/devilnet/venv/bin/pip install --quiet --upgrade pip
    sudo -u devilnet /var/lib/devilnet/venv/bin/pip install --quiet \
        scikit-learn==1.3.2 \
        numpy==1.24.3
    echo "  Installed dependencies"
    
    chmod -R 555 /var/lib/devilnet/venv/lib/python*/site-packages
else
    echo "  venv already exists"
fi

# 5. Copy AppArmor profile
echo "[5/6] Loading AppArmor profile..."
if command -v apparmor_parser &> /dev/null; then
    cp deploy/apparmor/devilnet-ml /etc/apparmor.d/
    apparmor_parser -r /etc/apparmor.d/devilnet-ml 2>/dev/null || true
    echo "  AppArmor profile loaded"
else
    echo "  AppArmor not available (SELinux may be used instead)"
fi

# 6. Print status
echo "[6/6] Deployment complete!"
echo ""
echo "====== VERIFICATION ======"
echo "User: $(id devilnet)"
echo "Python: $(sudo -u devilnet /var/lib/devilnet/venv/bin/python3 --version)"
echo "Directories:"
ls -ld /var/lib/devilnet /var/log/devilnet
echo ""
echo "====== NEXT STEPS ======"
echo "1. Train model on baseline:"
echo "   sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine --train /path/to/baseline.jsonl"
echo ""
echo "2. Run demonstration:"
echo "   sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine --demo"
echo ""
echo "3. Single inference cycle:"
echo "   sudo -u devilnet /var/lib/devilnet/venv/bin/python3 -m devilnet.engine --once"
echo ""
echo "4. For production deployment, see: deploy/HARDENING_GUIDE.md"
echo ""
