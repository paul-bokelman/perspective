from typing import Callable
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from agent.memory import Memory

load_dotenv()

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

# config = types.GenerateContentConfig(tools=[Memory.get_tools()])

# todo: enable thinking to properly handle disparate transcription
def summarize_transcriptions(transcriptions: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=transcriptions,
        config={
            "system_instruction": "You are a helpful assistant receives audio transcriptions and summarizes them in the most concise manner possible. You cannot style your responses with markdown in any way!"
        }
    )
    assert response.text is not None
    return response.text

def stream_response(transcription: str, on_start: Callable, on_chunk: Callable[[types.GenerateContentResponse], None], on_complete: Callable) -> None:
    on_start()
    print("Generating and streaming response...")
    for chunk in client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=transcription,
        config={
            "response_mime_type": "text/plain", 
            "response_modalities": ["text"],
            "system_instruction": "You are a helpful assistant that provides detailed and informative responses. You cannot style your responses with markdown in any way!"
        }
    ):
        on_chunk(chunk)
    print("\nResponse complete.")
    on_complete()

if __name__ == "__main__":
    transcription = "Hello, how are you? I am testing the streaming response feature. Give a long response so we can see multiple chunks."
    def print_callback(chunk: types.GenerateContentResponse):
        if chunk:
            print(chunk.text, end='', flush=True)
    stream_response(transcription, on_start=lambda: print("starting"), on_chunk=print_callback, on_complete=lambda: print("\ncomplete"))