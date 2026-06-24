package com.adcage.acaicodefree.model.vo.app;

import lombok.Data;

import java.io.Serializable;
import java.util.List;

@Data
public class ArtifactManifestVO implements Serializable {

    private static final long serialVersionUID = 1L;

    private String version;

    private String generationMode;

    private String artifactFormat;

    private String entry;

    private List<String> supportingFiles;

    private String status;
}
