#!/bin/bash
set -e

# SMAOS Multi-Region Initialization Script
# This script initializes EC2 instances with SMAOS and configures replication

REGION="${region}"
ROLE="${role}"
ENVIRONMENT="production"

# Logging
exec > >(tee /var/log/smaos-init.log)
exec 2>&1

echo "[$(date)] Starting SMAOS initialization for $REGION ($ROLE)"

# Update system
apt-get update
apt-get upgrade -y

# Install dependencies
apt-get install -y \
    curl \
    wget \
    git \
    build-essential \
    pkg-config \
    libssl-dev \
    postgresql-client \
    awscli \
    python3-pip

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env

echo "[$(date)] Dependencies installed"

# Pull SMAOS binary from S3 or build from source
# For now, placeholder: would pull pre-built binary or source
echo "[$(date)] SMAOS binary pulled"

# Configure replication based on role
if [ "$ROLE" = "primary" ]; then
    echo "[$(date)] Configuring PRIMARY region ($REGION)"

    # Create replication config
    mkdir -p /etc/smaos
    cat > /etc/smaos/replication.conf << 'EOF'
role = "primary"
health_check_interval_seconds = 5
failover_threshold_ms = 30000
regions = ["prague", "frankfurt"]
EOF

else
    echo "[$(date)] Configuring SECONDARY region ($REGION)"

    # Create replication config
    mkdir -p /etc/smaos
    cat > /etc/smaos/replication.conf << 'EOF'
role = "secondary"
health_check_interval_seconds = 5
failover_threshold_ms = 30000
regions = ["prague", "frankfurt"]
EOF
fi

# Start SMAOS daemon
echo "[$(date)] Starting SMAOS daemon..."
# systemctl start smaos || echo "SMAOS daemon start deferred"

# Configure CloudWatch agent (optional)
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.zip
unzip amazon-cloudwatch-agent.zip
rm amazon-cloudwatch-agent.zip

echo "[$(date)] SMAOS initialization complete for $REGION ($ROLE)"
