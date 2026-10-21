using System;
using System.Collections.Generic;

namespace PartCode.Connector;

public sealed class PartCodeApiException : Exception
{
    public PartCodeApiException(
        int statusCode,
        string code,
        string message,
        string responseBody,
        IReadOnlyDictionary<string, string>? fields = null)
        : base(message)
    {
        StatusCode = statusCode;
        Code = code;
        ResponseBody = responseBody;
        Fields = fields ?? new Dictionary<string, string>();
    }

    public int StatusCode { get; }
    public string Code { get; }
    public string ResponseBody { get; }
    public IReadOnlyDictionary<string, string> Fields { get; }
}
