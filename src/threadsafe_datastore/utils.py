from __future__ import annotations

from typing import Any, Callable, Dict, Iterator, List


def _path_to_string(keys: List[str]) -> str:
    """Convert a list of keys to a path string representation."""
    return ".".join(keys)


def _recursive_to_json(value: Any) -> Any:
    """
    Recursively convert a value to JSON-serializable format.
    
    Handles dicts, lists, and basic types. Custom objects are converted to strings.
    """
    if isinstance(value, dict):
        return {k: _recursive_to_json(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_recursive_to_json(item) for item in value]
    elif isinstance(value, (str, int, float, bool, type(None))):
        return value
    else:
        # For custom objects, convert to string representation
        return str(value)


class _UnlockedDatastore:
    """
    An unlocked view of a Datastore that shares the same data but has no locking.

    This is used internally when the Datastore is used as a context manager.
    All operations are performed directly on the shared data without thread safety.
    """

    def __init__(self, data: Dict[str, Any]) -> None:
        """Initialize with a reference to the shared data dictionary."""
        self.__data = data

    @property
    def data(self) -> Dict[str, Any]:
        """
        Return the raw internal dictionary.

        Returns:
            The internal dictionary (direct reference, not a copy).
        """
        return self.__data

    def __getitem__(self, name: str) -> Any:
        """Get a value by key."""
        return self.__data[name]

    def __setitem__(self, name: str, value: Any) -> None:
        """Set a value by key."""
        self.__data[name] = value

    def __contains__(self, name: str) -> bool:
        """Check if a key exists."""
        return name in self.__data

    def __delitem__(self, name: str) -> None:
        """Delete a key-value pair."""
        del self.__data[name]

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the store's keys."""
        return iter(self.__data.keys())

    def __len__(self) -> int:
        """Get the number of items in the store."""
        return len(self.__data)

    def __str__(self) -> str:
        """Return a string representation of the store."""
        if not self.__data:
            return "{}"

        items = []
        for key, value in self.__data.items():
            items.append(f"\t{key}: {value}")

        return "{\n" + ",\n".join(items) + "\n}"

    def __repr__(self) -> str:
        """Return a string representation of the store."""
        return f"_UnlockedDatastore(items={len(self.__data)})"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by key with a default."""
        return self.__data.get(key, default)

    def operate(
        self, keys: str | List[str], operation: Callable[[Any], Any]
    ) -> Any:
        """Perform an operation on a value, supporting nested access."""
        if isinstance(keys, str):
            keys = [keys]

        current = self.__data

        # Navigate to the target location
        for i, key in enumerate(keys[:-1]):
            if key not in current:
                path_str = _path_to_string(keys[: i + 1])
                raise KeyError(f"Path '{path_str}' does not exist")
            if not isinstance(current[key], dict):
                path_str = _path_to_string(keys[: i + 1])
                raise ValueError(f"Path '{path_str}' is not a dictionary")
            current = current[key]

        final_key = keys[-1]
        if final_key not in current:
            key_path = _path_to_string(keys)
            raise KeyError(f"Key path '{key_path}' does not exist")

        # Perform operation and update
        old_value = current[final_key]
        new_value = operation(old_value)
        current[final_key] = new_value

        return new_value

    def update(self, key: str, operation: Callable[[Any], Any]) -> Any:
        """Update a value using the provided operation."""
        old_value = self.__data[key]
        new_value = operation(old_value)
        self.__data[key] = new_value
        return new_value

    def items(self) -> List[tuple[str, Any]]:
        """Return a list of the store's (key, value) pairs."""
        return list(self.__data.items())

    def values(self) -> List[Any]:
        """Return a list of the store's values."""
        return list(self.__data.values())

    def keys(self) -> List[str]:
        """Return a list of the store's keys."""
        return list(self.__data.keys())

    def init(self, key: str, value: Any) -> None:
        """Initialize a key with a value only if it doesn't already exist."""
        if key not in self.__data:
            self.__data[key] = value

    def increment(self, key: str, amount: int | float = 1) -> int | float:
        """Increment a numeric value."""
        return self.update(key, lambda x: x + amount)

    def decrement(self, key: str, amount: int | float = 1) -> int | float:
        """Decrement a numeric value."""
        return self.update(key, lambda x: x - amount)

    def append(self, keys: str | List[str], value: Any) -> None:
        """Append a value to a list, supporting nested access."""
        def append_op(x: Any) -> Any:
            if not isinstance(x, list):
                key_path = _path_to_string(keys) if isinstance(keys, list) else keys
                raise ValueError(f"Target at path '{key_path}' is not a list")
            x.append(value)
            return x

        self.operate(keys, append_op)

    def concat(self, keys: str | List[str], value: Any) -> None:
        """Concatenate a value to a string or list."""
        self.operate(keys, lambda x: x + value)

    def to_json(self) -> Dict[str, Any]:
        """Convert the store to a JSON-serializable dictionary."""
        data = {}
        for key, value in self.__data.items():
            data[key] = _recursive_to_json(value)
        return data

