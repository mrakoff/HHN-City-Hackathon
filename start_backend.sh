#!/bin/bash
cd /Users/ckrasniqi/Documents/HHN-City-Hackathon
source .venv313/bin/activate
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
