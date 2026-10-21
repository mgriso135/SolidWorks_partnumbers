using System.Text.Json;
using PartCode.Connector;

var json = new JsonSerializerOptions { WriteIndented = true };

if (args.Length == 0 || args[0] is "-h" or "--help" or "help")
{
    Usage();
    return 0;
}

var options = PartCodeOptions.FromEnvironment();
if (string.IsNullOrWhiteSpace(options.ApiKey))
{
    Console.Error.WriteLine("PARTCODE_API_KEY is not set.");
    return 2;
}

var command = args[0].ToLowerInvariant();
var rest = args.Skip(1).ToArray();

try
{
    using var http = new HttpClient();
    var client = new PartCodeClient(http, options);

    switch (command)
    {
        case "rules":
            {
                var documentType = ReadOption(rest, "--document-type");
                var rules = await client.GetRulesAsync(documentType);
                Console.WriteLine(JsonSerializer.Serialize(rules, json));
                return 0;
            }
        case "preview":
        case "reserve":
            {
                var request = BuildGenerateRequest(rest);
                var result = command == "preview"
                    ? await client.PreviewAsync(request)
                    : await client.ReserveAsync(request);
                Console.WriteLine(JsonSerializer.Serialize(result, json));
                return 0;
            }
        case "lookup":
            {
                var code = ReadOption(rest, "--code");
                if (string.IsNullOrWhiteSpace(code))
                {
                    Console.Error.WriteLine("--code is required.");
                    return 2;
                }

                var result = await client.LookupAsync(code);
                Console.WriteLine(JsonSerializer.Serialize(result, json));
                return 0;
            }
        default:
            Console.Error.WriteLine("Unknown command: " + command);
            Usage();
            return 2;
    }
}
catch (PartCodeApiException error)
{
    Console.Error.WriteLine($"{error.Code} ({error.StatusCode}): {error.Message}");
    foreach (var field in error.Fields)
    {
        Console.Error.WriteLine($"  {field.Key}: {field.Value}");
    }

    return 3;
}
catch (Exception error)
{
    Console.Error.WriteLine(error.Message);
    return 1;
}

static GenerateRequest BuildGenerateRequest(string[] args)
{
    var rule = ReadOption(args, "--rule");
    if (string.IsNullOrWhiteSpace(rule))
    {
        throw new ArgumentException("--rule is required.");
    }

    var request = new GenerateRequest
    {
        RuleKey = rule,
        Source = ReadOption(args, "--source") ?? "pdm",
        ExternalRef = ReadOption(args, "--external-ref"),
        Notes = ReadOption(args, "--notes"),
    };

    foreach (var value in ReadOptions(args, "--value"))
    {
        var separator = value.IndexOf('=');
        if (separator <= 0)
        {
            throw new ArgumentException("--value must use KEY=VALUE.");
        }

        request.Values[value.Substring(0, separator)] = value.Substring(separator + 1);
    }

    foreach (var value in ReadOptions(args, "--metadata"))
    {
        var separator = value.IndexOf('=');
        if (separator <= 0)
        {
            throw new ArgumentException("--metadata must use KEY=VALUE.");
        }

        request.Metadata[value.Substring(0, separator)] = value.Substring(separator + 1);
    }

    return request;
}

static string? ReadOption(string[] args, string name)
{
    for (var index = 0; index < args.Length; index++)
    {
        if (args[index] == name && index + 1 < args.Length)
        {
            return args[index + 1];
        }
    }

    return null;
}

static IEnumerable<string> ReadOptions(string[] args, string name)
{
    for (var index = 0; index < args.Length; index++)
    {
        if (args[index] == name && index + 1 < args.Length)
        {
            yield return args[index + 1];
        }
    }
}

static void Usage()
{
    Console.WriteLine(
        """
        partcode-pdm - PartCode connector CLI and PDM simulator

        Environment:
          PARTCODE_URL      PartCode base URL (default http://localhost:8000)
          PARTCODE_API_KEY  API key created in PartCode

        Commands:
          rules   [--document-type TYPE]
          preview --rule KEY [--value KEY=VALUE]... [--external-ref REF]
          reserve --rule KEY [--value KEY=VALUE]... [--external-ref REF]
                  [--metadata KEY=VALUE]... [--source SOURCE] [--notes TEXT]
          lookup  --code CODE

        Examples:
          partcode-pdm rules --document-type part
          partcode-pdm preview --rule mechanical-part --value family=MEC
          partcode-pdm reserve --rule mechanical-part --value family=MEC \
              --external-ref PDM:12345 --metadata description="Bracket"
        """);
}
