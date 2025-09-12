from dataclasses import dataclass

@dataclass
class StateIndicatorState:
    label: str
    color: str
    blink: bool = False
