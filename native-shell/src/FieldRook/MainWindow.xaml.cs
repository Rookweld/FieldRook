// FieldRook native shell — main window (M026, section 2).
//
// Standard OS chrome (min/max/restore/close, taskbar, resizing) hosting a
// WebView2 pointed at the loopback backend UI. Owns: the typed JS bridge,
// the loopback navigation guard, .zip drag-and-drop delivery, graceful
// WebView2-missing + backend-crash UX, and fenced shutdown on close.

using System.Windows;
using FieldRook.Backend;
using FieldRook.Bridge;
using FieldRook.Core.Backend;
using FieldRook.Core.Bridge;
using FieldRook.Core.Infrastructure;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;

namespace FieldRook;

public partial class MainWindow : Window
{
    private readonly BackendManager _backend;
    private readonly int _port;
    private BridgeExecutor? _bridge;
    private bool _shuttingDown;

    public MainWindow(BackendManager backend, int port)
    {
        _backend = backend;
        _port = port;
        InitializeComponent();

        _backend.ChildExited += (_, _) => Dispatcher.InvokeAsync(OnBackendExited);
        Closing += OnClosing;
        Drop += OnDrop;
        Loaded += async (_, _) => await InitializeWebViewAsync().ConfigureAwait(true);
    }

    private async Task InitializeWebViewAsync()
    {
        try
        {
            SetStatus("Starting the FieldRook service…", showRetry: false);
            var env = await CoreWebView2Environment.CreateAsync(
                browserExecutableFolder: null,
                userDataFolder: AppPaths.WebView2DataDir()).ConfigureAwait(true);
            await Web.EnsureCoreWebView2Async(env).ConfigureAwait(true);
        }
        catch (WebView2RuntimeNotFoundException)
        {
            AppLogger.Error("WebView2 runtime not found at startup.");
            MessageBox.Show(
                "FieldRook needs the Microsoft Edge WebView2 Runtime, which was not found on this machine." +
                $"{Environment.NewLine}{Environment.NewLine}Install \"Microsoft Edge WebView2 Runtime\" " +
                "(evergreen bootstrapper, per-user is fine) from Microsoft, then start FieldRook again. " +
                "No browser fallback is used: the desktop app only runs in its native host.",
                "WebView2 Runtime is missing",
                MessageBoxButton.OK, MessageBoxImage.Error);
            // The backend is already up: shut it down, then quit for good.
            await Task.Run(() => _backend.Shutdown()).ConfigureAwait(true);
            _shuttingDown = true;
            Closing -= OnClosing;
            Application.Current.Shutdown(1);
            return;
        }
        catch (Exception ex)
        {
            AppLogger.Error($"WebView2 init failed: {ex.Message}");
            SetStatus($"The embedded browser failed to start: {ex.Message}", showRetry: true);
            return;
        }

        Web.CoreWebView2.Settings.AreDefaultContextMenusEnabled = true;
        Web.CoreWebView2.Settings.IsStatusBarEnabled = false;
        Web.CoreWebView2.NavigationStarting += OnNavigationStarting;
        Web.CoreWebView2.WebMessageReceived += OnWebMessage;
        Web.CoreWebView2.NavigationCompleted += OnNavigationCompleted;
        Web.CoreWebView2.ProcessFailed += OnWebViewProcessFailed;

        _bridge = new BridgeExecutor(this, () => _backend.LastIdentity);
        SetStatus("Loading the FieldRook workspace…", showRetry: false);
        Web.Source = new Uri($"http://127.0.0.1:{_port}/");
    }

