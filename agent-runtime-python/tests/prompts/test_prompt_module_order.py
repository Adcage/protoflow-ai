from app.runtime.context import CodeGenType


def test_artifact_output_contract_includes_mode_specific_rules():
    from app.prompts.asset_modules import ArtifactOutputContractModule

    module = ArtifactOutputContractModule()

    single = module.render(
        type("Context", (), {"code_gen_type": CodeGenType.SINGLE_FILE})(),
        None,
    )
    assert "single HTML file" in single
    assert "index.html" in single

    multi = module.render(
        type("Context", (), {"code_gen_type": CodeGenType.MULTI_FILE})(),
        None,
    )
    assert "multi-file HTML project" in multi
    assert "style.css" in multi

    vue = module.render(
        type("Context", (), {"code_gen_type": CodeGenType.VUE_PROJECT})(),
        None,
    )
    assert "Vue project" in vue
    assert "Vue SFC" in vue
