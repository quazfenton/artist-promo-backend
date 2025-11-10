#!/bin/bash

# 🎤 Artist Promotion Backend - Quick Setup Script
# This script automates the initial setup process

set -e

echo "🎤 Hip-Hop Artist Promotion Backend - Setup"
echo "==========================================="
echo ""

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    echo "✓ Python $PYTHON_VERSION found"
else
    echo "✗ Python 3 not found. Please install Python 3.9 or higher."
    exit 1
fi

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"

# Install dependencies
echo ""
echo "Installing dependencies (this may take a few minutes)..."
pip install -r requirements.txt > /dev/null 2>&1
echo "✓ Dependencies installed"

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env file with your API keys:"
    echo "   - SPOTIFY_CLIENT_ID"
    echo "   - SPOTIFY_CLIENT_SECRET"
    echo "   - YOUTUBE_API_KEY (optional but recommended)"
    echo ""
    echo "   Get Spotify keys from: https://developer.spotify.com/dashboard"
    echo "   Get YouTube keys from: https://console.cloud.google.com/apis/credentials"
else
    echo "✓ .env file already exists"
fi

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p exports logs
echo "✓ Directories created"

# Initialize database
echo ""
echo "Initializing database..."
python3 << PYTHON_SCRIPT
from app.models.database import Base
from sqlalchemy import create_engine
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./artist_promo.db")
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(bind=engine)
print("✓ Database initialized")
PYTHON_SCRIPT

# Make CLI executable
echo ""
echo "Making CLI executable..."
chmod +x cli.py
echo "✓ CLI is now executable"

# Test import
echo ""
echo "Testing imports..."
python3 -c "from app.models.database import Contact; from app.scrapers.base_scraper import BaseScraper; print('✓ All imports successful')"

# Summary
echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Edit .env file with your API keys:"
echo "   nano .env"
echo ""
echo "2. Start the API server:"
echo "   uvicorn app.api.main:app --reload"
echo ""
echo "3. Or use the CLI tool:"
echo "   ./cli.py scrape-spotify --genre hip-hop"
echo ""
echo "4. View API documentation:"
echo "   http://localhost:8000/docs"
echo ""
echo "5. Read the guides:"
echo "   - README.md - Full documentation"
echo "   - QUICKSTART.md - Quick start guide"
echo "   - TACTICS_GUIDE.md - Implementation tactics"
echo ""
echo "For help, run: ./cli.py --help"
echo ""
echo "Happy promoting! 🎤🔥"
