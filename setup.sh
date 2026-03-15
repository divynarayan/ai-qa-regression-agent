#!/bin/bash
set -euo pipefail

echo "Creating virtual environment..."

python3 -m venv venv

echo "Activating environment..."

source venv/bin/activate

echo "Upgrading pip..."

pip install --upgrade pip

echo "Installing project dependencies..."

pip install fastapi "uvicorn[standard]" streamlit openai pandas appium-python-client python-dotenv pillow sqlalchemy pydantic python-multipart requests

echo "Setup complete!"

echo "Run the project with:"
echo "streamlit run ui/dashboard.py"
