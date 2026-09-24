"""Exercise the installer's actual Embedded Python filesystem methods.

The methods are extracted from Fieldwork.Package.cls, not reimplemented here.
These tests use temporary directories and inject copy/rename failures. They do
not prove ObjectScript lifecycle ordering or IRIS global/web-app behavior; those
require integration tests in a disposable IRIS instance.
"""

import errno
from pathlib import Path
import re
import tempfile
import textwrap
import unittest
from unittest import mock


PACKAGE_SOURCE = Path(__file__).resolve().parent.parent / "iris" / "Fieldwork.Package.cls"


def embedded_method(name, parameters):
    source = PACKAGE_SOURCE.read_text(encoding="utf-8")
    pattern = (
        r"^ClassMethod " + re.escape(name)
        + r"\([^\n]*\) As %String \[ Language = python \]\n\{\n(.*?)\n\}"
    )
    match = re.search(pattern, source, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"Cannot locate Embedded Python method {name} in {PACKAGE_SOURCE.name}")
    body = textwrap.indent(textwrap.dedent(match.group(1)), "    ")
    namespace = {}
    code = compile(f"def method({parameters}):\n{body}\n", f"{PACKAGE_SOURCE}:{name}", "exec")
    exec(code, namespace)
    return namespace["method"]


COPY_FILES = embedded_method("CopyFiles", "sourceRoot, root")
ROOT_PROBLEM = embedded_method("RootProblem", "root, owned")


