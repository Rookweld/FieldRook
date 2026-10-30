// FieldRook native shell — JS bridge protocol (M026 contracts, section 2).
//
// WebView2 navigates to the loopback backend that serves the React UI.
// The JS side posts typed JSON messages {op, id, params} and the shell
// answers {id, ok, result | error}. Allowed ops ONLY:
//   openFile, saveFile, getVersion, windowControl.
// Everything else fails closed: unknown op, malformed envelope, path
// traversal, or non-.zip imports are rejected, never executed.
//
// This file is pure (no UI, no IO): every rule here is unit-tested in
// FieldRook.Bridge.Tests. Execution of validated commands lives in the
// WPF app (BridgeExecutor).

using System.Text.Json;
using System.Text.Json.Serialization;

namespace FieldRook.Core.Bridge;

public static class BridgeOps
{
    public const string OpenFile = "openFile";
    public const string SaveFile = "saveFile";
    public const string GetVersion = "getVersion";
    public const string WindowControl = "windowControl";
}

public static class BridgeErrorCodes
{
    public const string UnknownOp = "unknown_op";
    public const string BadEnvelope = "bad_envelope";
    public const string BadParams = "bad_params";
    public const string InvalidPath = "invalid_path";
    public const string Cancelled = "cancelled";
    public const string Failed = "failed";
}

/// <summary>Validated, ready-to-execute bridge command.</summary>
public sealed record BridgeCommand(string Op, string Id)
{
    // openFile: optional dialog title supplied by the page.
    public string? DialogTitle { get; init; }

    // saveFile: bare file name + payload bytes (base64 in transit).
    public string? FileName { get; init; }
    public byte[]? Content { get; init; }

    // windowControl: minimize | maximize | restore | close.
    public string? Action { get; init; }
}

public sealed record BridgeError(string Code, string Message);

public static class BridgeProtocol
{
    public const int MaxEnvelopeBytes = 256 * 1024;
    public const int MaxContentBytes = 64 * 1024 * 1024;
    public const int MaxFileNameLength = 180;
    public const int MaxIdLength = 128;

    private static readonly HashSet<string> WindowActions = new(StringComparer.Ordinal)
    {
        "minimize", "maximize", "restore", "close",
    };

