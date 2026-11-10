using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Input;
using System.Windows.Interop;
using System.Windows.Media.Animation;
using System.Windows.Threading;

namespace Whisper.Preview;

public partial class ReferenceToast : Window
{
    private readonly Action openReference;
    private readonly Window anchor;
    private readonly DispatcherTimer dismissal = new() { Interval = TimeSpan.FromSeconds(9) };
    private bool closing;

    internal ReferenceToast(Window anchor, string title, string body, string source, Action openReference)
    {
        this.anchor = anchor;
        this.openReference = openReference;
        InitializeComponent();
        TopicTitle.Text = title;
        TopicBody.Text = body;
        TopicSource.Text = source;
        var bounds = anchor.WindowState == WindowState.Minimized ? anchor.RestoreBounds : new Rect(anchor.Left, anchor.Top, anchor.Width, anchor.Height);
        Left = bounds.Left;
        Top = bounds.Top;
        SourceInitialized += PreventActivation;
        ContentRendered += Present;
        dismissal.Tick += Expire;
    }

    private void PreventActivation(object? sender, EventArgs args)
    {
        var handle = new WindowInteropHelper(this).Handle;
        nint style = GetWindowLongPtrW(handle, -20);
        SetWindowLongPtrW(handle, -20, style | 0x08000000 | 0x00000080);
    }

    private void Present(object? sender, EventArgs args)
    {
        var handle = new WindowInteropHelper(this).Handle;
        var monitor = MonitorFromWindow(new WindowInteropHelper(anchor).Handle, 2);
        var info = new MonitorInfo { Size = Marshal.SizeOf<MonitorInfo>() };
        if (GetMonitorInfoW(monitor, ref info))
        {
            double scale = GetDpiForWindow(handle) / 96.0;
            int width = (int)Math.Ceiling(ActualWidth * scale);
            int height = (int)Math.Ceiling(ActualHeight * scale);
            int gap = (int)Math.Round(12 * scale);
            SetWindowPos(handle, new nint(-1), info.Work.Right - width - gap, info.Work.Bottom - height - gap,
                width, height, 0x0010);
        }
        BeginAnimation(OpacityProperty, new DoubleAnimation(0, 1, TimeSpan.FromMilliseconds(180)));
        Slide.BeginAnimation(System.Windows.Media.TranslateTransform.YProperty,
            new DoubleAnimation(10, 0, TimeSpan.FromMilliseconds(180)) { EasingFunction = new QuadraticEase { EasingMode = EasingMode.EaseOut } });
        dismissal.Start();
    }

    private void PauseDismissal(object sender, MouseEventArgs args) => dismissal.Stop();

    private void ResumeDismissal(object sender, MouseEventArgs args)
    {
        if (!closing) dismissal.Start();
    }

    private void Expire(object? sender, EventArgs args) => FadeOut();

    private void Dismiss(object sender, RoutedEventArgs args) => FadeOut();

    private void FadeOut()
    {
        if (closing) return;
        closing = true;
        dismissal.Stop();
        var fade = new DoubleAnimation(0, TimeSpan.FromMilliseconds(140));
        fade.Completed += (_, _) => { if (IsVisible) Close(); };
        BeginAnimation(OpacityProperty, fade);
    }

    private void OpenReference(object sender, RoutedEventArgs args)
    {
        Close();
        openReference();
    }

    protected override void OnClosed(EventArgs args)
    {
        closing = true;
        dismissal.Stop();
        dismissal.Tick -= Expire;
        base.OnClosed(args);
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct NativeRect { public int Left, Top, Right, Bottom; }

    [StructLayout(LayoutKind.Sequential)]
    private struct MonitorInfo { public int Size; public NativeRect Monitor, Work; public uint Flags; }

    [DllImport("user32.dll")]
    private static extern nint GetWindowLongPtrW(nint window, int index);
    [DllImport("user32.dll")]
    private static extern nint SetWindowLongPtrW(nint window, int index, nint value);
    [DllImport("user32.dll")]
    private static extern nint MonitorFromWindow(nint window, uint flags);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetMonitorInfoW(nint monitor, ref MonitorInfo info);
    [DllImport("user32.dll")]
    private static extern uint GetDpiForWindow(nint window);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetWindowPos(nint window, nint insertAfter, int x, int y, int width, int height, uint flags);
}
