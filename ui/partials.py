from agent.persona import Persona
from textual.app import ComposeResult
from textual.widgets import Static, Header, OptionList
from textual.widget import Widget
from textual.containers import Container, Vertical
from textual.widgets.option_list import Option
from ui.signals import ToggleDisplaySignal, SelectedPersonaSignal

# ---------------------------- persona information --------------------------- #

class PersonaInfoPartial(Widget):
    """A partial for displaying persona information."""

    def __init__(self, persona: Persona, **kwargs):
        super().__init__(**kwargs)
        self.persona = persona

    def compose(self) -> ComposeResult:
        yield Static(self.persona.name, id="persona-preview-name")
        yield Static(f"---", classes="grey")
        yield Static(self.persona.description, id="persona-preview-description")
        yield Static(f"---", classes="grey")
        yield Static(f"Openness: {self.persona.temperament.openness:.1f}", id="trait-openness")
        yield Static(f"Conscientiousness: {self.persona.temperament.conscientiousness:.1f}", id="trait-conscientiousness")
        yield Static(f"Extraversion: {self.persona.temperament.extraversion:.1f}", id="trait-extraversion")
        yield Static(f"Agreeableness: {self.persona.temperament.agreeableness:.1f}", id="trait-agreeableness")
        yield Static(f"Neuroticism: {self.persona.temperament.neuroticism:.1f}", id="trait-neuroticism")

    def update_persona(self, persona: Persona) -> None:
        """Update the displayed persona information."""
        self.persona = persona
        self.query_one("#persona-preview-name", Static).update(persona.name)
        self.query_one("#persona-preview-description", Static).update(persona.description)
        self.query_one("#trait-openness", Static).update(f"Openness: {persona.temperament.openness:.1f}")
        self.query_one("#trait-conscientiousness", Static).update(f"Conscientiousness: {persona.temperament.conscientiousness:.1f}")
        self.query_one("#trait-extraversion", Static).update(f"Extraversion: {persona.temperament.extraversion:.1f}")
        self.query_one("#trait-agreeableness", Static).update(f"Agreeableness: {persona.temperament.agreeableness:.1f}")
        self.query_one("#trait-neuroticism", Static).update(f"Neuroticism: {persona.temperament.neuroticism:.1f}")

# ------------------------------ persona selection ----------------------------- #

class PersonaSelectionPartial(Widget):
    """A partial for selecting an persona from a list of personas."""

    def __init__(self, personas: dict[str, Persona], **kwargs):
        super().__init__(**kwargs)
        self.personas = personas
        self.selected_id = list(personas.keys())[0]
        self.highlighted_option_id = self.selected_id

    def on_mount(self) -> None:
        """Set focus to the option list when mounted."""
        self.post_message(ToggleDisplaySignal("#main"))
        self.query_one("#persona-option-list").focus()

    def compose(self) -> ComposeResult:
        selected_persona = self.personas[self.selected_id]
        with Container(id="persona-selection-main-container"):
            with Container(classes="grid-container"):
                yield Static("PERSONA SELECTION", id="persona-selection-title")
                options = [Option(persona.name, id=persona.id) for persona in self.personas.values()]
                yield OptionList(*options, id="persona-option-list")
            with Vertical(classes="grid-container"):
                yield PersonaInfoPartial(persona=selected_persona, id="persona-info-partial")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection from the option list."""
        assert isinstance(event.option_id, str), "Option ID should be a string"
        persona = self.personas[event.option_id]
        assert persona is not None, f"Persona with ID {event.option_id} not found"
        self.selected_id = persona.id
        self.post_message(SelectedPersonaSignal(persona))
        self.post_message(ToggleDisplaySignal("#main"))
        self.remove()

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        """Handle option highlight from the option list."""
        assert isinstance(event.option_id, str), "Option ID should be a string"
        persona = self.personas[event.option_id]
        assert persona is not None, f"Persona with ID {event.option_id} not found"
        self.highlighted_option_id = persona.id
        persona_info_partial = self.query_one("#persona-info-partial", PersonaInfoPartial)
        persona_info_partial.update_persona(persona)

# -------------------------------- help dialog ------------------------------- #

class HelpDialog(Widget):
    """A partial for displaying help information."""

    def compose(self) -> ComposeResult:
        help_text = (
            "[b]Keyboard Shortcuts:[/b]\n"
            "- [b]L[/b]: Toggle Listening\n"
            "- [b]R[/b]: Toggle Recording\n"
            "- [b]S[/b]: Switch Persona\n"
            "- [b]H[/b]: Show Help\n\n"
            "[b]Instructions:[/b]\n"
            "Use the keyboard shortcuts to interact with the application. "
            "You can switch between different personas, toggle listening and recording states, "
            "and view this help dialog at any time."
        )
        yield Static(help_text, id="help-dialog-text")

    def on_mount(self) -> None:
        """Set focus to the help dialog when mounted."""
        self.post_message(ToggleDisplaySignal("#main"))
        self.focus()

    def on_key(self, event) -> None:
        """Close the help dialog on any key press."""
        self.post_message(ToggleDisplaySignal("#main"))
        self.remove()