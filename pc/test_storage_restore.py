"""Exercise actual GUI storage handlers without serial hardware."""
import ast
from pathlib import Path
import queue
import unittest
from power_on_dump import PowerOnDump


class Value:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


class RestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(__file__).with_name("cartreader_pc.py").read_text(encoding="utf-8"))

    def setUp(self):
        self.sent = []
        self.ns = {
            "power_on": PowerOnDump({}),
            "power_on_guard": {"reset": False, "benchmark": False},
            "benchmark": {"index": None}, "menu_navigation": {},
            "storage_current": {"mode": "PC", "pending": None, "desired": "PC"},
            "storage_mode": Value(""), "transfer_speed": Value("転送: 待機"),
            "input_ready": Value(False), "input_mode": Value("menu"),
            "storage_widgets": {}, "reset_capability": {},
            "connection_state": Value("接続済み"),
            "connection_session": {"ever_connected": True},
            "set_connection_state": lambda value: None,
            "reset_dump_result": lambda: None, "inbox": queue.Queue(),
        }
        def send_key(code):
            if self.ns["input_ready"].get():
                self.sent.append(code)
                self.ns["input_ready"].set(False)
        self.ns["send_key"] = send_key
        for name in ("set_storage_state", "choose_storage"):
            node = next(n for n in ast.walk(self.tree) if isinstance(n, ast.FunctionDef) and n.name == name)
            exec(compile(ast.Module(body=[node], type_ignores=[]), name, "exec"), self.ns)

    def branch(self, predicate):
        node = next(n for n in ast.walk(self.tree) if isinstance(n, ast.If) and predicate(ast.unparse(n.test)))
        if eval(compile(ast.Expression(node.test), "condition", "eval"), self.ns):
            exec(compile(ast.Module(body=node.body, type_ignores=[]), "handler", "exec"), self.ns)

    def connected(self):
        self.ns["line"] = "[Connected: CRPC v1 / 250000 baud]"
        self.branch(lambda test: test == "line.startswith('[Connected:')")

    def report(self, mode):
        import re
        self.ns["storage_match"] = re.match("(PC|SD)", mode)
        self.branch(lambda test: test == "storage_match")

    def ready(self):
        self.ns["input_ready"].set(True)
        self.branch(lambda test: test == "storage_current['pending'] and input_mode.get() == 'menu'")

    def test_sd_restored_after_reset_not_assumed_active_before_confirmation(self):
        self.ns["input_ready"].set(True)
        self.ns["choose_storage"]("I")
        self.report("SD")
        self.assertEqual(self.ns["storage_current"]["desired"], "SD")
        self.connected()
        self.assertEqual(self.ns["storage_current"]["mode"], "PC")
        self.assertEqual(self.ns["storage_current"]["pending"], "SD")
        self.ready()
        self.assertEqual(self.sent, ["I", "I"])
        self.assertFalse(self.ns["input_ready"].get())
        self.report("SD")
        self.assertEqual(self.ns["storage_current"]["mode"], "SD")
        self.assertIsNone(self.ns["storage_current"]["pending"])
        self.ready()
        self.assertEqual(self.sent, ["I", "I"])

    def test_pc_default_does_not_send_restore(self):
        self.connected()
        self.ready()
        self.assertEqual(self.sent, [])

    def test_disconnected_sd_selection_survives_initial_pc_report(self):
        self.ns["choose_storage"]("I")
        self.connected()
        self.report("PC")
        self.assertEqual(self.ns["storage_current"]["pending"], "SD")
        self.ready()
        self.assertEqual(self.sent, ["I"])

    def test_latest_pc_selection_overrides_previous_sd(self):
        self.ns["choose_storage"]("I")
        self.ns["choose_storage"]("J")
        self.connected()
        self.ready()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.ns["storage_current"]["desired"], "PC")

    def test_repeated_reset_keeps_sd_intent(self):
        self.ns["choose_storage"]("I")
        for _ in range(3):
            self.connected()
            self.ready()
            self.report("SD")
        self.assertEqual(self.sent, ["I"] * 3)

    def test_failed_sd_restore_does_not_claim_sd_active_or_loop(self):
        self.ns["choose_storage"]("I")
        self.connected()
        self.ready()
        self.report("PC")
        self.ready()
        self.assertEqual(self.sent, ["I"])
        self.assertEqual(self.ns["storage_current"]["mode"], "PC")
        self.assertEqual(self.ns["storage_current"]["desired"], "SD")
