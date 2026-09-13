import secrets


def new_id(prefix: str = "") -> str:
    token = secrets.token_urlsafe(9).replace("-", "a").replace("_", "b")
    return f"{prefix}{token}" if prefix else token
