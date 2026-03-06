def slugify(text: str) -> str:
    """Convert text to a slug suitable for agent identifiers"""
    return text.lower().replace(" ", "-")