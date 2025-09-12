from uuid import uuid4
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static
from textual.containers import Container, Vertical
from ui.signals import ToggleDisplaySignal
from ui.partials import PersonaSelectionPartial, SelectedPersonaSignal, PersonaInfoPartial, HelpDialog
from ui.components import  StateIndicator, BinaryStateProperty, LoadingText, RecordingIndicatorStates
from models.sts import STSPipeline
from agent import persona
import random

personas = persona.load_local_personas()
sts_pipeline = STSPipeline()

text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat."

global streaming_text_index
streaming_text_index = 0

initial_persona_key = list(personas.keys())[0]
selected_persona = personas[initial_persona_key]

class PerspectiveApp(App):
    TITLE = "Perspective"
    CSS_PATH = "ui/ui.tcss"
    ENABLE_COMMAND_PALETTE = False 
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("l", "toggle_listening", "Toggle Listening"),
        ("r", "toggle_recording", "Toggle Recording"),
        ("s", "switch_persona", "Switch Persona"),
        # ("h", "help", "Show Help"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(name="Perspective", icon="🧠", show_clock=True)

        with Container(id="main"):
            with Container(id="tl", classes="grid-container"):
                yield Static("PERSONA", classes="grid-container-title")
                yield PersonaInfoPartial(persona=selected_persona, id="active-persona-info-partial")
            with Container(id="right", classes="grid-container"):
                yield Static("SYSTEM", classes="grid-container-title")
                with Vertical():
                    yield Static("", id="streaming-text")
                    yield LoadingText(text="Thinking", id="thinking-text")
            with Container(id="bl", classes="grid-container"):
                yield Static("INFO", classes="grid-container-title")
                with Vertical():
                    yield Static(f"Session ID: {str(uuid4())[:8]}", id="info-text")
                    yield Static(f"Memory Chunks: 212", id="memory-chunks-text")
                    yield Static(f"---", classes="grey")
                    yield BinaryStateProperty(id="memory-property", initial_state=0, label="Memory", locked=True)
                    yield BinaryStateProperty(id="shared-memory-property", initial_state=0, label="Shared Memory", locked=True)
                    yield BinaryStateProperty(id="listening-property", initial_state=1, label="Listening")
                    yield Static(f"---", classes="grey")
                    yield StateIndicator(id="recording-indicator", state=1, states=RecordingIndicatorStates)

        yield Footer()

    def on_ready(self) -> None:
        self._update_streaming_text()
        self.set_interval(0.1, self._update_streaming_text)

    # --------------------------------- internal --------------------------------- #

    def _update_streaming_text(self) -> None:
        """Update the streaming text area."""
        global streaming_text_index
        if streaming_text_index >= len(text):
            return
        streaming_text = self.query_one("#streaming-text", Static)
        streaming_text.update(text[:streaming_text_index])
        streaming_text_index += random.randint(1, 5)

    # ---------------------------------- actions --------------------------------- #

    def action_toggle_listening(self) -> None:
        """Toggle listening state"""
        if not sts_pipeline.listening:
            sts_pipeline.start_listening()
        else:
            sts_pipeline.stop_listening()
        listening_property = self.query_one("#listening-property", BinaryStateProperty)
        listening_property.state = listening_property.get_next_state()
        listening_property.refresh()
    
    def action_toggle_recording(self) -> None:
        """Toggle recording state"""
        if not sts_pipeline.recording:
            sts_pipeline.start_recording()
        else:
            sts_pipeline.stop_recording()

        recording_indicator = self.query_one("#recording-indicator", StateIndicator)
        recording_indicator.state = recording_indicator.get_next_state()
        recording_indicator.refresh()

    def action_switch_persona(self) -> None:
        """Switch between personas"""
        if not self.query("#persona-selection-partial"):
            self.mount(PersonaSelectionPartial(personas=personas, id="persona-selection-partial"))

    def action_custom_quit(self) -> None:
        """A custom action that performs cleanup before quitting."""
        self.log("Performing custom cleanup before quitting...")
        sts_pipeline.terminate()
        self.exit() 

    # def action_help(self) -> None:
    #     """Show help dialog"""
    #     if not self.query("#help-dialog"):
    #         self.mount(HelpDialog(id="help-dialog"))

    # ---------------------------------- signals --------------------------------- #

    def on_toggle_display_signal(self, message: ToggleDisplaySignal) -> None:
        """Handle toggle display signal to show/hide components."""
        component = self.query_one(message.target_id)
        component.display = not component.display

    def on_selected_persona_signal(self, message: SelectedPersonaSignal) -> None:
        """Handle selected persona signal to update the active persona."""
        self.query_one("#active-persona-info-partial", PersonaInfoPartial).update_persona(message.persona)
    
if __name__ == "__main__":
    app = PerspectiveApp()
    app.run()
