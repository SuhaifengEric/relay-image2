import importlib.util
import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_image2.py"
SPEC = importlib.util.spec_from_file_location("generate_image2", MODULE_PATH)
generate_image2 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generate_image2)


class GenerationParamTests(unittest.TestCase):
    def test_4k_sets_resolution_and_default_square_size(self):
        resolution, resolution_source, size, size_source = generate_image2.infer_generation_params(
            "生图 超清 4k 助力高考", "auto", None
        )

        self.assertEqual(resolution, "4k")
        self.assertEqual(resolution_source, "prompt-4k")
        self.assertEqual(size, "1:1")
        self.assertEqual(size_source, "default-size")

    def test_explicit_size_is_independent_from_resolution(self):
        resolution, resolution_source, size, size_source = generate_image2.infer_generation_params(
            "生成 4k 横版海报", "auto", "16:9"
        )

        self.assertEqual(resolution, "4k")
        self.assertEqual(resolution_source, "prompt-4k")
        self.assertEqual(size, "16:9")
        self.assertEqual(size_source, "explicit-size")


class PayloadTests(unittest.TestCase):
    def test_responses_payload_sends_resolution_separately_from_size(self):
        payload = generate_image2.build_payload("responses", "text-model", "prompt", "4k", "1:1")
        tool = payload["tools"][0]

        self.assertEqual(tool["resolution"], "4k")
        self.assertEqual(tool["size"], "1:1")
        self.assertNotIn("4096", str(payload))

    def test_images_payload_sends_resolution_separately_from_size(self):
        payload = generate_image2.build_payload("images", "gpt-image-2", "prompt", "4k", "1:1")

        self.assertEqual(payload["resolution"], "4k")
        self.assertEqual(payload["size"], "1:1")
        self.assertNotIn("4096", str(payload))


