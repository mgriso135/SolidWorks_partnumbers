using System.Net;
using System.Text;
using System.Text.Json;
using PartCode.Connector;
using Xunit;

namespace PartCode.Connector.Tests;

public sealed class PartCodeClientTests
{
    private const string ApiKey = "pk_live_test";

    [Fact]
    public async Task Reserve_sends_api_key_and_payload()
    {
        var handler = new RecordingHandler(_ => Json(HttpStatusCode.OK, new
        {
            code = "PRT-MEC-00001",
            rule_key = "mechanical-part",
            rule_version = 1,
            item_id = "abc",
            status = "reserved",
            segments = Array.Empty<object>(),
        }));
        var client = CreateClient(handler);
        var request = new GenerateRequest
        {
            RuleKey = "mechanical-part",
            Values = new Dictionary<string, string> { ["family"] = "MEC" },
            ExternalRef = "PDM:42",
            Metadata = new Dictionary<string, object?> { ["description"] = "Bracket" },
        };

        var result = await client.ReserveAsync(request);

        Assert.Equal("PRT-MEC-00001", result.Code);
        Assert.Equal("reserved", result.Status);
        Assert.Equal(HttpMethod.Post, handler.LastRequest!.Method);
        Assert.Equal("/api/integrations/pdm/reserve", handler.LastRequest.RequestUri!.AbsolutePath);
        Assert.Equal(ApiKey, string.Join(",", handler.LastRequest.Headers.GetValues("X-API-Key")));

        using var body = JsonDocument.Parse(handler.LastBody!);
        Assert.Equal("mechanical-part", body.RootElement.GetProperty("rule_key").GetString());
        Assert.Equal("PDM:42", body.RootElement.GetProperty("external_ref").GetString());
        Assert.Equal("MEC", body.RootElement.GetProperty("values").GetProperty("family").GetString());
    }

    [Fact]
    public async Task Lookup_escapes_code()
    {
        var handler = new RecordingHandler(_ => Json(HttpStatusCode.OK, new
        {
            exists = false,
            item = (object?)null,
        }));
        var client = CreateClient(handler);

        var result = await client.LookupAsync("PRT MEC/1");

        Assert.False(result.Exists);
        Assert.Equal(
            "/api/integrations/pdm/lookup?code=PRT%20MEC%2F1",
            handler.LastRequest!.RequestUri!.PathAndQuery);
    }

    [Fact]
    public async Task Rules_passes_document_type_filter()
    {
        var handler = new RecordingHandler(_ => Json(HttpStatusCode.OK, Array.Empty<object>()));
        var client = CreateClient(handler);

        var rules = await client.GetRulesAsync("part");

        Assert.Empty(rules);
        Assert.Equal("?document_type=part", handler.LastRequest!.RequestUri!.Query);
    }

    [Fact]
    public async Task Error_parses_structured_generation_error()
    {
        var handler = new RecordingHandler(_ => Json(HttpStatusCode.UnprocessableEntity, new
        {
            detail = new
            {
                code = "INVALID_INPUT",
                message = "Some fields are invalid",
                fields = new Dictionary<string, string> { ["family"] = "Must be one of: MEC, ELE" },
            },
        }));
        var client = CreateClient(handler);

        var error = await Assert.ThrowsAsync<PartCodeApiException>(
            () => client.PreviewAsync(new GenerateRequest { RuleKey = "mechanical-part" }));

        Assert.Equal(422, error.StatusCode);
        Assert.Equal("INVALID_INPUT", error.Code);
        Assert.Equal("Some fields are invalid", error.Message);
        Assert.Equal("Must be one of: MEC, ELE", error.Fields["family"]);
    }

    private static PartCodeClient CreateClient(HttpMessageHandler handler)
    {
        var http = new HttpClient(handler) { BaseAddress = new Uri("http://partcode.test/") };
        return new PartCodeClient(http, new PartCodeOptions
        {
            BaseUrl = "http://partcode.test",
            ApiKey = ApiKey,
        });
    }

    private static HttpResponseMessage Json(HttpStatusCode status, object payload)
    {
        return new HttpResponseMessage(status)
        {
            Content = new StringContent(
                JsonSerializer.Serialize(payload),
                Encoding.UTF8,
                "application/json"),
        };
    }

    private sealed class RecordingHandler : HttpMessageHandler
    {
        private readonly Func<HttpRequestMessage, HttpResponseMessage> _responder;

        public RecordingHandler(Func<HttpRequestMessage, HttpResponseMessage> responder)
        {
            _responder = responder;
        }

        public HttpRequestMessage? LastRequest { get; private set; }
        public string? LastBody { get; private set; }

        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request,
            CancellationToken cancellationToken)
        {
            LastRequest = request;
            LastBody = request.Content == null
                ? null
                : await request.Content.ReadAsStringAsync(cancellationToken);
            return _responder(request);
        }
    }
}
