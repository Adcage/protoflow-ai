package com.adcage.acaicodefree.legacy.workflow.e2e;

import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCategoryEnum;
import com.adcage.acaicodefree.legacy.workflow.model.ImageCollectionPlan;
import com.adcage.acaicodefree.legacy.workflow.model.ImageResource;
import com.adcage.acaicodefree.legacy.workflow.model.QualityResult;
import com.adcage.acaicodefree.legacy.workflow.node.*;
import com.adcage.acaicodefree.legacy.workflow.node.concurrent.*;
import com.adcage.acaicodefree.legacy.workflow.state.WorkflowContext;
import com.adcage.acaicodefree.legacy.workflow.service.CodeGenConcurrentWorkflow;
import com.adcage.acaicodefree.legacy.workflow.service.CodeGenWorkflow;
import org.bsc.langgraph4j.state.AgentState;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

public class WorkflowE2ETest extends BaseE2ETest {

    @Nested
    @DisplayName("线性工作流 E2E 测试")
    class LinearWorkflowE2E {

        @Test
        @DisplayName("线性工作流完整执行应返回包含原始提示的上下文")
        void defaultWorkflow_shouldExecuteToEnd() throws Exception {
            CodeGenWorkflow workflow = new CodeGenWorkflow();
            WorkflowContext result = workflow.execute(1L, "做一个产品网站");
            assertNotNull(result);
            assertEquals("做一个产品网站", result.getOriginalPrompt());
            assertEquals(1L, result.getAppId());
        }

        @Test
        @DisplayName("路由应将'首页'类提示路由为 MULTI_FILE")
        void defaultWorkflow_routerShouldRouteMultiFileForHomepage() throws Exception {
            CodeGenWorkflow workflow = new CodeGenWorkflow();
            WorkflowContext result = workflow.execute(2L, "做一个企业官网首页");
            assertEquals(CodeGenTypeEnum.MULTI_FILE, result.getGenerationType());
        }

        @Test
        @DisplayName("路由应将简单提示路由为 SINGLE_FILE")
        void defaultWorkflow_routerShouldRouteSingleFileForSimple() throws Exception {
            CodeGenWorkflow workflow = new CodeGenWorkflow();
            WorkflowContext result = workflow.execute(3L, "一个按钮");
            assertEquals(CodeGenTypeEnum.SINGLE_FILE, result.getGenerationType());
        }

        @Test
        @DisplayName("代码生成废桩应创建包含 index.html 的临时代码目录")
        void defaultWorkflow_codeGeneratorShouldCreateStubDir() throws Exception {
            CodeGenWorkflow workflow = new CodeGenWorkflow();
            WorkflowContext result = workflow.execute(4L, "测试桩目录");
            assertNotNull(result.getGeneratedCodeDir());
            Path dir = Path.of(result.getGeneratedCodeDir());
            assertTrue(Files.isDirectory(dir), "生成的代码目录应该存在");
            assertTrue(Files.exists(dir.resolve("index.html")), "应该包含 index.html");
        }

        @Test
        @DisplayName("质量检查节点对废桩目录应返回检查结果")
        void defaultWorkflow_qualityCheckShouldReturnResult() throws Exception {
            CodeGenWorkflow workflow = new CodeGenWorkflow();
            WorkflowContext result = workflow.execute(5L, "质量检查测试");
            assertNotNull(result.getQualityResult());
        }

        @Test
        @DisplayName("空图片收集不影响流程完成")
        void customWorkflow_emptyImageCollectionShouldNotBlock() throws Exception {
            ImageCollectorNode emptyCollector = new ImageCollectorNode();
            CodeGenWorkflow workflow = new CodeGenWorkflow(
                    emptyCollector, new PromptEnhancerNode(), new RouterNode(),
                    new CodeGeneratorNode(), new CodeQualityCheckNode(), new ProjectBuilderNode()
            );
            WorkflowContext result = workflow.execute(6L, "无图片收集测试");
            assertNotNull(result);
            assertEquals(6L, result.getAppId());
            assertNotNull(result.getImageList());
        }

