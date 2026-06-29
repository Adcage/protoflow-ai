package com.adcage.acaicodefree.model.dto.app;

import com.adcage.acaicodefree.common.PageRequest;
import lombok.Data;
import lombok.EqualsAndHashCode;

@Data
@EqualsAndHashCode(callSuper = true)
public class MarketplaceQueryRequest extends PageRequest {

    /**
     * 分类筛选
     */
    private String category;

    /**
     * 排序字段：latest / popular
     */
    private String sortField;
}
