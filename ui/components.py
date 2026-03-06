from ui.types import StateIndicatorState, ConversationAlertIdentifier
import random
from datetime import datetime
from textual.widgets import Static
    
# ------------------------------ state indicator ----------------------------- #
EnabledDisabledStates = [StateIndicatorState("Enabled", "#00FF00"), StateIndicatorState("Disabled", "grey")]
RecordingIndicatorStates = [StateIndicatorState("Not Recording", "grey"), StateIndicatorState("Recording...", "#FF2020", True)]
ConnectionIndicatorStates = [StateIndicatorState("Connecting...", "#FF5708"), StateIndicatorState("Connected", "#00FF00")]

class StateIndicator(Static):
    def __init__(
        self,
        id: str,
        state: int = 0,
        states: list[StateIndicatorState] = EnabledDisabledStates,
        blink_interval: float = 0.5,
        locked: bool = False,
    ):
        super().__init__(id=id)
        self.states = states
        assert 0 <= state < len(self.states), "Invalid state index"
        
        self.state = state
        self.blink_interval = blink_interval
        self._blink_visible = True
        self._blink_timer = None
        self.locked = locked
        
    def on_mount(self) -> None:
        """Start blinking if the initial state requires it."""
        if self.states[self.state].blink:
            self._start_blinking()

    def on_unmount(self) -> None:
        """Ensure blinking timer is stopped when the widget is removed."""
        self._stop_blinking()

    def _start_blinking(self) -> None:
        """Start the blinking timer if not already started."""
        if self._blink_timer is None:
            self._blink_timer = self.set_interval(self.blink_interval, self._toggle_blink)
            self._blink_visible = True

    def _stop_blinking(self) -> None:
        """Stop the blinking timer if it exists."""
        if self._blink_timer is not None:
            try:
                self._blink_timer.stop()
            except Exception:
                self._blink_timer = None
            self._blink_visible = True

    def _toggle_blink(self) -> None:
        """Toggle the visibility for blinking."""
        self._blink_visible = not self._blink_visible
        self.refresh()

    def render(self) -> str:
        """Render the current state with appropriate color and blinking."""
        current_state = self.states[self.state]
        dot = " " if current_state.blink and not self._blink_visible else f"[{current_state.color}]●[/{current_state.color}]"
        return f"{dot} {current_state.label} {'🔒' if self.locked else ''}"

    def get_next_state(self) -> int:
        """Helper function to get the next state index."""
        return (self.state + 1) % len(self.states)
        
    def set_state(self, state: int) -> None:
        """Set the current state and handle blinking if necessary."""
        if state != self.state:
            self.state = state
            self._stop_blinking()
            if self.states[self.state].blink:
                self._start_blinking()
            self.refresh()

    def toggle_lock(self) -> None:
        """Toggle the locked status."""
        self.locked = not self.locked
        self.refresh()

    def show_lock(self) -> None:
        """Lock the indicator."""
        self.locked = True
        self.refresh()

    def hide_lock(self) -> None:
        """Unlock the indicator."""
        self.locked = False
        self.refresh()

# ----------------------------- dynamic property ----------------------------- #

class BinaryStateProperty(Static):
    def __init__(self, id: str, label: str, locked: bool = False, initial_state: int = 0, states: list[StateIndicatorState] = EnabledDisabledStates):
        super().__init__(id=id)
        assert len(states) == 2, "BinaryStateProperty requires exactly two states"
        assert initial_state in (0, 1), "Initial state must be 0 or 1"
        
        self.states = states
        self.state = initial_state
        self.label = label
        self.locked = locked

    def render(self) -> str:
        """Render the current state with appropriate color and blinking."""
        current_state = self.states[self.state]
        return f"{self.label}: [{current_state.color}]{current_state.label}[/{current_state.color}] {'🔒' if self.locked else ''}"

    def get_next_state(self) -> int:
        """Helper function to get the next state index."""
        return (self.state + 1) % len(self.states)
    
# ------------------------------- chat message ------------------------------- #

class ConversationMessage(Static):
    """A widget that displays a chat message with a sender label."""

    def __init__(self, sender: str, message: str, cancelled: bool = False, responding: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.sender = sender
        self.message = message
        self.responding = responding
        self.cancelled = cancelled
        self.time = datetime.now().strftime("%I:%M %p")
        self.is_user = sender.lower() == "user"

    @staticmethod
    def _get_responding_keyword() -> str:
        return random.choice(["responding", "speaking", "talking", "explaining", "answering"])
    
    def get_formatted_message(self) -> str:
        if self.cancelled:
            return f"\n[red]\\[CANCELLED][/red]"
        if self.responding:
            return f"[grey]is {self._get_responding_keyword()}... [/grey]"
        return f"\n{self.message}"

    def render(self) -> str:
        """Render the chat message with sender label."""
        return f"[grey]\\[{self.time}] {self.sender}[/grey] {self.get_formatted_message()}"
    
class ConversationAlert(Static):
    """A widget that displays an alert message."""

    conversation_alert_color_mappings: dict[ConversationAlertIdentifier, str] = {
        "cancelled": "#FFD900", 
        "switched persona": "#00DDFF", 
        "connected": "#00FF00", 
        "disconnected": "#FF5708", 
        "error": "red"
    }

    def __init__(self, alert: ConversationAlertIdentifier, **kwargs):
        super().__init__(**kwargs)
        self.alert: ConversationAlertIdentifier = alert
        self.time = datetime.now().strftime("%I:%M %p")

    def render(self) -> str:
        """Render the alert message."""
        alert_color = self.conversation_alert_color_mappings[self.alert]
        return f"[grey]\\[{self.time}] [/grey][{alert_color}]\\[{self.alert}][/{alert_color}]"