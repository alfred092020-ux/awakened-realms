import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
LIB_DIR = TEST_DIR.parent / "lib"
sys.path.insert(0, str(LIB_DIR))

from logres_runtime_lanes import (
    ResourceBusy,
    RuntimeLaneStore,
    sandbox_path,
    workload_resources,
)


class RuntimeLaneStoreTests(unittest.TestCase):
    def make_store(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        store = RuntimeLaneStore(conn)
        store.ensure_schema()
        return store

    def test_capacity_allows_parallel_holders_then_rejects_next(self):
        store = self.make_store()
        store.define_resource("verify-heavy", capacity=2)

        first = store.acquire(["verify-heavy"], owner="chat-a", task_id="A", ttl_seconds=60, now=100)
        second = store.acquire(["verify-heavy"], owner="chat-b", task_id="B", ttl_seconds=60, now=100)

        self.assertNotEqual(first, second)
        with self.assertRaises(ResourceBusy):
            store.acquire(["verify-heavy"], owner="chat-c", task_id="C", ttl_seconds=60, now=100)

    def test_expired_holder_is_reclaimed(self):
        store = self.make_store()
        store.define_resource("phone", capacity=1)
        store.acquire(["phone"], owner="chat-a", task_id="A", ttl_seconds=10, now=100)

        lease = store.acquire(["phone"], owner="chat-b", task_id="B", ttl_seconds=10, now=111)
        holders = store.status(now=111)["phone"]["holders"]

        self.assertEqual(1, len(holders))
        self.assertEqual("chat-b", holders[0]["owner"])
        self.assertEqual(lease, holders[0]["lease_id"])

    def test_bundle_acquire_is_atomic(self):
        store = self.make_store()
        store.define_resource("live-runtime", capacity=1)
        store.define_resource("privileged-executor", capacity=1)
        store.acquire(["live-runtime"], owner="chat-a", task_id="A", ttl_seconds=60, now=100)

        with self.assertRaises(ResourceBusy):
            store.acquire(
                ["live-runtime", "privileged-executor"],
                owner="chat-b",
                task_id="B",
                ttl_seconds=60,
                now=100,
            )

        self.assertEqual([], store.status(now=100)["privileged-executor"]["holders"])

    def test_release_bundle_frees_all_resources(self):
        store = self.make_store()
        for name in ("promotion", "privileged-executor"):
            store.define_resource(name, capacity=1)
        lease = store.acquire(
            ["promotion", "privileged-executor"],
            owner="chat-a",
            task_id="A",
            ttl_seconds=60,
            now=100,
        )

        self.assertEqual(2, store.release(lease))
        status = store.status(now=100)
        self.assertEqual([], status["promotion"]["holders"])
        self.assertEqual([], status["privileged-executor"]["holders"])

    def test_sandbox_path_is_deterministic_and_isolated(self):
        root = Path("/tmp/runtime-sandboxes")
        a = sandbox_path(root, "chat/a", "TASK 1", "abcdef1234567890")
        b = sandbox_path(root, "chat/b", "TASK 1", "abcdef1234567890")

        self.assertNotEqual(a, b)
        self.assertEqual(root, Path(*a.parts[:len(root.parts)]))
        self.assertNotIn("/", a.relative_to(root).parts[0])
        self.assertTrue(str(a).endswith("abcdef123456"))

    def test_workload_resources_only_serializes_shared_mutation(self):
        self.assertEqual(("verify-heavy",), workload_resources("verify"))
        self.assertEqual(
            ("integration-promotion",),
            workload_resources("promote"),
        )
        self.assertEqual(
            ("nexus-live-runtime", "privileged-executor"),
            workload_resources("deploy-live-nexus"),
        )
        self.assertEqual(
            ("android-device",),
            workload_resources("device-qa"),
        )


if __name__ == "__main__":
    unittest.main()
