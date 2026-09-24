import base64
import io
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import repodx


SAMPLE_DIR = Path(__file__).parent / "sample"


class RepoDxTests(unittest.TestCase):
    def test_find_junk_files_reports_expected_items(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            (repo_path / "cache.tmp").write_text("tmp", encoding="utf-8")
            (repo_path / ".DS_Store").write_text("mac", encoding="utf-8")
            (repo_path / "__pycache__").mkdir()
            (repo_path / "__pycache__" / "example.pyc").write_text(
                "cache", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "node_modules" / "example.txt").write_text(
                "module", encoding="utf-8"
            )

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(
                result,
                [
                    ".DS_Store",
                    "__pycache__/",
                    "cache.tmp",
                    "debug.log",
                    "node_modules/",
                ],
            )

    def test_find_junk_files_skips_ignored_node_modules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/\n", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_skips_ignored_pycache(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/\n", encoding="utf-8"
            )
            (repo_path / "__pycache__").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_skips_directories_ignored_with_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/*\n__pycache__/*\n", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "__pycache__").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_reports_unignored_virtual_environment_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            for name in [".venv", "venv", "env"]:
                (repo_path / name).mkdir()
                (repo_path / name / "pyvenv.cfg").write_text(
                    "home = /usr/bin\n", encoding="utf-8"
                )

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [".venv/", "env/", "venv/"])

    def test_find_junk_files_skips_ignored_virtual_environment_folders(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                ".venv/\nvenv/\nenv/\n", encoding="utf-8"
            )
            for name in [".venv", "venv", "env"]:
                (repo_path / name).mkdir()
                (repo_path / name / "pyvenv.cfg").write_text(
                    "home = /usr/bin\n", encoding="utf-8"
                )

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_skips_directories_ignored_with_double_star_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/**\n__pycache__/**\n", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "__pycache__").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_does_not_report_files_inside_junk_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "__pycache__").mkdir()
            (repo_path / "__pycache__" / "debug.log").write_text(
                "log", encoding="utf-8"
            )
            (repo_path / "node_modules").mkdir()
            (repo_path / "node_modules" / "cache.tmp").write_text(
                "tmp", encoding="utf-8"
            )

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["__pycache__/", "node_modules/"])

    def test_find_junk_files_ignores_env_folders_that_are_not_virtualenvs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "env").mkdir()
            (repo_path / "env" / "production.yaml").write_text(
                "debug: false\n", encoding="utf-8"
            )
            (repo_path / "env" / "deploy.log").write_text("log", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["env/deploy.log"])

    def test_find_junk_files_skips_files_ignored_by_gitignore_patterns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "*.log\n**/*.tmp\n.DS_Store\n", encoding="utf-8"
            )
            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            (repo_path / "src").mkdir()
            (repo_path / "src" / "cache.tmp").write_text("tmp", encoding="utf-8")
            (repo_path / "src" / ".DS_Store").write_text("mac", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_find_junk_files_respects_gitignore_negation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "*.log\n!keep/**\n", encoding="utf-8"
            )
            (repo_path / "debug.log").write_text("log", encoding="utf-8")
            (repo_path / "keep").mkdir()
            (repo_path / "keep" / "trace.log").write_text("log", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["keep/trace.log"])

    def test_find_junk_files_matches_suffixes_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")
            (repo_path / "DEBUG.LOG").write_text("log", encoding="utf-8")
            (repo_path / "Cache.Tmp").write_text("tmp", encoding="utf-8")

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, ["Cache.Tmp", "DEBUG.LOG"])

    def test_find_junk_files_does_not_walk_into_junk_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "node_modules/\n", encoding="utf-8"
            )
            (repo_path / "node_modules" / "pkg").mkdir(parents=True)
            visited = []
            real_walk = repodx.os.walk

            def recording_walk(top):
                for current_dir, dir_names, file_names in real_walk(top):
                    visited.append(Path(current_dir).name)
                    yield current_dir, dir_names, file_names

            with mock.patch.object(repodx.os, "walk", recording_walk):
                result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])
            self.assertNotIn("node_modules", visited)
            self.assertNotIn("pkg", visited)

    def test_find_junk_files_respects_negated_directory_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/\nnode_modules/\n!fixtures/**\n", encoding="utf-8"
            )
            (repo_path / "__pycache__").mkdir()
            (repo_path / "fixtures" / "__pycache__").mkdir(parents=True)
            (repo_path / "fixtures" / "node_modules").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(
                result, ["fixtures/__pycache__/", "fixtures/node_modules/"]
            )

    def test_find_junk_files_skips_contents_of_ignored_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text("build/\n", encoding="utf-8")
            (repo_path / "build").mkdir()
            (repo_path / "build" / "output.log").write_text("log", encoding="utf-8")
            (repo_path / "build" / "__pycache__").mkdir()

            result = repodx.find_junk_files(repo_path)

            self.assertEqual(result, [])

    def test_check_gitignore_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, ["Missing .gitignore file"])

    def test_check_gitignore_reports_missing_entries(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(
                result,
                [
                    "Missing .gitignore entry: __pycache__/",
                    "Missing .gitignore entry: node_modules/",
                ],
            )

    def test_check_gitignore_accepts_common_entry_variations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "**/__pycache__/\n.env\n**/node_modules\n", encoding="utf-8"
            )

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, [])

    def test_check_gitignore_accepts_directory_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/*\n.env\nnode_modules/*\n", encoding="utf-8"
            )

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, [])

    def test_check_gitignore_accepts_double_star_directory_content_globs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(
                "__pycache__/**\n.env\nnode_modules/**\n", encoding="utf-8"
            )

            result = repodx.check_gitignore(repo_path)

            self.assertEqual(result, [])

    def test_has_gitignore_entry_accepts_double_star_prefix_and_slash_variants(self):
        entries = ["**/__pycache__/", ".env", "**/node_modules"]

        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules"))

    def test_has_gitignore_entry_accepts_directory_content_globs(self):
        entries = ["**/__pycache__/*", ".env", "node_modules/*"]

        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules/"))

    def test_has_gitignore_entry_accepts_double_star_content_globs(self):
        entries = ["**/__pycache__/**", ".env", "node_modules/**"]

        self.assertTrue(repodx.has_gitignore_entry(entries, "__pycache__/"))
        self.assertTrue(repodx.has_gitignore_entry(entries, "node_modules/"))

    def test_check_gitignore_reports_unreadable_file(self):
        repo_path = SAMPLE_DIR / "bad_gitignore_repo"

        result = repodx.check_gitignore(repo_path)

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("Could not read .gitignore:"))

    def test_check_gitignore_reports_os_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / ".gitignore").write_text(".env\n", encoding="utf-8")

            with mock.patch.object(
                Path, "read_text", side_effect=OSError("permission denied")
            ):
                result = repodx.check_gitignore(repo_path)

            self.assertEqual(len(result), 1)
            self.assertEqual(
                result[0], "Could not read .gitignore: permission denied"
            )

    def test_check_readme_accepts_english_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n## Installation\n\n## Usage\n", encoding="utf-8"
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_turkish_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n## Kurulum\n\n## Kullanım\n", encoding="utf-8"
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_setext_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "Project\n=======\n\nInstallation\n------------\n\nUsage\n-----\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_closed_atx_headings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project #\n\n## Installation ##\n\n## Usage ##\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_lowercase_file_name(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "readme.md").write_text(
                "# Project\n\n## Installation\n\n## Usage\n", encoding="utf-8"
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_accepts_rst_readme(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.rst").write_text(
                "Project\n=======\n\nInstallation\n~~~~~~~~~~~~\n\nUsage\n^^^^^\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_reports_missing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, ["Missing README file"])

    def test_check_readme_reports_unreadable_file(self):
        repo_path = SAMPLE_DIR / "bad_readme_repo"

        result = repodx.check_readme(repo_path)

        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("Could not read README.md:"))

    def test_check_readme_ignores_heading_like_lines_inside_code_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n"
                "```python\n"
                "# Installation\n"
                "# Usage\n"
                "```\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(
                result,
                [
                    "Missing README heading: Installation",
                    "Missing README heading: Usage",
                ],
            )

    def test_check_readme_ignores_setext_headings_inside_code_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n"
                "```text\n"
                "Installation\n"
                "------------\n"
                "Usage\n"
                "-----\n"
                "```\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(
                result,
                [
                    "Missing README heading: Installation",
                    "Missing README heading: Usage",
                ],
            )

    def test_check_readme_accepts_real_headings_around_code_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text(
                "# Project\n\n"
                "## Installation\n\n"
                "```python\n"
                "# Not a heading\n"
                "```\n\n"
                "## Usage\n",
                encoding="utf-8",
            )

            result = repodx.check_readme(repo_path)

            self.assertEqual(result, [])

    def test_check_readme_reports_os_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text("# Project\n", encoding="utf-8")

            with mock.patch.object(
                Path, "read_text", side_effect=OSError("permission denied")
            ):
                result = repodx.check_readme(repo_path)

            self.assertEqual(
                result, ["Could not read README.md: permission denied"]
            )

    def test_check_readme_reports_missing_sections(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "README.md").write_text("# Project\n", encoding="utf-8")

            result = repodx.check_readme(repo_path)

            self.assertEqual(
                result,
                [
                    "Missing README heading: Installation",
                    "Missing README heading: Usage",
                ],
            )

    def test_build_report_scores_sample_repo(self):
        report = repodx.build_report(Path("sample_repo"))
        found = {(finding["id"], finding["path"], finding["detail"]) for finding in report["findings"]}

        self.assertEqual(report["counts"], {"critical": 3, "warning": 8, "info": 3})
        self.assertEqual(report["grade"], "F")
        self.assertIn(("database-url", "app.js", "hunter...ke"), found)
        self.assertIn(("env-file", ".env", None), found)
        self.assertIn(("firebase-rules", "firestore.rules", None), found)
        self.assertIn(("supabase-rls", "supabase/migrations/001_init.sql", "profiles"), found)
        self.assertIn(("junk", "node_modules/", None), found)
        self.assertIn(("license", None, None), found)
        self.assertIn(("env-example", None, None), found)


