using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using PartCode.Connector;

namespace PartCode.PdmAddIn;

public sealed class ConnectorSettings : PdmSettings
{
    private static readonly byte[] Entropy = Encoding.UTF8.GetBytes("PartCode.PdmAddIn.v1");

    public string GetApiKey()
    {
        if (!string.IsNullOrWhiteSpace(ApiKey))
        {
            return ApiKey;
        }

        if (string.IsNullOrWhiteSpace(ApiKeyProtected))
        {
            return string.Empty;
        }

        var bytes = ProtectedData.Unprotect(
            Convert.FromBase64String(ApiKeyProtected),
            Entropy,
            DataProtectionScope.LocalMachine);
        return Encoding.UTF8.GetString(bytes);
    }

    public static ConnectorSettings Load()
    {
        foreach (var path in CandidatePaths())
        {
            if (!File.Exists(path))
            {
                continue;
            }

            var json = File.ReadAllText(path);
            var settings = JsonSerializer.Deserialize<ConnectorSettings>(
                json,
                new JsonSerializerOptions { PropertyNameCaseInsensitive = true });
            if (settings == null)
            {
                throw new InvalidOperationException("PartCode settings file is empty: " + path);
            }

            return settings;
        }

        throw new FileNotFoundException(
            "PartCode connector settings not found. Run installer/Install-PartCodePdmAddIn.ps1 " +
            "or create %ProgramData%\\PartCode\\pdm-connector.json.");
    }

    private static IEnumerable<string> CandidatePaths()
    {
        var configured = Environment.GetEnvironmentVariable("PARTCODE_PDM_CONFIG");
        if (!string.IsNullOrWhiteSpace(configured))
        {
            yield return configured;
        }

        var programData = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
        if (!string.IsNullOrWhiteSpace(programData))
        {
            yield return Path.Combine(programData, "PartCode", "pdm-connector.json");
        }

        var local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (!string.IsNullOrWhiteSpace(local))
        {
            yield return Path.Combine(local, "PartCode", "pdm-connector.json");
        }
    }
}
