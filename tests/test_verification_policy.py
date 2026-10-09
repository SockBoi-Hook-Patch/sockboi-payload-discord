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

    def test_new_members_can_verify_after_one_minute(self):
        self.assertEqual(sockboi_bot.VERIFY_WAIT.total_seconds(), 60)

    def test_member_copy_uses_bilingual_hacker_theme_and_current_policy(self):
        self.assertIn("HANDSHAKE ACCEPTED", sockboi_bot.WELCOME_DM_TEMPLATE)
        self.assertIn("ACCESS GATE", sockboi_bot.WELCOME_PUBLIC_FIELD_NAME)
        self.assertIn("1 นาที", sockboi_bot.WELCOME_PUBLIC_FIELD_VALUE)
        self.assertIn("1 hour", sockboi_bot.WELCOME_PUBLIC_FIELD_VALUE)
        self.assertIn("DEVICE ROLE LOADED", sockboi_bot.ROLE_ADDED_TEMPLATE)
        self.assertIn("ACCESS GATE OPEN", sockboi_bot.VERIFY_SUCCESS_MESSAGE)
        self.assertIn("wait 1 minute", sockboi_bot.VERIFY_SETUP_MESSAGE)
        self.assertIn("1 hour", sockboi_bot.VERIFY_SETUP_MESSAGE)
        self.assertIn("Android / Root / No-Root / Emulator", sockboi_bot.ROLE_SETUP_MESSAGE)

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
            self.assertEqual(loaded["verification_alerts"], {})


if __name__ == "__main__":
    unittest.main()
