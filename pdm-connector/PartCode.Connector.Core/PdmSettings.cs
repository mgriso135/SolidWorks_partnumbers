using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace PartCode.Connector;

public class PdmSettings
{
    [JsonPropertyName("baseUrl")]
    public string BaseUrl { get; set; } = "http://localhost:8000";

    [JsonPropertyName("apiKey")]
    public string ApiKey { get; set; } = string.Empty;

    [JsonPropertyName("apiKeyProtected")]
    public string ApiKeyProtected { get; set; } = string.Empty;

    [JsonPropertyName("documentType")]
    public string DocumentType { get; set; } = "part";

    [JsonPropertyName("targetVariable")]
    public string TargetVariable { get; set; } = "PartNumber";

    [JsonPropertyName("sourceVariables")]
    public Dictionary<string, string> SourceVariables { get; set; } = new Dictionary<string, string>
    {
        ["Description"] = "description",
        ["Material"] = "material",
        ["Family"] = "family",
    };
}