        @Test
        @DisplayName("带 imageList 的流程应正确传递 imageListStr")
        void customWorkflow_shouldPropagateImageSummary() throws Exception {
            List<ImageResource> testImages = List.of(
                    ImageResource.builder().category(ImageCategoryEnum.CONTENT).description("产品图").url("https://example.com/img.jpg").build(),
                    ImageResource.builder().category(ImageCategoryEnum.ILLUSTRATION).description("插画").url("https://example.com/ill.svg").build()
            );
            ImageCollectorNode collectorWithImages = new ImageCollectorNode() {
                @Override
                public Map<String, Object> apply(AgentState state) {
                    var ctx = WorkflowContext.fromState(state);
                    ctx.advanceStep("image_collect");
                    ctx.setImageList(testImages);
                    ctx.setImageListStr("[CONTENT] 产品图; [ILLUSTRATION] 插画");
                    return ctx.toStateUpdate();
                }
            };
            CodeGenWorkflow workflow = new CodeGenWorkflow(
                    collectorWithImages, new PromptEnhancerNode(), new RouterNode(),
                    new CodeGeneratorNode(), new CodeQualityCheckNode(), new ProjectBuilderNode()
            );
            WorkflowContext result = workflow.execute(7L, "带图片的工作流");
            assertNotNull(result.getImageListStr());
            assertTrue(result.getImageListStr().contains("产品图"));
            assertTrue(result.getImageListStr().contains("插画"));
        }

        @Test
        @DisplayName("工作流图 Mermaid 结构完整")
        void shouldGenerateValidMermaidGraph() throws Exception {
            CodeGenWorkflow workflow = new CodeGenWorkflow();
            var compiled = workflow.createWorkflow();
            String mermaid = compiled.getGraph(org.bsc.langgraph4j.GraphRepresentation.Type.MERMAID).content();
            assertNotNull(mermaid);
            assertTrue(mermaid.contains("image_collect"));
            assertTrue(mermaid.contains("prompt_enhancer"));
            assertTrue(mermaid.contains("router"));
            assertTrue(mermaid.contains("code_generator"));
            assertTrue(mermaid.contains("code_quality_check"));
            assertTrue(mermaid.contains("project_builder"));
        }
    }

    @Nested
    @DisplayName("并发工作流 E2E 测试")
    class ConcurrentWorkflowE2E {

        @Test
        @DisplayName("并发工作流执行后 appId 和 originalPrompt 应正确保留")
        void concurrentWorkflow_shouldRetainOriginalPrompt() throws Exception {
            CodeGenConcurrentWorkflow workflow = createConcurrentWorkflowWithStubs();
            WorkflowContext result = workflow.execute(10L, "做企业官网");
            assertNotNull(result);
            assertEquals(10L, result.getAppId());
            assertEquals("做企业官网", result.getOriginalPrompt());
        }

        @Test
        @DisplayName("并发收集应聚合所有类别的图片")
        void concurrentWorkflow_shouldCollectAndAggregateAllCategories() throws Exception {
            List<ImageResource> contentImages = List.of(
                    ImageResource.builder().category(ImageCategoryEnum.CONTENT).description("内容图1").url("https://example.com/c1.jpg").build()
            );
            List<ImageResource> illustrations = List.of(
                    ImageResource.builder().category(ImageCategoryEnum.ILLUSTRATION).description("插画1").url("https://example.com/i1.svg").build()
            );
            List<ImageResource> diagrams = List.of(
                    ImageResource.builder().category(ImageCategoryEnum.ARCHITECTURE).description("架构图1").url("https://example.com/d1.png").build()
            );
            List<ImageResource> logos = List.of(
                    ImageResource.builder().category(ImageCategoryEnum.LOGO).description("Logo1").url("https://example.com/l1.png").build()
            );
            CodeGenConcurrentWorkflow workflow = new CodeGenConcurrentWorkflow(
                    new ImagePlanNode(prompt ->
                            ImageCollectionPlan.builder()
                                    .contentQuery("企业产品图").illustrationQuery("企业插画")
                                    .diagramQuery("企业架构图").logoPrompt("企业Logo").build()),
                    new ContentImageCollectorNode(query -> contentImages),
                    new IllustrationCollectorNode(query -> illustrations),
                    new DiagramCollectorNode(query -> diagrams),
                    new LogoCollectorNode(query -> logos),
                    new ImageAggregatorNode()
            );
            WorkflowContext result = workflow.execute(11L, "做企业官网");
            assertEquals(4, result.getImageList().size());
            assertEquals(1, result.getContentImages().size());
            assertEquals(1, result.getIllustrations().size());
            assertEquals(1, result.getDiagrams().size());
            assertEquals(1, result.getLogos().size());
        }

