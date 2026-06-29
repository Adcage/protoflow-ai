package com.adcage.acaicodefree.ai.model.message;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@EqualsAndHashCode(callSuper = true)
public class AiResponseMessage extends StreamMessage {

    private String data;

    private String agentName;

    public AiResponseMessage(String data, String agentName) {
        super(StreamMessageTypeEnum.AI_RESPONSE.getValue());
        this.data = data;
        this.agentName = agentName;
    }
}
