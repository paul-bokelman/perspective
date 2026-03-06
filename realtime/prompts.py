from agent.persona import Persona

base_instructions = open("realtime/prompts/base.prompt.md").read()

def _inject_placeholders(template: str, values: dict[str, str]) -> str:
    """Replace placeholders in the template with actual values."""
    for key, val in values.items():
        template = template.replace(f"{{{{{key}}}}}", val.strip())
    return template

def construct(persona: Persona) -> str:
    """Construct the full instructions text."""
    return _inject_placeholders(base_instructions, {"persona": persona.prompt, "temperament": str(persona.temperament)})