#!/bin/bash

# Install dependencies
echo "Installing dependencies..."
pip install -q -r requirements.txt

# Run dashboard
echo "Starting Axiom Planet Dashboard..."
echo "Dashboard will open at: http://localhost:8501"
streamlit run planet_dashboard.py
