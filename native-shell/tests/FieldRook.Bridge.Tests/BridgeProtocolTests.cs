// FieldRook native shell — bridge contract tests (M026, section 2).
//
// Roundtrip each allowlisted op in isolation; an unknown op and every
// path-traversal payload MUST fail closed.

using System.Text;
using System.Text.Json;
using FieldRook.Core.Bridge;
using Xunit;

namespace FieldRook.Bridge.Tests;

public sealed class BridgeProtocolTests
{
    [Fact]
    public void OpenFile_Roundtrips_WithOptionalTitle()
    {
        var ok = BridgeProtocol.TryParse(
            """{"op":"openFile","id":"a1","params":{"title":"Import package"}}""",
            out var command, out var error);

        Assert.True(ok);
        Assert.Null(error);
        Assert.NotNull(command);
        Assert.Equal(BridgeOps.OpenFile, command.Op);
        Assert.Equal("a1", command.Id);
        Assert.Equal("Import package", command.DialogTitle);
    }

    [Fact]
    public void OpenFile_Roundtrips_WithoutParams()
    {
        var ok = BridgeProtocol.TryParse(
            """{"op":"openFile","id":"a2"}""",
            out var command, out var error);

        Assert.True(ok);
        Assert.Null(error);
        Assert.NotNull(command);
        Assert.Null(command.DialogTitle);
    }

    [Fact]
    public void SaveFile_Roundtrips_ValidPayload()
    {
        var payload = Convert.ToBase64String(Encoding.UTF8.GetBytes("hello"));
        var json = JsonSerializer.Serialize(new
        {
            op = "saveFile",
            id = "s1",
            @params = new { fileName = "export.json", contentBase64 = payload },
        });
        var ok = BridgeProtocol.TryParse(json, out var command, out var error);

        Assert.True(ok);
        Assert.Null(error);
        Assert.NotNull(command);
        Assert.Equal("export.json", command.FileName);
        Assert.Equal("hello", Encoding.UTF8.GetString(command.Content!));
    }

    [Fact]
    public void GetVersion_Roundtrips()
    {
        var ok = BridgeProtocol.TryParse(
            """{"op":"getVersion","id":"v1"}""",
            out var command, out var error);

        Assert.True(ok);
        Assert.Null(error);
        Assert.NotNull(command);
        Assert.Equal(BridgeOps.GetVersion, command.Op);
    }

    [Theory]
    [InlineData("minimize")]
    [InlineData("maximize")]
    [InlineData("restore")]
    [InlineData("close")]
    public void WindowControl_Roundtrips_EachAction(string action)
    {
        var json = JsonSerializer.Serialize(new
        {
            op = "windowControl",
            id = "w1",
            @params = new { action },
        });
        var ok = BridgeProtocol.TryParse(json, out var command, out var error);

        Assert.True(ok);
        Assert.Null(error);
        Assert.NotNull(command);
        Assert.Equal(action, command.Action);
    }

    [Fact]
    public void UnknownOp_FailsClosed()
    {
        var ok = BridgeProtocol.TryParse(
            """{"op":"eval","id":"e1","params":{"code":"1+1"}}""",
            out var command, out var error);

        Assert.False(ok);
        Assert.Null(command);
        Assert.NotNull(error);
        Assert.Equal(BridgeErrorCodes.UnknownOp, error.Code);
    }

    [Theory]
    [InlineData("""{"op":"windowControl","id":"w2","params":{"action":"fullscreen"}}""")]
    [InlineData("""{"op":"windowControl","id":"w3"}""")]
    [InlineData("""{"op":"saveFile","id":"s2"}""")]
    [InlineData("""{"op":"saveFile","id":"s3","params":{"fileName":"x.json"}}""")]
    [InlineData("""{"op":"saveFile","id":"s4","params":{"fileName":"x.json","contentBase64":"!!!"}}""")]
    [InlineData("""{"op":"openFile","id":"o9","params":{"title":42}}""")]
    public void BadParams_FailClosed(string json)
    {
        var ok = BridgeProtocol.TryParse(json, out var command, out var error);

        Assert.False(ok);
        Assert.Null(command);
        Assert.NotNull(error);
        Assert.Equal(BridgeErrorCodes.BadParams, error.Code);
    }

