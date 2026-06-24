-- Phase 6: 新增 generationMode 列，从 codeGenType 回填
-- 本脚本在 proto/Java/前端全链路迁移完成前执行
-- codeGenType 列暂不删除，待全链路验证后再物理删除

ALTER TABLE app ADD COLUMN generationMode VARCHAR(64) DEFAULT NULL COMMENT '生成模式（application/presentation/prototype/diagram）';

-- 回填现有记录：所有合法 codeGenType 对应 application
UPDATE app SET generationMode = 'application' WHERE codeGenType IN ('single_file', 'multi-file', 'vue_project');

-- 验证：检查是否存在无法映射的旧类型
-- SELECT id, codeGenType FROM app WHERE generationMode IS NULL AND codeGenType IS NOT NULL;
-- 如有结果，需人工审核后决定映射方式，不得默认映射为 application
