using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using Cronos;

namespace ParkingLotImagesTray
{
    public class TrayApplicationContext : ApplicationContext
    {
        private readonly NotifyIcon _notifyIcon;
        private readonly System.Threading.Timer _schedulerTimer;
        private FileSystemWatcher? _settingsWatcher;
        
        // Config
        private const string FFMPEG = "ffmpeg"; // executable name/path
        private const string LATEST_JPG = "latest.jpg";
        private AppConfig _config = AppConfig.Load();
        private string LOG_PATH => _config.LogPath;
        private string STATUS_PATH => _config.StatusPath;

        private List<(CronExpression Cron, string Id)> _jobs = new();
        private CronExpression? _housekeepingCron;
        
        private readonly object _scheduleLock = new();
        private CancellationTokenSource _reloadDebounceCts = new();

        public TrayApplicationContext()
        {
            Directory.CreateDirectory(_config.BaseDir);
            
            _notifyIcon = new NotifyIcon()
            {
                Icon = System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath),
                ContextMenuStrip = new ContextMenuStrip(),
                Visible = true,
                Text = "Parking Lot Image Capture"
            };
            _notifyIcon.MouseClick += (s, e) => {
                if (e.Button == MouseButtons.Left)
                {
                    ShowInfoDialog();
                }
            };

            _notifyIcon.ContextMenuStrip.Items.Add("View Log", null, (s, e) => ShowLogs());
            _notifyIcon.ContextMenuStrip.Items.Add("Capture Current Image", null, (s, e) => Task.Run(CaptureOne));
            _notifyIcon.ContextMenuStrip.Items.Add("Load Latest Image", null, (s, e) => OpenLatestImage());
            _notifyIcon.ContextMenuStrip.Items.Add("Open Images Folder", null, (s, e) => Process.Start("explorer.exe", Path.GetFullPath(_config.BaseDir)));
            _notifyIcon.ContextMenuStrip.Items.Add("Edit Config", null, (s, e) => OpenConfigFile());
            _notifyIcon.ContextMenuStrip.Items.Add("Reload Config", null, (s, e) => Task.Run(ReloadConfig));
            _notifyIcon.ContextMenuStrip.Items.Add("-");
            _notifyIcon.ContextMenuStrip.Items.Add("Exit", null, (s, e) => Exit());

            // Initialize and start the precise scheduler
            _schedulerTimer = new System.Threading.Timer(SchedulerTick, null, Timeout.Infinite, Timeout.Infinite);
            LoadJobsFromConfig();
            ScheduleNext();
            
            // Set up automatic config reloading
            SetupSettingsWatcher();

            Log("Scheduler started");
            PreventSleep();
            Task.Run(CaptureOne); // Initial capture
        }
        
        private void SetupSettingsWatcher()
        {
            try
            {
                _settingsWatcher = new FileSystemWatcher(AppConfig.AppDataDir)
                {
                    Filter = Path.GetFileName(AppConfig.SettingsPath),
                    NotifyFilter = NotifyFilters.LastWrite | NotifyFilters.FileName,
                    EnableRaisingEvents = true
                };
                _settingsWatcher.Changed += OnSettingsFileChanged;
                _settingsWatcher.Created += OnSettingsFileChanged;
                _settingsWatcher.Renamed += OnSettingsFileChanged;
            }
            catch (Exception ex)
            {
                Log($"Error setting up settings watcher: {ex.Message}");
            }
        }

        private void OnSettingsFileChanged(object sender, FileSystemEventArgs e)
        {
            // Debounce the reload operation
            lock (_scheduleLock)
            {
                _reloadDebounceCts.Cancel();
                _reloadDebounceCts = new CancellationTokenSource();
            }
            
            Task.Delay(500, _reloadDebounceCts.Token).ContinueWith(t =>
            {
                if (t.IsCanceled) return;
                
                // Must invoke on the main thread if we want to show balloons
                if (Application.OpenForms.Count > 0)
                {
                    var mainForm = Application.OpenForms[0];
                    if (mainForm != null && mainForm.InvokeRequired)
                    {
                        mainForm.Invoke(new MethodInvoker(ReloadConfig));
                        return;
                    }
                }
                ReloadConfig();

            }, TaskScheduler.Default);
        }

