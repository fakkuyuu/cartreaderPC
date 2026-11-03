"""Regression tests for #039 connection waiting and diagnostic handling.

Run with: python -m unittest discover -s pc -p 'test_connection_status.py'
"""
from pathlib import Path
import unittest

from connection_status import ConnectionFeedback
from batch_dump import BatchDump
from i18n import WORDS


class ConnectionFeedbackTests(unittest.TestCase):
    def test_missing_com_port_is_waiting_not_action_required(self):
        feedback = ConnectionFeedback()
        event, detail = feedback.failure(FileNotFoundError("The system cannot find COM5"))
        self.assertEqual(event, "[RECONNECT] WAIT\n")
        self.assertIn("FileNotFoundError: The system cannot find COM5", detail)

    def test_power_off_permission_error_is_ambiguous(self):
        feedback = ConnectionFeedback()
        event, detail = feedback.failure(PermissionError("Access is denied: COM5"))
        self.assertEqual(event, "[RECONNECT] WAIT\n")
        self.assertNotIn("ACTION_REQUIRED", event)
        self.assertIn("PermissionError:", detail)

    def test_clear_comm_error_and_repeated_retries_are_not_flooded(self):
        feedback = ConnectionFeedback()
        event, detail = feedback.failure(OSError("ClearCommError failed"))
        self.assertEqual(event, "[RECONNECT] WAIT\n")
        self.assertIn("ClearCommError", detail)
        self.assertEqual(feedback.failure(OSError("ClearCommError failed")), (None, None))
        event, detail = feedback.failure(PermissionError("Access denied"))
        self.assertIsNone(event)
        self.assertIn("PermissionError", detail)

    def test_actual_host_write_failures_are_actionable(self):
        for message in (
            "fatal host file error; transfer stopped",
            "streamed host file write failed; transfer stopped",
        ):
            with self.subTest(message=message):
                event, detail = ConnectionFeedback().failure(OSError(message))
                self.assertEqual(event, "[RECONNECT] ACTION_REQUIRED\n")
                self.assertIn(message, detail)

    def test_actionable_error_does_not_downgrade_to_wait(self):
        feedback = ConnectionFeedback()
        self.assertEqual(
            feedback.failure(OSError("fatal host file error; transfer stopped"))[0],
            "[RECONNECT] ACTION_REQUIRED\n",
        )
        event, detail = feedback.failure(PermissionError("Access denied"))
        self.assertIsNone(event)
        self.assertIn("PermissionError", detail)

    def test_successful_recovery_rearms_wait_and_diagnostics(self):
        feedback = ConnectionFeedback()
        feedback.failure(OSError("ClearCommError failed"))
        feedback.connected()
        event, detail = feedback.failure(OSError("ClearCommError failed"))
        self.assertEqual(event, "[RECONNECT] WAIT\n")
        self.assertIn("ClearCommError", detail)

    def test_retry_notification_stops_active_batch(self):
        batch = BatchDump()
        batch.begin("NES")
        batch.on_line("[RECONNECT] WAIT")
        self.assertFalse(batch.active)
        self.assertIn("通信切断", batch.reason)

    def test_japanese_and_english_connection_notices_present(self):
        for label in (
            "接続待ち",
            "本体の接続を待っています。",
            "本体に接続しました。",
            "本体との接続が復旧しました。",
            "PC保存先への書込みに失敗しました。保存先を確認してください。",
            "転送が中断され、未完了のファイルがあります。.pc-manifest.jsonを確認してください。",
            "通信速度の切替に失敗しました。詳細ログを確認してください。",
        ):
            with self.subTest(label=label):
                self.assertIn(label, WORDS)
                self.assertTrue(WORDS[label])

    def test_driver_baud_errors_are_private_and_partial_menu_is_discarded(self):
        gui = (Path(__file__).parent / "cartreader_pc.py").read_text(encoding="utf-8")
        self.assertIn('"USB serial driver rejected" in message', gui)
        self.assertIn('inbox.put(("connection_detail", message))', gui)
        self.assertIn('if item[1].startswith("[RECONNECT]"):', gui)
        self.assertIn('nonlocal parser_buffer, pending_title, pending_options, pending_paged', gui)

    def test_gui_routes_raw_exceptions_only_to_diagnostics(self):
        gui = (Path(__file__).parent / "cartreader_pc.py").read_text(encoding="utf-8")
        self.assertIn('inbox.put(("connection_detail", detail))', gui)
        self.assertIn('if diagnostic_log.get():\n                        text.insert("end", item[1])', gui)
        self.assertIn('inbox.put(("status", event))', gui)
        self.assertIn('line == "[RECONNECT] ACTION_REQUIRED"', gui)
        self.assertIn('set_connection_state("接続待ち")', gui)
        self.assertNotIn('inbox.put(f"\\n[RECONNECT] {message}\\n")', gui)
        self.assertNotIn('set_connection_state("再接続待ち")', gui)


if __name__ == "__main__":
    unittest.main()
