from agent.persona import Persona
from textual.message import Message

class ToggleDisplaySignal(Message):
    """Message to signal hiding a component."""
    def __init__(self, target_id: str) -> None:
        super().__init__()
        self.target_id = target_id

class SelectedPersonaSignal(Message):
    """Message to signal an persona has been selected."""
    def __init__(self, persona: Persona) -> None:
        super().__init__()
        self.persona = persona