    private void OnNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs e)
    {
        // Contract: no navigation outside loopback — block + log.
        if (!NavigationGuard.IsAllowed(e.Uri))
        {
            e.Cancel = true;
            AppLogger.Warn($"Blocked non-loopback navigation: {e.Uri}");
            SetStatusOverlayOnly("Blocked a navigation outside the local app.");
        }
    }

    private void OnNavigationCompleted(object? sender, CoreWebView2NavigationCompletedEventArgs e)
    {
        if (e.IsSuccess)
        {
            Overlay.Visibility = Visibility.Collapsed;
        }
        else
        {
            AppLogger.Warn($"Navigation failed: {e.WebErrorStatus}");
            SetStatus($"Could not load the workspace ({e.WebErrorStatus}). Is the service still running?", showRetry: true);
        }
    }

    private void OnWebViewProcessFailed(object? sender, CoreWebView2ProcessFailedEventArgs e)
    {
        AppLogger.Error($"WebView2 process failed: {e.ProcessFailedKind} ({e.Reason})");
        SetStatus("The embedded browser stopped unexpectedly. Retry to reload.", showRetry: true);
    }

    private void OnWebMessage(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
    {
        if (_bridge is null)
        {
            return;
        }

        string response;
        try
        {
            var body = e.WebMessageAsJson;
            if (!BridgeProtocol.TryParse(body, out var command, out var error) || command is null)
            {
                error ??= new BridgeError(BridgeErrorCodes.BadEnvelope, "Malformed bridge message.");
                AppLogger.Warn($"Bridge rejected message ({error.Code}): {error.Message}");
                response = BridgeProtocol.FailResponse(ExtractIdOrEmpty(body), error);
            }
            else
            {
                response = _bridge.Execute(command);
            }
        }
        catch (Exception ex)
        {
            AppLogger.Warn($"Bridge dispatch failed: {ex.Message}");
            response = BridgeProtocol.FailResponse(string.Empty, new BridgeError(
                BridgeErrorCodes.Failed, "The operation failed."));
        }

        try
        {
            Web.CoreWebView2.PostWebMessageAsJson(response);
        }
        catch (Exception ex)
        {
            AppLogger.Warn($"Bridge response post failed: {ex.Message}");
        }
    }

    private void OnDrop(object sender, DragEventArgs e)
    {
        if (!e.Data.GetDataPresent(DataFormats.FileDrop))
        {
            return;
        }

        var files = (string[])e.Data.GetData(DataFormats.FileDrop);
        if (files.Length != 1)
        {
            MessageBox.Show("Drop a single .zip collector package.", "FieldRook", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        var invalid = BridgeProtocol.ValidateImportZip(files[0]);
        if (invalid is not null)
        {
            AppLogger.Warn($"Rejected dropped file '{files[0]}': {invalid.Message}");
            MessageBox.Show(invalid.Message, "FieldRook", MessageBoxButton.OK, MessageBoxImage.Information);
            return;
        }

        // Same validated channel the importer bridge uses (GAMMA consumes).
        try
        {
            Web.CoreWebView2?.PostWebMessageAsJson(BridgeProtocol.FileDeliveredMessage(files[0]));
            AppLogger.Info($"Delivered dropped file to importer: {files[0]}");
        }
        catch (Exception ex)
        {
            AppLogger.Warn($"Drop delivery failed: {ex.Message}");
        }
    }

    private void OnBackendExited()
    {
        if (_shuttingDown)
        {
            return;
        }

        AppLogger.Error("Backend child exited unexpectedly.");
        var tail = string.Join(Environment.NewLine, AppPaths.TailLog(_backend.ServerErrLog));
        SetStatus("The FieldRook service stopped unexpectedly.", showRetry: true);
        MessageBox.Show(
            $"The FieldRook service stopped unexpectedly.{Environment.NewLine}{Environment.NewLine}" +
            $"--- server log ---{Environment.NewLine}{tail}",
            "FieldRook service stopped",
            MessageBoxButton.OK, MessageBoxImage.Error);
    }

    private async void OnRetryClick(object sender, RoutedEventArgs e)
    {
        SetStatus("Retrying…", showRetry: false);
        try
        {
            using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
            await _backend.WaitForHealthyAsync(30, cts.Token).ConfigureAwait(true);
            if (Web.CoreWebView2 is not null)
            {
                Web.CoreWebView2.Navigate($"http://127.0.0.1:{_port}/");
            }
            else
            {
                await InitializeWebViewAsync().ConfigureAwait(true);
            }
        }
        catch (Exception ex)
        {
            SetStatus($"Still unavailable: {ex.Message}", showRetry: true);
        }
    }

    private async void OnClosing(object? sender, System.ComponentModel.CancelEventArgs e)
    {
        if (_shuttingDown)
        {
            return;
        }

        e.Cancel = true;
        _shuttingDown = true;
        SetStatusOverlayOnly("Stopping the FieldRook service…");
        Overlay.Visibility = Visibility.Visible;
        try
        {
            await Task.Run(() => _backend.Shutdown()).ConfigureAwait(true);
        }
        catch (Exception ex)
        {
            AppLogger.Warn($"Shutdown error (continuing): {ex.Message}");
        }

        CloseForGood();
    }

    /// <summary>Real close: detaches the guard so OnClosing lets go.</summary>
    private void CloseForGood()
    {
        _shuttingDown = true;
        Closing -= OnClosing;
        Close();
    }

    private void SetStatus(string text, bool showRetry)
    {
        Overlay.Visibility = Visibility.Visible;
        StatusText.Text = text;
        RetryButton.Visibility = showRetry ? Visibility.Visible : Visibility.Collapsed;
    }

    private void SetStatusOverlayOnly(string text)
    {
        StatusText.Text = text;
        RetryButton.Visibility = Visibility.Collapsed;
    }

    private static string ExtractIdOrEmpty(string body)
    {
        try
        {
            using var doc = System.Text.Json.JsonDocument.Parse(body);
            if (doc.RootElement.ValueKind == System.Text.Json.JsonValueKind.Object &&
                doc.RootElement.TryGetProperty("id", out var id) &&
                id.ValueKind == System.Text.Json.JsonValueKind.String)
            {
                return id.GetString() ?? string.Empty;
            }
        }
        catch (Exception)
        {
            // Unparseable: answer with an empty id.
        }

        return string.Empty;
    }
}
