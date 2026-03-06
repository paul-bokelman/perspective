from ui.types import ConversationAlertIdentifier
from textual.binding import BindingType
from textual.app import ComposeResult
from textual.widgets import Static, OptionList, Footer
from textual.widget import Widget
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets.option_list import Option
from agent.persona import Persona
from ui.signals import ToggleDisplaySignal, SelectedPersonaSignal
from ui.components import ConversationMessage, ConversationAlert

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

# ------------------------------ chat container ------------------------------ #

class ConversationHistoryPartial(Widget):
    """A partial for displaying the conversation history."""

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="conversation-history-container"):
            yield Static("Conversation history will appear here.", id="conversation-history-placeholder", classes="grey")

    def _mount_to_container(self, widget: Widget) -> None:
        """Simplify mounting a widget to the conversation container and scrolling to the end."""
        conversation_container = self.query_one("#conversation-history-container", VerticalScroll)
        conversation_container.mount(widget)
        conversation_container.scroll_end(animate=False)

    def _remove_placeholder(self) -> None:
        """Hide the conversation placeholder if it's visible."""
        placeholder = self.query_one("#conversation-history-placeholder", Static)
        if placeholder.display:
            placeholder.display = False

    def add_message(self, sender: str, message: str) -> None:
        """Add a new message to the conversation history."""
        self._mount_to_container(ConversationMessage(sender=sender, message=message))

    def add_alert(self, alert: ConversationAlertIdentifier):
        """Add an alert message to the conversation history."""
        self._mount_to_container(ConversationAlert(alert=alert))

    def add_message_loader(self) -> None:
        """Add a loading indicator for the current message being generated."""
        self._remove_placeholder()
        self._mount_to_container(ConversationMessage(id="loading-message", sender="derrick", message="", responding=True))

    def remove_message_loader(self) -> None:
        """Remove the loading indicator for the current message being generated."""
        conversation_container = self.query_one("#conversation-history-container", VerticalScroll)

        try:
            conversation_container.query_one("#loading-message", ConversationMessage).remove()
        except Exception: # NoMatches -> return
            return

    def flag_last_message_cancelled(self) -> None: # todo: remove in favor of alerts
        conversation_container = self.query_one("#conversation-history-container", VerticalScroll)
        last_message = conversation_container.query(ConversationMessage)[-1]
        last_message.cancelled = True
        last_message.refresh()

# -------------------------------- help dialog ------------------------------- #

class HelpPartial(Widget):
    """A partial for displaying help information."""

    def __init__(self, bindings: list[BindingType], **kwargs):
        super().__init__(**kwargs)
        self.initial = True
        self.bindings = bindings

    def compose(self) -> ComposeResult:
        help_sections = ["[b]Instructions:[/b]"]
        help_sections.append(
            "Use the keyboard shortcuts above to interact with the application. "
            "You can switch between different personas, toggle various states, "
            "and view this help dialog at any time."

        )
        help_sections.append("\n[b]Keyboard Shortcuts:[/b]")
        for binding in self.bindings:
            assert isinstance(binding, tuple) and len(binding) == 3, "Binding should be a 3-tuple"
            help_sections.append(f"- [b]{binding[0]}[/b]: {binding[2]}")
        

        help_sections.append("\n\nClose this dialog to view the conversation by pressing 'h' again.")
        
        help_text = "\n".join(help_sections)
        yield Static(help_text, id="help-dialog-text")