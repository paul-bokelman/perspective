from typing import Any
from dataclasses import dataclass
import yaml
import os
import agent.constants as constants

@dataclass
class Temperament:
    """Personality temperament of the agent."""
    openness: float # curiosity and imagination (1=creative/open-minded, 0=practical/routine)
    conscientiousness: float # organization and responsibility (1=dependable/goal-oriented, 0=spontaneous/careless)
    extraversion: float # outgoingness and energy (1=sociable/talkative, 0=quiet/alone)
    agreeableness: float # kindness and cooperation (1=compassionate/trusting, 0=competitive/blunt)
    neuroticism: float # emotional stability (1=anxious/easily-stressed, 0=calm)

    def validate(self) -> bool:
        for trait in [self.openness, self.conscientiousness, self.extraversion, self.agreeableness, self.neuroticism]:
            if not (0.0 <= trait <= 1.0):
                return False
        return True

    def __str__(self) -> str:
        return f"Openness: {self.openness}, Conscientiousness: {self.conscientiousness}, Extraversion: {self.extraversion}, Agreeableness: {self.agreeableness}, Neuroticism: {self.neuroticism}"

@dataclass
class Persona:
    id: str
    name: str
    voice: str
    description: str
    temperament: Temperament
    prompt: str

def _load_local_persona(data: dict[str, Any]) -> Persona:
    """Helper function to load a single profile from a dictionary."""
    temperament_data = data.get("temperament", {})
    temperament = Temperament(
        openness=temperament_data.get("openness", 0.5),
        conscientiousness=temperament_data.get("conscientiousness", 0.5),
        extraversion=temperament_data.get("extraversion", 0.5),
        agreeableness=temperament_data.get("agreeableness", 0.5),
        neuroticism=temperament_data.get("neuroticism", 0.5),
    )
    if not temperament.validate():
        raise ValueError("Invalid temperament values")

    persona = Persona(
        id=data.get("id", "unknown"),
        name=data.get("name", "Unnamed Agent"),
        voice=data.get("voice", "default"),
        description=data.get("description", "No description provided."),
        temperament=temperament,
        prompt=data.get("prompt", ""),
    )
    return persona

def load_local_personas():
    """Load all the agent personas from the local personas directory."""
    personas: dict[str, Persona] = {}
    for filename in os.listdir(constants.local_personas_dir):
        if filename.endswith(".yaml") or filename.endswith(".yml"):
            filepath = os.path.join(constants.local_personas_dir, filename)
            with open(filepath, 'r') as file:
                data: dict[str, Any] = yaml.safe_load(file)
                try:
                    profile = _load_local_persona(data)
                    personas[profile.id] = _load_local_persona(data)
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
    return personas