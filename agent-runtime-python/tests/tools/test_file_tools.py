import pytest
import os
import tempfile

from app.tools.file_tools import Workspace, FileTools
from app.core.exceptions import AgentRuntimeError


class TestWorkspace:
    def test_creates_root_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "does", "not", "exist")
            ws = Workspace(nested)
            assert os.path.isdir(nested)
            assert ws.root == os.path.abspath(nested)

    def test_resolve_normal_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            result = ws.resolve("src/App.vue")
            expected = os.path.normpath(os.path.join(tmpdir, "src", "App.vue"))
            assert result == expected

    def test_resolve_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            with pytest.raises(AgentRuntimeError, match="路径穿越"):
                ws.resolve("../../etc/passwd")

    def test_resolve_empty_path_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            with pytest.raises(AgentRuntimeError, match="路径不能为空"):
                ws.resolve("")

    def test_ensure_dir_creates_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            file_path = os.path.join(tmpdir, "src", "components", "App.vue")
            ws.ensure_dir(file_path)
            assert os.path.isdir(os.path.join(tmpdir, "src", "components"))


class TestFileTools:
    @pytest.mark.asyncio
    async def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            result = await tools.write_file("src/App.vue", "<template>Hi</template>")
            assert "写入成功" in result
            content = await tools.read_file("src/App.vue")
            assert "<template>Hi</template>" in content

    @pytest.mark.asyncio
    async def test_read_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            with pytest.raises(AgentRuntimeError, match="文件不存在"):
                await tools.read_file("missing.txt")

    @pytest.mark.asyncio
    async def test_modify_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            await tools.write_file("test.txt", "hello world")
            result = await tools.modify_file("test.txt", "hello", "goodbye")
            assert "修改成功" in result
            content = await tools.read_file("test.txt")
            assert content == "goodbye world"

    @pytest.mark.asyncio
    async def test_modify_file_not_found_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            await tools.write_file("test.txt", "hello")
            with pytest.raises(AgentRuntimeError, match="未找到"):
                await tools.modify_file("test.txt", "xyz", "abc")

    @pytest.mark.asyncio
    async def test_delete_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            await tools.write_file("del.txt", "bye")
            result = await tools.delete_file("del.txt")
            assert "删除成功" in result

    @pytest.mark.asyncio
    async def test_read_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            await tools.write_file("a.txt", "a")
            await tools.write_file("b.txt", "b")
            result = await tools.read_dir(".")
            assert "a.txt" in result
            assert "b.txt" in result

    @pytest.mark.asyncio
    async def test_read_dir_nonexistent_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            result = await tools.read_dir("newdir")
            assert result == ""
            assert os.path.isdir(os.path.join(tmpdir, "newdir"))


class TestSkillScopeReading:
    @pytest.mark.asyncio
    async def test_read_file_skill_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as skill_dir:
                ref_content = "skill reference content"
                ref_path = os.path.join(skill_dir, "references", "layout.md")
                os.makedirs(os.path.dirname(ref_path), exist_ok=True)
                with open(ref_path, "w", encoding="utf-8") as f:
                    f.write(ref_content)

                ws = Workspace(tmpdir)
                tools = FileTools(ws, skill_dir=skill_dir)
                result = await tools.read_file("references/layout.md", scope="skill")
                assert ref_content in result

    @pytest.mark.asyncio
    async def test_read_file_skill_scope_no_skill_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ws = Workspace(tmpdir)
            tools = FileTools(ws)
            with pytest.raises(AgentRuntimeError) as exc_info:
                await tools.read_file("references/layout.md", scope="skill")
            assert exc_info.value.code == 62009

    @pytest.mark.asyncio
    async def test_read_file_skill_scope_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as skill_dir:
                ws = Workspace(tmpdir)
                tools = FileTools(ws, skill_dir=skill_dir)
                with pytest.raises(AgentRuntimeError, match="路径穿越"):
                    await tools.read_file("../../../etc/passwd", scope="skill")

    @pytest.mark.asyncio
    async def test_read_file_skill_scope_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with tempfile.TemporaryDirectory() as skill_dir:
                ws = Workspace(tmpdir)
                tools = FileTools(ws, skill_dir=skill_dir)
                with pytest.raises(AgentRuntimeError, match="文件不存在"):
                    await tools.read_file("nonexistent.md", scope="skill")
