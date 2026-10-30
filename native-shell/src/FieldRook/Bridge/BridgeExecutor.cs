// FieldRook native shell — bridge command execution (M026, section 2).
//
// Runs validated BridgeCommands (see FieldRook.Core): native file dialogs
// for .zip import / export, version reporting, standard-chrome window
// control. Every path is re-validated at execution time; failures answer
// {ok:false} and never touch the filesystem outside dialog results.
//
// Result shapes are built by FieldRook.Core helpers so the JSON contract
// the signalforge client parses stays unit-tested (see BridgeProtocolTests
// ResultShapes_MatchSignalforgeClient).

using System.Reflection;
using System.Windows;
using FieldRook.Core.Backend;
using FieldRook.Core.Bridge;
using Microsoft.Win32;

namespace FieldRook.Bridge;

public sealed class BridgeExecutor
{
    private readonly Window _window;
    private readonly Func<StatusIdentity> _serverIdentity;

    public BridgeExecutor(Window window, Func<StatusIdentity> serverIdentity)
    {
        _window = window;
        _serverIdentity = serverIdentity;
    }

    public string Execute(BridgeCommand command)
    {
        try
        {
            return command.Op switch
            {
                BridgeOps.OpenFile => ExecuteOpenFile(command),
                BridgeOps.SaveFile => ExecuteSaveFile(command),
                BridgeOps.GetVersion => ExecuteGetVersion(command),
                BridgeOps.WindowControl => ExecuteWindowControl(command),
                _ => BridgeProtocol.FailResponse(command.Id, new BridgeError(
                    BridgeErrorCodes.UnknownOp, $"Unknown bridge op '{command.Op}'.")),
            };
        }
        catch (Exception ex)
        {
            return BridgeProtocol.FailResponse(command.Id, new BridgeError(
                BridgeErrorCodes.Failed, $"The operation failed: {ex.Message}"));
        }
    }

    private string ExecuteOpenFile(BridgeCommand command)
    {
        var dialog = new OpenFileDialog
        {
            Filter = "Collector packages (*.zip)|*.zip",
            Title = string.IsNullOrWhiteSpace(command.DialogTitle) ? "Import collector package" : command.DialogTitle,
            CheckFileExists = true,
            Multiselect = false,
        };

        if (dialog.ShowDialog(_window) != true)
        {
            return BridgeProtocol.FailResponse(command.Id, new BridgeError(
                BridgeErrorCodes.Cancelled, "The dialog was cancelled."));
        }

        var invalid = BridgeProtocol.ValidateImportZip(dialog.FileName);
        if (invalid is not null)
        {
            return BridgeProtocol.FailResponse(command.Id, invalid);
        }

        // The page cannot read an arbitrary native path, so the shell
        // delivers the bytes it just had the user authorize (capped like
        // save payloads; oversize zips fail honestly instead of truncating).
        byte[] content;
        try
        {
            content = File.ReadAllBytes(dialog.FileName);
        }
        catch (Exception ex)
        {
            return BridgeProtocol.FailResponse(command.Id, new BridgeError(
                BridgeErrorCodes.Failed, $"The file could not be read: {ex.Message}"));
        }

        if (content.Length > BridgeProtocol.MaxContentBytes)
        {
            return BridgeProtocol.FailResponse(command.Id, new BridgeError(
                BridgeErrorCodes.Failed, "The file exceeds 16 MiB."));
        }

        return BridgeProtocol.SuccessResponse(command.Id, BridgeProtocol.OpenFileResult(
            dialog.FileName, Path.GetFileName(dialog.FileName), content.Length,
            Convert.ToBase64String(content)));
    }

    private string ExecuteSaveFile(BridgeCommand command)
    {
        var suggested = command.FileName ?? "export.json";
        var ext = Path.GetExtension(suggested);
        var dialog = new SaveFileDialog
        {
            FileName = suggested,
            Filter = $"{ext} files (*{ext})|*{ext}|All files (*.*)|*.*",
            OverwritePrompt = true,
        };

        if (dialog.ShowDialog(_window) != true)
        {
            return BridgeProtocol.FailResponse(command.Id, new BridgeError(
                BridgeErrorCodes.Cancelled, "The dialog was cancelled."));
        }

        // The user may retype the name in the dialog: re-validate the final
        // choice (bare name, allowlisted extension) before writing a byte.
        var finalName = Path.GetFileName(dialog.FileName);
        var invalid = string.IsNullOrWhiteSpace(finalName)
            ? new BridgeError(BridgeErrorCodes.InvalidPath, "No file name was chosen.")
            : BridgeProtocol.ValidateBareFileName(finalName);
        if (invalid is not null)
        {
            return BridgeProtocol.FailResponse(command.Id, invalid);
        }

        var bytes = command.Content ?? [];
        File.WriteAllBytes(dialog.FileName, bytes);
        return BridgeProtocol.SuccessResponse(command.Id, BridgeProtocol.SaveFileResult(
            dialog.FileName, bytes.Length));
    }

    private string ExecuteGetVersion(BridgeCommand command)
    {
        var server = _serverIdentity();
        return BridgeProtocol.SuccessResponse(command.Id, BridgeProtocol.VersionResult(
            ShellVersion(), server.Version, server.Runtime));
    }

    private string ExecuteWindowControl(BridgeCommand command)
    {
        switch (command.Action)
        {
            case "minimize":
                _window.WindowState = WindowState.Minimized;
                break;
            case "maximize":
                _window.WindowState = WindowState.Maximized;
                break;
            case "restore":
                _window.WindowState = WindowState.Normal;
                break;
            case "close":
                _window.Close();
                break;
            default:
                return BridgeProtocol.FailResponse(command.Id, new BridgeError(
                    BridgeErrorCodes.BadParams, $"Unknown window action '{command.Action}'."));
        }

        return BridgeProtocol.SuccessResponse(command.Id, new { action = command.Action });
    }

    public static string ShellVersion()
    {
        return Assembly.GetExecutingAssembly()
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
            ?.InformationalVersion ?? "0.0.0-dev";
    }
}
