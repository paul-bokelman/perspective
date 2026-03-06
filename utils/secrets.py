import os
import requests
import dotenv
from datetime import datetime
from realtime import prompts
from agent.persona import Persona

dotenv.load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("OPENAI_API_KEY not set. Please set it in a .env file in the root directory.")
    exit(1)

def get_ephemeral_key(persona: Persona, expiry: int = 300) -> tuple[str, str]:
    """Generate a client secret for the OpenAI Realtime API. Returns the client secret response as a dictionary."""
    
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "expires_after": {"anchor": "created_at", "seconds": expiry },
        "session": {
            "type": "realtime",
            "model": "gpt-realtime",
            "instructions": prompts.construct(persona),
            "audio": { "output": {"voice": "cedar"}, "input": {"turn_detection": None} },
        }
    }
    
    response = requests.post(
        "https://api.openai.com/v1/realtime/client_secrets",
        headers=headers,
        json=data
    )

    if response.status_code == 200:
        data = response.json()
        return data["value"], datetime.fromtimestamp(data["expires_at"]).strftime("%b %d, %Y, %I:%M %p")
    else:
        raise Exception(f"Error getting client secret: {response.status_code} - {response.text}")