def fake(*parts):
    """Join parts at runtime so no scanner sees a literal key in this file."""
    return "".join(parts)


def make_repo(temp_dir, files):
    repo_path = Path(temp_dir)

    for relative_text, content in files.items():
        path = repo_path / relative_text
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    return repo_path


def findings_for(repo_path, check_id):
    report = repodx.build_report(repo_path)
    return [finding for finding in report["findings"] if finding["id"] == check_id]


class SecretScanTests(unittest.TestCase):
    def test_detects_provider_keys(self):
        keys = {
            "OpenAI API key": fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2"),
            "Anthropic API key": fake("sk-", "ant-", "api03-", "A1b2C3d4E5f6G7h8I9j0"),
            "AWS access key": fake("AKIA", "ABCDEFGHIJKLMNOP"),
            "GitHub token": fake("ghp", "_", "A" * 36),
            "Stripe secret key": fake("sk", "_live_", "A1b2C3d4E5f6G7h8I9j0K1"),
            "Supabase secret key": fake("sb", "_secret_", "A1b2C3d4E5f6G7h8I9j0K1"),
            "Private key": fake("-----BEGIN ", "RSA PRIVATE KEY-----"),
        }

        for name, key in keys.items():
            with self.subTest(name=name):
                hits = repodx.scan_line_for_secrets(f'const key = "{key}";')

                self.assertEqual([(hit[0], hit[1], hit[2]) for hit in hits], [("secret", "critical", name)])

    def test_reports_secret_location_and_masks_value(self):
        key = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"src/app.js": f"// setup\nconst key = '{key}';\n"})

            result = findings_for(repo_path, "secret")

        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["path"], result[0]["line"]), ("src/app.js", 2))
        self.assertEqual(result[0]["detail"], "sk-pro...l2")
        self.assertNotIn(key, result[0]["detail"])

    def test_skips_files_ignored_by_gitignore(self):
        key = fake("sk-", "proj-", "A1b2C3d4E5f6G7h8I9j0K1l2")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {".gitignore": ".env\n", ".env": f"OPENAI_API_KEY={key}\n"})

            self.assertEqual(findings_for(repo_path, "secret"), [])
            self.assertEqual(findings_for(repo_path, "env-file"), [])

    def test_inline_ignore_marker_suppresses_finding(self):
        key = fake("AKIA", "ABCDEFGHIJKLMNOP")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"docs.md": f"Example: {key} <!-- repodx:ignore -->\n"})

            self.assertEqual(findings_for(repo_path, "secret"), [])

    def test_repodxignore_excludes_paths(self):
        key = fake("AKIA", "ABCDEFGHIJKLMNOP")

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {".repodxignore": "fixtures/\n", "fixtures/key.txt": key, "fixtures/node_modules/x.js": ""},
            )

            report = repodx.build_report(repo_path)

        self.assertEqual([f for f in report["findings"] if f["path"] and "fixtures" in f["path"]], [])

    def test_skips_binary_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            (repo_path / "image.png").write_bytes(b"\x89PNG\0" + fake("AKIA", "ABCDEFGHIJKLMNOP").encode())

            self.assertEqual(findings_for(repo_path, "secret"), [])

    def test_google_key_is_a_warning(self):
        hits = repodx.scan_line_for_secrets(fake("apiKey: 'AIza", "A" * 35, "'"))

        self.assertEqual([(hit[0], hit[1]) for hit in hits], [("google-api-key", "warning")])

    def test_detects_supabase_service_role_jwt_but_not_anon(self):
        def jwt(role):
            header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
            payload = base64.urlsafe_b64encode(
                json.dumps({"iss": "supabase", "role": role}).encode()
            ).decode().rstrip("=")
            return f"{header}.{payload}.c2lnbmF0dXJlc2lnbmF0dXJl"

        service_hits = repodx.scan_line_for_secrets(f"key = '{jwt('service_role')}'")
        anon_hits = repodx.scan_line_for_secrets(f"key = '{jwt('anon')}'")

        self.assertEqual([hit[0] for hit in service_hits], ["supabase-service-role"])
        self.assertEqual(anon_hits, [])

    def test_database_url_ignores_local_hosts_and_placeholders(self):
        remote = repodx.scan_line_for_secrets("postgres://app:s3cr3t-value@db.prod.example.net:5432/app")
        local = repodx.scan_line_for_secrets("postgres://app:s3cr3t-value@localhost:5432/app")
        placeholder = repodx.scan_line_for_secrets("postgres://user:password@db.prod.example.net/app")
        template = repodx.scan_line_for_secrets("postgres://user:${DB_PASSWORD}@db.prod.example.net/app")

        self.assertEqual([hit[0] for hit in remote], ["database-url"])
        self.assertEqual((local, placeholder, template), ([], [], []))


