import pytest

from seqrename import journal


@pytest.fixture(autouse=True)
def isolated_journals(tmp_path_factory, monkeypatch):
    """Keep tests out of the real per-user journal directory."""
    monkeypatch.setenv(journal.ENV_DIR, str(tmp_path_factory.mktemp("journals")))
