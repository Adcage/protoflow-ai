from app.agent_loop.state import AgentLoopState
from app.prompts.loop_modules import SkillContextModule
from app.runtime.event_bus import EventBus
from app.runtime.orchestrator import RuntimeOrchestrator


def test_agent_loop_registry_excludes_conversation_content_modules():
    services = RuntimeOrchestrator()._build_services(EventBus(agent_run_id=1))
    module_ids = services.prompt_module_registry.module_ids

    assert "chat_history_summary" not in module_ids
    assert "user_prompt" not in module_ids


def test_plan_workflow_does_not_use_hardcoded_tool_signatures():
    from app.prompts.loop_modules import PlanWorkflowModule

    module = PlanWorkflowModule()
    rendered = module.render(None, AgentLoopState(mode="plan"))

    assert "write_file" not in rendered
    assert "switch_mode" not in rendered
    assert "ask_user(" not in rendered
    assert "write_plan(" not in rendered


def test_skill_context_module_lists_available_skills_before_selection():
    skill = type(
        "SkillDef",
        (),
        {"id": "ui-ux-pro-max", "description": "UI/UX design intelligence"},
    )()
    registry = type("SkillRegistry", (), {"all": lambda self: [skill]})()
    index = type("AssetIndex", (), {"skill_registry": registry})()
    state = AgentLoopState(mode="plan")
    state._asset_index = index

    from app.prompts.composer import PromptComposer

    messages = PromptComposer([SkillContextModule()]).compose(None, state)

    assert messages
    assert "可用 Skill 列表" in messages[0]["content"]
    assert "ui-ux-pro-max" in messages[0]["content"]


def test_implement_workflow_shows_artifact_progress_for_multi_file():
    from app.prompts.loop_modules import ImplementWorkflowModule

    module = ImplementWorkflowModule()
    state = AgentLoopState(mode="implement")
    state.implement_phase_files = ["style.css"]
    context = type("Ctx", (), {"code_gen_type": type("Enum", (), {"value": "multi-file"})()})()

    rendered = module.render(context, state)

    assert "index.html" in rendered
    assert "style.css" in rendered
    assert "script.js" in rendered
    assert "[已完成]" in rendered
    assert "[待生成]" in rendered
    assert "下一个待生成文件" in rendered
    assert "不得在同一文件上反复重写" in rendered


def test_implement_workflow_reports_all_done_when_artifacts_complete():
    from app.prompts.loop_modules import ImplementWorkflowModule

    module = ImplementWorkflowModule()
    state = AgentLoopState(mode="implement")
    state.implement_phase_files = ["index.html", "style.css", "script.js"]
    context = type("Ctx", (), {"code_gen_type": type("Enum", (), {"value": "multi-file"})()})()

    rendered = module.render(context, state)

    assert "所有必须文件已生成" in rendered


def test_plan_workflow_shows_clarification_history():
    from app.prompts.loop_modules import PlanWorkflowModule

    module = PlanWorkflowModule()
    state = AgentLoopState(mode="plan")
    state.clarification_questions = [
        {"question": "您想要创建哪种类型的登录界面？"}
    ]

    rendered = module.render(None, state)

    assert "已澄清的问题" in rendered
    assert "您想要创建哪种类型的登录界面？" in rendered
    assert "请勿再次询问" in rendered