        private void ReloadConfig()
        {
            try
            {
                _config = AppConfig.Load();
                LoadJobsFromConfig();
                ScheduleNext();
                Log("Configuration reloaded automatically");
                _notifyIcon.BalloonTipTitle = "Parking Lot Image Capture";
                _notifyIcon.BalloonTipText = "Configuration reloaded successfully.";
                _notifyIcon.BalloonTipIcon = ToolTipIcon.Info;
                _notifyIcon.ShowBalloonTip(2000);
            }
            catch (Exception ex)
            {
                Log($"Config reload error: {ex.Message}");
            }
        }

        private void ScheduleNext()
        {
            lock (_scheduleLock)
            {
                var now = DateTime.UtcNow;
                DateTime? nextRun = null;

                var allCrons = _jobs.Select(j => j.Cron).ToList();
                if (_housekeepingCron != null)
                {
                    allCrons.Add(_housekeepingCron);
                }

                foreach (var cron in allCrons)
                {
                    var next = cron.GetNextOccurrence(now);
                    if (next.HasValue)
                    {
                        if (!nextRun.HasValue || next.Value < nextRun.Value)
                        {
                            nextRun = next;
                        }
                    }
                }

                if (nextRun.HasValue)
                {
                    var delay = nextRun.Value - now;
                    if (delay < TimeSpan.Zero) delay = TimeSpan.Zero; // If it's in the past, run now
                    _schedulerTimer.Change(delay, Timeout.InfiniteTimeSpan);
                    Log($"Next job scheduled for: {nextRun.Value.ToLocalTime()} (in {delay.TotalSeconds:F0}s)");
                }
                else
                {
                    _schedulerTimer.Change(Timeout.Infinite, Timeout.Infinite); // No jobs, stop timer
                    Log("No jobs scheduled.");
                }
            }
        }

        private void SchedulerTick(object? state)
        {
            var now = DateTime.UtcNow;
            var utcNowMinusGrace = now.AddSeconds(-5); // 5-second grace period
            
            lock (_scheduleLock)
            {
                // Capture jobs
                foreach (var job in _jobs)
                {
                    var nextOccurrence = job.Cron.GetNextOccurrence(utcNowMinusGrace);
                    if (nextOccurrence.HasValue && nextOccurrence.Value <= now)
                    {
                        Log($"Running job {job.Id}");
                        Task.Run(CaptureOne);
                    }
                }

                // Housekeeping job
                if (_housekeepingCron != null)
                {
                    var nextOccurrence = _housekeepingCron.GetNextOccurrence(utcNowMinusGrace);
                    if (nextOccurrence.HasValue && nextOccurrence.Value <= now)
                    {
                        Task.Run(Housekeeping);
                    }
                }
                
                // Anti-sleep call
                PreventSleep();
            }
            
            // Reschedule for the next run
            ScheduleNext();
        }

        private void ShowLogs()
        {
            try
            {
                if (File.Exists(LOG_PATH))
                {
                    var psi = new ProcessStartInfo(LOG_PATH)
                    {
                        UseShellExecute = true
                    };
                    Process.Start(psi);
                }
                else
                {
                    _notifyIcon.BalloonTipTitle = "Parking Lot Image Capture";
                    _notifyIcon.BalloonTipText = "Log file not found yet. It will appear after the first write.";
                    _notifyIcon.BalloonTipIcon = ToolTipIcon.Info;
                    _notifyIcon.ShowBalloonTip(3000);
                }
            }
            catch (Exception ex)
            {
                Log($"Failed to open log file: {ex.Message}");
            }
        }

        private void OpenConfigFile()
        {
            try
            {
                var settingsPath = AppConfig.SettingsPath;
                if (!File.Exists(settingsPath))
                {
                    File.WriteAllText(settingsPath, "{\n  \"Schedules\": []\n}\n");
                }

                var psi = new ProcessStartInfo(settingsPath)
                {
                    UseShellExecute = true
                };
                Process.Start(psi);
            }
            catch (Exception ex)
            {
                Log($"Failed to open settings file: {ex.Message}");
            }
        }

