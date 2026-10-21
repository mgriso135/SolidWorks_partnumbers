using System;
using System.Collections.Generic;
using System.Globalization;
using EPDM.Interop.epdm;

namespace PartCode.PdmAddIn;

public sealed class PdmContext
{
    public PdmContext(
        string path,
        string externalReference,
        Dictionary<string, string> values,
        Dictionary<string, object?> metadata,
        IEdmEnumeratorVariable5 variables)
    {
        Path = path;
        ExternalReference = externalReference;
        Values = values;
        Metadata = metadata;
        Variables = variables;
    }

    public string Path { get; }
    public string ExternalReference { get; }
    public Dictionary<string, string> Values { get; }
    public Dictionary<string, object?> Metadata { get; }
    public IEdmEnumeratorVariable5 Variables { get; }

    public static PdmContext Read(
        IEdmVault5 vault,
        string path,
        ConnectorSettings settings)
    {
        IEdmFolder5 folder;
        var file = vault.GetFileFromPath(path, out folder);
        if (file == null)
        {
            throw new InvalidOperationException("PDM file not found: " + path);
        }

        var variables = file.GetEnumeratorVariable();
        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var metadata = new Dictionary<string, object?>
        {
            ["pdm_path"] = path,
            ["pdm_file_id"] = file.ID.ToString(CultureInfo.InvariantCulture),
            ["pdm_file_name"] = file.Name,
            ["pdm_vault"] = vault.Name,
        };

        if (settings.SourceVariables != null)
        {
            foreach (var mapping in settings.SourceVariables)
            {
                var value = ReadVariable(variables, mapping.Key);
                if (string.IsNullOrWhiteSpace(value))
                {
                    continue;
                }

                values[mapping.Key] = value!;
                values[mapping.Value] = value!;
                metadata[mapping.Value] = value;
            }
        }

        var externalReference = "PDM:" + vault.Name + ":" + file.ID.ToString(CultureInfo.InvariantCulture);
        return new PdmContext(path, externalReference, values, metadata, variables);
    }

    public static void WriteCode(IEdmEnumeratorVariable5 variables, string variableName, string code)
    {
        object value = code;
        variables.SetVar(variableName, "@", ref value);
        variables.Flush();
    }

    private static string? ReadVariable(IEdmEnumeratorVariable5 variables, string name)
    {
        object value;
        if (!variables.GetVar(name, "@", out value) || value == null)
        {
            return null;
        }

        return Convert.ToString(value, CultureInfo.InvariantCulture);
    }
}
