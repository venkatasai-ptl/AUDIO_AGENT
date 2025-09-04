import openai
import os
import io

def transcribe_audio(wav_bytes: bytes) -> str:
    """
    Transcribe audio file to text using OpenAI Whisper
    Returns transcribed text
    """
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    with io.BytesIO(wav_bytes) as f:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=("audio.wav", f, "audio/wav"),
            language="en"
        )
    return transcript.text
