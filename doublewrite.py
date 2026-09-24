"""doublewrite.py：双写（基线：数据与索引各写各的）。"""
from __future__ import annotations


class Store:
    def __init__(self):
        self.data = {}
        self.index = {}
        self.wal = []
        self.repaired = 0
        self.replayed = 0

    def put(self, key: str, value: str, crash_after_data: bool = False) -> dict:
        """基线：写数据后如果崩了，索引就不写，也不留痕迹。"""
        self.data[key] = value
        if crash_after_data:
            return {"data": True, "index": False}
        self.index.setdefault(value, set()).add(key)
        return {"data": True, "index": True}

    def get(self, value: str) -> dict:
        return {"keys": sorted(self.index.get(value, set()))}

    def replay(self) -> dict:
        raise NotImplementedError("恢复重放还没实现")

    def reconcile(self) -> dict:
        raise NotImplementedError("对账修复还没实现")

    def recover(self) -> dict:
        raise NotImplementedError("重启恢复还没实现")

    def stats(self) -> dict:
        return {"data": len(self.data), "index": len(self.index), "replayed": self.replayed,
                "repaired": self.repaired}