        @Test
        @DisplayName("部分收集器返回空不应阻塞流程")
        void concurrentWorkflow_partialEmptyShouldNotBlock() throws Exception {
            List<ImageResource> contentImages = List.of(
                    ImageResource.builder().category(ImageCategoryEnum.CONTENT).description("产品图").url("https://example.com/img.jpg").build()
            );
            CodeGenConcurrentWorkflow workflow = new CodeGenConcurrentWorkflow(
                    new ImagePlanNode(prompt ->
                            ImageCollectionPlan.builder()
                                    .contentQuery("产品图").illustrationQuery(null)
                                    .diagramQuery(null).logoPrompt("Logo").build()),
                    new ContentImageCollectorNode(query -> contentImages),
                    new IllustrationCollectorNode(query -> Collections.emptyList()),
                    new DiagramCollectorNode(query -> Collections.emptyList()),
                    new LogoCollectorNode(query -> Collections.emptyList()),
                    new ImageAggregatorNode()
            );
            WorkflowContext result = workflow.execute(12L, "部分空收集");
            assertEquals(1, result.getImageList().size());
            assertEquals(ImageCategoryEnum.CONTENT, result.getImageList().get(0).getCategory());
        }

        @Test
        @DisplayName("并发工作流 Mermaid 图验证")
        void concurrentWorkflow_shouldGenerateValidMermaidGraph() throws Exception {
            CodeGenConcurrentWorkflow workflow = createConcurrentWorkflowWithStubs();
            var compiled = workflow.createWorkflow();
            String mermaid = compiled.getGraph(org.bsc.langgraph4j.GraphRepresentation.Type.MERMAID).content();
            assertNotNull(mermaid);
            assertTrue(mermaid.contains("image_plan"));
            assertTrue(mermaid.contains("content_image_collector"));
            assertTrue(mermaid.contains("illustration_collector"));
            assertTrue(mermaid.contains("diagram_collector"));
            assertTrue(mermaid.contains("logo_collector"));
            assertTrue(mermaid.contains("image_aggregator"));
        }
    }

    @Nested
    @DisplayName("节点级 E2E 测试")
    class NodeE2E {

        @Test
        @DisplayName("RouterNode: '首页'关键词路由到 MULTI_FILE")
        void router_shouldRouteToMultiFileForHomepageKeyword() {
            RouterNode router = new RouterNode();
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L).enhancedPrompt("请生成一个企业首页，包含导航栏和轮播图")
                    .build();
            AgentState state = new AgentState(ctx.toStateUpdate());
            Map<String, Object> result = router.apply(state);
            WorkflowContext updated = WorkflowContext.fromState(new AgentState(result));
            assertEquals(CodeGenTypeEnum.MULTI_FILE, updated.getGenerationType());
        }

