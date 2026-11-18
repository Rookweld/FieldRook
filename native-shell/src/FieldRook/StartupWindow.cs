// M035 — honest startup feedback before the local backend becomes healthy.
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace FieldRook;

internal sealed class StartupWindow : Window
{
    private readonly TextBlock _phase;

    public StartupWindow()
    {
        Title = "FieldRook — Starting";
        Width = 520;
        Height = 270;
        MinWidth = 520;
        MinHeight = 270;
        MaxWidth = 520;
        MaxHeight = 270;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        ResizeMode = ResizeMode.NoResize;
        Background = Brush(0x18, 0x12, 0x22);
        Foreground = Brush(0xF1, 0xE9, 0xE0);

        var panel = new StackPanel { Margin = new Thickness(32, 24, 32, 20) };
        panel.Children.Add(new TextBlock
        {
            Text = "FieldRook",
            FontSize = 36,
            FontWeight = FontWeights.Bold,
            Foreground = Brush(0xFF, 0x74, 0x57),
        });
        panel.Children.Add(new TextBlock
        {
            Text = "Preparing your local technician workspace",
            FontSize = 14,
            Margin = new Thickness(0, 6, 0, 0),
        });

        _phase = new TextBlock
        {
            Text = "Checking local service…",
            FontSize = 13,
            Foreground = Brush(0xC0, 0xB7, 0xB4),
            Margin = new Thickness(0, 26, 0, 0),
            TextWrapping = TextWrapping.Wrap,
        };
        panel.Children.Add(_phase);
        panel.Children.Add(new TextBlock
        {
            Text = "Your investigations and settings remain on this computer.",
            FontSize = 11,
            Foreground = Brush(0xA9, 0xA0, 0xA5),
            Margin = new Thickness(0, 12, 0, 0),
        });

        var cancel = new Button
        {
            Content = "Cancel startup",
            Width = 130,
            Height = 30,
            HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 14, 0, 0),
        };
        cancel.Click += (_, _) => Close();
        panel.Children.Add(cancel);
        Content = panel;
    }

    public void SetPhase(string message) => _phase.Text = message;

    private static SolidColorBrush Brush(byte red, byte green, byte blue) =>
        new(Color.FromRgb(red, green, blue));
}