def snapshot(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = ("symlink", str(path.readlink()))
        elif path.is_dir():
            result[relative] = ("directory",)
        else:
            result[relative] = ("file", path.read_bytes())
    return result


class PackageFilesystemTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fieldwork-package-test-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.source = self.base / "source"
        self.target = self.base / "installed" / "USER"
        # Synthetic package inputs; the installer itself decides what to copy.
        for name in (
            "app/backend.py", "app/static/index.html", "app/static/app.js",
            "iris/fieldwork_runtime.py", "tools/start_installed.py",
            "README.md", "IPM.md", "LICENSE", "NOTICE.md",
        ):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"original fixture: {name}\n", encoding="utf-8")

    def copy(self):
        return COPY_FILES(str(self.source), str(self.target))

    def install(self):
        self.assertEqual(self.copy(), "")
        self.assertEqual(ROOT_PROBLEM(str(self.target), True), "")

    def assert_no_staging_or_backup(self, installed=True):
        self.assertEqual(
            sorted(path.name for path in self.target.parent.iterdir()),
            ["USER"] if installed else [],
        )

    def assert_guard_refuses_without_mutation(self, phrase=""):
        before = snapshot(self.target)
        problem = ROOT_PROBLEM(str(self.target), True)
        self.assertTrue(problem, "Guard accepted changed installation contents")
        self.assertIn(phrase, problem)
        self.assertEqual(snapshot(self.target), before)

    def symlink(self, link, destination, directory=False):
        try:
            link.symlink_to(destination, target_is_directory=directory)
        except NotImplementedError:
            self.skipTest("This platform does not support symbolic links")
        except OSError as error:
            if error.errno in (errno.EPERM, errno.EACCES, errno.ENOSYS) or getattr(error, "winerror", None) in (5, 1314):
                self.skipTest("The OS does not permit this process to create symbolic links")
            raise

    def test_fresh_copy_failure_is_clean_and_retry_succeeds(self):
        with mock.patch("shutil.copy2", side_effect=OSError("injected copy failure")):
            self.assertTrue(self.copy())
        self.assertFalse(self.target.exists())
        self.assert_no_staging_or_backup(installed=False)
        self.assertEqual(ROOT_PROBLEM(str(self.target), False), "")
        self.install()
        self.assert_no_staging_or_backup()

    def test_update_copy_failure_preserves_prior_files_and_manifest(self):
        self.install()
        before = snapshot(self.target)
        (self.source / "app" / "backend.py").write_text("updated candidate", encoding="utf-8")
        with mock.patch("shutil.copy2", side_effect=OSError("injected copy failure")):
            self.assertTrue(self.copy())
        self.assertEqual(snapshot(self.target), before)
        self.assertEqual(ROOT_PROBLEM(str(self.target), True), "")
        self.assert_no_staging_or_backup()

    def test_update_swap_failure_restores_prior_files_and_manifest(self):
        self.install()
        before = snapshot(self.target)
        (self.source / "app" / "backend.py").write_text("updated candidate", encoding="utf-8")
        original_rename = Path.rename

        def fail_swap(path, destination):
            if path.name.startswith(".fieldwork-stage-"):
                raise OSError("injected swap failure")
            return original_rename(path, destination)

        with mock.patch.object(Path, "rename", fail_swap):
            self.assertTrue(self.copy())
        self.assertEqual(snapshot(self.target), before)
        self.assertEqual(ROOT_PROBLEM(str(self.target), True), "")
        self.assert_no_staging_or_backup()

    def test_update_retry_replaces_complete_candidate_after_copy_failure(self):
        self.install()
        candidate = "updated candidate\n"
        (self.source / "app" / "backend.py").write_text(candidate, encoding="utf-8")
        with mock.patch("shutil.copy2", side_effect=OSError("injected copy failure")):
            self.assertTrue(self.copy())
        self.install()
        self.assertEqual((self.target / "app" / "backend.py").read_text(encoding="utf-8"), candidate)
        self.assert_no_staging_or_backup()

    def test_modified_gateway_file_refused_and_preserved(self):
        self.install()
        (self.target / "app" / "backend.py").write_text("local modifications", encoding="utf-8")
        self.assert_guard_refuses_without_mutation("modified, removed or added")

    def test_added_file_refused_and_preserved(self):
        self.install()
        (self.target / "local-notes.txt").write_text("keep this file", encoding="utf-8")
        self.assert_guard_refuses_without_mutation("modified, removed or added")

    def test_deleted_file_refused(self):
        self.install()
        (self.target / "app" / "backend.py").unlink()
        self.assert_guard_refuses_without_mutation("modified, removed or added")

    def test_added_empty_directory_refused_and_preserved(self):
        self.install()
        (self.target / "local-directory").mkdir()
        self.assert_guard_refuses_without_mutation("modified, removed or added")

    def test_replaced_owner_marker_refused_and_preserved(self):
        self.install()
        (self.target / ".fieldwork-owner").write_text("someone else's installation\n", encoding="utf-8")
        self.assert_guard_refuses_without_mutation("ownership marker does not match")

    def test_python_cache_bytecode_is_accepted(self):
        self.install()
        cache = self.target / "app" / "__pycache__"
        cache.mkdir()
        (cache / "backend.cpython-313.pyc").write_bytes(b"synthetic bytecode fixture")
        before = snapshot(self.target)
        self.assertEqual(ROOT_PROBLEM(str(self.target), True), "")
        self.assertEqual(snapshot(self.target), before)

    def test_non_bytecode_file_in_python_cache_refused_and_preserved(self):
        self.install()
        cache = self.target / "app" / "__pycache__"
        cache.mkdir()
        (cache / "local-notes.txt").write_text("keep this file", encoding="utf-8")
        self.assert_guard_refuses_without_mutation("non-cache file")

    def test_symbolic_link_inside_installation_refused(self):
        self.install()
        outside = self.base / "outside.txt"
        outside.write_text("outside file", encoding="utf-8")
        self.symlink(self.target / "app" / "outside.txt", outside)
        self.assert_guard_refuses_without_mutation("symbolic link")
        self.assertEqual(outside.read_text(encoding="utf-8"), "outside file")

    def test_symbolic_link_installation_root_refused(self):
        self.install()
        real = self.target.parent / "original"
        self.target.rename(real)
        self.symlink(self.target, real, directory=True)
        before = snapshot(real)
        self.assertIn("symbolic links", ROOT_PROBLEM(str(self.target), True))
        self.assertEqual(snapshot(real), before)

    def test_symbolic_link_installation_parent_refused(self):
        self.install()
        alias = self.base / "alias"
        self.symlink(alias, self.target.parent, directory=True)
        before = snapshot(self.target)
        self.assertIn("symbolic links", ROOT_PROBLEM(str(alias / "USER"), True))
        self.assertEqual(snapshot(self.target), before)


if __name__ == "__main__":
    unittest.main()