class MainBehaviorTests(unittest.TestCase):
    def test_confirmed_default_uses_direct_image_model(self):
        calls = []

        def fake_request_json(url, key, payload, timeout, method="POST"):
            calls.append((url, payload, method))
            return 200, "image/png", b"\x89PNG\r\n\x1a\nfake"

        argv = ["generate_image2.py", "--prompt", "2026 高考加油", "--resolution", "2k", "--size", "1:1", "--confirmed"]
        env = {
            "RELAY_IMAGE2_BASE_URL": "https://relay.test",
            "RELAY_IMAGE2_KEY": "secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(sys, "argv", argv):
                with patch.object(generate_image2, "load_env_file"):
                    with patch.object(generate_image2, "request_json", side_effect=fake_request_json):
                        with patch.object(generate_image2, "save_bytes", return_value=Path("/tmp/out.png")):
                            code = generate_image2.main()

        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        url, payload, method = calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://relay.test/v1/images/generations")
        self.assertEqual(payload["model"], "gpt-image-2")
        self.assertEqual(payload["resolution"], "2k")
        self.assertEqual(payload["size"], "1:1")
        self.assertNotIn("gpt-5.5", str(payload))

    def test_env_can_override_default_image_model(self):
        calls = []

        def fake_request_json(url, key, payload, timeout, method="POST"):
            calls.append((url, payload, method))
            return 200, "image/png", b"\x89PNG\r\n\x1a\nfake"

        argv = ["generate_image2.py", "--prompt", "2026 高考加油", "--resolution", "2k", "--size", "1:1", "--confirmed"]
        env = {
            "RELAY_IMAGE2_BASE_URL": "https://relay.test",
            "RELAY_IMAGE2_KEY": "secret",
            "RELAY_IMAGE2_IMAGE_MODEL": "provider-image-model",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(sys, "argv", argv):
                with patch.object(generate_image2, "load_env_file"):
                    with patch.object(generate_image2, "request_json", side_effect=fake_request_json):
                        with patch.object(generate_image2, "save_bytes", return_value=Path("/tmp/out.png")):
                            code = generate_image2.main()

        self.assertEqual(code, 0)
        self.assertEqual(calls[0][1]["model"], "provider-image-model")

    def test_custom_task_endpoint_template_is_used_before_defaults(self):
        calls = []
        task_id = "task_custom"
        def fake_request_json(url, key, payload, timeout, method="POST"):
            calls.append((url, payload, method))
            if method == "POST":
                return 200, "application/json", json.dumps({"task_id": task_id}).encode("utf-8")
            if url == "https://relay.test/custom/tasks/task_custom":
                return 200, "image/png", b"\x89PNG\r\n\x1a\nfake"
            raise RuntimeError(f"unexpected endpoint: {url}")

        argv = [
            "generate_image2.py",
            "--prompt",
            "2026 高考加油",
            "--task-endpoint",
            "/custom/tasks/{task_id}",
            "--confirmed",
        ]
        env = {
            "RELAY_IMAGE2_BASE_URL": "https://relay.test",
            "RELAY_IMAGE2_KEY": "secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(sys, "argv", argv):
                with patch.object(generate_image2, "load_env_file"):
                    with patch.object(generate_image2, "request_json", side_effect=fake_request_json):
                        with patch.object(generate_image2, "save_bytes", return_value=Path("/tmp/out.png")):
                            code = generate_image2.main()

        self.assertEqual(code, 0)
        self.assertEqual(calls[1][0], "https://relay.test/custom/tasks/task_custom")

    def test_responses_mode_requires_explicit_responses_model(self):
        calls = []

        def fake_request_json(url, key, payload, timeout, method="POST"):
            calls.append((url, payload, method))
            return 200, "image/png", b"\x89PNG\r\n\x1a\nfake"

        argv = ["generate_image2.py", "--mode", "responses", "--prompt", "2026 高考加油", "--confirmed"]
        env = {
            "RELAY_IMAGE2_BASE_URL": "https://relay.test",
            "RELAY_IMAGE2_KEY": "secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(sys, "argv", argv):
                with patch.object(generate_image2, "load_env_file"):
                    with patch.object(generate_image2, "request_json", side_effect=fake_request_json):
                        stderr = io.StringIO()
                        with patch("sys.stderr", stderr):
                            code = generate_image2.main()

        self.assertEqual(code, 1)
        self.assertEqual(calls, [])
        self.assertIn("Responses mode requires --responses-model", stderr.getvalue())

    def test_auto_mode_stops_after_first_api_error(self):
        calls = []

        def fake_request_json(url, key, payload, timeout, method="POST"):
            calls.append((url, payload, method))
            raise RuntimeError("HTTP 400: relay rejected request")

        argv = ["generate_image2.py", "--prompt", "生图 4k 助力高考", "--confirmed"]
        env = {
            "RELAY_IMAGE2_BASE_URL": "https://relay.test",
            "RELAY_IMAGE2_KEY": "secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(sys, "argv", argv):
                with patch.object(generate_image2, "load_env_file"):
                    with patch.object(generate_image2, "request_json", side_effect=fake_request_json):
                        stderr = io.StringIO()
                        with patch("sys.stderr", stderr):
                            code = generate_image2.main()

        self.assertEqual(code, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("HTTP 400: relay rejected request", stderr.getvalue())
        self.assertNotIn("falling back", stderr.getvalue())

    def test_main_requires_confirmation_before_api_call(self):
        calls = []

        def fake_request_json(url, key, payload, timeout, method="POST"):
            calls.append((url, payload, method))
            return 200, "application/json", b"{}"

        argv = ["generate_image2.py", "--prompt", "生图 超清 4k 助力高考"]
        env = {
            "RELAY_IMAGE2_BASE_URL": "https://relay.test",
            "RELAY_IMAGE2_KEY": "secret",
        }

        with patch.dict(os.environ, env, clear=True):
            with patch.object(sys, "argv", argv):
                with patch.object(generate_image2, "load_env_file"):
                    with patch.object(generate_image2, "request_json", side_effect=fake_request_json):
                        stdout = io.StringIO()
                        with patch("sys.stdout", stdout):
                            code = generate_image2.main()

        self.assertEqual(code, 3)
        self.assertEqual(calls, [])
        summary = json.loads(stdout.getvalue())
        self.assertEqual(summary["prompt"], "生图 超清 4k 助力高考")
        self.assertEqual(summary["resolution"], "4k")
        self.assertEqual(summary["size"], "1:1")


if __name__ == "__main__":
    unittest.main()
