// FieldRook native shell — bridge command execution (M026, section 2).
//
// Runs validated BridgeCommands (see FieldRook.Core): native file dialogs
// for .zip import / export, version reporting, standard-chrome window
// control. Every path is re-validated at execution time; failures answer
// {ok:false} and never touch the filesystem outside dialog results.

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

        return BridgeProtocol.SuccessResponse(command.Id, new { path = dialog.FileName });
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

        File.WriteAllBytes(dialog.FileName, command.Content ?? []);
        return BridgeProtocol.SuccessResponse(command.Id, new { path = dialog.FileName });
    }

    private string ExecuteGetVersion(BridgeCommand command)
    {
        var server = _serverIdentity();
        return BridgeProtocol.SuccessResponse(command.Id, new
        {
            shell = ShellVersion(),
            server = server.Version,
            runtime = server.Runtime,
        });
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