    private static readonly HashSet<string> SaveExtensions = new(StringComparer.OrdinalIgnoreCase)
    {
        ".zip", ".json", ".md", ".txt", ".csv", ".log",
    };

    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    /// <summary>
    /// Parse + validate one bridge envelope. Returns a command on success;
    /// any failure (unknown op, bad params, traversal, oversize) returns an
    /// error and no command — the caller must never execute on error.
    /// </summary>
    public static bool TryParse(string json, out BridgeCommand? command, out BridgeError? error)
    {
        command = null;
        error = new BridgeError(BridgeErrorCodes.BadEnvelope, "Malformed bridge message.");

        if (string.IsNullOrWhiteSpace(json) || json.Length > MaxEnvelopeBytes + 1024)
        {
            error = new BridgeError(BridgeErrorCodes.BadEnvelope, "Empty or oversize bridge message.");
            return false;
        }

        JsonDocument doc;
        try
        {
            doc = JsonDocument.Parse(json);
        }
        catch (JsonException)
        {
            error = new BridgeError(BridgeErrorCodes.BadEnvelope, "Message is not valid JSON.");
            return false;
        }

        using (doc)
        {
            var root = doc.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                return false;
            }

            if (!TryGetString(root, "op", out var op) || string.IsNullOrWhiteSpace(op))
            {
                return false;
            }

            if (!TryGetString(root, "id", out var id) || string.IsNullOrWhiteSpace(id) || id.Length > MaxIdLength)
            {
                error = new BridgeError(BridgeErrorCodes.BadEnvelope, "Message id is missing or invalid.");
                return false;
            }

            var paramsElement = root.TryGetProperty("params", out var p) && p.ValueKind == JsonValueKind.Object
                ? p
                : (JsonElement?)null;

            switch (op)
            {
                case BridgeOps.OpenFile:
                    return TryOpenFile(id, paramsElement, out command, out error);
                case BridgeOps.SaveFile:
                    return TrySaveFile(id, paramsElement, out command, out error);
                case BridgeOps.GetVersion:
                    command = new BridgeCommand(BridgeOps.GetVersion, id);
                    error = null;
                    return true;
                case BridgeOps.WindowControl:
                    return TryWindowControl(id, paramsElement, out command, out error);
                default:
                    error = new BridgeError(BridgeErrorCodes.UnknownOp, $"Unknown bridge op '{op}'.");
                    return false;
            }
        }
    }

    private static bool TryOpenFile(string id, JsonElement? paramsElement, out BridgeCommand? command, out BridgeError? error)
    {
        command = null;
        error = null;
        string? title = null;
        if (paramsElement is { } ps && ps.TryGetProperty("title", out var t))
        {
            if (t.ValueKind != JsonValueKind.String)
            {
                error = new BridgeError(BridgeErrorCodes.BadParams, "openFile.title must be a string.");
                return false;
            }

            title = t.GetString();
            if (title is not null && title.Length > 120)
            {
                error = new BridgeError(BridgeErrorCodes.BadParams, "openFile.title is too long.");
                return false;
            }
        }

        command = new BridgeCommand(BridgeOps.OpenFile, id) { DialogTitle = title };
        return true;
    }

    private static bool TrySaveFile(string id, JsonElement? paramsElement, out BridgeCommand? command, out BridgeError? error)
    {
        command = null;
        error = null;
        if (paramsElement is not { } ps)
        {
            error = new BridgeError(BridgeErrorCodes.BadParams, "saveFile.params is required.");
            return false;
        }

        if (!TryGetString(ps, "fileName", out var fileName) || string.IsNullOrWhiteSpace(fileName))
        {
            error = new BridgeError(BridgeErrorCodes.BadParams, "saveFile.fileName is required.");
            return false;
        }

        var nameError = ValidateBareFileName(fileName, SaveExtensions);
        if (nameError is not null)
        {
            error = nameError;
            return false;
        }

        if (!TryGetString(ps, "contentBase64", out var b64) || string.IsNullOrEmpty(b64))
        {
            error = new BridgeError(BridgeErrorCodes.BadParams, "saveFile.contentBase64 is required.");
            return false;
        }

        byte[] content;
        try
        {
            content = Convert.FromBase64String(b64);
        }
        catch (FormatException)
        {
            error = new BridgeError(BridgeErrorCodes.BadParams, "saveFile.contentBase64 is not valid base64.");
            return false;
        }

        if (content.Length == 0 || content.Length > MaxContentBytes)
        {
            error = new BridgeError(BridgeErrorCodes.BadParams, "saveFile payload is empty or exceeds 64 MiB.");
            return false;
        }

        command = new BridgeCommand(BridgeOps.SaveFile, id) { FileName = fileName, Content = content };
        return true;
    }

    private static bool TryWindowControl(string id, JsonElement? paramsElement, out BridgeCommand? command, out BridgeError? error)
    {
        command = null;
        error = null;
        if (paramsElement is not { } ps || !TryGetString(ps, "action", out var action) || string.IsNullOrWhiteSpace(action))
        {
            error = new BridgeError(BridgeErrorCodes.BadParams, "windowControl.action is required.");
            return false;
        }

        if (!WindowActions.Contains(action))
        {
            error = new BridgeError(BridgeErrorCodes.BadParams, $"Unknown window action '{action}'.");
            return false;
        }

        command = new BridgeCommand(BridgeOps.WindowControl, id) { Action = action };
        return true;
    }

    /// <summary>
    /// A save/export name must be a bare file name: no directories, no
    /// traversal, no reserved device names, allowlisted extension.
    /// Returns null when valid, otherwise the fail-closed error.
    /// </summary>
    public static BridgeError? ValidateBareFileName(string fileName, ISet<string>? allowedExtensions = null)
    {
        if (string.IsNullOrWhiteSpace(fileName) || fileName.Length > MaxFileNameLength)
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, "File name is missing or too long.");
        }

        if (fileName.Contains('/') || fileName.Contains('\\') || fileName.Contains("..") ||
            fileName.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0)
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, "File name must not contain path separators.");
        }

        var stem = Path.GetFileNameWithoutExtension(fileName);
        if (IsReservedDeviceName(stem))
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, "Reserved file name.");
        }

        var ext = Path.GetExtension(fileName);
        var allow = allowedExtensions ?? SaveExtensions;
        if (string.IsNullOrEmpty(ext) || !allow.Contains(ext))
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, $"File extension '{ext}' is not allowed.");
        }

        return null;
    }

    /// <summary>
    /// Import/drop candidates must be existing .zip files. The dialog/drop
    /// result is an absolute path; this re-validates it before delivery.
    /// </summary>
    public static BridgeError? ValidateImportZip(string? path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, "No file was provided.");
        }

        string full;
        try
        {
            full = Path.GetFullPath(path);
        }
        catch (Exception)
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, "File path is not valid.");
        }

        if (!string.Equals(Path.GetExtension(full), ".zip", StringComparison.OrdinalIgnoreCase))
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, "Only .zip collector packages can be imported.");
        }

        if (!File.Exists(full))
        {
            return new BridgeError(BridgeErrorCodes.InvalidPath, "File does not exist.");
        }

        return null;
    }

    public static string SuccessResponse(string id, object? result)
    {
        return JsonSerializer.Serialize(new { id, ok = true, result }, JsonOptions);
    }

    public static string FailResponse(string id, BridgeError error)
    {
        return JsonSerializer.Serialize(
            new { id, ok = false, error = new { code = error.Code, message = error.Message } },
            JsonOptions);
    }

    /// <summary>File-delivery notice posted to the page after a validated drop.</summary>
    public static string FileDeliveredMessage(string path)
    {
        return JsonSerializer.Serialize(
            new { kind = "fieldrook:file", fileName = Path.GetFileName(path), path },
            JsonOptions);
    }

    private static bool TryGetString(JsonElement element, string name, out string value)
    {
        value = string.Empty;
        if (!element.TryGetProperty(name, out var prop) || prop.ValueKind != JsonValueKind.String)
        {
            return false;
        }

        value = prop.GetString() ?? string.Empty;
        return true;
    }

    private static bool IsReservedDeviceName(string? stem)
    {
        if (string.IsNullOrEmpty(stem))
        {
            return true;
        }

        var upper = stem.ToUpperInvariant();
        if (upper is "CON" or "PRN" or "AUX" or "NUL")
        {
            return true;
        }

        if ((upper.StartsWith("COM", StringComparison.Ordinal) || upper.StartsWith("LPT", StringComparison.Ordinal)) &&
            upper.Length == 4 && char.IsDigit(upper[3]) && upper[3] != '0')
        {
            return true;
        }

        return false;
    }
}