    [Theory]
    [InlineData("""{"op":"nope"}""")]
    [InlineData("""{"id":"x"}""")]
    [InlineData("""{"op":"getVersion"}""")]
    [InlineData("not json at all")]
    [InlineData("[1,2,3]")]
    [InlineData("")]
    public void BadEnvelopes_FailClosed(string json)
    {
        var ok = BridgeProtocol.TryParse(json, out var command, out var error);

        Assert.False(ok);
        Assert.Null(command);
        Assert.NotNull(error);
        Assert.Equal(BridgeErrorCodes.BadEnvelope, error.Code);
    }

    [Theory]
    [InlineData("../evil.json")]
    [InlineData("..\\evil.json")]
    [InlineData("sub/dir/export.json")]
    [InlineData("sub\\dir\\export.json")]
    [InlineData("C:\\temp\\export.json")]
    [InlineData("/tmp/export.json")]
    [InlineData("....//evil.json")]
    public void SaveFile_TraversalNames_FailClosed(string fileName)
    {
        var payload = Convert.ToBase64String("x"u8.ToArray());
        var json = JsonSerializer.Serialize(new
        {
            op = "saveFile",
            id = "t1",
            @params = new { fileName, contentBase64 = payload },
        });

        var ok = BridgeProtocol.TryParse(json, out var command, out var error);

        Assert.False(ok);
        Assert.Null(command);
        Assert.NotNull(error);
        Assert.Equal(BridgeErrorCodes.InvalidPath, error.Code);
    }

    [Theory]
    [InlineData("export.exe")]
    [InlineData("run.bat")]
    [InlineData("noextension")]
    [InlineData("CON.json")]
    [InlineData("nul.txt")]
    [InlineData("COM1.log")]
    public void SaveFile_DangerousNames_FailClosed(string fileName)
    {
        Assert.NotNull(BridgeProtocol.ValidateBareFileName(fileName));
    }

    [Fact]
    public void ImportZip_RejectsNonZip_AndMissingFiles()
    {
        Assert.NotNull(BridgeProtocol.ValidateImportZip("C:\\temp\\notes.txt"));
        Assert.NotNull(BridgeProtocol.ValidateImportZip("C:\\temp\\nope.zip"));
        Assert.NotNull(BridgeProtocol.ValidateImportZip(""));
        Assert.NotNull(BridgeProtocol.ValidateImportZip(null));
    }

    [Fact]
    public void ImportZip_AcceptsExistingZip()
    {
        var path = Path.Combine(Path.GetTempPath(), $"fr-test-{Guid.NewGuid():N}.zip");
        File.WriteAllBytes(path, [0x50, 0x4B, 0x03, 0x04]);
        try
        {
            Assert.Null(BridgeProtocol.ValidateImportZip(path));
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void SizeCaps_AreConsistent()
    {
        // The envelope must fit the largest saveFile payload (base64 4/3).
        Assert.True(BridgeProtocol.MaxEnvelopeBytes > BridgeProtocol.MaxContentBytes * 4 / 3);
    }

    [Fact]
    public void Responses_CarryIdAndShape()
    {
        var success = BridgeProtocol.SuccessResponse("k1", new { path = "C:\\x.zip" });
        using var okDoc = JsonDocument.Parse(success);
        Assert.Equal("k1", okDoc.RootElement.GetProperty("id").GetString());
        Assert.True(okDoc.RootElement.GetProperty("ok").GetBoolean());

        var failure = BridgeProtocol.FailResponse("k2", new BridgeError("unknown_op", "nope"));
        using var errDoc = JsonDocument.Parse(failure);
        Assert.Equal("k2", errDoc.RootElement.GetProperty("id").GetString());
        Assert.False(errDoc.RootElement.GetProperty("ok").GetBoolean());
        Assert.Equal("unknown_op", errDoc.RootElement.GetProperty("error").GetProperty("code").GetString());
    }
}
