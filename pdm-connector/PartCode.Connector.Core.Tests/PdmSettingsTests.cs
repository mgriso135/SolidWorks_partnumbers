using System.Text.Json;
using PartCode.Connector;
using Xunit;

namespace PartCode.Connector.Tests;

public sealed class PdmSettingsTests
{
    [Fact]
    public void Parses_installer_camel_case_settings()
    {
        const string json = """
        {
          "baseUrl": "https://partcode.example.com",
          "apiKeyProtected": "AQID",
          "documentType": "drawing",
          "targetVariable": "Code",
          "sourceVariables": { "PartName": "description" }
        }
        """;

        var settings = JsonSerializer.Deserialize<PdmSettings>(
            json,
            new JsonSerializerOptions { PropertyNameCaseInsensitive = true });

        Assert.NotNull(settings);
        Assert.Equal("https://partcode.example.com", settings!.BaseUrl);
        Assert.Equal("AQID", settings.ApiKeyProtected);
        Assert.Equal("drawing", settings.DocumentType);
        Assert.Equal("Code", settings.TargetVariable);
        Assert.Equal("description", settings.SourceVariables["PartName"]);
    }

    [Fact]
    public void Uses_defaults_when_optional_fields_are_missing()
    {
        var settings = JsonSerializer.Deserialize<PdmSettings>("{}");

        Assert.NotNull(settings);
        Assert.Equal("http://localhost:8000", settings!.BaseUrl);
        Assert.Equal("part", settings.DocumentType);
        Assert.Equal("PartNumber", settings.TargetVariable);
        Assert.Equal("family", settings.SourceVariables["Family"]);
    }
}
