// FieldRook native shell — file logger (%LOCALAPPDATA%\FieldRook\logs).

using FieldRook.Core.Infrastructure;

namespace FieldRook.Backend;

public static class AppLogger
{
    private static readonly object Sync = new();
    private static string? _path;

    public static void Info(string message) => Write("INFO", message);
    public static void Warn(string message) => Write("WARN", message);
    public static void Error(string message) => Write("ERROR", message);

    private static void Write(string level, string message)
    {
        try
        {
            _path ??= Path.Combine(AppPaths.LogsDir(), "shell.log");
            Directory.CreateDirectory(AppPaths.LogsDir());
            var line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} [{level}] {message}";
            lock (Sync)
            {
                File.AppendAllText(_path, line + Environment.NewLine);
            }
        }
        catch (Exception)
        {
            // Logging must never crash the shell.
        }
    }
}