        private void OpenLatestImage()
        {
            try
            {
                var latest = Path.Combine(_config.BaseDir, LATEST_JPG);
                if (File.Exists(latest))
                {
                    var psi = new ProcessStartInfo(latest)
                    {
                        UseShellExecute = true
                    };
                    Process.Start(psi);
                }
                else
                {
                    _notifyIcon.BalloonTipTitle = "Parking Lot Image Capture";
                    _notifyIcon.BalloonTipText = $"No {LATEST_JPG} found yet. Capture one now via 'Capture Current Image'.";
                    _notifyIcon.BalloonTipIcon = ToolTipIcon.Info;
                    _notifyIcon.ShowBalloonTip(3000);
                }
            }
            catch (Exception ex)
            {
                Log($"Failed to open latest image: {ex.Message}");
            }
        }

        private void AddJob(string cronStr, string id)
        {
            _jobs.Add((CronExpression.Parse(cronStr), id));
        }

        private void LoadJobsFromConfig()
        {
            _jobs.Clear();
            try
            {
                foreach (var s in _config.Schedules)
                {
                    try
                    {
                        if (!string.IsNullOrWhiteSpace(s.Cron) && !string.IsNullOrWhiteSpace(s.Id))
                        {
                            AddJob(s.Cron!, s.Id!);
                        }
                    }
                    catch (Exception ex)
                    {
                        Log($"Invalid schedule '{s.Id}': {ex.Message}");
                    }
                }
                _housekeepingCron = null;
                try
                {
                    if (!string.IsNullOrWhiteSpace(_config.HousekeepingCron))
                    {
                        _housekeepingCron = CronExpression.Parse(_config.HousekeepingCron);
                    }
                }
                catch (Exception ex)
                {
                    Log($"Invalid housekeeping cron: {_config.HousekeepingCron} → {ex.Message}");
                }

                Log($"Loaded {_jobs.Count} schedules from config{(_housekeepingCron != null ? ", housekeeping cron active" : ", housekeeping disabled")}");
            }
            catch (Exception ex)
            {
                Log($"Error loading schedules: {ex.Message}");
            }
        }

