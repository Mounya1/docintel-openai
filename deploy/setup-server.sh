#!/usr/bin/env bash
# One-time bootstrap for an Ubuntu 24.04 server (Oracle Cloud Always Free, x86 or ARM).
# Run as the ubuntu user:
#   curl -fsSL https://raw.githubusercontent.com/Mounya1/docintel-openai/main/deploy/setup-server.sh | bash
set -euo pipefail

# Oracle's Ubuntu images ship iptables rules that drop everything except SSH,
# even when the VCN security list allows it. Open 80/443 and persist the rules.
if sudo iptables -C INPUT -p tcp --dport 80 -j ACCEPT 2>/dev/null; then
  echo "Ports 80/443 already open"
else
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent
  sudo netfilter-persistent save
fi

# 2 GB swap so the Docker build fits on the 1 GB micro shape
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
sudo apt-get install -y git

if [ ! -d ~/docintel-openai ]; then
  git clone https://github.com/Mounya1/docintel-openai.git ~/docintel-openai
fi

echo
echo "Done. Next:"
echo "  1. Log out and back in (for docker group)"
echo "  2. cp ~/docintel-openai/deploy/.env.prod.example ~/docintel-openai/deploy/.env.prod && nano ~/docintel-openai/deploy/.env.prod"
echo "  3. ~/docintel-openai/deploy/deploy.sh"
