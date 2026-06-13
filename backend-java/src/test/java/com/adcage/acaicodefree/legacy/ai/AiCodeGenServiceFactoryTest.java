package com.adcage.acaicodefree.legacy.ai;

import com.adcage.acaicodefree.legacy.core.memory.ChatMemoryLoader;
import com.adcage.acaicodefree.model.enums.CodeGenTypeEnum;
import dev.langchain4j.memory.ChatMemory;
import dev.langchain4j.model.chat.StreamingChatLanguageModel;
import org.springframework.beans.factory.ObjectProvider;
import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.mockito.Mockito;
import org.springframework.test.util.ReflectionTestUtils;

class AiCodeGenServiceFactoryTest {

    @Test
    void shouldCacheServiceByAppIdAndCodeGenType() {
        TestFactory factory = new TestFactory();

        AiCodeGeneratorService first = factory.getService(1L, CodeGenTypeEnum.VUE_PROJECT);
        AiCodeGeneratorService second = factory.getService(1L, CodeGenTypeEnum.VUE_PROJECT);
        AiCodeGeneratorService third = factory.getService(2L, CodeGenTypeEnum.VUE_PROJECT);

        Assertions.assertSame(first, second);
        Assertions.assertNotSame(first, third);
        Assertions.assertEquals(2, factory.createCount);
    }

    @Test
    void shouldBuildToolServiceForVueProject() {
        TestFactory factory = new TestFactory();

        factory.getService(1L, CodeGenTypeEnum.VUE_PROJECT);

        Assertions.assertEquals(1, factory.vueCreateCount);
    }

    @Test
    void shouldBuildToolServiceForSingleFile() {
        TestFactory factory = new TestFactory();

        factory.getService(1L, CodeGenTypeEnum.SINGLE_FILE);

        Assertions.assertEquals(0, factory.vueCreateCount);
        Assertions.assertEquals(1, factory.legacyCreateCount);
    }

    @Test
    void shouldBuildToolServiceForMultiFile() {
        TestFactory factory = new TestFactory();

        factory.getService(1L, CodeGenTypeEnum.MULTI_FILE);

        Assertions.assertEquals(0, factory.vueCreateCount);
        Assertions.assertEquals(1, factory.legacyCreateCount);
    }

    @Test
    void shouldFallbackToInMemoryChatMemoryWhenLoaderIsUnavailable() {
        TestFactory factory = new TestFactory(new EmptyObjectProvider<ChatMemoryLoader>());

        ChatMemory chatMemory = factory.resolveChatMemory(1L, 1L);

        Assertions.assertNotNull(chatMemory);
    }

    @Test
    void shouldUseProvidedLoaderWhenAvailable() {
        ChatMemoryLoaderStub loaderStub = new ChatMemoryLoaderStub();
        TestFactory factory = new TestFactory(new SingleObjectProvider<>(loaderStub));

        factory.resolveChatMemory(123L, 456L);

        Assertions.assertEquals(123L, loaderStub.lastAppId);
    }

    private static class TestFactory extends AiCodeGenServiceFactory {

        private int createCount;
        private int vueCreateCount;
        private int legacyCreateCount;

        private TestFactory() {
            this(new EmptyObjectProvider<>());
        }

        private TestFactory(ObjectProvider<ChatMemoryLoader> chatMemoryLoaderProvider) {
            ReflectionTestUtils.setField(this, "chatMemoryLoaderProvider", chatMemoryLoaderProvider);
            ReflectionTestUtils.setField(this, "memoryWindowSize", 20);
            ReflectionTestUtils.setField(this, "legacyStreamingChatLanguageModel", Mockito.mock(StreamingChatLanguageModel.class));
            ReflectionTestUtils.setField(this, "reasoningStreamingChatModel", Mockito.mock(StreamingChatLanguageModel.class));
        }

        @Override
        protected AiCodeGeneratorService createToolService(Long appId, StreamingChatLanguageModel streamingChatLanguageModel) {
            createCount++;
            StreamingChatLanguageModel reasoningModel = (StreamingChatLanguageModel) ReflectionTestUtils
                    .getField(this, "reasoningStreamingChatModel");
            if (streamingChatLanguageModel == reasoningModel) {
                vueCreateCount++;
            } else {
                legacyCreateCount++;
            }
            return Mockito.mock(AiCodeGeneratorService.class);
        }
    }

    private static class EmptyObjectProvider<T> implements ObjectProvider<T> {

        @Override
        public T getObject(Object... args) {
            throw new UnsupportedOperationException();
        }

        @Override
        public T getIfAvailable() {
            return null;
        }

        @Override
        public T getObject() {
            throw new UnsupportedOperationException();
        }
    }

    private static class SingleObjectProvider<T> extends EmptyObjectProvider<T> {

        private final T value;

        private SingleObjectProvider(T value) {
            this.value = value;
        }

        @Override
        public T getIfAvailable() {
            return value;
        }
    }

    private static class ChatMemoryLoaderStub extends ChatMemoryLoader {

        private Long lastAppId;

        @Override
        public ChatMemory load(Long appId) {
            lastAppId = appId;
            return dev.langchain4j.memory.chat.MessageWindowChatMemory.withMaxMessages(20);
        }
    }
}
