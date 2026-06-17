import unittest.mock
from pathlib import Path

from app.capabilities.seeds.applier import SeedApplier, _is_path_traversal
from app.capabilities.seeds.types import SeedDefinition


def _make_seed(
    id: str = "test-seed",
    copy_mode: str = "missing-only",
    files_dir: Path | None = None,
) -> SeedDefinition:
    return SeedDefinition(
        id=id,
        name="Test Seed",
        description="Test seed",
        code_gen_type="vue_project",
        entry="src/App.vue",
        files_dir=files_dir or Path("/seeds/test/files"),
        copy_mode=copy_mode,
        source_path=Path("/seeds/test/seed.json"),
    )


class TestSeedApplier:
    def test_missing_only_copies_nonexistent_files(self, tmp_path: Path):
        files_dir = tmp_path / "seed-files"
        (files_dir / "src").mkdir(parents=True)
        (files_dir / "src" / "App.vue").write_text("<template></template>", encoding="utf-8")
        (files_dir / "package.json").write_text('{"name": "test"}', encoding="utf-8")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        seed = _make_seed(files_dir=files_dir)
        applier = SeedApplier()
        copied = applier.apply(seed, workspace)

        assert "package.json" in copied
        assert str(Path("src/App.vue")) in copied
        assert (workspace / "package.json").exists()
        assert (workspace / "src" / "App.vue").exists()

    def test_missing_only_does_not_overwrite_existing(self, tmp_path: Path):
        files_dir = tmp_path / "seed-files"
        (files_dir / "src").mkdir(parents=True)
        (files_dir / "src" / "App.vue").write_text("seed content", encoding="utf-8")

        workspace = tmp_path / "workspace"
        (workspace / "src").mkdir(parents=True)
        (workspace / "src" / "App.vue").write_text("existing content", encoding="utf-8")

        seed = _make_seed(files_dir=files_dir)
        applier = SeedApplier()
        copied = applier.apply(seed, workspace)

        assert str(Path("src/App.vue")) not in copied
        assert (workspace / "src" / "App.vue").read_text(encoding="utf-8") == "existing content"

    def test_overwrite_mode_copies_and_overwrites(self, tmp_path: Path):
        files_dir = tmp_path / "seed-files"
        (files_dir / "src").mkdir(parents=True)
        (files_dir / "src" / "App.vue").write_text("new content", encoding="utf-8")

        workspace = tmp_path / "workspace"
        (workspace / "src").mkdir(parents=True)
        (workspace / "src" / "App.vue").write_text("old content", encoding="utf-8")

        seed = _make_seed(copy_mode="overwrite", files_dir=files_dir)
        applier = SeedApplier()
        copied = applier.apply(seed, workspace)

        assert str(Path("src/App.vue")) in copied
        assert (workspace / "src" / "App.vue").read_text(encoding="utf-8") == "new content"

    def test_path_traversal_file_skipped(self, tmp_path: Path):
        files_dir = tmp_path / "seed-files"
        files_dir.mkdir(parents=True)
        (files_dir / "safe.txt").write_text("safe", encoding="utf-8")

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        applier = SeedApplier()

        mock_file = files_dir / "safe.txt"
        with unittest.mock.patch.object(Path, "rglob", return_value=[mock_file]):
            with unittest.mock.patch.object(Path, "relative_to", return_value=Path("../evil.txt")):
                seed = _make_seed(files_dir=files_dir)
                applier.apply(seed, workspace)

        assert not (workspace / "evil.txt").exists()

    def test_empty_files_dir_returns_empty(self, tmp_path: Path):
        files_dir = tmp_path / "seed-files"
        files_dir.mkdir()

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        seed = _make_seed(files_dir=files_dir)
        applier = SeedApplier()
        copied = applier.apply(seed, workspace)

        assert copied == []

    def test_nonexistent_files_dir_returns_empty(self, tmp_path: Path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        seed = _make_seed(files_dir=Path("/nonexistent"))
        applier = SeedApplier()
        copied = applier.apply(seed, workspace)

        assert copied == []

    def test_nested_directories_created(self, tmp_path: Path):
        files_dir = tmp_path / "seed-files"
        (files_dir / "src" / "components").mkdir(parents=True)
        (files_dir / "src" / "components" / "Header.vue").write_text(
            "<template>Header</template>", encoding="utf-8"
        )

        workspace = tmp_path / "workspace"
        workspace.mkdir()

        seed = _make_seed(files_dir=files_dir)
        applier = SeedApplier()
        copied = applier.apply(seed, workspace)

        expected = str(Path("src/components/Header.vue"))
        assert expected in copied
        assert (workspace / "src" / "components" / "Header.vue").exists()


class TestPathTraversalDetection:
    def test_parent_reference_detected(self):
        assert _is_path_traversal("../evil.txt") is True

    def test_nested_parent_reference_detected(self):
        assert _is_path_traversal("foo/../../evil.txt") is True

    def test_normal_path_not_detected(self):
        assert _is_path_traversal("src/App.vue") is False

    def test_unix_absolute_path_detected(self):
        assert _is_path_traversal("/etc/passwd") is True

    def test_backslash_absolute_path_detected(self):
        assert _is_path_traversal("\\etc\\passwd") is True

    def test_simple_filename_not_detected(self):
        assert _is_path_traversal("package.json") is False
