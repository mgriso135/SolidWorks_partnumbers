using System;

namespace PartCode.Connector;

public sealed class PartCodeOptions
{
    public string BaseUrl { get; set; } = "http://localhost:8000";
    public string ApiKey { get; set; } = string.Empty;

    public static PartCodeOptions FromEnvironment()
    {
        return new PartCodeOptions
        {
            BaseUrl = Environment.GetEnvironmentVariable("PARTCODE_URL") ?? "http://localhost:8000",
            ApiKey = Environment.GetEnvironmentVariable("PARTCODE_API_KEY") ?? string.Empty,
        };
    }

    internal Uri GetBaseUri()
    {
        if (string.IsNullOrWhiteSpace(BaseUrl))
        {
            throw new InvalidOperationException("PartCode BaseUrl is not configured.");
        }

        var value = BaseUrl.Trim();
        if (!value.EndsWith("/", StringComparison.Ordinal))
        {
            value += "/";
        }

        return new Uri(value, UriKind.Absolute);
    }

    internal void Validate()
    {
        if (string.IsNullOrWhiteSpace(ApiKey))
        {
            throw new InvalidOperationException("PartCode API key is not configured.");
        }
    }
}
