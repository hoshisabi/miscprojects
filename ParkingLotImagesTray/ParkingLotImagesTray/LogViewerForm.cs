using System;
using System.IO;
using System.Windows.Forms;

namespace ParkingLotImagesTray
{
    public class LogViewerForm : Form
    {
        private TextBox logTextBox;
        private readonly string _logPath;

        public LogViewerForm(string logPath)
        {
            _logPath = logPath;
            InitializeComponent();
            LoadLog();
        }

        private void InitializeComponent()
        {
            this.logTextBox = new TextBox();
            this.SuspendLayout();

            this.logTextBox.Dock = DockStyle.Fill;
            this.logTextBox.Multiline = true;
            this.logTextBox.ReadOnly = true;
            this.logTextBox.ScrollBars = ScrollBars.Vertical;
            this.logTextBox.Font = new System.Drawing.Font("Consolas", 9F);
            this.logTextBox.BackColor = System.Drawing.Color.White;

            this.ClientSize = new System.Drawing.Size(600, 400);
            this.Controls.Add(this.logTextBox);
            this.Name = "LogViewerForm";
            this.Text = "Parking Lot Capture Logs";
            this.ResumeLayout(false);
            this.PerformLayout();
        }

        private void LoadLog()
        {
            try
            {
                if (File.Exists(_logPath))
                {
                    using (var fs = new FileStream(_logPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                    using (var sr = new StreamReader(fs))
                    {
                        string content = sr.ReadToEnd();
                        logTextBox.Text = content;
                        logTextBox.SelectionStart = logTextBox.Text.Length;
                        logTextBox.ScrollToCaret();
                    }
                }
                else
                {
                    logTextBox.Text = "No log file found.";
                }
            }
            catch (Exception ex)
            {
                logTextBox.Text = $"Error reading log: {ex.Message}";
            }
        }
    }
}
