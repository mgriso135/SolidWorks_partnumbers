using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace PartCode.Connector;

public sealed class PartCodeRule
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("key")]
    public string Key { get; set; } = string.Empty;

    [JsonPropertyName("name")]
    public string Name { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("document_type")]
    public string DocumentType { get; set; } = string.Empty;

    [JsonPropertyName("version")]
    public int Version { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("definition")]
    public RuleDefinition Definition { get; set; } = new RuleDefinition();
}

public sealed class RuleDefinition
{
    [JsonPropertyName("segments")]
    public List<RuleSegment> Segments { get; set; } = new List<RuleSegment>();

    [JsonPropertyName("max_length")]
    public int MaxLength { get; set; }

    [JsonPropertyName("case")]
    public string Case { get; set; } = "upper";
}

public sealed class RuleSegment
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("key")]
    public string? Key { get; set; }

    [JsonPropertyName("label")]
    public string? Label { get; set; }

    [JsonPropertyName("value")]
    public string? Value { get; set; }

    [JsonPropertyName("required")]
    public bool? Required { get; set; }

    [JsonPropertyName("options")]
    public List<ListOption>? Options { get; set; }

    [JsonPropertyName("min_length")]
    public int? MinLength { get; set; }

    [JsonPropertyName("max_length")]
    public int? MaxLength { get; set; }

    [JsonPropertyName("regex")]
    public string? Regex { get; set; }

    [JsonPropertyName("padding")]
    public int? Padding { get; set; }

    [JsonPropertyName("start")]
    public int? Start { get; set; }

    [JsonPropertyName("step")]
    public int? Step { get; set; }

    [JsonPropertyName("scope")]
    public string? Scope { get; set; }

    [JsonPropertyName("scope_keys")]
    public List<string>? ScopeKeys { get; set; }

    [JsonPropertyName("format")]
    public string? Format { get; set; }

    [JsonPropertyName("algorithm")]
    public string? Algorithm { get; set; }
}

public sealed class ListOption
{
    [JsonPropertyName("value")]
    public string Value { get; set; } = string.Empty;

    [JsonPropertyName("label")]
    public string? Label { get; set; }
}

public sealed class GenerateRequest
{
    [JsonPropertyName("rule_key")]
    public string RuleKey { get; set; } = string.Empty;

    [JsonPropertyName("values")]
    public Dictionary<string, string> Values { get; set; } = new Dictionary<string, string>();

    [JsonPropertyName("source")]
    public string Source { get; set; } = "pdm";

    [JsonPropertyName("external_ref")]
    public string? ExternalRef { get; set; }

    [JsonPropertyName("metadata")]
    public Dictionary<string, object?> Metadata { get; set; } = new Dictionary<string, object?>();

    [JsonPropertyName("notes")]
    public string? Notes { get; set; }
}

public sealed class GenerateResult
{
    [JsonPropertyName("code")]
    public string Code { get; set; } = string.Empty;

    [JsonPropertyName("rule_key")]
    public string RuleKey { get; set; } = string.Empty;

    [JsonPropertyName("rule_version")]
    public int RuleVersion { get; set; }

    [JsonPropertyName("item_id")]
    public string? ItemId { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("segments")]
    public List<GeneratedSegment> Segments { get; set; } = new List<GeneratedSegment>();

    [JsonPropertyName("created_at")]
    public DateTimeOffset? CreatedAt { get; set; }
}

public sealed class GeneratedSegment
{
    [JsonPropertyName("type")]
    public string Type { get; set; } = string.Empty;

    [JsonPropertyName("key")]
    public string? Key { get; set; }

    [JsonPropertyName("value")]
    public string Value { get; set; } = string.Empty;
}

public sealed class LookupResult
{
    [JsonPropertyName("exists")]
    public bool Exists { get; set; }

    [JsonPropertyName("item")]
    public PartCodeItem? Item { get; set; }
}

public sealed class PartCodeItem
{
    [JsonPropertyName("id")]
    public string Id { get; set; } = string.Empty;

    [JsonPropertyName("code")]
    public string Code { get; set; } = string.Empty;

    [JsonPropertyName("rule_key")]
    public string RuleKey { get; set; } = string.Empty;

    [JsonPropertyName("rule_version")]
    public int RuleVersion { get; set; }

    [JsonPropertyName("status")]
    public string Status { get; set; } = string.Empty;

    [JsonPropertyName("source")]
    public string Source { get; set; } = string.Empty;

    [JsonPropertyName("external_ref")]
    public string? ExternalRef { get; set; }

    [JsonPropertyName("payload")]
    public Dictionary<string, object?> Payload { get; set; } = new Dictionary<string, object?>();

    [JsonPropertyName("created_at")]
    public DateTimeOffset? CreatedAt { get; set; }
}
