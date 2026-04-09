"""Tests for oar.core.slug — Slug generation."""

from oar.core.slug import slugify


class TestSlugify:
    """slugify function."""

    def test_slugify_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_slugify_special_chars(self):
        assert slugify("C++ & Python!") == "c-python"

    def test_slugify_already_slug(self):
        assert slugify("already-slug") == "already-slug"

    def test_slugify_unicode(self):
        assert slugify("Café Résumé") == "cafe-resume"

    def test_slugify_empty_string(self):
        assert slugify("") == ""
