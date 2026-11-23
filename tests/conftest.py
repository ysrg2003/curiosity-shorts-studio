"""Keep synthetic research persistence out of the production drafts directory."""
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def isolated_research_persistence(monkeypatch,tmp_path):
    from curiosity import spec,router_ai
    original=spec.write_json
    production=spec.ROOT/'drafts'
    def write(path,data):
        path=Path(path)
        if path.parent==production:
            path=tmp_path/'synthetic-drafts'/path.name
            path.parent.mkdir(parents=True,exist_ok=True)
        original(path,data)
    monkeypatch.setattr(spec,'write_json',write)
    monkeypatch.setattr(router_ai,'_STOPPED',{})