        @Test
        @DisplayName("RouterNode: 简单提示路由到 SINGLE_FILE")
        void router_shouldRouteToSingleFileForSimplePrompt() {
            RouterNode router = new RouterNode();
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L).enhancedPrompt("一个简单的按钮组件")
                    .build();
            AgentState state = new AgentState(ctx.toStateUpdate());
            Map<String, Object> result = router.apply(state);
            WorkflowContext updated = WorkflowContext.fromState(new AgentState(result));
            assertEquals(CodeGenTypeEnum.SINGLE_FILE, updated.getGenerationType());
        }

        @Test
        @DisplayName("CodeQualityCheckNode: 有效 MULTI_FILE 目录返回 valid 并路由到 skip_build")
        void qualityCheck_shouldReturnValidForMultiFileDir(@TempDir Path tempDir) throws IOException {
            Path testDir = Files.createDirectories(tempDir.resolve("quality-test-multi"));
            Files.writeString(testDir.resolve("index.html"), "<html></html>");
            Files.writeString(testDir.resolve("style.css"), "body{}");
            Files.writeString(testDir.resolve("script.js"), "console.log(1);");

            CodeQualityCheckNode node = new CodeQualityCheckNode();
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L)
                    .generationType(CodeGenTypeEnum.MULTI_FILE)
                    .generatedCodeDir(testDir.toAbsolutePath().toString())
                    .build();
            AgentState state = new AgentState(ctx.toStateUpdate());
            Map<String, Object> result = node.apply(state);
            WorkflowContext updated = WorkflowContext.fromState(new AgentState(result));
            assertNotNull(updated.getQualityResult());
            assertTrue(updated.getQualityResult().getIsValid());
            assertEquals(CodeQualityCheckNode.ROUTE_SKIP_BUILD, node.routeAfterCheck(new AgentState(result)));
        }

        @Test
        @DisplayName("CodeQualityCheckNode: 缺失文件返回 invalid 并路由到 retry")
        void qualityCheck_shouldReturnInvalidForMissingFiles(@TempDir Path tempDir) throws IOException {
            Path testDir = Files.createDirectories(tempDir.resolve("quality-test-missing"));
            Files.writeString(testDir.resolve("index.html"), "<html></html>");

            CodeQualityCheckNode node = new CodeQualityCheckNode();
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L)
                    .generationType(CodeGenTypeEnum.MULTI_FILE)
                    .generatedCodeDir(testDir.toAbsolutePath().toString())
                    .build();
            AgentState state = new AgentState(ctx.toStateUpdate());
            Map<String, Object> result = node.apply(state);
            WorkflowContext updated = WorkflowContext.fromState(new AgentState(result));
            assertNotNull(updated.getQualityResult());
            assertFalse(updated.getQualityResult().getIsValid());
            assertTrue(updated.getQualityResult().getErrors().stream()
                    .anyMatch(e -> e.contains("style.css") || e.contains("script.js")));
            assertEquals(CodeQualityCheckNode.ROUTE_RETRY, node.routeAfterCheck(new AgentState(result)));
        }

        @Test
        @DisplayName("CodeQualityCheckNode: 空目录路径返回 invalid")
        void qualityCheck_shouldReturnInvalidForEmptyDir() {
            CodeQualityCheckNode node = new CodeQualityCheckNode();
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L)
                    .generationType(CodeGenTypeEnum.SINGLE_FILE)
                    .generatedCodeDir("")
                    .build();
            AgentState state = new AgentState(ctx.toStateUpdate());
            Map<String, Object> result = node.apply(state);
            WorkflowContext updated = WorkflowContext.fromState(new AgentState(result));
            assertFalse(updated.getQualityResult().getIsValid());
        }

        @Test
        @DisplayName("PromptEnhancerNode: fallback 应正确增强提示")
        void promptEnhancer_shouldFallbackWhenNoService() {
            PromptEnhancerNode node = new PromptEnhancerNode();
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L)
                    .originalPrompt("做一个登录页面")
                    .imageListStr("[CONTENT] 登录背景图; [LOGO] 公司Logo")
                    .build();
            AgentState state = new AgentState(ctx.toStateUpdate());
            Map<String, Object> result = node.apply(state);
            WorkflowContext updated = WorkflowContext.fromState(new AgentState(result));
            assertNotNull(updated.getEnhancedPrompt());
            assertTrue(updated.getEnhancedPrompt().contains("做一个登录页面"));
            assertTrue(updated.getEnhancedPrompt().contains("登录背景图"));
        }

        @Test
        @DisplayName("CodeGeneratorNode: facade 为 null 时创建临时目录并生成文件")
        void codeGenerator_shouldFallbackWhenFacadeNull() throws IOException {
            CodeGeneratorNode node = new CodeGeneratorNode(null);
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(100L)
                    .enhancedPrompt("测试代码生成")
                    .generationType(CodeGenTypeEnum.SINGLE_FILE)
                    .build();
            AgentState state = new AgentState(ctx.toStateUpdate());
            Map<String, Object> result = node.apply(state);
            WorkflowContext updated = WorkflowContext.fromState(new AgentState(result));
            assertNotNull(updated.getGeneratedCodeDir());
            Path dir = Path.of(updated.getGeneratedCodeDir());
            assertTrue(Files.isDirectory(dir));
            assertTrue(Files.exists(dir.resolve("index.html")));
        }
    }

    @Nested
    @DisplayName("WorkflowContext 状态持久化 E2E 测试")
    class ContextPersistenceE2E {

        @Test
        @DisplayName("WorkflowContext 序列化后可从 AgentState 恢复")
        void contextShouldSurviveStateRoundTrip() {
            WorkflowContext original = WorkflowContext.builder()
                    .appId(1L)
                    .originalPrompt("做一个产品网站")
                    .imageListStr("[CONTENT] 产品图1; [ILLUSTRATION] 插画1")
                    .enhancedPrompt("增强后的提示")
                    .generationType(CodeGenTypeEnum.MULTI_FILE)
                    .generatedCodeDir("/tmp/generated-1")
                    .build();
            Map<String, Object> stateUpdate = original.toStateUpdate();
            AgentState state = new AgentState(stateUpdate);
            WorkflowContext restored = WorkflowContext.fromState(state);
            assertEquals(original.getAppId(), restored.getAppId());
            assertEquals(original.getOriginalPrompt(), restored.getOriginalPrompt());
            assertEquals(original.getImageListStr(), restored.getImageListStr());
            assertEquals(original.getEnhancedPrompt(), restored.getEnhancedPrompt());
            assertEquals(original.getGenerationType(), restored.getGenerationType());
            assertEquals(original.getGeneratedCodeDir(), restored.getGeneratedCodeDir());
        }

        @Test
        @DisplayName("WorkflowContext builder 默认值应正确初始化列表字段")
        void contextBuilderShouldInitializeDefaultCollections() {
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L)
                    .originalPrompt("默认值测试")
                    .build();
            assertNotNull(ctx.getImageList());
            assertTrue(ctx.getImageList().isEmpty());
            assertNotNull(ctx.getContentImages());
            assertNotNull(ctx.getIllustrations());
            assertNotNull(ctx.getDiagrams());
            assertNotNull(ctx.getLogos());
        }

        @Test
        @DisplayName("WorkflowContext advanceStep 应更新 currentStep")
        void contextAdvanceStepShouldUpdate() {
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L)
                    .originalPrompt("步骤测试")
                    .build();
            assertNull(ctx.getCurrentStep());
            ctx.advanceStep("image_collect");
            assertEquals("image_collect", ctx.getCurrentStep());
            ctx.advanceStep("prompt_enhancer");
            assertEquals("prompt_enhancer", ctx.getCurrentStep());
        }

        @Test
        @DisplayName("WorkflowContext addError 应记录错误信息")
        void contextAddErrorShouldRecordMessage() {
            WorkflowContext ctx = WorkflowContext.builder()
                    .appId(1L)
                    .originalPrompt("错误测试")
                    .build();
            assertNull(ctx.getErrorMessage());
            ctx.addError("生成文件失败");
            assertEquals("生成文件失败", ctx.getErrorMessage());
        }
    }

    @Nested
    @DisplayName("QualityResult 工厂方法 E2E 测试")
    class QualityResultE2E {

        @Test
        @DisplayName("QualityResult.valid() 返回有效空错误列表")
        void validFactoryShouldReturnValidResult() {
            QualityResult result = QualityResult.valid();
            assertTrue(result.getIsValid());
            assertTrue(result.getErrors().isEmpty());
            assertTrue(result.getSuggestions().isEmpty());
        }

        @Test
        @DisplayName("QualityResult.invalid() 包含错误列表")
        void invalidFactoryShouldContainErrors() {
            List<String> errors = List.of("缺少 style.css", "缺少 script.js");
            QualityResult result = QualityResult.invalid(errors);
            assertFalse(result.getIsValid());
            assertEquals(2, result.getErrors().size());
            assertTrue(result.getErrors().contains("缺少 style.css"));
        }

        @Test
        @DisplayName("QualityResult.invalidWithSuggestions() 包含错误和建议")
        void invalidWithSuggestionsShouldContainBoth() {
            List<String> errors = List.of("代码不完整");
            List<String> suggestions = List.of("建议增加样式文件");
            QualityResult result = QualityResult.invalidWithSuggestions(errors, suggestions);
            assertFalse(result.getIsValid());
            assertEquals(1, result.getErrors().size());
            assertEquals(1, result.getSuggestions().size());
        }
    }

    private CodeGenConcurrentWorkflow createConcurrentWorkflowWithStubs() {
        List<ImageResource> stubImages = List.of(
                ImageResource.builder().category(ImageCategoryEnum.CONTENT).description("测试图").url("https://example.com/stub.jpg").build()
        );
        return new CodeGenConcurrentWorkflow(
                new ImagePlanNode(prompt ->
                        ImageCollectionPlan.builder()
                                .contentQuery("产品图").illustrationQuery("插画")
                                .diagramQuery("架构图").logoPrompt("Logo").build()),
                new ContentImageCollectorNode(query -> stubImages),
                new IllustrationCollectorNode(query -> stubImages),
                new DiagramCollectorNode(query -> stubImages),
                new LogoCollectorNode(query -> stubImages),
                new ImageAggregatorNode()
        );
    }
}