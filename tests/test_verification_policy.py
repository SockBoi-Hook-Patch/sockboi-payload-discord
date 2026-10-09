import os
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("GUILD_ID", "1555677417518137354")

import sockboi_bot  # noqa: E402


class VerificationPolicyTests(unittest.TestCase):
    def test_only_welcome_and_verify_are_allowlisted(self):
        self.assertEqual(sockboi_bot.VERIFY_ALLOWED_CHANNELS, {"👋・welcome", "✅・verify"})
        self.assertEqual(sockboi_bot.VERIFY_ALLOWED_CATEGORIES, set())

    def test_verification_timeout_is_one_hour(self):
        self.assertEqual(sockboi_bot.VERIFY_TIMEOUT.total_seconds(), 3600)

    def test_gate_denies_view_but_preserves_unrelated_permissions(self):
        existing = sockboi_bot.discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_messages=True,
        )
        locked = sockboi_bot.verification_overwrite(existing, can_view=False)
        self.assertIs(locked.view_channel, False)
        self.assertIs(locked.send_messages, False)
        self.assertIs(locked.manage_messages, True)

    def test_verification_area_is_visible_but_read_only(self):
        existing = sockboi_bot.discord.PermissionOverwrite(send_messages=True)
        allowed = sockboi_bot.verification_overwrite(existing, can_view=True)
        self.assertIs(allowed.view_channel, True)
        self.assertIs(allowed.read_message_history, True)
        self.assertIs(allowed.send_messages, False)

    def test_old_data_gets_deadline_store_without_losing_offenses(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = os.path.join(tmp, "bot-data.json")
            with open(data_path, "w", encoding="utf-8") as handle:
                handle.write('{"offenses":{"spam:123":2}}')
            with mock.patch.object(sockboi_bot, "DATA_FILE", data_path):
                loaded = sockboi_bot.load_data()
            self.assertEqual(loaded["offenses"], {"spam:123": 2})
            self.assertEqual(loaded["verification_deadlines"], {})


if __name__ == "__main__":
    unittest.main()
