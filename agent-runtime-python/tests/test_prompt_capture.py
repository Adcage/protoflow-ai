import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.prompt_capture import CaptureStep, EnhanceRecord, PromptCapture


@pytest.fixture
def capture_dir(tmp_path):
    return str(tmp_path / "debug" / "prompts")


class TestPromptCapture:
    def test_disabled_by_default(self):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = False
            mock_settings.prompt_capture_dir = "debug/prompts"
            capture = PromptCapture(agent_run_id=1)
            assert not capture.enabled

    def test_record_step(self, capture_dir):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = True
            mock_settings.prompt_capture_dir = capture_dir
            capture = PromptCapture(agent_run_id=999, code_gen_type="vue_project", run_mode="generate")
            step = CaptureStep(
                mode="plan",
                iteration=1,
                model="gpt-4o",
                tool_count=7,
                system_prompt="你处于规划模式",
                user_prompt="创建登录页",
            )
            capture.record_step(step)
            assert len(capture._steps) == 1
            assert capture._steps[0].mode == "plan"
            assert capture._steps[0].iteration == 1

    def test_record_step_no_op_when_disabled(self):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = False
            mock_settings.prompt_capture_dir = "debug/prompts"
            capture = PromptCapture(agent_run_id=1)
            capture.record_step(CaptureStep(mode="plan", iteration=1))
            assert len(capture._steps) == 0

    def test_record_enhance(self, capture_dir):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = True
            mock_settings.prompt_capture_dir = capture_dir
            capture = PromptCapture(agent_run_id=999)
            record = EnhanceRecord(
                model="gpt-4o",
                original_prompt="原始",
                enhanced_prompt="增强后",
            )
            capture.record_enhance(record)
            assert capture._enhance is not None
            assert capture._enhance.original_prompt == "原始"
            assert capture._enhance.enhanced_prompt == "增强后"

    def test_record_enhance_no_op_when_disabled(self):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = False
            mock_settings.prompt_capture_dir = "debug/prompts"
            capture = PromptCapture(agent_run_id=1)
            capture.record_enhance(EnhanceRecord(original_prompt="x", enhanced_prompt="y"))
            assert capture._enhance is None

    @pytest.mark.asyncio
    async def test_save_creates_files(self, capture_dir):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = True
            mock_settings.prompt_capture_dir = capture_dir
            capture = PromptCapture(agent_run_id=999, code_gen_type="vue_project", run_mode="generate")
            capture.set_user_prompt("测试用户提示词")
            capture.record_step(CaptureStep(
                mode="plan",
                iteration=1,
                model="gpt-4o",
                system_prompt="系统提示词内容",
                user_prompt="测试用户提示词",
                response_text="我来规划一下",
                duration_ms=100.0,
            ))
            capture.record_step(CaptureStep(
                mode="implement",
                iteration=2,
                model="gpt-4o",
                system_prompt="实现提示词内容",
                user_prompt="测试用户提示词",
                tool_calls=[{"name": "write_file", "arguments": {"relative_path": "index.html"}}],
                duration_ms=2000.0,
            ))
            with patch.dict(os.environ, {"AGENT_RUNTIME_ROOT": ""}):
                result_dir = await capture.save()
            assert result_dir is not None
            output_dir = Path(result_dir)
            assert output_dir.exists()
            assert (output_dir / "index.json").exists()
            assert (output_dir / "01_plan_step_iter_1.md").exists()
            assert (output_dir / "02_implement_step_iter_2.md").exists()

            with open(output_dir / "index.json", encoding="utf-8") as f:
                data = json.load(f)
            assert data["agent_run_id"] == 999
            assert data["code_gen_type"] == "vue_project"
            assert data["run_mode"] == "generate"
            assert data["user_prompt"] == "测试用户提示词"
            assert data["total_iterations"] == 2
            assert len(data["chain"]) == 2
            assert data["chain"][0]["mode"] == "plan"
            assert data["chain"][0]["file"] == "01_plan_step_iter_1.md"
            assert data["chain"][1]["mode"] == "implement"
            assert data["chain"][1]["file"] == "02_implement_step_iter_2.md"

    @pytest.mark.asyncio
    async def test_save_returns_none_when_disabled(self):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = False
            mock_settings.prompt_capture_dir = "debug/prompts"
            capture = PromptCapture(agent_run_id=1)
            assert await capture.save() is None

    @pytest.mark.asyncio
    async def test_save_with_enhance(self, capture_dir):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = True
            mock_settings.prompt_capture_dir = capture_dir
            capture = PromptCapture(agent_run_id=888, run_mode="enhance")
            capture.record_enhance(EnhanceRecord(
                model="gpt-4o",
                original_prompt="原始提示词",
                enhanced_prompt="增强后的提示词内容",
                messages=[
                    {"role": "system", "content": "增强助手"},
                    {"role": "user", "content": "优化提示词：原始提示词"},
                ],
            ))
            with patch.dict(os.environ, {"AGENT_RUNTIME_ROOT": ""}):
                result_dir = await capture.save()
            assert result_dir is not None
            assert (Path(result_dir) / "enhance_prompt.md").exists()
            with open(Path(result_dir) / "index.json", encoding="utf-8") as f:
                data = json.load(f)
            assert data["agent_run_id"] == 888
            assert "enhance_prompt" in data
            assert data["enhance_prompt"]["original_length"] == 5
            assert data["enhance_prompt"]["file"] == "enhance_prompt.md"

    @pytest.mark.asyncio
    async def test_md_file_content(self, capture_dir):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = True
            mock_settings.prompt_capture_dir = capture_dir
            capture = PromptCapture(agent_run_id=100)
            capture.record_step(CaptureStep(
                mode="plan",
                iteration=1,
                model="gpt-4",
                tool_count=7,
                system_prompt="你是一个助手",
                user_prompt="创建页面",
                conversation_messages=[{"role": "user", "content": "之前的问题"}],
                response_text="我来规划",
                tool_calls=[{"name": "read_file", "arguments": {"path": "test.txt"}}],
                duration_ms=500.0,
            ))
            with patch.dict(os.environ, {"AGENT_RUNTIME_ROOT": ""}):
                result_dir = await capture.save()
            md_path = Path(result_dir) / "01_plan_step_iter_1.md"
            content = md_path.read_text(encoding="utf-8")
            assert "Plan Step" in content
            assert "Iteration 1" in content
            assert "gpt-4" in content
            assert "System Prompt (6 字符)" in content
            assert "你是一个助手" in content
            assert "User Message (4 字符)" in content
            assert "创建页面" in content
            assert "之前的问题" in content
            assert "我来规划" in content
            assert "read_file" in content
            assert "500ms" in content

    @pytest.mark.asyncio
    async def test_save_to_custom_dir(self, capture_dir):
        with patch("app.core.prompt_capture.settings") as mock_settings:
            mock_settings.prompt_capture_enabled = True
            mock_settings.prompt_capture_dir = capture_dir
            capture = PromptCapture(agent_run_id=555)
            capture.set_user_prompt("hello")
            with patch.dict(os.environ, {"AGENT_RUNTIME_ROOT": ""}):
                result_dir = await capture.save()
            assert capture_dir in result_dir
            assert "555" in result_dir
