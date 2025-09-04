# Audio Agent - Voice-Driven Interview Assistant

Audio Agent is a voice-driven AI interview assistant built with FastAPI, WebSockets, OpenAI, and Socket.IO. It listens to your voice, transcribes your responses, streams AI-generated answers in real time, and keeps track of chat history for personalized interview coaching.

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Usage](#usage)

## 🚀 Features
- **🎧 Real-time audio capture** from system or microphone
- **🧠 AI-powered responses** via OpenAI API
- **🗣️ Automatic transcription** of spoken responses
- **🔄 Streaming responses** using WebSockets + Socket.IO
- **📝 Session management** with resume & job descriptions
- **📜 Chat history storage** per session
- **🛠️ FastAPI backend** + Flask-style templates frontend

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone https://github.com/venkatasai-ptl/AUDIO_AGENT.git
cd AUDIO_AGENT
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv .venv
```

- **Windows (PowerShell):**
  ```bash
  .venv\Scripts\Activate
  ```

- **Mac/Linux:**
  ```bash
  source .venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** We removed pyaudiowpatch from requirements.txt since we are not recording system audio directly in this repo.

## 📁 Project Structure
```
audio_agent/
├── .gitignore
├── README.md
├── requirements.txt
├── run.sh
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py
│   │   └── transcribe.py
│   ├── static/
│   │   └── pcm_collector.js
│   └── templates/
│       └── index.html
├── data/
│   ├── last_session_id.txt
│   ├── prompts/
│   ├── recordings/
│   ├── responses/
│   ├── sessions/
│   └── transcripts/
└── segments/
```

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

```env
OPENAI_API_KEY=your_openai_api_key_here
FLASK_SECRET_KEY=some_random_secret
```

## 🚀 Running the Application

Start the FastAPI server:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Open http://localhost:8001 in your browser to access the application.

## 💻 Usage

### Starting a Session
1. Paste your resume and job description
2. Click "Start Session"

### Speaking or Streaming Audio
- The app listens for your voice and processes it
- AI-generated answers will stream in real-time

### Viewing Chat History
- All chat history per session is stored under `data/sessions/`
- Previous sessions are displayed in the UI for review

### Notes on `webrtcvad` installation

This project uses [`webrtcvad`](https://pypi.org/project/webrtcvad/) (WebRTC Voice Activity Detection) for real-time speech detection.

- On **Linux/Ubuntu** (or Docker based on Debian/Ubuntu):
  - Usually installs directly via prebuilt wheels.
  - If a wheel is not available for your Python version, you just need basic build tools:
    ```bash
    sudo apt-get update && sudo apt-get install -y build-essential
    ```
  - In Docker, you can add this to your `Dockerfile`:
    ```dockerfile
    RUN apt-get update && apt-get install -y --no-install-recommends build-essential
    ```

- On **Windows**:
  - If no wheel is available, `pip install webrtcvad` will try to build from source and require
    [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
  - Common error message:  
    ```
    error: Microsoft Visual C++ 14.0 or greater is required.
    ```
  - Fix: Install the build tools, or run the project inside Docker/Linux to avoid this.

✅ Tip: For production hosting on Linux/Docker you don’t need Microsoft Build Tools. The compile step (if needed) happens once during image build, not at runtime.
