package com.adcage.acaicodefree.constant;

import java.util.Map;

public interface StyleTemplateConstant {

    String MINIMAL = "minimal";
    String BUSINESS = "business";
    String TECH = "tech";
    String PLAYFUL = "playful";
    String DARK = "dark";

    Map<String, String> STYLE_DESCRIPTIONS = Map.of(
            MINIMAL, "极简风格：简洁布局、大量留白、黑白灰配色",
            BUSINESS, "商务风格：专业配色、清晰层级、数据驱动",
            TECH, "科技风格：深色背景、霓虹强调、动态元素",
            PLAYFUL, "活泼风格：明亮色彩、圆润元素、趣味交互",
            DARK, "暗黑风格：深色主题、高对比度、沉浸体验"
    );
}
