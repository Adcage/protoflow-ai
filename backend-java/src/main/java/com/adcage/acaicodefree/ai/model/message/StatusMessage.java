package com.adcage.acaicodefree.ai.model.message;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class StatusMessage extends StreamMessage {

    private String message;

    private String agentName;

    public StatusMessage(String message, String agentName) {
        super(StreamMessageTypeEnum.STATUS.getValue());
        this.message = message;
        this.agentName = agentName;
    }
}
