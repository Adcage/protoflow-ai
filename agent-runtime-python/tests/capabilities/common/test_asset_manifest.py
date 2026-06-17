from pathlib import Path

from app.capabilities.common.asset_manifest import AssetManifest, load_asset_manifest


def test_load_asset_manifest_supports_enabled_assets(tmp_path: Path):
    manifest_file = tmp_path / "asset-manifest.json"
    manifest_file.write_text(
        """{
          "schemaVersion": "ac-assets/v1",
          "enabled": {
            "skills": ["dashboard"],
            "seeds": ["vue-basic"],
            "templates": ["web-prototype"],
            "designSystems": ["default", "ant"],
            "craft": ["anti-ai-slop"]
          }
        }""",
        encoding="utf-8",
    )

    manifest = load_asset_manifest(tmp_path)

    assert manifest.enabled_skills == {"dashboard"}
    assert manifest.enabled_design_systems == {"default", "ant"}
    assert manifest.is_enabled("skills", "dashboard") is True
    assert manifest.is_enabled("skills", "landing-page") is False


def test_load_asset_manifest_returns_empty_when_no_file(tmp_path: Path):
    manifest = load_asset_manifest(tmp_path)
    assert manifest.enabled_skills == set()
    assert manifest.defaults == {}


def test_asset_manifest_is_enabled_returns_true_when_empty_enabled_set():
    manifest = AssetManifest()
    assert manifest.is_enabled("skills", "any-skill") is True
    assert manifest.is_enabled("seeds", "any-seed") is True


def test_asset_manifest_is_enabled_returns_false_for_disabled_asset():
    manifest = AssetManifest(enabled_skills={"dashboard"})
    assert manifest.is_enabled("skills", "dashboard") is True
    assert manifest.is_enabled("skills", "landing-page") is False


def test_load_asset_manifest_falls_back_on_invalid_json(tmp_path: Path):
    manifest_file = tmp_path / "asset-manifest.json"
    manifest_file.write_text("{invalid json!!!", encoding="utf-8")

    manifest = load_asset_manifest(tmp_path)

    assert manifest.enabled_skills == set()
    assert manifest.defaults == {}


def test_load_asset_manifest_falls_back_on_encoding_error(tmp_path: Path):
    manifest_file = tmp_path / "asset-manifest.json"
    manifest_file.write_bytes(b"\xff\xfe" + "invalid".encode("utf-16-le"))

    manifest = load_asset_manifest(tmp_path)

    assert manifest.enabled_skills == set()
