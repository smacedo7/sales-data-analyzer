def validate_non_empty_string(value, name):
    if not isinstance(value, str):
        raise TypeError(f" {name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} cannot be empty")
    return value.strip()
