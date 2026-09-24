import json
import threading
import unittest
import urllib.error
import urllib.request

from doublewrite import Store
from server import serve

class TestStore(unittest.TestCase):
    def test_put_both(self):
        store = Store()
        self.assertTrue(store.put("k1", "v1")["index"])

    def test_get_finds_key(self):
        store = Store()
        store.put("k1", "v1")
        self.assertEqual(store.get("v1")["keys"], ["k1"])

    def test_crash_stops_index(self):
        store = Store()
        self.assertFalse(store.put("k1", "v1", True)["index"])

    def test_stats_shape(self):
        self.assertIn("repaired", Store().stats())

    def test_http_put_get(self):
        server = serve(0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        urllib.request.urlopen(base + "/put", data=b'{"key": "k1", "value": "v1"}', timeout=5).read()
        with urllib.request.urlopen(base + "/get", data=b'{"value": "v1"}', timeout=5) as response:
            self.assertEqual(json.loads(response.read())["keys"], ["k1"])
        server.shutdown()
