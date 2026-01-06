# ThreadSafe DataStore

Simple, convenient thread safe data store.

## Features

- **Thread-safe**: All operations are atomic and synchronized using locks
- **Nested access**: Support for deep nested dictionary operations via key paths
- **Atomic operations**: Safe read-modify-write operations on values
- **Context manager**: Direct unlocked access to data while holding the lock
- **Utility methods**: Convenient methods for common operations (increment, append, etc.)

## Why?

...because I kept rebuilding this feature to pass around context within AI agents working on the same data across ultiple threads. I kept wanting a simple atomic datastore that wasn't a pain to use. You can see that this is clearly inspired by my earlier version within the [arkaine](https://github.com/hlfshell/arkaine) AI library. So - here it is as a stand alone package for easier use. Hopefully it helps you out.

## Installation

Install from PyPI:

```bash
pip install threadsafe-datastore
```

Or install from source:

```bash
git clone https://github.com/hlfshell/threadsafe-datastore.git
cd threadsafe-datastore
pip install -e .
```

## Quick Start

```python
from threadsafe_datastore import Datastore

# Create a store
store = Datastore()

# Basic set / get operation
store["counter"] = 0
store["counter"]  # 0

# The helper functions provide common features that
# are thread safe
store.increment("counter", 5)  # Returns 5
store["counter"]  # 5

# Nested dictionary support while supporting thread safety:
store["nested"] = {"items": []}
store.append(["nested", "items"], "value1")
store.append(["nested", "items"], "value2")
store["nested"]["items"]  # ["value1", "value2"]

# Context manager to perform multiple step or batch
# operations all while maintaining a lock:
with store as unlocked:
    unlocked["a"] = 1
    unlocked["b"] = unlocked.get("a", 0) + 1
    
    # You can also access the raw dict here, though
    # this is dangerous and should only be used with
    # careful forethought.
    raw_data = unlocked.data
```

⚠️ **Important**: While all dictionary operations are thread-safe, if you retrieve mutable objects (lists, dicts, custom objects) via `get()` or `__getitem__()`, you must **NOT** mutate them directly outside of the store's atomic operations.

Or, in other words, never do something like this:
```python
my_list = store["my_list"]
my_list.append("item")
```
Instead use the helper functions:
```python
store.append("my_list", "item")  # Thread-safe
# or
store.operate("my_list", lambda x: x + ["item"])  # Thread-safe
# or
with store as unlocked:
    list = store["my_list"]
    list.append("item")
```

## API Reference

### Core Operations

- `store[key]` - Get a value
- `store[key] = value` - Set a value
- `del store[key]` - Delete a key
- `key in store` - Check if key exists
- `len(store)` - Get number of items
- `iter(store)` - Iterate over keys

### Methods

#### `get(key, default=None)`
Get a value with a default if key doesn't exist.

#### `operate(keys, operation)`
Perform an atomic operation on a value. Supports nested paths.

```python
# Single key
store.operate("counter", lambda x: x + 1)

# Nested path
store.operate(["user", "profile", "score"], lambda x: x + 10)
```

#### `update(key, operation)`
Update a top-level key atomically.

```python
store.update("counter", lambda x: x * 2)
```

#### `init(key, value)`
Initialize a key only if it doesn't exist.

#### `increment(key, amount=1)` / `decrement(key, amount=1)`
Atomically increment or decrement a numeric value.

#### `append(keys, value)`
Append to a list atomically. Supports nested paths.

```python
store.append("items", "new_item")
store.append(["nested", "items"], "new_item")
```

#### `concat(keys, value)`
Concatenate to a string or list atomically.

#### Context Manager
Use the store as a context manager to get an unlocked datastore view with direct access.

```python
with store as unlocked:
    # Perform multiple operations atomically
    unlocked["a"] = 1
    unlocked["b"] = unlocked.get("a", 0) + 1
    raw = unlocked.data  # Get raw dict reference via .data property
```

#### `to_json()` / `from_json(data)`
Serialize/deserialize the store to/from JSON. A recursive function is used to dive into nested functions.

## Examples

### Nested Operations

```python
store = Datastore()

# Create nested structure
store["config"] = {
    "database": {
        "host": "localhost",
        "port": 5432
    }
}

# Atomic operation on nested value
store.operate(["config", "database", "port"], lambda x: x + 1)
```

### Context Manager for Batch Operations

```python
import time

store = Datastore()

# Use context manager for multiple atomic operations
with store as unlocked:
    unlocked["total"] = unlocked.get("total", 0) + 10
    unlocked["count"] = unlocked.get("count", 0) + 1
    unlocked["last_updated"] = time.time()
    # All operations happen while lock is held
```

## License

This code is provided under the MIT licesne - see LICENSE.
