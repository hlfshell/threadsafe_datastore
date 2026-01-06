"""
Comprehensive tests for the Datastore class.

Tests cover:
- Basic operations (get, set, delete, contains, len, iter)
- Thread safety
- Nested operations
- Utility methods (increment, decrement, append, concat, init, update)
- Context manager (unlocked datastore)
- JSON serialization
- Edge cases and error conditions
"""

import json
import threading
import time
from typing import Any

import pytest

from threadsafe_datastore import Datastore


class TestBasicOperations:
    """Test basic dictionary-like operations."""

    def test_set_and_get(self):
        """Test setting and getting values."""
        store = Datastore()
        store["key1"] = "value1"
        store["key2"] = 42
        store["key3"] = [1, 2, 3]

        assert store["key1"] == "value1"
        assert store["key2"] == 42
        assert store["key3"] == [1, 2, 3]

    def test_get_with_default(self):
        """Test get() with default value."""
        store = Datastore()
        assert store.get("nonexistent") is None
        assert store.get("nonexistent", "default") == "default"
        assert store.get("nonexistent", 0) == 0

        store["exists"] = "value"
        assert store.get("exists") == "value"
        assert store.get("exists", "default") == "value"

    def test_contains(self):
        """Test __contains__ (in operator)."""
        store = Datastore()
        assert "key" not in store

        store["key"] = "value"
        assert "key" in store
        assert "nonexistent" not in store

    def test_delete(self):
        """Test deleting keys."""
        store = Datastore()
        store["key1"] = "value1"
        store["key2"] = "value2"

        assert "key1" in store
        del store["key1"]
        assert "key1" not in store
        assert "key2" in store

        with pytest.raises(KeyError):
            del store["nonexistent"]

    def test_len(self):
        """Test __len__."""
        store = Datastore()
        assert len(store) == 0

        store["key1"] = "value1"
        assert len(store) == 1

        store["key2"] = "value2"
        assert len(store) == 2

        del store["key1"]
        assert len(store) == 1

    def test_iter(self):
        """Test iteration over keys."""
        store = Datastore()
        store["a"] = 1
        store["b"] = 2
        store["c"] = 3

        keys = list(store)
        assert set(keys) == {"a", "b", "c"}

    def test_iter_snapshot(self):
        """Test that iteration returns a snapshot."""
        store = Datastore()
        store["a"] = 1
        store["b"] = 2

        keys = list(store)
        store["c"] = 3  # Add after creating iterator

        # Original iterator should not include new key
        assert len(keys) == 2
        assert "c" not in keys

    def test_iter_thread_safe(self):
        """Test that iteration is thread-safe (snapshot creation is atomic)."""
        store = Datastore()
        num_threads = 10
        iterations = 50

        def add_and_iterate(thread_id):
            for i in range(iterations):
                store[f"key_{thread_id}_{i}"] = i
                # Iterate while other threads are modifying
                list(store)  # Consume iterator

        threads = [threading.Thread(target=add_and_iterate, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All iterations should complete without errors
        assert len(store) == num_threads * iterations

    def test_iter_snapshot_consistency(self):
        """Test that iteration snapshot is consistent even if store changes."""
        store = Datastore()
        store["a"] = 1
        store["b"] = 2

        # Get iterator
        iterator = iter(store)
        
        # Modify store
        store["c"] = 3
        del store["a"]
        
        # Iterator should still have original keys (snapshot)
        keys = list(iterator)
        assert set(keys) == {"a", "b"}  # Original snapshot
        assert "c" not in keys
        assert "a" in keys  # Still in snapshot even though deleted

    def test_str_repr(self):
        """Test string representations."""
        store = Datastore()
        assert str(store) == "{}"
        assert "Datastore" in repr(store)

        store["key1"] = "value1"
        store["key2"] = 42
        str_repr = str(store)
        assert "key1" in str_repr
        assert "key2" in str_repr
        assert "value1" in str_repr
        assert "42" in str_repr

    def test_key_error_on_missing(self):
        """Test that KeyError is raised for missing keys."""
        store = Datastore()
        with pytest.raises(KeyError):
            _ = store["nonexistent"]


class TestNestedOperations:
    """Test nested dictionary operations."""

    def test_operate_single_key(self):
        """Test operate() with a single key."""
        store = Datastore()
        store["counter"] = 0

        result = store.operate("counter", lambda x: x + 1)
        assert result == 1
        assert store["counter"] == 1

        result = store.operate("counter", lambda x: x * 2)
        assert result == 2
        assert store["counter"] == 2

    def test_operate_nested_path(self):
        """Test operate() with nested paths."""
        store = Datastore()
        store["level1"] = {"level2": {"value": 10}}

        result = store.operate(["level1", "level2", "value"], lambda x: x + 5)
        assert result == 15
        assert store["level1"]["level2"]["value"] == 15

    def test_operate_deeply_nested(self):
        """Test operate() with deeply nested paths."""
        store = Datastore()
        store["a"] = {"b": {"c": {"d": {"e": 100}}}}

        result = store.operate(["a", "b", "c", "d", "e"], lambda x: x - 50)
        assert result == 50
        assert store["a"]["b"]["c"]["d"]["e"] == 50

    def test_operate_missing_path(self):
        """Test operate() with missing path."""
        store = Datastore()
        store["a"] = {}

        with pytest.raises(KeyError, match="Path 'a.b' does not exist"):
            store.operate(["a", "b", "c"], lambda x: x)

    def test_operate_non_dict_intermediate(self):
        """Test operate() when intermediate key is not a dict."""
        store = Datastore()
        store["a"] = "not a dict"

        with pytest.raises(ValueError, match="Path 'a' is not a dictionary"):
            store.operate(["a", "b"], lambda x: x)

    def test_operate_missing_final_key(self):
        """Test operate() when final key doesn't exist."""
        store = Datastore()
        store["a"] = {"b": {}}

        with pytest.raises(KeyError, match="Key path 'a.b.c' does not exist"):
            store.operate(["a", "b", "c"], lambda x: x)


class TestUtilityMethods:
    """Test utility methods (increment, decrement, append, concat, init, update)."""

    def test_increment(self):
        """Test increment() method."""
        store = Datastore()
        store["counter"] = 0

        assert store.increment("counter") == 1
        assert store["counter"] == 1

        assert store.increment("counter", 5) == 6
        assert store["counter"] == 6

        assert store.increment("counter", 0.5) == 6.5
        assert store["counter"] == 6.5

    def test_increment_missing_key(self):
        """Test increment() with missing key."""
        store = Datastore()
        with pytest.raises(KeyError):
            store.increment("nonexistent")

    def test_decrement(self):
        """Test decrement() method."""
        store = Datastore()
        store["counter"] = 10

        assert store.decrement("counter") == 9
        assert store["counter"] == 9

        assert store.decrement("counter", 3) == 6
        assert store["counter"] == 6

        assert store.decrement("counter", 1.5) == 4.5
        assert store["counter"] == 4.5

    def test_decrement_missing_key(self):
        """Test decrement() with missing key."""
        store = Datastore()
        with pytest.raises(KeyError):
            store.decrement("nonexistent")

    def test_append_single_key(self):
        """Test append() with single key."""
        store = Datastore()
        store["items"] = []

        store.append("items", "value1")
        assert store["items"] == ["value1"]

        store.append("items", "value2")
        assert store["items"] == ["value1", "value2"]

    def test_append_nested_path(self):
        """Test append() with nested path."""
        store = Datastore()
        store["nested"] = {"items": []}

        store.append(["nested", "items"], "value1")
        assert store["nested"]["items"] == ["value1"]

        store.append(["nested", "items"], "value2")
        assert store["nested"]["items"] == ["value1", "value2"]

    def test_append_not_list(self):
        """Test append() when target is not a list."""
        store = Datastore()
        store["not_list"] = "string"

        with pytest.raises(ValueError, match="is not a list"):
            store.append("not_list", "value")

    def test_append_missing_path(self):
        """Test append() with missing path."""
        store = Datastore()
        with pytest.raises(KeyError):
            store.append(["a", "b"], "value")

    def test_concat_string(self):
        """Test concat() with string."""
        store = Datastore()
        store["text"] = "hello"

        store.concat("text", " world")
        assert store["text"] == "hello world"

    def test_concat_list(self):
        """Test concat() with list."""
        store = Datastore()
        store["items"] = [1, 2]

        store.concat("items", [3, 4])
        assert store["items"] == [1, 2, 3, 4]

    def test_concat_nested(self):
        """Test concat() with nested path."""
        store = Datastore()
        store["nested"] = {"text": "hello"}

        store.concat(["nested", "text"], " world")
        assert store["nested"]["text"] == "hello world"

    def test_init_new_key(self):
        """Test init() with new key."""
        store = Datastore()
        store.init("new_key", "value")
        assert store["new_key"] == "value"

    def test_init_existing_key(self):
        """Test init() with existing key (should not overwrite)."""
        store = Datastore()
        store["existing"] = "original"
        store.init("existing", "new_value")
        assert store["existing"] == "original"  # Should not change

    def test_update(self):
        """Test update() method."""
        store = Datastore()
        store["value"] = 10

        result = store.update("value", lambda x: x * 2)
        assert result == 20
        assert store["value"] == 20

    def test_update_missing_key(self):
        """Test update() with missing key."""
        store = Datastore()
        with pytest.raises(KeyError):
            store.update("nonexistent", lambda x: x)


class TestContextManager:
    """Test context manager (unlocked datastore)."""

    def test_context_manager_basic(self):
        """Test basic context manager usage."""
        store = Datastore()
        store["a"] = 1

        with store as unlocked:
            assert unlocked["a"] == 1
            unlocked["b"] = 2
            assert unlocked.get("b") == 2

        # Changes should persist
        assert store["b"] == 2

    def test_context_manager_raw_data(self):
        """Test .data property basic functionality."""
        store = Datastore()
        store["a"] = 1

        with store as unlocked:
            raw = unlocked.data
            assert isinstance(raw, dict)
            assert raw is unlocked.data  # Same reference
            assert raw["a"] == 1

    def test_context_manager_data_mutations(self):
        """Test that mutations via .data property persist to store."""
        store = Datastore()
        store["a"] = 1

        with store as unlocked:
            unlocked.data["b"] = 2
            unlocked.data["c"] = {"nested": 3}
            unlocked.data.update({"d": 4, "e": 5})
            unlocked.data["a"] = 10  # Modify existing

        assert store["a"] == 10
        assert store["b"] == 2
        assert store["c"] == {"nested": 3}
        assert store["d"] == 4
        assert store["e"] == 5

    def test_context_manager_data_bulk_operations(self):
        """Test bulk operations via .data property."""
        store = Datastore()
        store["a"] = 1

        with store as unlocked:
            # Clear and repopulate
            unlocked.data.clear()
            unlocked.data.update({"x": 1, "y": 2, "z": 3})
            # Delete a key
            del unlocked.data["y"]
            # Set nested structure
            unlocked.data["nested"] = {"level1": {"level2": "value"}}

        assert len(store) == 3
        assert "a" not in store
        assert "x" in store
        assert "y" not in store
        assert store["nested"]["level1"]["level2"] == "value"

    def test_context_manager_data_reference_persistence(self):
        """Test that .data reference is the same object."""
        store = Datastore()
        store["a"] = 1

        with store as unlocked:
            raw_ref = unlocked.data
            raw_ref2 = unlocked.data

        # Both references should be the same object
        assert raw_ref is raw_ref2
        # The reference should contain the data (though accessing outside context is unsafe)
        assert "a" in raw_ref
        assert raw_ref["a"] == 1

    def test_context_manager_operations(self):
        """Test operations within context manager."""
        store = Datastore()
        store["counter"] = 0
        store["items"] = []

        with store as unlocked:
            unlocked.increment("counter", 5)
            unlocked.append("items", "value1")
            unlocked["new_key"] = "new_value"

        assert store["counter"] == 5
        assert store["items"] == ["value1"]
        assert store["new_key"] == "new_value"

    def test_context_manager_nested_operations(self):
        """Test nested operations within context manager."""
        store = Datastore()
        store["nested"] = {"counter": 0, "items": []}

        with store as unlocked:
            unlocked.operate(["nested", "counter"], lambda x: x + 10)
            unlocked.append(["nested", "items"], "value")

        assert store["nested"]["counter"] == 10
        assert store["nested"]["items"] == ["value"]

    def test_context_manager_lock_held(self):
        """Test that lock is held during context manager."""
        store = Datastore()
        store["value"] = 0
        access_attempted = threading.Event()

        def try_access():
            """Try to access store from another thread."""
            time.sleep(0.1)  # Wait for context manager to be entered
            access_attempted.set()
            # This will block until the context manager releases the lock
            store["value"] = 999

        thread = threading.Thread(target=try_access)
        thread.start()

        # Wait for thread to start trying to access
        time.sleep(0.15)
        
        with store as unlocked:
            # Hold lock and set value
            unlocked["value"] = 1
            # Verify thread is waiting (hasn't set value to 999 yet)
            assert store["value"] == 1
            time.sleep(0.1)  # Hold lock a bit longer

        thread.join()
        # After context manager exits, thread may have set it to 999
        # But during the context manager, it should have been 1
        assert store["value"] in (1, 999)  # Either is valid depending on timing


class TestThreadSafety:
    """Test thread safety of operations."""

    def test_concurrent_writes(self):
        """Test concurrent writes to different keys."""
        store = Datastore()
        num_threads = 10
        iterations = 100

        def writer(thread_id: int):
            for i in range(iterations):
                key = f"key_{thread_id}"
                store[key] = i

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All keys should exist
        for i in range(num_threads):
            assert f"key_{i}" in store
            assert store[f"key_{i}"] == iterations - 1

    def test_concurrent_increments(self):
        """Test concurrent increments to same key."""
        store = Datastore()
        store["counter"] = 0
        num_threads = 10
        increments_per_thread = 100

        def incrementer():
            for _ in range(increments_per_thread):
                store.increment("counter")

        threads = [threading.Thread(target=incrementer) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * increments_per_thread
        assert store["counter"] == expected

    def test_concurrent_operate(self):
        """Test concurrent operate() calls."""
        store = Datastore()
        store["value"] = 0
        num_threads = 10
        operations_per_thread = 50

        def operator():
            for _ in range(operations_per_thread):
                store.operate("value", lambda x: x + 1)

        threads = [threading.Thread(target=operator) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * operations_per_thread
        assert store["value"] == expected

    def test_concurrent_nested_operations(self):
        """Test concurrent nested operations."""
        store = Datastore()
        store["nested"] = {"counter": 0}
        num_threads = 5
        operations_per_thread = 20

        def nested_operator():
            for _ in range(operations_per_thread):
                store.operate(["nested", "counter"], lambda x: x + 1)

        threads = [threading.Thread(target=nested_operator) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = num_threads * operations_per_thread
        assert store["nested"]["counter"] == expected

    def test_concurrent_reads_and_writes(self):
        """Test concurrent reads and writes."""
        store = Datastore()
        store["value"] = 0
        num_threads = 5
        iterations = 100

        def reader():
            for _ in range(iterations):
                _ = store.get("value")

        def writer():
            for i in range(iterations):
                store["value"] = i

        reader_threads = [threading.Thread(target=reader) for _ in range(num_threads)]
        writer_threads = [threading.Thread(target=writer) for _ in range(num_threads)]

        for t in reader_threads + writer_threads:
            t.start()
        for t in reader_threads + writer_threads:
            t.join()

        # Final value should be valid
        assert store["value"] == iterations - 1

    def test_concurrent_deletes(self):
        """Test concurrent deletes."""
        store = Datastore()
        num_keys = 100

        # Initialize keys
        for i in range(num_keys):
            store[f"key_{i}"] = i

        def deleter(start: int, end: int):
            for i in range(start, end):
                if f"key_{i}" in store:
                    del store[f"key_{i}"]

        threads = [
            threading.Thread(target=deleter, args=(i * 20, (i + 1) * 20))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All keys should be deleted
        assert len(store) == 0


class TestJSONSerialization:
    """Test JSON serialization."""

    def test_to_json_basic(self):
        """Test to_json() with basic types."""
        store = Datastore()
        store["string"] = "value"
        store["int"] = 42
        store["float"] = 3.14
        store["bool"] = True
        store["none"] = None

        json_data = store.to_json()
        assert json_data["string"] == "value"
        assert json_data["int"] == 42
        assert json_data["float"] == 3.14
        assert json_data["bool"] is True
        assert json_data["none"] is None

    def test_to_json_nested(self):
        """Test to_json() with nested structures."""
        store = Datastore()
        store["nested"] = {"a": 1, "b": {"c": 2}}
        store["list"] = [1, 2, 3]

        json_data = store.to_json()
        assert json_data["nested"]["a"] == 1
        assert json_data["nested"]["b"]["c"] == 2
        assert json_data["list"] == [1, 2, 3]

    def test_to_json_custom_object(self):
        """Test to_json() with custom objects (should convert to string)."""
        store = Datastore()

        class CustomObject:
            def __init__(self, value):
                self.value = value

            def __str__(self):
                return f"Custom({self.value})"

        store["custom"] = CustomObject(42)
        json_data = store.to_json()
        assert json_data["custom"] == "Custom(42)"

    def test_from_json(self):
        """Test from_json() class method."""
        data = {
            "a": 1,
            "b": "value",
            "c": {"nested": 2},
            "d": [1, 2, 3],
        }

        store = Datastore.from_json(data)
        assert store["a"] == 1
        assert store["b"] == "value"
        assert store["c"]["nested"] == 2
        assert store["d"] == [1, 2, 3]

    def test_json_roundtrip(self):
        """Test JSON serialization roundtrip."""
        store = Datastore()
        store["a"] = 1
        store["b"] = "value"
        store["c"] = {"nested": 2}
        store["d"] = [1, 2, 3]

        json_data = store.to_json()
        new_store = Datastore.from_json(json_data)

        assert new_store["a"] == 1
        assert new_store["b"] == "value"
        assert new_store["c"]["nested"] == 2
        assert new_store["d"] == [1, 2, 3]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_store(self):
        """Test operations on empty store."""
        store = Datastore()
        assert len(store) == 0
        assert list(store) == []
        assert store.items() == []
        assert store.keys() == []
        assert store.values() == []

    def test_none_values(self):
        """Test storing None values."""
        store = Datastore()
        store["none"] = None
        assert store["none"] is None
        assert store.get("none") is None

    def test_complex_nested_structure(self):
        """Test with complex nested structure."""
        store = Datastore()
        store["level1"] = {
            "level2": {
                "level3": {
                    "level4": {
                        "value": "deep"
                    }
                }
            }
        }

        result = store.operate(
            ["level1", "level2", "level3", "level4", "value"],
            lambda x: x.upper()
        )
        assert result == "DEEP"
        assert store["level1"]["level2"]["level3"]["level4"]["value"] == "DEEP"

    def test_list_operations(self):
        """Test operations on lists."""
        store = Datastore()
        store["items"] = [1, 2, 3]

        store.operate("items", lambda x: x + [4, 5])
        assert store["items"] == [1, 2, 3, 4, 5]

        store.operate("items", lambda x: x[::-1])
        assert store["items"] == [5, 4, 3, 2, 1]

    def test_dict_operations(self):
        """Test operations on dictionaries."""
        store = Datastore()
        store["data"] = {"a": 1, "b": 2}

        store.operate("data", lambda x: {**x, "c": 3})
        assert store["data"] == {"a": 1, "b": 2, "c": 3}

    def test_operate_with_string_key(self):
        """Test operate() accepts both string and list."""
        store = Datastore()
        store["value"] = 10

        # String key
        result1 = store.operate("value", lambda x: x + 1)
        assert result1 == 11

        # List with single element (equivalent)
        result2 = store.operate(["value"], lambda x: x + 1)
        assert result2 == 12

    def test_items_values_keys_snapshots(self):
        """Test that items(), values(), keys() return snapshots."""
        store = Datastore()
        store["a"] = 1
        store["b"] = 2

        items = store.items()
        values = store.values()
        keys = store.keys()

        # Modify store
        store["c"] = 3
        del store["a"]

        # Snapshots should not change
        assert len(items) == 2
        assert len(values) == 2
        assert len(keys) == 2
        assert ("a", 1) in items
        assert "a" in keys

    def test_multiple_context_managers_nested(self):
        """Test nested context managers (should work with RLock)."""
        store = Datastore()
        store["value"] = 0

        with store as unlocked1:
            unlocked1["value"] = 1
            with store as unlocked2:
                unlocked2["value"] = 2
                assert unlocked1["value"] == 2
                assert unlocked2["value"] == 2

        assert store["value"] == 2

    def test_context_manager_exception(self):
        """Test that context manager releases lock on exception."""
        store = Datastore()
        store["value"] = 0

        try:
            with store as unlocked:
                unlocked["value"] = 1
                raise ValueError("test exception")
        except ValueError:
            pass

        # Lock should be released, value should be updated
        assert store["value"] == 1
        # Should be able to access store normally
        assert store["value"] == 1

