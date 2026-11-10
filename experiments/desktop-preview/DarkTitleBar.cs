using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace Whisper.Preview;

/// <summary>Pinta a barra de título nativa com as cores do tema (Windows 10 20H1+; cores próprias no Windows 11).</summary>
internal static class DarkTitleBar
{
    private const int UseImmersiveDarkMode = 20;
    private const int BorderColor = 34;
    private const int CaptionColor = 35;
    private const int TextColor = 36;

    [DllImport("dwmapi.dll")]
    private static extern int DwmSetWindowAttribute(IntPtr hwnd, int attribute, ref int value, int size);

    public static void Apply(Window window)
    {
        window.SourceInitialized += (_, _) =>
        {
            IntPtr handle = new WindowInteropHelper(window).Handle;
            Set(handle, UseImmersiveDarkMode, 1);
            Set(handle, CaptionColor, 0x131711);  // #111713 (COLORREF = 0xBBGGRR)
            Set(handle, TextColor, 0xE9F3F2);     // #F2F3E9
            Set(handle, BorderColor, 0x3C4836);   // #36483C
        };
    }

    private static void Set(IntPtr handle, int attribute, int value)
    {
        try
        {
            _ = DwmSetWindowAttribute(handle, attribute, ref value, sizeof(int));
        }
        catch (Exception ex) when (ex is DllNotFoundException or EntryPointNotFoundException)
        {
            // Sistema sem suporte: mantém a barra padrão.
        }
    }
}
