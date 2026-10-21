using System;
using System.Collections.Generic;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;

namespace PartCode.Connector;

public sealed class PartCodeClient
{
    private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions
    {
        PropertyNameCaseInsensitive = true,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private readonly HttpClient _http;
    private readonly PartCodeOptions _options;

    public PartCodeClient(HttpClient httpClient, PartCodeOptions options)
    {
        _http = httpClient ?? throw new ArgumentNullException(nameof(httpClient));
        _options = options ?? throw new ArgumentNullException(nameof(options));
        _options.Validate();

        if (_http.BaseAddress == null)
        {
            _http.BaseAddress = _options.GetBaseUri();
        }
    }

    public Task<List<PartCodeRule>> GetRulesAsync(
        string? documentType = null,
        CancellationToken cancellationToken = default)
    {
        var path = "api/integrations/pdm/rules";
        if (!string.IsNullOrWhiteSpace(documentType))
        {
            path += "?document_type=" + Uri.EscapeDataString(documentType);
        }

        return SendAsync<List<PartCodeRule>>(HttpMethod.Get, path, null, cancellationToken);
    }

    public Task<GenerateResult> PreviewAsync(
        GenerateRequest request,
        CancellationToken cancellationToken = default)
    {
        return SendAsync<GenerateResult>(
            HttpMethod.Post,
            "api/integrations/pdm/preview",
            request,
            cancellationToken);
    }

    public Task<GenerateResult> ReserveAsync(
        GenerateRequest request,
        CancellationToken cancellationToken = default)
    {
        return SendAsync<GenerateResult>(
            HttpMethod.Post,
            "api/integrations/pdm/reserve",
            request,
            cancellationToken);
    }

    public Task<LookupResult> LookupAsync(
        string code,
        CancellationToken cancellationToken = default)
    {
        var path = "api/integrations/pdm/lookup?code=" + Uri.EscapeDataString(code);
        return SendAsync<LookupResult>(HttpMethod.Get, path, null, cancellationToken);
    }

    private async Task<T> SendAsync<T>(
        HttpMethod method,
        string path,
        object? body,
        CancellationToken cancellationToken)
    {
        using (var request = new HttpRequestMessage(method, path))
        {
            request.Headers.Accept.Add(new MediaTypeWithQualityHeaderValue("application/json"));
            request.Headers.TryAddWithoutValidation("X-API-Key", _options.ApiKey);

            if (body != null)
            {
                var json = JsonSerializer.Serialize(body, JsonOptions);
                request.Content = new StringContent(json, Encoding.UTF8, "application/json");
            }

            using (var response = await _http.SendAsync(request, cancellationToken).ConfigureAwait(false))
            {
                var payload = await response.Content.ReadAsStringAsync().ConfigureAwait(false);

                if (!response.IsSuccessStatusCode)
                {
                    throw BuildException((int)response.StatusCode, payload);
                }

                var result = JsonSerializer.Deserialize<T>(payload, JsonOptions);
                if (result == null)
                {
                    throw new InvalidOperationException("PartCode returned an empty response.");
                }

                return result;
            }
        }
    }

    private static PartCodeApiException BuildException(int statusCode, string payload)
    {
        var code = "HTTP_" + statusCode;
        var message = "PartCode request failed with HTTP " + statusCode + ".";
        var fields = new Dictionary<string, string>();

        try
        {
            using (var document = JsonDocument.Parse(payload))
            {
                JsonElement detail;
                if (!document.RootElement.TryGetProperty("detail", out detail))
                {
                    return new PartCodeApiException(statusCode, code, message, payload);
                }

                if (detail.ValueKind == JsonValueKind.String)
                {
                    message = detail.GetString() ?? message;
                }
                else if (detail.ValueKind == JsonValueKind.Object)
                {
                    JsonElement property;
                    if (detail.TryGetProperty("code", out property) && property.ValueKind == JsonValueKind.String)
                    {
                        code = property.GetString() ?? code;
                    }

                    if (detail.TryGetProperty("message", out property) && property.ValueKind == JsonValueKind.String)
                    {
                        message = property.GetString() ?? message;
                    }

                    if (detail.TryGetProperty("fields", out property) && property.ValueKind == JsonValueKind.Object)
                    {
                        foreach (var field in property.EnumerateObject())
                        {
                            fields[field.Name] = field.Value.ValueKind == JsonValueKind.String
                                ? field.Value.GetString() ?? string.Empty
                                : field.Value.ToString();
                        }
                    }
                }
                else if (detail.ValueKind == JsonValueKind.Array)
                {
                    message = "PartCode rejected the request because one or more fields are invalid.";
                }
            }
        }
        catch (JsonException)
        {
            // Keep the generic HTTP message when the response is not JSON.
        }

        return new PartCodeApiException(statusCode, code, message, payload, fields);
    }
}
