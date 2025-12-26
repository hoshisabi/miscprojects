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
        private NotifyIcon notifyIcon;
        private System.Windows.Forms.Timer schedulerTimer;
        
        // Config
        private const string FFMPEG = "ffmpeg"; // executable name/path
        private AppConfig _config = AppConfig.Load();
        private string LOG_PATH => _config.LogPath;
        private string STATUS_PATH => _config.StatusPath;

        private List<(CronExpression Cron, string Id)> jobs = new List<(CronExpression, string)>();
        private DateTime lastHousekeeping = DateTime.MinValue;
        private CronExpression? _housekeepingCron;

        public TrayApplicationContext()
        {
            Directory.CreateDirectory(_config.BaseDir);
            
            notifyIcon = new NotifyIcon()
            {
                Icon = System.Drawing.Icon.ExtractAssociatedIcon(Application.ExecutablePath),
                ContextMenuStrip = new ContextMenuStrip(),
                Visible = true,
                Text = "Parking Lot Image Capture"
            };

            notifyIcon.ContextMenuStrip.Items.Add("View Log", null, (s, e) => ShowLogs());
            notifyIcon.ContextMenuStrip.Items.Add("Capture Current Image", null, (s, e) => Task.Run(CaptureOne));
            notifyIcon.ContextMenuStrip.Items.Add("Load Latest Image", null, (s, e) => OpenLatestImage());
            notifyIcon.ContextMenuStrip.Items.Add("Open Images Folder", null, (s, e) => Process.Start("explorer.exe", _config.BaseDir));
            notifyIcon.ContextMenuStrip.Items.Add("Edit Config", null, (s, e) => OpenConfigFile());
            notifyIcon.ContextMenuStrip.Items.Add("Reload Config", null, (s, e) => {
                try
                {
                    _config = AppConfig.Load();
                    LoadJobsFromConfig();
                    Log("Configuration reloaded");
                }
                catch (Exception ex)
                {
                    Log($"Config reload error: {ex.Message}");
                }
            });
            notifyIcon.ContextMenuStrip.Items.Add("-");
            notifyIcon.ContextMenuStrip.Items.Add("Exit", null, (s, e) => Exit());

            // Initialize Jobs from config
            LoadJobsFromConfig();

            schedulerTimer = new System.Windows.Forms.Timer();
            schedulerTimer.Interval = 10000; // Check every 10 seconds
            schedulerTimer.Tick += SchedulerTimer_Tick;
            schedulerTimer.Start();

            Log("Scheduler started");
            PreventSleep();
            Task.Run(CaptureOne); // Initial capture
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
                    // Friendly message if the log file isn't present yet
                    notifyIcon.BalloonTipTitle = "Parking Lot Image Capture";
                    notifyIcon.BalloonTipText = "Log file not found yet. It will appear after the first write.";
                    notifyIcon.BalloonTipIcon = ToolTipIcon.Info;
                    notifyIcon.ShowBalloonTip(3000);
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
                var exeDir = AppDomain.CurrentDomain.BaseDirectory;
                var settingsPath = Path.Combine(exeDir, "ParkingLotImagesTray.settings.json");
                if (!File.Exists(settingsPath))
                {
                    // Create a minimal JSON stub so the user has something to edit
                    File.WriteAllText(settingsPath, "{\n}\n");
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
                var latest = Path.Combine(_config.BaseDir, "latest.jpg");
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
                    notifyIcon.BalloonTipTitle = "Parking Lot Image Capture";
                    notifyIcon.BalloonTipText = "No latest.jpg found yet. Capture one now via 'Capture Current Image'.";
                    notifyIcon.BalloonTipIcon = ToolTipIcon.Info;
                    notifyIcon.ShowBalloonTip(3000);
                }
            }
            catch (Exception ex)
            {
                Log($"Failed to open latest image: {ex.Message}");
            }
        }

        private void AddJob(string cronStr, string id)
        {
            jobs.Add((CronExpression.Parse(cronStr), id));
        }

        private void LoadJobsFromConfig()
        {
            jobs.Clear();
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
                // Parse housekeeping cron
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

                Log($"Loaded {jobs.Count} schedules from config{(_housekeepingCron != null ? ", housekeeping cron active" : ", housekeeping disabled")}");
            }
            catch (Exception ex)
            {
                Log($"Error loading schedules: {ex.Message}");
            }
        }

        private void SchedulerTimer_Tick(object? sender, EventArgs e)
        {
            var now = DateTime.Now;
            
            // Check if any cron job should run
            // Note: This is a simplified scheduler compared to APScheduler
            // It checks if 'now' is within the last 10 seconds of a scheduled run.
            foreach (var job in jobs)
            {
                var nextUtc = job.Cron.GetNextOccurrence(DateTime.UtcNow.AddSeconds(-10));
                if (nextUtc.HasValue)
                {
                    var nextLocal = nextUtc.Value.ToLocalTime();
                    if (Math.Abs((now - nextLocal).TotalSeconds) < 5)
                    {
                        Log($"Running job {job.Id}");
                        Task.Run(CaptureOne);
                    }
                }
            }

            // Housekeeping via cron (default 00:10 daily). Debounce to avoid double runs.
            if (_housekeepingCron != null)
            {
                try
                {
                    var nextUtc = _housekeepingCron.GetNextOccurrence(DateTime.UtcNow.AddSeconds(-10));
                    if (nextUtc.HasValue)
                    {
                        var nextLocal = nextUtc.Value.ToLocalTime();
                        if (Math.Abs((now - nextLocal).TotalSeconds) < 5 && (now - lastHousekeeping).TotalMinutes > 1)
                        {
                            lastHousekeeping = now;
                            Task.Run(Housekeeping);
                        }
                    }
                }
                catch (Exception ex)
                {
                    Log($"Housekeeping cron evaluation error: {ex.Message}");
                }
            }

            // Heartbeat / Anti-sleep (every 5 mins handled by naturally calling it in tick if we want, 
            // but Python did it via interval. We'll just call it periodically.)
            if (now.Second < 10 && now.Minute % 5 == 0)
            {
                PreventSleep();
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

                            if (process.WaitForExit(_config.FfmpegTimeoutSec * 1000))
                            {
                                if (process.ExitCode == 0)
                                {
                                    if (File.Exists(finalPath)) File.Delete(finalPath);
                                    File.Move(tmpPath, finalPath);
                                    
                                    try { File.Copy(finalPath, Path.Combine(_config.BaseDir, "latest.jpg"), true); } catch { }

                                    string? root = Path.GetPathRoot(_config.BaseDir);
                                    var drive = new DriveInfo(root ?? "C:");
                                    WriteStatus(true, finalPath, dt, drive.AvailableFreeSpace / 1e9);
                                    Log($"Saved -> {finalPath}");
                                    return;
                                }
                                else
                                {
                                    Log($"ffmpeg failed (attempt {attempt}/3, exit {process.ExitCode})");
                                }
                            }
                            else
                            {
                                process.Kill();
                                Log($"ffmpeg timeout (attempt {attempt}/3)");
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        Log($"Capture error (attempt {attempt}/3): {ex.Message}");
                    }
                    await Task.Delay(3000);
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
            if (_config.ZipYesterday && _config.UseDateSubfolders)
            {
                var y = DateTime.Now.AddDays(-1);
                var folder = GetOutDir(y);
                var zipPath = Path.Combine(_config.BaseDir, Path.GetFileName(folder) + ".zip");

                if (Directory.Exists(folder) && !File.Exists(zipPath))
                {
                    try
                    {
                        ZipFile.CreateFromDirectory(folder, zipPath);
                        Directory.Delete(folder, true);
                        Log($"Zipped {Path.GetFileName(folder)} -> {Path.GetFileName(zipPath)}");
                    }
                    catch (Exception ex)
                    {
                        Log($"Zip error: {ex.Message}");
                    }
                }
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
                            Directory.Delete(dir, true);
                            Log($"Pruned folder: {name}");
                        }
                    }
                }
                // Prune zips
                foreach (var file in Directory.GetFiles(_config.BaseDir, "*.zip"))
                {
                    var name = Path.GetFileNameWithoutExtension(file);
                    if (DateTime.TryParse(name, out var dt) && dt < cutoff)
                    {
                        File.Delete(file);
                        Log($"Pruned zip: {Path.GetFileName(file)}");
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
                ok = ok,
                last_capture = lastCapture,
                last_capture_time = lastTime.ToString("yyyy-MM-ddTHH:mm:ss"),
                free_gb = Math.Round(freeGb, 2),
                error = error
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

        private void Exit()
        {
            notifyIcon.Visible = false;
            Application.Exit();
        }
    }
}
