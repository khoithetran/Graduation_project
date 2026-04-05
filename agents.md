AI System Refactoring Task: Safety Helmet Detection
## 1. Role & Objective
You are an Expert AI Software Engineer and MLOps Specialist. Your mission is to refactor the current graduation project (KLTN) from a script-based repository into a production-ready AI application.

The goal is to move from "it runs on my machine" to a scalable, modular, and deployable architecture using FastAPI, YOLOv8, and Docker.

## 2. Target Project Structure
Refactor the current directory into the following hierarchy:

Plaintext
/safety-helmet-detection
├── data/               # Test samples and documentation
├── models/             # Storage for .pt, .onnx, or .engine weights
├── src/                # Main Source Code
│   ├── api/            # FastAPI routes and middleware
│   ├── core/           # Logic for Inference (The "Brain")
│   ├── utils/          # Image processing and BBox drawing
│   └── config/         # System settings and Hyperparameters
├── deployment/         # Dockerfile and docker-compose
├── .gitignore          # Professional exclusion list
├── requirements.txt    # Versioned dependencies
└── README.md           # Documentation
## 3. Engineering Requirements
A. Core Inference Engine (src/core/predictor.py)
Singleton Pattern: Ensure the YOLOv8 model is loaded only once into memory when the server starts.

Hardware Acceleration: Implement logic to automatically detect and use CUDA (GPU) if available, falling back to CPU otherwise.

Optimization: Support loading models in .pt (PyTorch) and .onnx (for high-speed CPU inference).

B. Backend API (src/api/main.py)
FastAPI: Replace basic Flask/Python scripts with FastAPI for high-performance asynchronous handling.

Endpoints:

POST /predict: Accepts an image file, runs inference, and returns JSON results (coordinates, confidence, class).

GET /health: Checks if the model is loaded and the API is alive.

CORS: Enable Cross-Origin Resource Sharing so the Frontend can communicate without browser blocks.

Pydantic: Use schemas for data validation.

C. Clean Code & Logging
No print(): Use the Python logging module for all system messages and errors.

Configuration: Store paths (like model location) and confidence thresholds in a config/settings.py file instead of hardcoding.

D. Deployment (Containerization)
.gitignore: Must exclude __pycache__, .venv, .env, and all large weight files (*.pt).

Dockerfile: Create a multi-stage or optimized Dockerfile using a lightweight Python image (e.g., python:3.11-slim).

## 4. Specific Action Items for Codex
Generate a comprehensive .gitignore file.

Rewrite the model loading logic into a Predictor class.

Bootstrap the FastAPI server structure.

Create a requirements.txt with essential libraries (ultralytics, fastapi, uvicorn, opencv-python-headless, python-multipart).

Draft a Dockerfile for the backend.

## 5. Coding Standard
Follow PEP 8 style guidelines.

Add Docstrings to every major class and function.

Ensure the code is modular so that any component (e.g., the model) can be swapped out easily in the future.