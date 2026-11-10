using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Markup;
using System.Windows.Media;
using Entry = Whisper.Preview.VaesenCatalog.Entry;

namespace Whisper.Preview;

public partial class VaesenLibrary : Window
{
    private readonly VaesenCatalog catalog;
    private bool filtersReady;
    private Entry? readerRow;
    private bool showOriginal;

    internal VaesenLibrary(VaesenCatalog catalog, string? book = null, int? page = null, string? query = null, string? topicTitle = null)
    {
        this.catalog = catalog;
        InitializeComponent();
        Query.Text = query ?? "";
        var filters = new List<FilterChoice> { new(null, "Todos os livros") };
        filters.AddRange(catalog.Books.Select(source => new FilterChoice(source.Id, source.Title)));
        BookFilter.ItemsSource = filters;
        BookFilter.DisplayMemberPath = nameof(FilterChoice.Title);
        BookFilter.SelectedValuePath = nameof(FilterChoice.Id);
        BookFilter.SelectedIndex = book is null ? 0 : Math.Max(0, filters.FindIndex(item => item.Id == book));
        var categories = new List<FilterChoice> { new(null, "Todas as categorias") };
        categories.AddRange(catalog.Categories.Select(category => new FilterChoice(category, category)));
        CategoryFilter.ItemsSource = categories;
        CategoryFilter.DisplayMemberPath = nameof(FilterChoice.Title);
        CategoryFilter.SelectedValuePath = nameof(FilterChoice.Id);
        CategoryFilter.SelectedIndex = 0;
        filtersReady = true;
        Search();
        var rows = Results.Items.OfType<Entry>();
        string? titleKey = topicTitle is null ? null : VaesenCatalog.Normalize(topicTitle);
        var matchingTitle = titleKey is null ? null : rows.FirstOrDefault(row => row.Topic.SearchNames.Contains(titleKey) &&
            (page is null || row.Page.Page.Number <= page && (row.Topic.ThroughPage ?? row.Page.Page.Number) >= page));
        var selected = matchingTitle ?? rows.FirstOrDefault(row => row.Page.Page.Number == page);
        if (selected is not null)
        {
            Results.SelectedItem = selected;
            Results.ScrollIntoView(selected);
        }
    }

    private void Search()
    {
        string? category = CategoryFilter.SelectedValue as string;
        bool optionalOnly = OptionalOnly.IsChecked == true;
        var matches = catalog.Search(Query.Text, BookFilter.SelectedValue as string, optionalOnly, category);
        Results.ItemsSource = matches;
        ResultCount.Text = matches.Length == 1 ? "1 tópico" : $"{matches.Length} tópicos";
        if (matches.Length > 0)
        {
            Results.SelectedIndex = 0;
        }
        else
        {
            ReaderTitle.Text = "Nenhuma referência encontrada";
            ReaderSource.Text = "";
            ReaderLocation.Text = "";
            ReaderNote.Visibility = Visibility.Collapsed;
            ReaderSummaryPanel.Visibility = Visibility.Collapsed;
            PageText.Document = CreateDocument([new ReferenceText.Block(ReferenceText.Kind.Paragraph, "Tente outro termo ou ajuste os filtros.")]);
            readerRow = null;
            ReadingLanguage.Text = "";
            ToggleLanguageButton.Visibility = Visibility.Collapsed;
            OpenPdfButton.IsEnabled = false;
        }
    }

    private void RunSearch(object sender, RoutedEventArgs args) => Search();

    private void SubmitQuery(object sender, KeyEventArgs args)
    {
        if (args.Key == Key.Enter)
        {
            Search();
            args.Handled = true;
        }
    }

    private void RefreshFilter(object sender, RoutedEventArgs args)
    {
        if (filtersReady)
        {
            Search();
        }
    }

    private void SelectPage(object sender, RoutedEventArgs args)
    {
        if (Results.SelectedItem is Entry row)
        {
            DisplayPage(row);
        }
    }

    private void DisplayPage(Entry row)
    {
        readerRow = row;
        showOriginal = false;
        var item = row.Page;
        ReaderTitle.Text = row.Title;
        ReaderSource.Text = item.Book.Title;
        ReaderLocation.Text = row.Topic.ThroughPage is int end ? $"{row.PageLabel} · PDF {item.Page.Number}–{end}" :
            $"{row.PageLabel} · PDF {item.Page.Number}";
        ReaderNote.Text = row.Note;
        ReaderNote.Visibility = string.IsNullOrEmpty(ReaderNote.Text) ? Visibility.Collapsed : Visibility.Visible;
        ReaderSummary.Text = row.Topic.Summary;
        SetPageText(row);
        OpenPdfButton.IsEnabled = true;
    }

