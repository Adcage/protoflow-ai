from app.generation_modes.registry import GenerationModeRegistry


def register_application(registry: GenerationModeRegistry) -> None:
    """注册 application 生成模式定义。

    当前阶段生产环境只注册 application，暂不注册 PPT、界面原型、架构图或流程图模式。
    """
    from app.generation_modes.types import GenerationModeDefinition
    from app.agent_loop.agents.application import ApplicationImplementAgent

    definition = GenerationModeDefinition(
        mode_id="application",
        plan_prompt_module_ids=("application_plan",),
        implement_agent_factory=ApplicationImplementAgent,
        validate_prompt_module_ids=("application_validate",),
        supported_artifact_formats=frozenset({
            "web_single_file",
            "web_multi_file",
            "vue_project",
        }),
    )
    registry.register(definition)
