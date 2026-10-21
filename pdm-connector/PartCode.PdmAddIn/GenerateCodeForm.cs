using System;
using System.Collections.Generic;
using System.Drawing;
using System.Linq;
using System.Threading.Tasks;
using System.Windows.Forms;
using PartCode.Connector;

namespace PartCode.PdmAddIn;

public sealed class GenerateCodeForm : Form
{
    private readonly PartCodeClient _client;
    private readonly ConnectorSettings _settings;
    private readonly PdmContext _context;
    private readonly ComboBox _ruleBox;
    private readonly FlowLayoutPanel _fieldPanel;
    private readonly Label _preview;
    private readonly Label _status;
    private readonly Button _previewButton;
    private readonly Button _reserveButton;
    private readonly Dictionary<string, Control> _inputs = new Dictionary<string, Control>();
    private List<PartCodeRule> _rules = new List<PartCodeRule>();

    public GenerateCodeForm(
        PartCodeClient client,
        ConnectorSettings settings,
        PdmContext context)
    {
        _client = client;
        _settings = settings;
        _context = context;

        Text = "PartCode - assign code";
        Width = 620;
        Height = 560;
        MinimumSize = new Size(560, 480);
        StartPosition = FormStartPosition.CenterParent;
        FormBorderStyle = FormBorderStyle.Sizable;
        MaximizeBox = false;
        MinimizeBox = false;

        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 1,
            RowCount = 5,
            Padding = new Padding(16),
        };
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));
        root.RowStyles.Add(new RowStyle(SizeType.AutoSize));

        var header = new Label
        {
            Text = "Assign a PartCode number to this PDM file",
            Font = new Font(Font.FontFamily, 12, FontStyle.Bold),
            AutoSize = true,
            Margin = new Padding(0, 0, 0, 8),
        };

        var ruleRow = new TableLayoutPanel
        {
            Dock = DockStyle.Top,
            ColumnCount = 2,
            AutoSize = true,
            Margin = new Padding(0, 0, 0, 8),
        };
        ruleRow.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 80));
        ruleRow.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        ruleRow.Controls.Add(new Label
        {
            Text = "Rule",
            TextAlign = ContentAlignment.MiddleLeft,
            AutoSize = true,
            Margin = new Padding(0, 6, 8, 0),
        }, 0, 0);

        _ruleBox = new ComboBox
        {
            Dock = DockStyle.Fill,
            DropDownStyle = ComboBoxStyle.DropDownList,
            Enabled = false,
        };
        _ruleBox.SelectedIndexChanged += (_, __) => BuildFields();
        ruleRow.Controls.Add(_ruleBox, 1, 0);

        _fieldPanel = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.TopDown,
            WrapContents = false,
            AutoScroll = true,
            Padding = new Padding(0, 4, 0, 4),
        };

        var previewRow = new Panel { Dock = DockStyle.Top, Height = 34 };
        previewRow.Controls.Add(new Label
        {
            Text = "Preview",
            AutoSize = true,
            Location = new Point(0, 8),
        });
        _preview = new Label
        {
            Text = "—",
            AutoSize = true,
            Font = new Font("Consolas", 11, FontStyle.Bold),
            ForeColor = Color.FromArgb(47, 84, 235),
            Location = new Point(64, 8),
        };
        previewRow.Controls.Add(_preview);

        _status = new Label
        {
            Text = "Reading PDM data card…",
            AutoSize = true,
            ForeColor = Color.DimGray,
            Dock = DockStyle.Top,
            Margin = new Padding(0, 6, 0, 6),
        };

        var buttons = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.RightToLeft,
            AutoSize = true,
        };
        _reserveButton = new Button
        {
            Text = "Reserve and write to PDM",
            AutoSize = true,
            Enabled = false,
        };
        _reserveButton.Click += async (_, __) => await ReserveAsync();
        _previewButton = new Button
        {
            Text = "Preview",
            AutoSize = true,
            Enabled = false,
        };
        _previewButton.Click += async (_, __) => await PreviewAsync();
        var cancel = new Button { Text = "Cancel", AutoSize = true, DialogResult = DialogResult.Cancel };
        buttons.Controls.Add(_reserveButton);
        buttons.Controls.Add(_previewButton);
        buttons.Controls.Add(cancel);

        root.Controls.Add(header, 0, 0);
        root.Controls.Add(ruleRow, 0, 1);
        root.Controls.Add(_fieldPanel, 0, 2);
        root.Controls.Add(previewRow, 0, 3);
        root.Controls.Add(buttons, 0, 4);
        Controls.Add(root);
        CancelButton = cancel;
    }

    protected override async void OnShown(EventArgs e)
    {
        base.OnShown(e);
        try
        {
            SetBusy(true);
            _status.Text = "Loading active PartCode rules…";
            _rules = await _client.GetRulesAsync(_settings.DocumentType);
            if (_rules.Count == 0)
            {
                _status.Text = "No active rules for document type '" + _settings.DocumentType + "'.";
                return;
            }

            foreach (var rule in _rules)
            {
                _ruleBox.Items.Add(new RuleChoice(rule));
            }

            _ruleBox.Enabled = true;
            _ruleBox.SelectedIndex = 0;
            _status.Text = "PDM: " + _context.Path;
        }
        catch (PartCodeApiException error)
        {
            ShowApiError(error);
        }
        catch (Exception error)
        {
            ShowError(error);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private void BuildFields()
    {
        _fieldPanel.SuspendLayout();
        foreach (Control control in _fieldPanel.Controls)
        {
            control.Dispose();
        }

        _fieldPanel.Controls.Clear();
        _inputs.Clear();
        _preview.Text = "—";

        var rule = SelectedRule;
        if (rule == null)
        {
            _fieldPanel.ResumeLayout();
            return;
        }

        foreach (var segment in rule.Definition.Segments)
        {
            if (segment.Type == "list" && segment.Options != null)
            {
                AddField(segment, BuildListInput(segment));
            }
            else if (segment.Type == "text")
            {
                AddField(segment, BuildTextInput(segment));
            }
        }

        _fieldPanel.ResumeLayout();
        var enabled = rule.Definition.Segments.Count > 0;
        _previewButton.Enabled = enabled;
        _reserveButton.Enabled = enabled;
    }

    private ComboBox BuildListInput(RuleSegment segment)
    {
        var combo = new ComboBox
        {
            Width = 520,
            DropDownStyle = ComboBoxStyle.DropDownList,
        };

        foreach (var option in segment.Options ?? new List<ListOption>())
        {
            combo.Items.Add(new OptionChoice(option));
        }

        var current = PreferredValue(segment);
        if (!string.IsNullOrWhiteSpace(current))
        {
            for (var index = 0; index < combo.Items.Count; index++)
            {
                var option = (OptionChoice)combo.Items[index]!;
                if (string.Equals(option.Value, current, StringComparison.OrdinalIgnoreCase))
                {
                    combo.SelectedIndex = index;
                    break;
                }
            }
        }

        if (combo.SelectedIndex < 0 && combo.Items.Count > 0 && segment.Required == true)
        {
            combo.SelectedIndex = 0;
        }

        return combo;
    }

    private TextBox BuildTextInput(RuleSegment segment)
    {
        return new TextBox
        {
            Width = 520,
            Text = PreferredValue(segment) ?? string.Empty,
        };
    }

    private void AddField(RuleSegment segment, Control input)
    {
        var panel = new Panel
        {
            Width = 545,
            Height = 58,
            Margin = new Padding(0, 0, 0, 4),
        };
        var label = new Label
        {
            Text = (string.IsNullOrWhiteSpace(segment.Label) ? segment.Key : segment.Label)
                + (segment.Required == true ? " *" : string.Empty),
            AutoSize = true,
            Location = new Point(0, 2),
        };
        input.Location = new Point(0, 24);
        panel.Controls.Add(label);
        panel.Controls.Add(input);
        _fieldPanel.Controls.Add(panel);

        if (!string.IsNullOrWhiteSpace(segment.Key))
        {
            _inputs[segment.Key!] = input;
        }
    }

    private string? PreferredValue(RuleSegment segment)
    {
        var keys = new[] { segment.Key, segment.Label };
        foreach (var key in keys)
        {
            if (string.IsNullOrWhiteSpace(key))
            {
                continue;
            }

            string value;
            if (_context.Values.TryGetValue(key!, out value))
            {
                return value;
            }
        }

        return null;
    }

    private async Task PreviewAsync()
    {
        var rule = SelectedRule;
        if (rule == null)
        {
            return;
        }

        try
        {
            SetBusy(true);
            var result = await _client.PreviewAsync(BuildRequest(rule));
            _preview.Text = result.Code;
            _status.Text = "Preview only - no counter consumed, no PDM write performed.";
        }
        catch (PartCodeApiException error)
        {
            ShowApiError(error);
        }
        catch (Exception error)
        {
            ShowError(error);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private async Task ReserveAsync()
    {
        var rule = SelectedRule;
        if (rule == null)
        {
            return;
        }

        try
        {
            SetBusy(true);
            var result = await _client.ReserveAsync(BuildRequest(rule));
            PdmContext.WriteCode(_context.Variables, _settings.TargetVariable, result.Code);
            _preview.Text = result.Code;
            MessageBox.Show(
                this,
                "Code " + result.Code + " was reserved and written to PDM variable '" +
                _settings.TargetVariable + "'.",
                "PartCode",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
            DialogResult = DialogResult.OK;
            Close();
        }
        catch (PartCodeApiException error)
        {
            ShowApiError(error);
        }
        catch (Exception error)
        {
            ShowError(error);
        }
        finally
        {
            SetBusy(false);
        }
    }

    private GenerateRequest BuildRequest(PartCodeRule rule)
    {
        var values = new Dictionary<string, string>();
        foreach (var segment in rule.Definition.Segments)
        {
            Control control;
            if (string.IsNullOrWhiteSpace(segment.Key) || !_inputs.TryGetValue(segment.Key!, out control))
            {
                continue;
            }

            var combo = control as ComboBox;
            if (combo != null)
            {
                var option = combo.SelectedItem as OptionChoice;
                if (option != null)
                {
                    values[segment.Key!] = option.Value;
                }

                continue;
            }

            values[segment.Key!] = control.Text.Trim();
        }

        return new GenerateRequest
        {
            RuleKey = rule.Key,
            Values = values,
            Source = "pdm",
            ExternalRef = _context.ExternalReference,
            Metadata = _context.Metadata,
        };
    }

    private PartCodeRule? SelectedRule
    {
        get
        {
            var choice = _ruleBox.SelectedItem as RuleChoice;
            return choice == null ? null : choice.Rule;
        }
    }

    private void SetBusy(bool busy)
    {
        UseWaitCursor = busy;
        _previewButton.Enabled = !busy && SelectedRule != null;
        _reserveButton.Enabled = !busy && SelectedRule != null;
        _ruleBox.Enabled = !busy && _rules.Count > 0;
        Application.DoEvents();
    }

    private void ShowApiError(PartCodeApiException error)
    {
        var details = error.Message;
        if (error.Fields.Count > 0)
        {
            details += Environment.NewLine + string.Join(
                Environment.NewLine,
                error.Fields.Select(field => field.Key + ": " + field.Value));
        }

        _status.Text = error.Message;
        MessageBox.Show(this, details, "PartCode error", MessageBoxButtons.OK, MessageBoxIcon.Warning);
    }

    private void ShowError(Exception error)
    {
        _status.Text = error.Message;
        MessageBox.Show(this, error.Message, "PartCode error", MessageBoxButtons.OK, MessageBoxIcon.Error);
    }

    private sealed class RuleChoice
    {
        public RuleChoice(PartCodeRule rule)
        {
            Rule = rule;
        }

        public PartCodeRule Rule { get; }

        public override string ToString()
        {
            return Rule.Name + " (v" + Rule.Version + ")";
        }
    }

    private sealed class OptionChoice
    {
        public OptionChoice(ListOption option)
        {
            Value = option.Value;
            Label = option.Label;
        }

        public string Value { get; }
        public string? Label { get; }

        public override string ToString()
        {
            return string.IsNullOrWhiteSpace(Label) ? Value : Label!;
        }
    }
}
