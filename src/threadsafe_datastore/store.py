from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Iterator, List

from threadsafe_datastore.utils import _UnlockedDatastore, _path_to_string, _recursive_to_json


class Datastore:
    """
    A thread-safe key-value store that provides synchronized access to a dictionary,
    with some convenient methods for common operations and the ability to easily add
    functionality.

    Notes on thread safety:
        - All dictionary operations are atomic and thread-safe
        - However, if you retrieve mutable objects (lists, dicts, custom objects)
          via get() or __getitem__(), you must NOT mutate them directly outside
          of the store's atomic operations. Use operate(), update(), append(), etc.
          for safe mutations.
        - The store uses a lock for all operations, which may impact performance
          under high contention.

    Example:
        >>> store = Datastore()
        >>> store["counter"] = 0
        >>> store.increment("counter", 5)
        5
        >>> store.append(["nested", "items"], "value")
        >>> store.get(["nested", "items"])
        ['value']
    """

    def __init__(self) -> None:
        """Initialize an empty datastore."""
        # We use RLock to allow nested operations - specifically the operate method
        self.__lock = threading.RLock()
        self.__data: Dict[str, Any] = {}

    def __getitem__(self, name: str) -> Any:
        """
        Get a value by key.

        Warning: If the returned value is mutable (list, dict, custom object),
        do NOT mutate it directly. Use operate(), update(), append(), etc. instead.

        Args:
            name: The key to retrieve.

        Returns:
            The value associated with the key.

        Raises:
            KeyError: If the key doesn't exist.
        """
        with self.__lock:
            return self.__data[name]

    def __setitem__(self, name: str, value: Any) -> None:
        """
        Set a value by key.

        Args:
            name: The key to set.
            value: The value to store.
        """
        with self.__lock:
            self.__data[name] = value

    def __contains__(self, name: str) -> bool:
        """
        Check if a key exists.

        Args:
            name: The key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        with self.__lock:
            return name in self.__data

    def __delitem__(self, name: str) -> None:
        """
        Delete a key-value pair.

        Args:
            name: The key to delete.

        Raises:
            KeyError: If the key doesn't exist.
        """
        with self.__lock:
            del self.__data[name]

    def __iter__(self) -> Iterator[str]:
        """
        Return an iterator over the store's keys.

        Returns a snapshot of keys to avoid "dictionary changed during iteration" errors.

        Returns:
            An iterator over the keys.
        """
        with self.__lock:
            # Return iterator over a snapshot to avoid mutation during iteration
            return iter(list(self.__data.keys()))

    def __len__(self) -> int:
        """
        Get the number of items in the store.

        Returns:
            The number of key-value pairs.
        """
        with self.__lock:
            return len(self.__data)

    def __str__(self) -> str:
        """Return a string representation of the store."""
        with self.__lock:
            unlocked = _UnlockedDatastore(self.__data)
            return str(unlocked)

    def __repr__(self) -> str:
        """Return a string representation of the store."""
        return f"Datastore(items={len(self.__data)})"

    def __enter__(self) -> _UnlockedDatastore:
        """
        Enter context manager, acquiring the lock and returning an unlocked datastore view.

        This returns a Datastore-like object that shares the same data but has no locking.
        All operations on the unlocked datastore are performed directly on the shared data
        while the lock is held, ensuring thread safety.

        Warning: Do not hold this lock for long periods or perform slow operations,
        as it will block all other threads. As long as the context manager is open,
        the lock is held and therefore other functionality will fail.

        Example:
            >>> with store as unlocked:
            ...     unlocked["a"] = 1
            ...     unlocked["b"] = unlocked.get("a", 0) + 1
        
        Note that the unlocked datastore has an additional .data property
        which gives you raw access to the internal data. This allows you
        to do whatever you want with the data, but you must consider how 
        thread safety when doing so. Do not keep references to this outside
        of the context manager.

        Returns:
            An _UnlockedDatastore instance that shares the same data.
        """
        self.__lock.acquire()
        return _UnlockedDatastore(self.__data)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context manager, releasing the lock."""
        self.__lock.release()

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value by key with a default.

        Warning: If the returned value is mutable, do NOT mutate it directly.
        Use operate(), update(), append(), etc. instead.

        Args:
            key: The key to retrieve.
            default: The default value if key doesn't exist.

        Returns:
            The value associated with the key, or default if key doesn't exist.
        """
        with self.__lock:
            return self.__data.get(key, default)

    def operate(
        self, keys: str | List[str], operation: Callable[[Any], Any]
    ) -> Any:
        """
        Perform an atomic operation on a value in the store, supporting nested access.

        This method is fully atomic - the entire read-modify-write cycle happens
        under the lock, ensuring thread safety.

        Args:
            keys: A single key or list of keys forming a path to the target value.
                For nested access, use a list like ["a", "b", "c"].
            operation: A callable that takes the current value, transforms it,
                and returns the new value.

        Returns:
            The new value after applying the operation.

        Raises:
            ValueError: If a non-terminal key in the path doesn't point to a dictionary.
            KeyError: If the target key doesn't exist.

        Example:
            >>> store = Datastore()
            >>> store["nested"] = {"counter": 0}
            >>> store.operate(["nested", "counter"], lambda x: x + 1)
            1
        """
        with self.__lock:
            unlocked = _UnlockedDatastore(self.__data)
            return unlocked.operate(keys, operation)

    def update(self, key: str, operation: Callable[[Any], Any]) -> Any:
        """
        Update a value atomically using the provided operation.

        Args:
            key: The key to update.
            operation: A callable that takes the current value and returns the new value.

        Returns:
            The new value after applying the operation.

        Raises:
            KeyError: If the key doesn't exist.
        """
        with self.__lock:
            unlocked = _UnlockedDatastore(self.__data)
            return unlocked.update(key, operation)

    def items(self) -> List[tuple[str, Any]]:
        """
        Return a snapshot of the store's (key, value) pairs.

        Returns:
            A list of (key, value) tuples. This is a snapshot, not a live view.
        """
        with self.__lock:
            unlocked = _UnlockedDatastore(self.__data)
            return unlocked.items()

    def values(self) -> List[Any]:
        """
        Return a snapshot of the store's values.

        Returns:
            A list of values. This is a snapshot, not a live view.

        Warning: If values are mutable, do NOT mutate them directly.
        """
        with self.__lock:
            unlocked = _UnlockedDatastore(self.__data)
            return unlocked.values()

    def keys(self) -> List[str]:
        """
        Return a snapshot of the store's keys.

        Returns:
            A list of keys. This is a snapshot, not a live view.
        """
        with self.__lock:
            unlocked = _UnlockedDatastore(self.__data)
            return unlocked.keys()

    def init(self, key: str, value: Any) -> None:
        """
        Initialize a key with a value only if it doesn't already exist.

        Args:
            key: The key to initialize.
            value: The value to set if the key doesn't exist.
        """
        with self.__lock:
            if key not in self.__data:
                self.__data[key] = value

    def increment(self, key: str, amount: int | float = 1) -> int | float:
        """
        Increment a numeric value atomically.

        Args:
            key: The key to increment.
            amount: The amount to add. Defaults to 1.

        Returns:
            The new value after incrementing.

        Raises:
            KeyError: If the key doesn't exist.
            TypeError: If the value is not numeric.
        """
        return self.update(key, lambda x: x + amount)

    def decrement(self, key: str, amount: int | float = 1) -> int | float:
        """
        Decrement a numeric value atomically.

        Args:
            key: The key to decrement.
            amount: The amount to subtract. Defaults to 1.

        Returns:
            The new value after decrementing.

        Raises:
            KeyError: If the key doesn't exist.
            TypeError: If the value is not numeric.
        """
        return self.update(key, lambda x: x - amount)

    def append(self, keys: str | List[str], value: Any) -> None:
        """
        Append a value to a list atomically, supporting nested access.

        Args:
            keys: A single key or list of keys forming a path to the target list.
            value: The value to append.

        Raises:
            KeyError: If the key path doesn't exist.
            ValueError: If the target is not a list.
        """
        def append_op(x: Any) -> Any:
            if not isinstance(x, list):
                key_path = _path_to_string(keys) if isinstance(keys, list) else keys
                raise ValueError(f"Target at path '{key_path}' is not a list")
            x.append(value)
            return x

        self.operate(keys, append_op)

    def concat(self, keys: str | List[str], value: Any) -> None:
        """
        Concatenate a value to a string or list atomically.

        For strings: performs string concatenation.
        For lists: performs list concatenation (extends the list).

        Args:
            keys: A single key or list of keys forming a path to the target.
            value: The value to concatenate.

        Raises:
            KeyError: If the key path doesn't exist.
        """
        self.operate(keys, lambda x: x + value)


    def to_json(self) -> Dict[str, Any]:
        """
        Convert the store to a JSON-serializable dictionary.

        Returns:
            A dictionary containing the serialized data.
        """
        with self.__lock:
            unlocked = _UnlockedDatastore(self.__data)
            return unlocked.to_json()

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> Datastore:
        """
        Create a Datastore from JSON data.

        Args:
            data: A dictionary containing the data to load.

        Returns:
            A new Datastore instance.
        """
        store = cls()
        with store.__lock:
            unlocked = _UnlockedDatastore(store.__data)
            unlocked.data.update(data)
        return store
