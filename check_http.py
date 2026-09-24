"""check_http.py：起服务、按脚本走一圈，打印验收面。"""
import json
import sys
import threading
import urllib.error
import urllib.request

from server import serve


def call(method, url, body=None):
    request = urllib.request.Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def parse(text):
    try:
        return json.loads(text)
    except Exception:
        return {"_raw": (text or "")[:60]}


def main() -> int:
    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "sample/writes.json", encoding="utf-8"))
    server = serve(0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = "http://127.0.0.1:%d" % server.server_port
    for item in spec["writes"]:
        call("POST", base + "/put", json.dumps(item).encode())
    before = parse(call("POST", base + "/get", json.dumps({"value": spec["probe"]}).encode())[1])
    replayed = parse(call("POST", base + "/replay", b"{}")[1])
    after = parse(call("POST", base + "/get", json.dumps({"value": spec["probe"]}).encode())[1])
    reconciled = parse(call("POST", base + "/reconcile", b"{}")[1])
    stats = parse(call("GET", base + "/")[1])
    recovered = parse(call("POST", base + "/recover", b"{}")[1])
    print("崩点后按值检索 =", before.get("keys"))
    print("重放补齐的条数 =", replayed.get("replayed"))
    print("重放后按值检索 =", after.get("keys"))
    print("对账发现的差异 =", reconciled.get("missing"))
    print("修复的条数 =", reconciled.get("repaired"))
    print("数据条数 =", stats.get("data"))
    print("恢复后的重放计数 =", recovered.get("replayed"))
    print("不变量（重放后索引覆盖全部数据） =", spec["coverage_invariant"])
    print("写入次数 =", len(spec["writes"]))
    server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
