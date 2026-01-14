from dataclasses import is_dataclass
from typing import Type, Any, Dict, List

def from_dict(cls: Type[Any], data: Dict[str, Any]) -> Any:
    """
    Recursively creates a dataclass instance from a dictionary.
    """
    if not is_dataclass(cls):
        return data

    kwargs = {}
    for field_name, field_type in cls.__annotations__.items():
        field_value = data.get(field_name)
        if field_value is None:
            kwargs[field_name] = None
        elif is_dataclass(field_type):
            kwargs[field_name] = from_dict(field_type, field_value)
        elif isinstance(field_value, list) and hasattr(field_type, '__args__'):
            list_type = field_type.__args__[0]
            kwargs[field_name] = [from_dict(list_type, item) for item in field_value]
        elif isinstance(field_value, dict) and hasattr(field_type, '__args__'):
            # This handles Dict[str, RegimeConfig]
            val_type = field_type.__args__[1]
            kwargs[field_name] = {k: from_dict(val_type, v) for k, v in field_value.items()}
        else:
            kwargs[field_name] = field_value

    return cls(**kwargs)