    private void ToggleLanguage(object sender, RoutedEventArgs args)
    {
        if (readerRow is { } row)
        {
            showOriginal = !showOriginal;
            SetPageText(row);
        }
    }

    private void SetPageText(Entry row)
    {
        var item = row.Page;
        bool canTranslate = row.Portuguese.Length > 0 || item.Book.IsEnglish && row.Topic.Summary is not null;
        bool translated = canTranslate && !showOriginal;
        var blocks = translated ? row.Portuguese : row.Original;
        bool hasExcerpt = blocks.Length > 0;
        ReadingLanguage.Text = !hasExcerpt ? "Explicação da regra · PT-BR" : translated ? "Trecho técnico · Tradução automática" :
            item.Book.IsEnglish ? "Trecho técnico · Original em inglês" : "Trecho técnico · Original em português";
        ToggleLanguageButton.Visibility = canTranslate && row.Original.Length > 0 ? Visibility.Visible : Visibility.Collapsed;
        ToggleLanguageButton.Content = translated ? "Ver original em inglês" : "Ver tradução";
        ReaderSummaryPanel.Visibility = hasExcerpt && !string.IsNullOrWhiteSpace(ReaderSummary.Text)
            ? Visibility.Visible : Visibility.Collapsed;
        if (!hasExcerpt)
        {
            blocks = [new ReferenceText.Block(ReferenceText.Kind.Paragraph,
                row.Topic.Summary ?? "Abra a fonte para conferir os detalhes técnicos desta regra.")];
        }
        FlowDocument document = CreateDocument(blocks);
        document.Language = XmlLanguage.GetLanguage(hasExcerpt && item.Book.IsEnglish && !translated ? "en" : "pt-BR");
        PageText.Document = document;
    }

    private FlowDocument CreateDocument(IEnumerable<ReferenceText.Block> blocks)
    {
        var document = new FlowDocument
        {
            FontFamily = new FontFamily("Georgia"),
            FontSize = 16,
            Foreground = (Brush)FindResource("PaperInk"),
            PagePadding = new Thickness(24, 17, 22, 20),
            LineHeight = 24,
        };
        foreach (var block in blocks)
        {
            var paragraph = new Paragraph { Margin = new Thickness(0, 0, 0, 10) };
            switch (block.Type)
            {
                case ReferenceText.Kind.Heading:
                    paragraph.FontFamily = new FontFamily("Segoe UI");
                    paragraph.FontSize = 15;
                    paragraph.FontWeight = FontWeights.SemiBold;
                    paragraph.Foreground = (Brush)FindResource("PaperMuted");
                    paragraph.Margin = new Thickness(0, 12, 0, 5);
                    paragraph.KeepWithNext = true;
                    break;
                case ReferenceText.Kind.Bullet:
                    paragraph.Margin = new Thickness(18, 0, 0, 6);
                    paragraph.TextIndent = -15;
                    paragraph.Inlines.Add(new Run("•  "));
                    break;
                case ReferenceText.Kind.Values:
                    paragraph.FontFamily = new FontFamily("Consolas");
                    paragraph.FontSize = 13;
                    paragraph.LineHeight = 20;
                    paragraph.Background = (Brush)FindResource("PaperLine");
                    paragraph.Padding = new Thickness(9, 7, 9, 7);
                    break;
            }
            foreach (string line in block.Text.Split('\n'))
            {
                if (paragraph.Inlines.LastInline is not null && block.Type == ReferenceText.Kind.Values)
                {
                    paragraph.Inlines.Add(new LineBreak());
                }
                paragraph.Inlines.Add(new Run(line));
            }
            document.Blocks.Add(paragraph);
        }
        return document;
    }

    private void OpenPdf(object sender, RoutedEventArgs args)
    {
        if (Results.SelectedItem is not Entry row)
        {
            return;
        }
        var item = row.Page;
        if (!Path.IsPathFullyQualified(item.Book.Path) || !File.Exists(item.Book.Path) ||
            !string.Equals(Path.GetExtension(item.Book.Path), ".pdf", StringComparison.OrdinalIgnoreCase))
        {
            ResultCount.Text = "O PDF original não está mais no local importado.";
            return;
        }
        try
        {
            var link = new UriBuilder(new Uri(item.Book.Path)) { Fragment = $"page={item.Page.Number}" };
            using Process? process = Process.Start(new ProcessStartInfo(link.Uri.AbsoluteUri) { UseShellExecute = true });
        }
        catch (Win32Exception)
        {
            ResultCount.Text = $"Abra o PDF original manualmente na página {item.Page.Number} do arquivo.";
        }
    }

    private sealed record FilterChoice(string? Id, string Title);
}
