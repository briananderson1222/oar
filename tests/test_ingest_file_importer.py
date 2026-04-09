"""Tests for oar.ingest.file_importer — FileImporter."""

from pathlib import Path

from oar.core.vault import Vault
from oar.ingest.file_importer import FileImporter


class TestFileImporterDetectType:
    """FileImporter.detect_type behaviour."""

    def test_import_file_detects_type_md(self):
        importer = FileImporter()
        assert importer.detect_type(Path("notes.md")) == "article"

    def test_import_file_detects_type_txt(self):
        importer = FileImporter()
        assert importer.detect_type(Path("notes.txt")) == "article"

    def test_import_file_detects_type_pdf(self):
        importer = FileImporter()
        assert importer.detect_type(Path("paper.pdf")) == "paper"

    def test_import_file_detects_type_other(self):
        importer = FileImporter()
        assert importer.detect_type(Path("data.csv")) == "file"


class TestFileImporterImportFile:
    """FileImporter.import_file behaviour."""

    def test_import_file_creates_raw_article(self, tmp_vault):
        # Create a source markdown file.
        source = tmp_vault / "source.md"
        source.write_text("# Hello World\n\nSome content here.")

        vault = Vault(tmp_vault)
        importer = FileImporter()
        result = importer.import_file(source, vault)

        # Result should be a path inside 01-raw/articles/.
        assert result.parent == tmp_vault / "01-raw" / "articles"
        assert result.suffix == ".md"
        assert result.exists()

    def test_import_file_preserves_content(self, tmp_vault):
        body = "# My Notes\n\nThis is my note content."
        source = tmp_vault / "mynote.md"
        source.write_text(body)

        vault = Vault(tmp_vault)
        importer = FileImporter()
        result = importer.import_file(source, vault)

        content = result.read_text()
        assert "This is my note content." in content


class TestFileImporterImportDirectory:
    """FileImporter.import_directory behaviour."""

    def test_import_directory_imports_all_md(self, tmp_vault):
        # Create a source directory with multiple .md files.
        src_dir = tmp_vault / "sources"
        src_dir.mkdir()
        (src_dir / "note1.md").write_text("Note one content.")
        (src_dir / "note2.md").write_text("Note two content.")
        (src_dir / "note3.txt").write_text("Text file content.")

        vault = Vault(tmp_vault)
        importer = FileImporter()
        results = importer.import_directory(src_dir, vault)

        assert len(results) == 3  # 2 .md + 1 .txt
        for path in results:
            assert path.parent == tmp_vault / "01-raw" / "articles"

    def test_import_directory_skips_hidden_files(self, tmp_vault):
        src_dir = tmp_vault / "sources"
        src_dir.mkdir()
        (src_dir / ".DS_Store").write_text("junk")
        (src_dir / ".hidden.md").write_text("hidden")
        (src_dir / "visible.md").write_text("visible content")

        vault = Vault(tmp_vault)
        importer = FileImporter()
        results = importer.import_directory(src_dir, vault)

        assert len(results) == 1
        assert "visible" in results[0].read_text()

    def test_import_directory_skips_index(self, tmp_vault):
        src_dir = tmp_vault / "sources"
        src_dir.mkdir()
        (src_dir / "_index.md").write_text("index")
        (src_dir / "real.md").write_text("real content")

        vault = Vault(tmp_vault)
        importer = FileImporter()
        results = importer.import_directory(src_dir, vault)

        assert len(results) == 1
        assert "real content" in results[0].read_text()
