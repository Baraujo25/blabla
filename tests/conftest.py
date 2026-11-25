import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "blabla-home"
    support = tmp_path / "support"
    home.mkdir()
    support.mkdir()
    monkeypatch.setenv("BLABLA_HOME", str(home))
    monkeypatch.setenv("BLABLA_SUPPORT_DIR", str(support))
    return home
