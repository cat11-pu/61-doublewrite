"""doublewrite.py：双写（WAL 意图 -> 数据 -> 索引 -> 清 WAL，可重放、对账、快照恢复）。"""
from __future__ import annotations

import json
import os

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "doublewrite.snapshot.json")


class Store:
    def __init__(self):
        self.data = {}
        self.index = {}
        self.wal = []
        self.repaired = 0
        self.replayed = 0

    def put(self, key: str, value: str, crash_after_data: bool = False) -> dict:
        """记 WAL 意图 -> 写数据 -> 写索引 -> 清 WAL；崩溃则保留 WAL。"""
        intent = {"op": "put", "key": key, "value": value}
        self.wal.append(intent)
        old_value = self.data.get(key)
        self.data[key] = value
        if crash_after_data:
            return {"data": True, "index": False}
        self._index_add(key, value, old_value)
        self.wal.remove(intent)
        return {"data": True, "index": True}

    def _index_add(self, key: str, value: str, old_value=None) -> None:
        if old_value is not None and old_value != value:
            old_keys = self.index.get(old_value)
            if old_keys is not None:
                old_keys.discard(key)
                if not old_keys:
                    del self.index[old_value]
        self.index.setdefault(value, set()).add(key)

    def get(self, value: str) -> dict:
        return {"keys": sorted(self.index.get(value, set()))}

    def replay(self) -> dict:
        """重放 WAL 里未完成的意图，把索引补齐，然后清空 WAL。"""
        count = 0
        for intent in list(self.wal):
            if intent.get("op") != "put":
                continue
            key, value = intent["key"], intent["value"]
            self.data[key] = value
            self.index.setdefault(value, set()).add(key)
            count += 1
        self.wal.clear()
        self.replayed += count
        return {"replayed": count}

    def reconcile(self) -> dict:
        """O(键数) 扫描：数据里有、索引里没有的键，修复并报告。"""
        missing = []
        for key, value in self.data.items():
            if key not in self.index.get(value, ()):
                missing.append(key)
                self.index.setdefault(value, set()).add(key)
        missing.sort()
        self.repaired += len(missing)
        return {"missing": missing, "repaired": len(missing)}

    def persist(self) -> dict:
        """快照落盘，返回 blob（索引的 set 序列化为有序列表）。"""
        blob = {
            "data": dict(self.data),
            "index": {value: sorted(keys) for value, keys in self.index.items()},
            "wal": [dict(intent) for intent in self.wal],
            "replayed": self.replayed,
            "repaired": self.repaired,
        }
        with open(SNAPSHOT_PATH, "w", encoding="utf-8") as handle:
            json.dump(blob, handle, ensure_ascii=False)
        return blob

    def restore(self, blob) -> dict:
        """从 blob（dict 或 JSON 字符串）恢复数据、索引与 WAL。"""
        if isinstance(blob, (str, bytes)):
            blob = json.loads(blob)
        self.data = dict(blob.get("data", {}))
        self.index = {value: set(keys) for value, keys in blob.get("index", {}).items()}
        self.wal = [dict(intent) for intent in blob.get("wal", [])]
        self.replayed = blob.get("replayed", 0)
        self.repaired = blob.get("repaired", 0)
        return self.stats()

    def recover(self) -> dict:
        """模拟重启：落盘后清空内存，再从快照恢复。"""
        self.persist()
        with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
            blob = json.load(handle)
        self.__init__()
        self.restore(blob)
        return self.stats()

    def stats(self) -> dict:
        return {"data": len(self.data), "index": len(self.index), "replayed": self.replayed,
                "repaired": self.repaired}
