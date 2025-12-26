using System;
using System.Collections.Generic;
using System.Configuration;
using System.IO;
using System.Linq;
using System.Text.Json;

namespace ParkingLotImagesTray
{
    public class AppConfig
    {
        // App.config (stable) keys
        public string StreamUrl { get; set; } = "https://558312d54930d.streamlock.net/live/ccrb2.fois.axis.stream/playlist.m3u8";
        public List<string> FfmpegCommon { get; set; } = new List<string> { "-hide_banner", "-loglevel", "error", "-y", "-rw_timeout", "15000000" };

        // User-editable settings (JSON)
        public string BaseDir { get; set; } = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyPictures), "ParkingLotImages");
        public bool UseDateSubfolders { get; set; } = true;
        public int RetentionDays { get; set; } = 30;
        public bool ZipYesterday { get; set; } = false;
        public string JpegQuality { get; set; } = "2";
        public int FfmpegTimeoutSec { get; set; } = 60;
        public List<ScheduleEntry> Schedules { get; set; } = new List<ScheduleEntry>
        {
            new ScheduleEntry { Cron = "0 18-23 * * *", Id = "cap_evening" },
            new ScheduleEntry { Cron = "0 0-6 * * *", Id = "cap_overnight" },
            new ScheduleEntry { Cron = "0,10,20,30,40,50 7-8 * * *", Id = "cap_morning_rush" },
            new ScheduleEntry { Cron = "0 9-15 * * *", Id = "cap_daytime" },
            new ScheduleEntry { Cron = "0,10,20,30,40,50 16-17 * * *", Id = "cap_evening_rush" }
        };
        // Single housekeeping cron (local time). Default: 00:10 every day
        public string HousekeepingCron { get; set; } = "10 0 * * *";

        public string LogPath => Path.Combine(BaseDir, "timelapse.log");
        public string StatusPath => Path.Combine(BaseDir, "status.json");

        public static AppConfig Load(string? exeDir = null)
        {
            var cfg = new AppConfig();

            try
            {
                // Load from App.config appSettings
                var streamUrl = ConfigurationManager.AppSettings[nameof(StreamUrl)];
                if (!string.IsNullOrWhiteSpace(streamUrl))
                    cfg.StreamUrl = streamUrl!;

                var ffmpegCommonStr = ConfigurationManager.AppSettings[nameof(FfmpegCommon)];
                if (!string.IsNullOrWhiteSpace(ffmpegCommonStr))
                {
                    cfg.FfmpegCommon = ffmpegCommonStr
                        .Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries)
                        .Select(s => s.Trim())
                        .ToList();
                }
            }
            catch
            {
                // ignore and keep defaults
            }

            try
            {
                // Load user JSON next to the EXE
                exeDir ??= AppDomain.CurrentDomain.BaseDirectory;
                var settingsPath = Path.Combine(exeDir, "ParkingLotImagesTray.settings.json");
                if (File.Exists(settingsPath))
                {
                    var json = File.ReadAllText(settingsPath);
                    var userCfg = JsonSerializer.Deserialize<UserSettings>(json, new JsonSerializerOptions
                    {
                        PropertyNameCaseInsensitive = true
                    });
                    if (userCfg != null)
                    {
                        if (!string.IsNullOrWhiteSpace(userCfg.BaseDir)) cfg.BaseDir = userCfg.BaseDir!;
                        if (userCfg.UseDateSubfolders.HasValue) cfg.UseDateSubfolders = userCfg.UseDateSubfolders.Value;
                        if (userCfg.RetentionDays.HasValue && userCfg.RetentionDays.Value > 0) cfg.RetentionDays = userCfg.RetentionDays.Value;
                        if (userCfg.ZipYesterday.HasValue) cfg.ZipYesterday = userCfg.ZipYesterday.Value;
                        if (!string.IsNullOrWhiteSpace(userCfg.JpegQuality)) cfg.JpegQuality = userCfg.JpegQuality!;
                        if (userCfg.FfmpegTimeoutSec.HasValue && userCfg.FfmpegTimeoutSec.Value > 0) cfg.FfmpegTimeoutSec = userCfg.FfmpegTimeoutSec.Value;
                        if (userCfg.Schedules != null && userCfg.Schedules.Count > 0)
                        {
                            // Keep only valid entries (non-empty cron and id)
                            cfg.Schedules = userCfg.Schedules
                                .Where(s => !string.IsNullOrWhiteSpace(s.Cron) && !string.IsNullOrWhiteSpace(s.Id))
                                .ToList();
                        }
                        if (!string.IsNullOrWhiteSpace(userCfg.HousekeepingCron))
                        {
                            cfg.HousekeepingCron = userCfg.HousekeepingCron!;
                        }
                    }
                }
            }
            catch
            {
                // ignore and keep defaults
            }

            // Ensure base dir exists
            try { Directory.CreateDirectory(cfg.BaseDir); } catch { }

            return cfg;
        }

        private class UserSettings
        {
            public string? BaseDir { get; set; }
            public bool? UseDateSubfolders { get; set; }
            public int? RetentionDays { get; set; }
            public bool? ZipYesterday { get; set; }
            public string? JpegQuality { get; set; }
            public int? FfmpegTimeoutSec { get; set; }
            public List<ScheduleEntry>? Schedules { get; set; }
            public string? HousekeepingCron { get; set; }
        }

        public class ScheduleEntry
        {
            public string? Cron { get; set; }
            public string? Id { get; set; }
        }
    }
}
