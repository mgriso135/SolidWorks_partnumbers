using System;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;
using EPDM.Interop.epdm;
using PartCode.Connector;

namespace PartCode.PdmAddIn;

[Guid("0661068E-3935-456F-A478-1EA95636D7EB")]
[ProgId("PartCode.PdmAddIn")]
[ClassInterface(ClassInterfaceType.None)]
[ComVisible(true)]
public sealed class PartCodeAddIn : IEdmAddIn5
{
    private const int CommandId = 1;

    public void GetAddInInfo(
        ref EdmAddInInfo poInfo,
        IEdmVault5 poVault,
        IEdmCmdMgr5 poCmdMgr)
    {
        poInfo.mbsAddInName = "PartCode";
        poInfo.mbsCompany = "PartCode";
        poInfo.mbsDescription = "Assign a centrally managed PartCode number to a PDM file.";
        poInfo.mlAddInVersion = 1;
        poInfo.mlRequiredVersionMajor = 6;
        poInfo.mlRequiredVersionMinor = 4;

        var flags = EdmMenuFlags.EdmMenu_MustHaveSelection
            | EdmMenuFlags.EdmMenu_OnlyFiles
            | EdmMenuFlags.EdmMenu_OnlySingleSelection;

        poCmdMgr.AddCmd(
            CommandId,
            "PartCode: assign code...",
            (int)flags,
            "Generate and write a PartCode number to this file");
    }

    public void OnCmd(ref EdmCmd poCmd, ref EdmCmdData[] ppoData)
    {
        try
        {
            if (poCmd.meCmdType != EdmCmdType.EdmCmd_Menu || poCmd.mlCmdID != CommandId)
            {
                return;
            }

            if (ppoData == null || ppoData.Length == 0)
            {
                Show("Select a single file in the vault first.");
                return;
            }

            var path = ppoData[0].mbsStrData1;
            if (string.IsNullOrWhiteSpace(path))
            {
                path = ppoData[0].mbsStrData2;
            }

            if (string.IsNullOrWhiteSpace(path))
            {
                Show("PartCode could not determine the selected file path.");
                return;
            }

            var vault = poCmd.mpoVault as IEdmVault5;
            if (vault == null)
            {
                Show("PartCode could not access the PDM vault.");
                return;
            }

            var settings = ConnectorSettings.Load();
            var apiKey = settings.GetApiKey();
            if (string.IsNullOrWhiteSpace(apiKey))
            {
                Show(
                    "PartCode API key is missing. Run the installer again or update " +
                    "%ProgramData%\\PartCode\\pdm-connector.json.");
                return;
            }

            var context = PdmContext.Read(vault, path, settings);
            ServicePointManager.SecurityProtocol |= SecurityProtocolType.Tls12;
            using (var http = new HttpClient { Timeout = TimeSpan.FromSeconds(30) })
            {
                var client = new PartCodeClient(http, new PartCodeOptions
                {
                    BaseUrl = settings.BaseUrl,
                    ApiKey = apiKey,
                });

                using (var form = new GenerateCodeForm(client, settings, context))
                {
                    form.ShowDialog();
                }
            }
        }
        catch (Exception error)
        {
            Log(error);
            Show(
                "PartCode failed: " + error.Message + Environment.NewLine +
                "See " + LogPath() + " for details.");
        }
    }

    private static void Show(string message)
    {
        MessageBox.Show(
            message,
            "PartCode",
            MessageBoxButtons.OK,
            MessageBoxIcon.Information);
    }

    private static void Log(Exception error)
    {
        try
        {
            var path = LogPath();
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.AppendAllText(
                path,
                DateTime.UtcNow.ToString("O") + " " + error + Environment.NewLine,
                Encoding.UTF8);
        }
        catch
        {
            // Logging must never break the PDM add-in.
        }
    }

    private static string LogPath()
    {
        return Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "PartCode",
            "pdm-addin.log");
    }
}
