from datetime import datetime
import feedparser
import html2text

FONTI_RSS = {
    "La Repubblica": "https://www.repubblica.it/rss/homepage/rss2.0.xml",
    "Il Sole 24 Ore": "https://www.ilsole24ore.com/rss/mondo.xml",
    "ANSA": "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",
    "BBC News": "http://feeds.bbci.co.uk/news/world/rss.xml",
    "The New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "Financial Times": "https://www.ft.com/?format=rss",
    "TechCrunch": "https://techcrunch.com/feed/",
    "The Verge": "https://www.theverge.com/rss/index.xml",
    "Ars Technica": "https://feeds.arstechnica.com/arstechnica/index",
    "Nature": "https://www.nature.com/nature.rss",
    "New Scientist": "https://www.newscientist.com/section/news/feed/",
    "NASA": "https://www.nasa.gov/news-release/feed/",
}
NUMERO_NOTIZIE_PER_FONTE = 5


def _pulisci_testo(html_content: str) -> str:
    """Rimuove tag HTML e restituisce testo piano pulito."""
    if not html_content:
        return ""
    h = html2text.HTML2Text()
    h.ignore_links = True
    h.ignore_images = True
    h.emphasis_mark = ''
    return h.handle(html_content).strip().replace('\n', ' ')


def estrai_notizie_grezze() -> str:
    """Legge i feed RSS e formatta un blocco di testo aggregato per l'LLM."""
    oggi = datetime.now().date()
    output = [f"Data estrazione: {oggi.strftime('%d/%m/%Y')}\n"]

    for nome_giornale, url_rss in FONTI_RSS.items():
        feed = feedparser.parse(url_rss)

        if not feed.entries:
            continue

        viste = set()
        notizie_inserite = 0
        notizie_fonte = []

        for entry in feed.entries:
            if notizie_inserite >= NUMERO_NOTIZIE_PER_FONTE:
                break

            titolo = entry.get('title', 'Nessun titolo')
            if titolo in viste:
                continue

            link = entry.get('link', 'Nessun link')
            sommario_raw = entry.get('summary', entry.get('description', ''))
            sommario = _pulisci_testo(sommario_raw)

            data_pub_stringa = entry.get('published', 'Data non disponibile')
            data_strutturata = entry.get('published_parsed')

            mostra_notizia = False
            if not data_strutturata or data_pub_stringa == 'Data non disponibile':
                mostra_notizia = True
            else:
                data_notizia = datetime(*data_strutturata[:3]).date()
                if data_notizia == oggi:
                    mostra_notizia = True

            if mostra_notizia:
                notizia_formattata = (
                    f"- Titolo: {titolo}\n"
                    f"  Sommario: {sommario}\n"
                    f"  Link: {link}\n"
                )
                notizie_fonte.append(notizia_formattata)
                viste.add(titolo)
                notizie_inserite += 1

        if notizie_fonte:
            output.append(f"## FONTE: {nome_giornale}")
            output.extend(notizie_fonte)
            output.append("-" * 40)

    return "\n".join(output)