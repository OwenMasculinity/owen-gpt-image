"""Backend boundary tests: no subscription quota or browser is required."""
import base64
import io
import re
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from PIL import Image
import gen_via_codex as codex
import gen_via_chatgpt_web as web
from image_output import publish_image, validate_jobs


def png(color="red", size=(40, 20)):
    stream = io.BytesIO()
    Image.new("RGB", size, color).save(stream, "PNG")
    return stream.getvalue()


def generated_path(instruction):
    return Path(re.search(r"保存到 (.+?)。", instruction).group(1))


class TestOutput(unittest.TestCase):
    def test_exact_size_and_aspect_preserving_crop(self):
        with tempfile.TemporaryDirectory() as directory:
            source, out = Path(directory) / "source.png", Path(directory) / "out.png"
            image = Image.new("RGB", (60, 20), "red")
            image.paste("blue", (20, 0, 40, 20))
            image.save(source)
            self.assertEqual(publish_image(source, out, "10x10"), "10x10")
            with Image.open(out) as result:
                self.assertEqual(result.size, (10, 10))
                self.assertEqual(result.getpixel((5, 5)), (0, 0, 255, 255))

    def test_invalid_image_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, out = Path(directory) / "bad", Path(directory) / "out.png"
            source.write_bytes(b"not an image")
            out.write_bytes(b"existing")
            with self.assertRaises(OSError):
                publish_image(source, out)
            self.assertEqual(out.read_bytes(), b"existing")

    def test_duplicate_outputs_rejected_before_dispatch(self):
        jobs = [{"prompt": "one", "out": "same.png"}, {"prompt": "two", "out": "./same.png"}]
        with patch.object(codex, "generate_one") as generate:
            self.assertEqual(codex.run_batch(jobs, 2), 2)
            generate.assert_not_called()

    def test_invalid_size_and_empty_jobs_rejected(self):
        for jobs in ([], [{"prompt": "x", "out": "x.png", "size": "0x10"}],
                     [{"prompt": "x", "out": "x.png", "ref": 123}],
                     [{"prompt": "x", "out": "x.png", "model": 123}],
                     [{"prompt": "x", "out": "x.png", "size": [10, 10]}]):
            with self.assertRaises(ValueError):
                validate_jobs(jobs)


