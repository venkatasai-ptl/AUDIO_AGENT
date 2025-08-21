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
