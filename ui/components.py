from ui.types import StateIndicatorState
from textual.widgets import Static
    
# ------------------------------- loading text ------------------------------- #

class LoadingText(Static):
    """A widget that displays loading text with animated dots."""
    DEFAULT_CSS = """
    LoadingText {
        background: transparent;
        color: grey;
    }
    """

    def __init__(self, text: str = "Loading", dot_count: int = 3, interval: float = 0.5, **kwargs):
        super().__init__(**kwargs)
        self.base_text = text
        self.dot_count = dot_count
        self.interval = interval
        self.current_dots = 0
        self._timer = None

    def on_mount(self) -> None:
        """Start the animation timer when the widget is mounted."""
        self._timer = self.set_interval(self.interval, self._update_dots)

    def on_unmount(self) -> None:
        """Stop the animation timer when the widget is unmounted."""
        if self._timer:
            try:
                self._timer.stop()
            except Exception:
                self._timer = None

    def _update_dots(self) -> None:
        """Update the number of dots and refresh the display."""
        self.current_dots = (self.current_dots + 1) % (self.dot_count + 1)
        self.refresh()

    def render(self) -> str:
        """Render the loading text with the current number of dots."""
        dots = '.' * self.current_dots
        return f"{self.base_text}{dots}"
    
# ------------------------------ state indicator ----------------------------- #
EnabledDisabledStates = [StateIndicatorState("Enabled", "#00FF00"), StateIndicatorState("Disabled", "grey")]
RecordingIndicatorStates = [StateIndicatorState("Recording...", "#FF2020", True), StateIndicatorState("Not Recording", "grey")]

class StateIndicator(Static):
    def __init__(
        self,
        id: str,
        state: int = 0,
        states: list[StateIndicatorState] = EnabledDisabledStates,
        blink_interval: float = 0.5,
    ):
        super().__init__(id=id)
        self.states = states
        assert 0 <= state < len(self.states), "Invalid state index"
        
        self.state = state
        self.blink_interval = blink_interval
        self._blink_visible = True
        self._blink_timer = None
        
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
        return f"{dot} {current_state.label}"

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