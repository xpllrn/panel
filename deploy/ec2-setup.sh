#!/bin/bash
# EC2 Django Deployment Script
# Run this on your EC2 instance after SSH connection

set -e  # Exit on error

echo "=========================================="
echo "Django App Deployment on EC2"
echo "=========================================="

# Update system
echo "Step 1: Updating system packages..."
sudo apt update
sudo apt upgrade -y

# Install Python and dependencies
echo "Step 2: Installing Python 3.11 and pip..."
sudo apt install -y python3.11 python3.11-venv python3-pip
sudo apt install -y python3.11-dev build-essential libpq-dev

# Install Nginx
echo "Step 3: Installing Nginx..."
sudo apt install -y nginx

# Install Git
echo "Step 4: Installing Git..."
sudo apt install -y git

# Create app directory
echo "Step 5: Setting up application directory..."
sudo mkdir -p /var/www/app
sudo chown -R $USER:$USER /var/www/app
cd /var/www/app

# Clone your repository (you'll need to replace this with your repo URL)
echo "Step 6: Clone your repository..."
echo "Run manually: git clone <your-repo-url> ."
echo "Or upload your code using scp"

# Create virtual environment
echo "Step 7: Creating virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "Step 8: Installing Python packages..."
# pip install -r requirements.txt
# Uncomment above after you upload your code

echo "=========================================="
echo "Basic setup complete!"
echo "Next steps:"
echo "1. Upload your Django code to /var/www/app"
echo "2. Create .env file with your credentials"
echo "3. Run: source venv/bin/activate && pip install -r requirements.txt"
echo "4. Run: python manage.py migrate"
echo "5. Run: python manage.py collectstatic"
echo "6. Configure Gunicorn and Nginx (see other scripts)"
echo "=========================================="