class TestCodex(unittest.TestCase):
    def test_parallel_jobs_keep_their_own_images(self):
        def execute(command, **kwargs):
            text = kwargs["input"]
            generated_path(text).write_bytes(png("red" if "red subject" in text else "blue"))
            return CompletedProcess(command, 0, "", "")
        with tempfile.TemporaryDirectory() as directory, patch.object(codex.shutil, "which", return_value="codex.exe"), patch.object(codex.subprocess, "run", side_effect=execute):
            outputs = [Path(directory) / "red.png", Path(directory) / "blue.png"]
            with ThreadPoolExecutor(2) as executor:
                results = list(executor.map(lambda pair: codex.generate_one(pair[0], str(pair[1]), "12x12", use_craft=False), zip(("red subject", "blue subject"), outputs)))
            self.assertTrue(all(ok for ok, _ in results))
            for path, expected in zip(outputs, ((255, 0, 0, 255), (0, 0, 255, 255))):
                with Image.open(path) as image:
                    self.assertEqual(image.size, (12, 12))
                    self.assertEqual(image.getpixel((6, 6)), expected)

    def test_old_output_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(codex.shutil, "which", return_value="codex"), patch.object(codex.subprocess, "run", return_value=CompletedProcess([], 0, "", "")):
            out = Path(directory) / "out.png"
            out.write_bytes(png())
            original = out.read_bytes()
            ok, _ = codex.generate_one("test", str(out), use_craft=False)
            self.assertFalse(ok)
            self.assertEqual(out.read_bytes(), original)

    def test_nonzero_exit_cannot_publish_image(self):
        def execute(command, **kwargs):
            generated_path(kwargs["input"]).write_bytes(png())
            return CompletedProcess(command, 1, "", "failed")
        with tempfile.TemporaryDirectory() as directory, patch.object(codex.shutil, "which", return_value="codex"), patch.object(codex.subprocess, "run", side_effect=execute):
            out = Path(directory) / "out.png"
            self.assertFalse(codex.generate_one("x", str(out), use_craft=False)[0])
            self.assertFalse(out.exists())

    def test_quota_fallback_and_opt_out(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(codex.shutil, "which", return_value="codex"), patch.object(codex.subprocess, "run", return_value=CompletedProcess([], 1, "", "HTTP 429 quota exceeded")), patch.object(web, "check_health", return_value=(True, "online")), patch.object(web, "generate_one", return_value=(True, "web image")) as generate:
            out = str(Path(directory) / "out.png")
            self.assertTrue(codex.generate_one("x", out, use_craft=False)[0])
            generate.assert_called_once()
            generate.reset_mock()
            self.assertFalse(codex.generate_one("x", out, use_craft=False, fallback=False)[0])
            generate.assert_not_called()

    def test_other_errors_never_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(codex.shutil, "which", return_value="codex"), patch.object(codex.subprocess, "run", return_value=CompletedProcess([], 1, "", "authentication failed")), patch.object(web, "generate_one") as generate:
            self.assertFalse(codex.generate_one("x", str(Path(directory) / "x.png"), use_craft=False)[0])
            generate.assert_not_called()

    def test_policy_failure_does_not_dispatch(self):
        with patch.object(codex.subprocess, "run") as execute:
            self.assertFalse(codex.generate_one("高级", "unused.png")[0])
            execute.assert_not_called()

    def test_missing_cli_reports_error(self):
        with patch.object(codex.shutil, "which", return_value=None), patch.object(codex.subprocess, "run") as execute:
            ok, message = codex.generate_one("x", "unused.png", use_craft=False)
            self.assertFalse(ok)
            self.assertIn("找不到 codex", message)
            execute.assert_not_called()

    def test_model_override_and_utf8_are_forwarded(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(codex.shutil, "which", return_value="codex.exe"), patch.dict(codex.os.environ, {"GEN_CODEX_MODEL": "env-model"}), patch.object(codex.subprocess, "run", return_value=CompletedProcess([], 1, "", "model_not_found")) as execute:
            ok, message = codex.generate_one("x", str(Path(directory) / "x.png"), use_craft=False, model="selected-model")
            self.assertFalse(ok)
            self.assertIn("--model", message)
            command = execute.call_args.args[0]
            self.assertEqual(command[command.index("--model") + 1], "selected-model")
            self.assertEqual(execute.call_args.kwargs["encoding"], "utf-8")
            codex.generate_one("x", str(Path(directory) / "x.png"), use_craft=False)
            self.assertIn("env-model", execute.call_args.args[0])

    def test_unavailable_bridge_reports_both_failures(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(codex.shutil, "which", return_value="codex"), patch.object(codex.subprocess, "run", return_value=CompletedProcess([], 1, "", "HTTP 429")), patch.object(web, "check_health", return_value=(False, "offline")):
            ok, message = codex.generate_one("x", str(Path(directory) / "x.png"), use_craft=False)
            self.assertFalse(ok)
            self.assertIn("Codex 额度受限", message)
            self.assertIn("offline", message)

    def test_failed_batch_job_does_not_stop_other_jobs(self):
        with patch.object(codex, "generate_one", side_effect=[(False, "policy failed"), (True, "done")]) as generate:
            self.assertEqual(codex.run_batch([{"prompt": "a", "out": "a.png"}, {"prompt": "b", "out": "b.png"}], 1), 1)
            self.assertEqual(generate.call_count, 2)


class TestWeb(unittest.TestCase):
    def test_http_timeout_and_wrong_json_are_reported(self):
        with patch.object(web._opener, "open", side_effect=TimeoutError("timed out")):
            code, response = web._http("GET", "/health")
            self.assertEqual(code, 0)
            self.assertIn("timed out", response["error"])
        with patch.object(web._opener, "open") as opened:
            opened.return_value.__enter__.return_value.read.return_value = b"[]"
            self.assertEqual(web._http("GET", "/health")[0], 0)

    def test_response_validated_and_resized(self):
        response = {"ok": True, "imageBase64": base64.b64encode(png()).decode()}
        with tempfile.TemporaryDirectory() as directory, patch.object(web, "_http", return_value=(200, response)):
            out = Path(directory) / "out.png"
            self.assertTrue(web.generate_one("x", str(out), "15x15", use_craft=False)[0])
            with Image.open(out) as image:
                self.assertEqual(image.size, (15, 15))

    def test_bad_payload_preserves_existing_output(self):
        for data in ("%%%", base64.b64encode(b"not an image").decode()):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory, patch.object(web, "_http", return_value=(200, {"ok": True, "imageBase64": data})):
                out = Path(directory) / "out.png"
                out.write_bytes(b"existing")
                self.assertFalse(web.generate_one("x", str(out), use_craft=False)[0])
                self.assertEqual(out.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
