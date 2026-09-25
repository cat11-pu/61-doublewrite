"""doublewrite.py：数据 + 倒排索引双写，WAL 兜底崩溃与对账。"""
from __future__ import annotations

import json
import os
import tempfile

SNAPSHOT_PATH = os.path.join(tempfile.gettempdir(), "doublewrite.snapshot.json")


class Store:
    def __init__(self):
        self.data = {}
        self.index = {}
        self.wal = []
        self.repaired = 0
        self.replayed = 0

    def put(self, key: str, value: str, crash_after_data: bool = False) -> dict:
        """记 WAL 意图 → 写数据 → 写索引 → 清 WAL。"""
        intent = {"key": key, "value": value}
        self.wal.append(intent)
        self.data[key] = value
        if crash_after_data:
            return {"data": True, "index": False}
        self.index.setdefault(value, set()).add(key)
        self.wal.pop()
        return {"data": True, "index": True}

    def get(self, value: str) -> dict:
        return {"keys": sorted(self.index.get(value, set()))}

    def replay(self) -> dict:
        """重放 WAL 中未完成的意图，把索引补齐，然后清空 WAL。"""
        pending = self.wal
        self.wal = []
        count = 0
        for intent in pending:
            count += self._index_intent(intent)
        self.replayed += count
        return {"replayed": count}

    def reconcile(self) -> dict:
        """一遍扫描数据：找出“数据里有、索引里没有（或挂错值）”的键并修复。O(键数)。"""
        missing = []
        repaired = 0
        for key, value in self.data.items():
            if key not in self.index.get(value, ()):
                missing.append(key)
                self.index.setdefault(value, set()).add(key)
                repaired += 1
        self.repaired += repaired
        return {"missing": sorted(missing), "repaired": repaired}

    def _index_intent(self, intent: dict) -> int:
        """按当前数据把意图补进索引；数据已被覆盖则只清旧映射，不计数。"""
        key = intent["key"]
        value = intent["value"]
        if self.data.get(key) != value:
            return 0
        for keys in self.index.values():
            keys.discard(key)
        self.index.setdefault(value, set()).add(key)
        return 1

    def persist(self, path: str = SNAPSHOT_PATH) -> str:
        """落盘快照：数据、索引、WAL 与计数器一致序列化，返回 JSON 文本。"""
        blob = json.dumps({
            "data": self.data,
            "index": {value: sorted(keys) for value, keys in self.index.items()},
            "wal": self.wal,
            "replayed": self.replayed,
            "repaired": self.repaired,
        }, ensure_ascii=False, sort_keys=True)
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(blob)
        return blob

    def restore(self, blob=None, path: str = SNAPSHOT_PATH) -> dict:
        """从快照恢复；blob 缺省时从落盘文件读。"""
        if blob is None:
            with open(path, encoding="utf-8") as handle:
                blob = handle.read()
        if isinstance(blob, (bytes, bytearray)):
            blob = blob.decode("utf-8")
        snapshot = json.loads(blob)
        self.data = dict(snapshot["data"])
        self.index = {value: set(keys) for value, keys in snapshot["index"].items()}
        self.wal = [dict(intent) for intent in snapshot["wal"]]
        self.replayed = snapshot.get("replayed", 0)
        self.repaired = snapshot.get("repaired", 0)
        return self.stats()

    def recover(self, path: str = SNAPSHOT_PATH) -> dict:
        """模拟重启：先落盘，再从快照恢复，并重放残留 WAL 意图。"""
        blob = self.persist(path)
        self.restore(blob)
        self.replay()
        return self.stats()

    def stats(self) -> dict:
        return {"data": len(self.data), "index": len(self.index), "replayed": self.replayed,
                "repaired": self.repaired}
