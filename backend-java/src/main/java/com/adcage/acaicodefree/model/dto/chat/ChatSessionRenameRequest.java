package com.adcage.acaicodefree.model.dto.chat;

import lombok.Data;

import java.io.Serializable;

@Data
public class ChatSessionRenameRequest implements Serializable {

    private Long sessionId;

    private String title;

    private static final long serialVersionUID = 1L;
}
