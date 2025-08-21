Audio Agent

Audio Agent is a voice-driven AI interview assistant built with FastAPI, WebSockets, OpenAI, and Socket.IO.
It listens to your voice, transcribes your responses, streams AI-generated answers in real time, and keeps track of chat history for personalized interview coaching.

🚀 Features

🎧 Real-time audio capture from system or microphone

🧠 AI-powered answers via OpenAI API

🗣️ Automatic transcription of spoken responses

🔄 Streaming responses using WebSockets + Socket.IO

📝 Session management with resume & job descriptions

📜 Chat history storage per session

🛠 FastAPI backend + Flask-style templates frontend

🛠️ Installation
1. Clone the Repository
git clone https://github.com/your-username/audio_agent.git
cd audio_agent

2. Create a Virtual Environment
python -m venv .venv


Activate it:

Windows (PowerShell):

.venv\Scripts\Activate


Mac/Linux:

source .venv/bin/activate

3. Install Dependencies
pip install --upgrade pip
pip install -r requirements.txt


Note: We removed pyaudiowpatch from requirements.txt since we are not recording system audio directly in this repo.

4. Set Up Environment Variables

Create a .env file in the project root:

OPENAI_API_KEY=your_openai_api_key_here
FLASK_SECRET_KEY=some_random_secret

5. Project Structure
audio_agent/
│── app/
│   ├── main.py            # FastAPI app entry point
│   ├── llm.py             # OpenAI LLM integration (copy from old repo)
│   ├── transcribe.py      # Audio transcription logic (copy from old repo)
│   ├── processor.py       # Audio frames processing + VAD
│── templates/
│   ├── index.html         # Frontend interface
│── data/                  # Generated at runtime
│   ├── recordings/        # Saved audio recordings
│   ├── transcripts/       # Saved transcriptions
│   ├── responses/         # AI responses per segment
│   ├── sessions/          # Per-session files
│── requirements.txt
│── .env
│── README.md

6. Run the Application

Start the FastAPI server:

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload


Open http://localhost:8001
 in your browser.

7. Usage
Start a Session

Paste your resume and job description.

Click Start Session.

Speak or Stream Audio

The app listens for your voice, processes it, and sends it to OpenAI.

You’ll see live AI-generated answers streaming on the page.

View Chat History

Chat history per session is stored under data/sessions/ and displayed in the UI.