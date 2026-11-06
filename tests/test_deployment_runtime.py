import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("DISCORD_BOT_TOKEN", "test-token")
os.environ.setdefault("GUILD_ID", "1555677417518137354")

import sockboi_bot  # noqa: E402


class DeploymentRuntimeTests(unittest.TestCase):
    def test_environment_validation_accepts_required_values(self):
        config = sockboi_bot.validate_environment({
            "DISCORD_BOT_TOKEN": "test-token", "GUILD_ID": "123456789012345678", "PORT": "8080"
        })
        self.assertEqual(config, {"token": "test-token", "guild_id": 123456789012345678, "port": 8080})

    def test_environment_validation_rejects_missing_or_placeholder_token(self):
        for token in ("", "PASTE_BOT_TOKEN_HERE"):
            with self.subTest(token=token), self.assertRaisesRegex(ValueError, "DISCORD_BOT_TOKEN"):
                sockboi_bot.validate_environment({"DISCORD_BOT_TOKEN": token, "GUILD_ID": "123"})

    def test_environment_validation_rejects_invalid_guild_and_port(self):
        with self.assertRaisesRegex(ValueError, "GUILD_ID"):
            sockboi_bot.validate_environment({"DISCORD_BOT_TOKEN": "test-token", "GUILD_ID": "abc"})
        with self.assertRaisesRegex(ValueError, "PORT"):
            sockboi_bot.validate_environment({"DISCORD_BOT_TOKEN": "test-token", "GUILD_ID": "123", "PORT": "70000"})

    def test_save_and_load_data_round_trip_and_create_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_path = str(Path(tmp) / "nested" / "sockboi_bot_data.json")
            payload = {"offenses":{"spam:123":2},"verification_deadlines":{"123:456":"2026-11-06T12:00:00+00:00"},
                       "verification_alerts":{},"verification_reminders":{}}
            with mock.patch.object(sockboi_bot, "DATA_FILE", data_path):
                sockboi_bot.save_data(payload)
                loaded = sockboi_bot.load_data()
            self.assertEqual(loaded, payload)
            self.assertTrue(Path(data_path).exists())

    def test_health_handler_is_available(self):
        self.assertTrue(callable(sockboi_bot.health_http_handler))
        self.assertEqual(sockboi_bot.PORT, 8080)


if __name__ == "__main__":
    unittest.main()