class ConfigCheckTests(unittest.TestCase):
    def test_env_file_reported_but_example_is_fine(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {".env": "A=1\n", ".env.local": "A=1\n", ".env.production": "A=1\n", ".env.example": "A=\n"},
            )

            result = findings_for(repo_path, "env-file")

        self.assertEqual(
            sorted((f["path"], f["severity"]) for f in result),
            [(".env", "critical"), (".env.local", "critical"), (".env.production", "warning")],
        )

    def test_env_example_suggested_when_code_reads_env(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"main.py": "import os\nkey = os.getenv('KEY')\n"})
            missing = findings_for(repo_path, "env-example")
            (repo_path / ".env.example").write_text("KEY=\n", encoding="utf-8")
            present = findings_for(repo_path, "env-example")

        self.assertEqual(len(missing), 1)
        self.assertEqual(present, [])

    def test_supabase_rls_reports_only_unprotected_public_tables(self):
        sql = (
            "create table public.profiles (id uuid);\n"
            "create table if not exists notes (id int);\n"
            'ALTER TABLE "public"."notes" ENABLE ROW LEVEL SECURITY;\n'
            "create table private.audit (id int);\n"
            "-- create table commented_out (id int);\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"supabase/migrations/001.sql": sql})

            result = findings_for(repo_path, "supabase-rls")

        self.assertEqual([f["detail"] for f in result], ["profiles"])

    def test_firebase_rules_detect_public_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(
                temp_dir,
                {
                    "firestore.rules": "allow read, write: if true;\n// allow read: if true;\n",
                    "database.rules.json": '{"rules": {".read": true, ".write": "auth != null"}}\n',
                    "storage.rules": "allow read: if request.auth != null;\n",
                },
            )

            result = findings_for(repo_path, "firebase-rules")

        self.assertEqual(
            sorted((f["path"], f["line"]) for f in result),
            [("database.rules.json", 1), ("firestore.rules", 1)],
        )

    def test_large_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)

            with open(repo_path / "model.bin", "wb") as handle:
                handle.truncate(repodx.LARGE_FILE_LIMIT_BYTES + 1)

            with open(repo_path / "video.mp4", "wb") as handle:
                handle.truncate(repodx.LARGE_FILE_WARNING_BYTES + 1)

            result = findings_for(repo_path, "large-file")

        self.assertEqual(
            sorted((f["path"], f["severity"]) for f in result),
            [("model.bin", "critical"), ("video.mp4", "warning")],
        )

    def test_build_output_folders_are_junk(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {".next/cache.json": "{}", "dist/app.js": ""})

            self.assertEqual(repodx.find_junk_files(repo_path), [".next/", "dist/"])

    def test_license_check(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir)
            missing = repodx.check_license(repo_path)
            (repo_path / "LICENSE.md").write_text("MIT", encoding="utf-8")

            self.assertEqual(len(missing), 1)
            self.assertEqual(repodx.check_license(repo_path), [])

    def test_long_agent_file_is_info(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = make_repo(temp_dir, {"CLAUDE.md": "- rule\n" * 301, "AGENTS.md": "- rule\n"})

            result = findings_for(repo_path, "agent-file-size")

        self.assertEqual([(f["path"], f["detail"]) for f in result], [("CLAUDE.md", "301 lines")])


class ReportTests(unittest.TestCase):
    def clean_repo(self, temp_dir):
        return make_repo(
            temp_dir,
            {
                ".gitignore": "__pycache__/\n.env\nnode_modules/\n",
                "LICENSE": "MIT",
                "README.md": "# App\n\n## Installation\n\n## Usage\n",
            },
        )

    def test_clean_repo_scores_100(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            report = repodx.build_report(self.clean_repo(temp_dir))

        self.assertEqual((report["score"], report["grade"], report["findings"]), (100, "A", []))

    def test_score_and_grade(self):
        self.assertEqual(repodx.grade_for_score(90), "A")
        self.assertEqual(repodx.grade_for_score(80), "B")
        self.assertEqual(repodx.grade_for_score(65), "C")
        self.assertEqual(repodx.grade_for_score(50), "D")
        self.assertEqual(repodx.grade_for_score(49), "F")

    def test_main_exit_codes_and_fail_on(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self.clean_repo(temp_dir)

            with mock.patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(repodx.main([str(repo_path)]), 0)
                (repo_path / "debug.log").write_text("log", encoding="utf-8")
                self.assertEqual(repodx.main([str(repo_path)]), 1)
                self.assertEqual(repodx.main([str(repo_path), "--fail-on", "critical"]), 0)
                self.assertEqual(repodx.main([str(repo_path), "--fail-on", "never"]), 0)

            with mock.patch("sys.stderr", new=io.StringIO()):
                self.assertEqual(repodx.main([str(repo_path / "missing")]), 2)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = self.clean_repo(temp_dir)
            output = io.StringIO()

            with mock.patch("sys.stdout", new=output):
                repodx.main([str(repo_path), "--json"])

        data = json.loads(output.getvalue())
        self.assertEqual((data["score"], data["grade"], data["findings"]), (100, "A", []))

    def test_markdown_and_text_output_list_fixes(self):
        report = repodx.build_report(Path("sample_repo"))

        markdown = repodx.format_markdown(report)
        text = repodx.format_text(report)

        self.assertIn("## RepoDx: 0/100 (F)", markdown)
        self.assertIn("| critical | Environment file is not ignored | `.env` |", markdown)
        self.assertIn("[CRITICAL] Firebase rules allow public access", text)
        self.assertIn("Fix: ", text)
        self.assertNotIn("\033[", text)

    def test_badge(self):
        report = {"score": 94, "grade": "A"}

        self.assertEqual(
            repodx.badge_markdown(report),
            "[![repodx](https://img.shields.io/badge/repodx-A%2094%2F100-brightgreen)]"
            "(https://github.com/omerbek/repodx)",
        )


if __name__ == "__main__":
    unittest.main()