        private async Task CaptureOne()
        {
            try
            {
                var dt = DateTime.Now;
                var outDir = GetOutDir(dt);
                Directory.CreateDirectory(outDir);

                string finalName = $"pl-{dt:yyyy-MM-dd-HH-mm-ss}.jpg";
                string finalPath = Path.Combine(outDir, finalName);
                string tmpPath = Path.Combine(outDir, finalName + ".part");

                var args = new List<string>(_config.FfmpegCommon);
                args.AddRange(new[] { "-i", _config.StreamUrl, "-f", "image2", "-vcodec", "mjpeg", "-q:v", _config.JpegQuality, "-vframes", "1", tmpPath });

                for (int attempt = 1; attempt <= 3; attempt++)
                {
                    try
                    {
                        PreventSleep();
                        using (var process = new Process())
                        {
                            process.StartInfo.FileName = FFMPEG;
                            process.StartInfo.Arguments = string.Join(" ", args);
                            process.StartInfo.UseShellExecute = false;
                            process.StartInfo.CreateNoWindow = true;
                            process.Start();

                            // Correctly handle timeout with CancellationToken
                            using (var cts = new CancellationTokenSource(TimeSpan.FromSeconds(_config.FfmpegTimeoutSec)))
                            {
                                try
                                {
                                    await process.WaitForExitAsync(cts.Token);
                                    
                                    // Process exited without timeout
                                    if (process.ExitCode == 0)
                                    {
                                        if (File.Exists(finalPath)) File.Delete(finalPath);
                                        File.Move(tmpPath, finalPath);
                                        
                                        try { File.Copy(finalPath, Path.Combine(_config.BaseDir, LATEST_JPG), true); } catch { }

                                        string? root = Path.GetPathRoot(_config.BaseDir);
                                        var drive = new DriveInfo(root ?? "C:");
                                        WriteStatus(true, finalPath, dt, drive.AvailableFreeSpace / 1e9);
                                        Log($"Saved -> {finalPath}");
                                        return; // Success, exit method
                                    }
                                    else
                                    {
                                        Log($"ffmpeg failed (attempt {attempt}/3, exit {process.ExitCode})");
                                    }
                                }
                                catch (OperationCanceledException)
                                {
                                    // Timeout occurred
                                    if (!process.HasExited)
                                    {
                                        process.Kill();
                                    }
                                    Log($"ffmpeg timeout (attempt {attempt}/3)");
                                }
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Log($"Capture error (attempt {attempt}/3): {ex.Message}");
                    }
                    await Task.Delay(3000); // Wait before next retry
                }
                WriteStatus(false, null, DateTime.Now, 0, "ffmpeg failed after retries");
            }
            catch (Exception ex)
            {
                Log($"Unexpected capture error: {ex.Message}");
            }
        }

        private string GetOutDir(DateTime dt)
        {
            if (_config.UseDateSubfolders)
            {
                return Path.Combine(_config.BaseDir, dt.ToString("yyyy-MM-dd"));
            }
            return _config.BaseDir;
        }

        private void Housekeeping()
        {
            Log("Starting housekeeping");
            ZipYesterday();
            PruneOld();
        }

        private void ZipYesterday()
        {
            if (!_config.ZipYesterday || !_config.UseDateSubfolders) return;
            
            var y = DateTime.Now.AddDays(-1);
            var folder = GetOutDir(y);
            var zipPath = Path.Combine(_config.BaseDir, Path.GetFileName(folder) + ".zip");

            if (!Directory.Exists(folder) || File.Exists(zipPath)) return;
            
            try
            {
                long beforeSize = 0;
                
                using (var archive = ZipFile.Open(zipPath, ZipArchiveMode.Create))
                {
                    foreach (var file in Directory.GetFiles(folder, "*", SearchOption.AllDirectories))
                    {
                        var fileInfo = new FileInfo(file);
                        beforeSize += fileInfo.Length;
                        
                        var entryName = Path.GetRelativePath(folder, file);
                        var entry = archive.CreateEntry(entryName, CompressionLevel.Optimal);
                        using var fileStream = fileInfo.OpenRead();
                        using var entryStream = entry.Open();
                        fileStream.CopyTo(entryStream);
                    }
                }

                if (beforeSize == 0)
                {
                    File.Delete(zipPath); // Delete empty zip
                    Log($"Zip skipped (empty folder): {Path.GetFileName(folder)}");
                    return;
                }

                long afterSize = new FileInfo(zipPath).Length;
                double ratio = (afterSize / (double)beforeSize) * 100;
                string beforeMB = (beforeSize / (1024.0 * 1024.0)).ToString("F2");
                string afterMB = (afterSize / (1024.0 * 1024.0)).ToString("F2");
                
                Directory.Delete(folder, true);
                Log($"Zipped {Path.GetFileName(folder)} | Before: {beforeMB}MB | After: {afterMB}MB | Ratio: {ratio:F1}%");
            }
            catch (UnauthorizedAccessException ex)
            {
                Log($"Zip skipped (access denied): {Path.GetFileName(folder)} - {ex.Message}");
            }
            catch (Exception ex)
            {
                Log($"Zip error: {ex.Message}");
            }
        }

        private void PruneOld()
        {
            try
            {
                var cutoff = DateTime.Now.AddDays(-_config.RetentionDays);
                // Prune folders
                if (_config.UseDateSubfolders)
                {
                    foreach (var dir in Directory.GetDirectories(_config.BaseDir))
                    {
                        var name = Path.GetFileName(dir);
                        if (DateTime.TryParse(name, out var dt) && dt < cutoff)
                        {
                            try
                            {
                                Directory.Delete(dir, true);
                                Log($"Pruned folder: {name}");
                            }
                            catch (UnauthorizedAccessException)
                            {
                                Log($"Prune skipped (access denied): {name}");
                            }
                            catch (Exception ex)
                            {
                                Log($"Prune folder error for {name}: {ex.Message}");
                            }
                        }
                    }
                }
                // Prune zips
                foreach (var file in Directory.GetFiles(_config.BaseDir, "*.zip"))
                {
                    var name = Path.GetFileNameWithoutExtension(file);
                    if (DateTime.TryParse(name, out var dt) && dt < cutoff)
                    {
                        try
                        {
                            File.Delete(file);
                            Log($"Pruned zip: {Path.GetFileName(file)}");
                        }
                        catch (UnauthorizedAccessException)
                        {
                            Log($"Prune skipped (access denied): {Path.GetFileName(file)}");
                        }
                        catch (Exception ex)
                        {
                            Log($"Prune zip error for {Path.GetFileName(file)}: {ex.Message}");
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Log($"Prune error: {ex.Message}");
            }
        }

        private void Log(string message)
        {
            var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {message}{Environment.NewLine}";
            try
            {
                File.AppendAllText(LOG_PATH, line);
            }
            catch { }
        }

        private void WriteStatus(bool ok, string? lastCapture, DateTime lastTime, double freeGb, string? error = null)
        {
            var status = new
            {
                updated_at = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
                ok,
                last_capture = lastCapture,
                last_capture_time = lastTime.ToString("yyyy-MM-ddTHH:mm:ss"),
                free_gb = Math.Round(freeGb, 2),
                error
            };
            try
            {
                File.WriteAllText(STATUS_PATH, JsonSerializer.Serialize(status, new JsonSerializerOptions { WriteIndented = true }));
            }
            catch { }
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
        static extern uint SetThreadExecutionState(uint esFlags);
        private const uint ES_CONTINUOUS = 0x80000000;
        private const uint ES_SYSTEM_REQUIRED = 0x00000001;
        private const uint ES_AWAYMODE_REQUIRED = 0x00000040;

        private void PreventSleep()
        {
            SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED);
        }

        private void ShowInfoDialog()
        {
            try
            {
                var exePath = Application.ExecutablePath;
                var compiledTime = File.GetLastWriteTime(exePath).ToString("yyyy-MM-dd HH:mm:ss");
                var logModifiedTime = File.Exists(LOG_PATH) ? File.GetLastWriteTime(LOG_PATH).ToString("yyyy-MM-dd HH:mm:ss") : "No log file yet";
                var destDir = Path.GetFullPath(_config.BaseDir);

                var infoText = $"Parking Lot Image Capture\n\n" +
                    $"Compiled: {compiledTime}\n" +
                    $"Log File: {logModifiedTime}\n" +
                    $"Destination: {destDir}";

                using var form = new Form
                {
                    Text = "Application Info",
                    Width = 600,
                    Height = 250,
                    StartPosition = FormStartPosition.CenterScreen,
                    FormBorderStyle = FormBorderStyle.FixedDialog,
                    MaximizeBox = false,
                    MinimizeBox = false
                };

                var textBox = new TextBox
                {
                    Text = infoText,
                    ReadOnly = true,
                    Multiline = true,
                    Dock = DockStyle.Top,
                    Height = 100,
                    Font = new System.Drawing.Font("Segoe UI", 10)
                };

                var panel = new Panel
                {
                    Dock = DockStyle.Bottom,
                    Height = 50,
                    Padding = new Padding(10)
                };

                var openLogBtn = new Button
                {
                    Text = "Open Log File",
                    Width = 120,
                    Left = 10,
                    Top = 10,
                    DialogResult = DialogResult.None
                };
                openLogBtn.Click += (s, e) => ShowLogs();

                var openFolderBtn = new Button
                {
                    Text = "Open Folder",
                    Width = 120,
                    Left = 140,
                    Top = 10,
                    DialogResult = DialogResult.None
                };
                openFolderBtn.Click += (s, e) => Process.Start("explorer.exe", destDir);

                var closeBtn = new Button
                {
                    Text = "Close",
                    Width = 120,
                    Left = 270,
                    Top = 10,
                    DialogResult = DialogResult.OK
                };

                panel.Controls.Add(openLogBtn);
                panel.Controls.Add(openFolderBtn);
                panel.Controls.Add(closeBtn);

                form.Controls.Add(textBox);
                form.Controls.Add(panel);

                form.ShowDialog();
            }
            catch (Exception ex)
            {
                MessageBox.Show($"Error showing info dialog: {ex.Message}", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }

        private void Exit()
        {
            _notifyIcon.Visible = false;
            _schedulerTimer.Dispose();
            _settingsWatcher?.Dispose();
            _reloadDebounceCts.Dispose();
            Application.Exit();
        }
    }
}
