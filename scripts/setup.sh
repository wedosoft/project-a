#!/bin/bash
# AI Contact Center OS - Development Setup Script

set -e

echo "🚀 Setting up AI Contact Center OS..."

# Check Python version
echo "📦 Checking Python version..."
python3 --version || { echo "❌ Python 3.9+ required"; exit 1; }

# Create virtual environment
echo "🐍 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate virtual environment
echo "✨ Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Copy .env.example to .env if not exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from .env.example..."
    cp .env.example .env
    echo "⚠️  Please update .env with your API keys"
fi

# Initialize database (if needed)
echo "🗄️  Database initialization..."
# TODO: Add database setup when ready

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Update .env with your API keys"
echo "2. Run: source venv/bin/activate"
echo "3. Run: uvicorn backend.main:app --reload"
echo ""
