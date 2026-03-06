from typing import Literal
from dataclasses import dataclass

@dataclass
class StateIndicatorState:
    label: str
    color: str
    blink: bool = False

type ConversationAlertIdentifier = Literal["cancelled", "switched persona", "disconnected", "connected", "error"]