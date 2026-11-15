"""Regenerer le guide PDF et le dictionnaire : pip install -r requirements-docs.txt.

Le PDF explique le projet existant. Il ne genere ni donnees ni previsions.
"""
import csv
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, Line, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageBreak,
                               PageTemplate, Paragraph, Spacer, Table, TableStyle)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tourism.config import OUTPUT, RAW  # noqa: E402

TEAL = colors.HexColor("#123d37")
ACCENT = colors.HexColor("#147d6c")
INK = colors.HexColor("#18372f")
MUTED = colors.HexColor("#61736c")
PALE = colors.HexColor("#eef2e9")
SAND = colors.HexColor("#d8a475")
WIDTH = A4[0] - 88


def fonts():
    candidates = [Path("/usr/share/fonts/truetype/dejavu"), ROOT / "docs" / "fonts"]
    for folder in candidates:
        if (folder / "DejaVuSans.ttf").exists():
            for name, filename in [("Body", "DejaVuSans.ttf"), ("BodyBold", "DejaVuSans-Bold.ttf"), ("Mono", "DejaVuSansMono.ttf")]:
                pdfmetrics.registerFont(TTFont(name, str(folder / filename)))
            pdfmetrics.registerFontFamily("Body", normal="Body", bold="BodyBold", italic="Body", boldItalic="BodyBold")
            return "Body", "BodyBold", "Mono"
    # Helvetica suffit aussi aux accents francais si les polices DejaVu sont absentes.
    return "Helvetica", "Helvetica-Bold", "Courier"


FONT, BOLD, MONO = fonts()
STYLES = {
    "title": ParagraphStyle("title", fontName=BOLD, fontSize=31, leading=37, textColor=TEAL, spaceAfter=18),
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=23, leading=29, textColor=TEAL, spaceAfter=16),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=13, leading=18, textColor=TEAL, spaceBefore=12, spaceAfter=7),
    "body": ParagraphStyle("body", fontName=FONT, fontSize=10.2, leading=15.5, textColor=INK, spaceAfter=9),
    "lead": ParagraphStyle("lead", fontName=FONT, fontSize=12.6, leading=19, textColor=MUTED, spaceAfter=14),
    "small": ParagraphStyle("small", fontName=FONT, fontSize=8.3, leading=12, textColor=MUTED, spaceAfter=7),
    "cell": ParagraphStyle("cell", fontName=FONT, fontSize=8.4, leading=12, textColor=INK),
    "th": ParagraphStyle("th", fontName=BOLD, fontSize=8.5, leading=12, textColor=colors.white),
    "code": ParagraphStyle("code", fontName=MONO, fontSize=8.6, leading=13, textColor=TEAL, backColor=PALE, borderPadding=10, spaceAfter=12),
}


def p(text, style="body"):
    return Paragraph(text, STYLES[style])


def table(headers, rows, widths):
    data = [[p(escape(str(h)), "th") for h in headers]]
    data += [[p(escape(str(c)), "cell") for c in row] for row in rows]
    t = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), TEAL),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PALE, colors.white]),
        ("LINEBELOW", (0, 0), (-1, 0), 1, ACCENT),
    ]))
    return t


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#dce4d8"))
    canvas.line(44, 795, A4[0] - 44, 795)
    canvas.setFont(BOLD, 8)
    canvas.setFillColor(TEAL)
    canvas.drawString(44, 807, "TOURISME TUNISIE")
    canvas.setFont(FONT, 8)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(A4[0] - 44, 807, "Projet intégré BI · S1-S4")
    canvas.line(44, 40, A4[0] - 44, 40)
    canvas.drawString(44, 26, "Guide du projet · 15 novembre 2026")
    canvas.drawRightString(A4[0] - 44, 26, f"{doc.page}")
    canvas.restoreState()


def revenue_chart(con):
    rows = con.execute("SELECT MoisKey/100, SUM(Recettes_MDT) FROM fact_recettes GROUP BY MoisKey/100 ORDER BY 1").fetchall()
    d = Drawing(WIDTH, 220)
    chart = VerticalBarChart()
    chart.x, chart.y = 48, 30
    chart.width, chart.height = WIDTH-62, 165
    chart.data = [[r[1] for r in rows]]
    chart.categoryAxis.categoryNames = [str(r[0]) for r in rows]
    chart.categoryAxis.labels.fontName = FONT
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontName = FONT
    chart.valueAxis.labels.fontSize = 8
    chart.valueAxis.valueMin, chart.valueAxis.valueMax, chart.valueAxis.valueStep = 0, 8000, 2000
    chart.bars[0].fillColor = ACCENT
    chart.bars[0].strokeColor = None
    chart.valueAxis.gridStrokeColor = colors.HexColor("#dce4d8")
    chart.valueAxis.visibleGrid = True
    chart.categoryAxis.strokeColor = MUTED
    chart.valueAxis.strokeColor = None
    d.add(chart)
    d.add(String(48, 207, "Recettes annuelles observées, en millions de dinars", fontName=BOLD, fontSize=9, fillColor=TEAL))
    return d


def constellation():
    d = Drawing(WIDTH, 170)
    boxes = [(0, 115, 130, "Année"), (185, 115, 130, "Région"), (370, 115, 130, "Catégorie"),
             (60, 10, 175, "Fait capacité"), (290, 10, 175, "Fait occupation")]
    for start, end in [(65, 148), (65, 378), (250, 148), (250, 378), (435, 148), (435, 378)]:
        d.add(Line(start, 115, end, 52, strokeColor=colors.HexColor("#b9cbbb"), strokeWidth=1))
    for x, y, w, label in boxes:
        is_fact = y < 100
        d.add(Rect(x, y, w, 42, rx=8, ry=8, fillColor=TEAL if is_fact else PALE, strokeColor=None))
        d.add(String(x+w/2, y+17, label, textAnchor="middle", fontName=BOLD, fontSize=10, fillColor=colors.white if is_fact else TEAL))
    return d


def dictionary():
    import pandas as pd
    rows = []
    descriptions = {
        "AnneeKey": "Annee de l'observation. Une valeur annuelle n'est pas une date mensuelle.",
        "MoisKey": "Cle du mois AAAAMM.", "Date": "Premier jour du mois, utilise comme repere mensuel.",
        "Recettes_MDT": "Recettes touristiques observees en millions de dinars tunisiens.",
        "Taux_TND": "Nombre de dinars pour une unite de devise.",
        "Arrivees": "Arrivees aux frontieres des non-residents.",
        "Nuitees": "Nuitees hotelieres ; segment resident distinct.",
        "Taux_pct": "Taux publie en pourcentage. NULL si absent ou mis en quarantaine.",
        "Total_kTND": "Investissement total en milliers de dinars.",
        "Hebergement_kTND": "Investissement hebergement en milliers de dinars.",
        "Animation_kTND": "Investissement animation en milliers de dinars.",
        "Lits": "Nombre de lits du stock hotelier 2023.",
        "Etablissements": "Nombre d'etablissements hoteliers du stock 2023.",
        "Capacite_lits": "Capacite associee aux investissements, distincte du stock hotelier.",
        "SourceKey": "Cle de l'organisme et du fichier charge.",
        "SourceFeuille": "Nom exact de la feuille source ou BCT_HTML.",
        "SourceLigne": "Ligne Excel (entete comprise) ou position de la ligne de taux HTML.",
        "ObservationKey": "Cle technique d'une observation, sans signification metier.",
        "Valeur_MDT": "Prevision future en MDT ; aucune ligne generee en S4.",
        "Borne_basse": "Borne inferieure d'un intervalle de prevision futur.",
        "Borne_haute": "Borne superieure d'un intervalle de prevision futur.",
        "Modele": "Nom du modele de prevision a ajouter en S5.",
        "Cible": "Nom de l'indicateur prevu.",
        "Date_entrainement": "Horodatage de l'entrainement du futur modele.",
        "Valeur": "Valeur du controle source ou de l'indicateur de duree selon la table et l'unite.",
        "Visiteurs": "Nombre de visites dans le site ou musee pendant l'annee, non necessairement des personnes uniques.",
        "Agences": "Nombre d'agences pour une annee, une region et une licence.",
        "Restaurants": "Nombre de restaurants touristiques pour une region et une classe.",
    }
    source_descriptions = {
        "Annee": "Annee civile de l'observation.",
        "Mois": "Nom du mois de l'observation mensuelle.",
        "Mois_num": "Numero du mois, de 1 a 12.",
        "DateKey": "Cle source du mois ; AAAAMM dans l'echantillon, AAAA-MM dans le classeur BCT.",
        "Date_fin_mois": "Dernier jour du mois de reference BCT.",
        "EUR_TND_moyen": "Taux moyen mensuel, dinars tunisiens pour 1 EUR.",
        "USD_TND_moyen": "Taux moyen mensuel, dinars tunisiens pour 1 USD.",
        "Source": "Organisme ou reference du tableau indique par le fichier fourni.",
        "Nationalite": "Marche ou groupe source. Peut aussi contenir un total, un sous-total ou une ligne de pourcentage.",
        "Nombre_arrivees": "Arrivees des non-residents aux frontieres ; exclure les lignes de pourcentage et sous-totaux pour sommer.",
        "Nombre_nuitees": "Nuitees hotelieres, avec sous-totaux, % et segment residents a distinguer.",
        "Recettes_touristiques_MDT": "Recettes mensuelles observees en millions de dinars tunisiens.",
        "Recettes_MDT": "Recettes trimestrielles en millions de dinars. Ne pas ajouter aux valeurs mensuelles.",
        "Trimestre": "Trimestre T1 a T4.",
        "Region": "Region touristique ou administrative selon la feuille ; les decoupages ne sont pas interchangeables.",
        "Gouvernorat": "Gouvernorat tunisien concerne par l'investissement, ou ligne Total.",
        "Categorie_hebergement": "Classe ou type d'hebergement ; varie entre etoiles et libelles selon la feuille.",
        "Nombre_lits": "Stock de lits hoteliers du rapport 2023.",
        "Nombre_etablissements": "Stock d'etablissements hoteliers du rapport 2023.",
        "Capacite_hoteliere_lits": "Capacite associee aux investissements, pas le stock hotelier total.",
        "Invest_hebergement_milliers_DT": "Investissement en hebergement, milliers de dinars tunisiens.",
        "Invest_animation_milliers_DT": "Investissement en animation, milliers de dinars tunisiens.",
        "Invest_total_milliers_DT": "Investissement total, milliers de dinars tunisiens.",
        "Taux_occupation_pct": "Taux d'occupation publie en pourcentage ; non additif, cellules vides a conserver.",
        "Variation_pct_2023_2022": "Variation 2023/2022 publiee en points de pourcentage de croissance, non additive.",
        "Indicateur": "Nom de la mesure ; verifier son unite et sa population avant toute aggregation.",
        "Valeur": "Valeur de l'indicateur nomme dans la meme ligne, avec l'unite de la table ou la colonne Unite.",
        "Saison": "Saison Haute_moyenne ou Basse telle que fournie par l'ONTT.",
        "Arrivees": "Compte d'arrivees pour une saison ; lignes % et sous-totaux presentes dans la source.",
        "Licence": "Licence A, B ou Total pour les agences de voyages.",
        "Nombre_agences": "Nombre d'agences, selon annee, region et licence.",
        "Site_musee": "Nom du site ou du musee, ou ligne TOTAL.",
        "Nombre_visiteurs": "Nombre de visites du site ou du musee ; blancs conserves comme absents.",
        "Unite": "Unite originale de la valeur. Certains libelles ambigus sont signales dans la documentation.",
        "ID_observation": "Identifiant de ligne de la base maitresse derivee, sans ajout d'une observation independante.",
        "Domaine": "Domaine touristique de la base maitresse derivee.",
        "Periode": "Mois, trimestre ou cellule vide selon le grain original.",
        "Categorie": "Categorie transcrite dans la base maitresse.",
        "Site_ou_Musee": "Nom transcrit du site ou du musee.",
        "Feuille_source": "Nom de la feuille ayant alimente la base maitresse derivee.",
        "Page_source_PDF": "Page indiquee lors de la transcription ; non verifiee par une extraction PDF locale.",
        "Commentaire": "Note de transcription ou d'aggregation fournie.",
        "Ecart_jours_2023_2022": "Ecart de duree 2023-2022 en jours ; deux blocs regionaux sans libelle, non charges.",
        "Total": "Total source : controle des details, sans addition supplementaire.",
    }
    con = sqlite3.connect(OUTPUT / "tourisme.sqlite")
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for name in tables:
        fks = {r[3]: r[2] + "." + r[4] for r in con.execute(f'PRAGMA foreign_key_list("{name}")')}
        for _, column, kind, nullable, _, pk in con.execute(f'PRAGMA table_info("{name}")'):
            meaning = descriptions.get(column, "Cle technique de la dimension correspondante." if column.endswith("Key") else "Libelle ou attribut de " + name + ".")
            rows.append({"Couche": "DWH", "Fichier_ou_table": name, "Feuille": "", "Colonne": column,
                         "Type": kind, "Cle_primaire": bool(pk), "Reference": fks.get(column, ""),
                         "Nullable": not bool(nullable or pk), "Description": meaning})
    con.close()
    for file in RAW.glob("*.xlsx"):
        excel = pd.ExcelFile(file)
        for name in excel.sheet_names:
            frame = pd.read_excel(excel, sheet_name=name)
            for column in frame.columns:
                rows.append({"Couche": "Source", "Fichier_ou_table": file.name, "Feuille": name, "Colonne": column,
                             "Type": str(frame[column].dtype), "Cle_primaire": "", "Reference": "",
                             "Nullable": bool(frame[column].isna().any()),
                             "Description": source_descriptions.get(column,
                                 "Nombre d'arrivees de l'annee dans le nom de colonne." if str(column).startswith("Arrivees_") else
                                 "Nombre de nuitees de l'annee dans le nom de colonne." if str(column).startswith("Nuitees_") else
                                 "Duree de sejour en jours ; bloc regional ambigu conserve seulement dans la source." if str(column).startswith("Duree_sejour_") else
                                 "Nombre de restaurants pour la classe indiquee dans le nom de colonne." if "fourchette" in str(column) else
                                 "Metadonnee descriptive de la feuille fournie, conservee pour contexte.")})
    target = ROOT / "docs" / "DICTIONNAIRE_DONNEES.csv"
    with target.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build_pdf():
    report = json.loads((OUTPUT / "rapport_qualite.json").read_text())
    junit = OUTPUT / "tests_junit.xml"
    tests, failures = None, None
    if junit.exists():
        root = ET.parse(junit).getroot()
        suites = root.findall("testsuite") if root.tag == "testsuites" else [root]
        tests = sum(int(s.get("tests", 0)) for s in suites)
        failures = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    test_label = f"{tests} tests réussis" if tests is not None and failures == 0 else "Voir le rapport de tests joint"
    con = sqlite3.connect(OUTPUT / "tourisme.sqlite")
    path = ROOT / "docs" / "Guide_Projet_Tourisme_S1_S4.pdf"
    doc = BaseDocTemplate(str(path), pagesize=A4, leftMargin=44, rightMargin=44, topMargin=64,
                          bottomMargin=56, title="Tourisme Tunisie - Guide du projet S1-S4",
                          author="Projet integre BI", subject="Installation, donnees, ETL, DWH, Power BI et interface")
    frame = Frame(44, 56, WIDTH, A4[1]-120, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="main", frames=frame, onPage=header_footer))
    story = []
    def add(*items):
        story.extend(items)
    def next_page():
        story.append(PageBreak())

    add(Spacer(1, 20), p("Des fichiers aux<br/>décisions.", "title"),
        p("Le projet de tourisme tunisien, expliqué simplement.", "lead"),
        p("Ce dossier réunit les données, le programme qui les prépare, la base de données et une interface pour les explorer. Il couvre le travail prévu jusqu'à la <b>semaine 4</b>."),
        Spacer(1, 12), table(["96 mois", "2 organismes", "8 écrans"], [["Recettes et change de 2016 à 2023", "ONTT pour le tourisme, BCT pour le change", "Une application locale avec filtres et graphiques"]], [WIDTH/3]*3),
        Spacer(1, 18), p("Pour démarrer chez ton ami", "h2"),
        p("<b>1.</b> Extraire le ZIP en entier et installer Python 3.12, version 64 bits."),
        p("<b>2.</b> Ouvrir <b>INSTALLER_WINDOWS.bat</b>. Il installe les bibliothèques, construit la base et configure Power BI."),
        p("<b>3.</b> Ouvrir <b>LANCER_WINDOWS.bat</b>, puis aller sur <b>http://localhost:8501</b>."),
        p("Ce qui est vérifié", "h2"),
        p(f"{test_label}. Les chiffres nettoyés correspondent aux totaux fournis. L'installation a aussi été vérifiée dans un environnement Python neuf."),
        p("Power BI Desktop doit encore être ouvert et actualisé sur Windows. Le paquet fournit les fichiers du projet, mais le rendu natif et les calculs DAX n'ont pas pu être exécutés sous Linux.", "small"))
    next_page()

    add(p("01 · À quoi sert le projet ?", "h1"),
        p("Au départ, les informations sont réparties entre plusieurs fichiers. Il est difficile de les comparer rapidement.", "lead"),
        p("Nous voulons répondre à des questions concrètes : combien le tourisme rapporte-t-il ? Quels marchés amènent le plus de visiteurs ? Où se trouvent les lits et les investissements ? Quelles périodes sont les plus fortes ?"),
        p("Les deux sources", "h2"),
        table(["Source", "Ce qu'elle apporte", "Période"], [
            ["ONTT", "Recettes, arrivées, nuitées, hébergement, investissements et sites.", "Selon la table : 2016-2023, 2019-2023 ou 2021-2023."],
            ["BCT", "Taux moyens mensuels EUR/TND et USD/TND.", "Janvier 2016 à décembre 2023."],
        ], [70, 265, WIDTH-335]),
        Spacer(1, 10), p("Deux formats réellement différents", "h2"),
        p("La partie tourisme arrive sous forme de classeur Excel. Le fichier BCT porte le nom <b>BCT_statistque.xls</b>, mais son contenu réel est une page HTML. Le code sait lire ce format."),
        p("Les copies ne sont pas de nouvelles sources", "h2"),
        p("La base maîtresse, l'échantillon et le fichier BCT converti reprennent des données déjà présentes. Ils servent à vérifier ou à présenter les données. Les charger une deuxième fois gonflerait les chiffres."),
        p("Une limite de collecte à annoncer", "h2"),
        p("Le PDF ONTT original n'était pas joint. Le code utilise donc la transcription Excel fournie. Le lien officiel est documenté, mais le groupe doit conserver le PDF brut et compléter la date d'extraction et la licence. La date de réception des fichiers ne remplace pas ces informations."),
        p("Le cahier des charges demande une collecte réelle. Il ne faut pas présenter ces fichiers dérivés comme une collecte brute autonome.", "small"))
    next_page()

    add(p("02 · Ce que fait l'ETL", "h1"),
        p("ETL signifie simplement : lire, préparer et ranger.", "lead"),
        table(["Étape", "Ce qui se passe"], [
            ["Extraire", "Lire les feuilles Excel et les cellules HTML de la BCT."],
            ["Harmoniser", "Uniformiser les mois, les régions et les catégories. Par exemple, ***** et 5_etoiles désignent la même catégorie."],
            ["Nettoyer", "Séparer les détails, les sous-totaux et les pourcentages. Garder les cellules absentes comme valeurs manquantes."],
            ["Contrôler", "Vérifier les 96 mois, les taux BCT, les clés et les totaux avant de livrer la base."],
            ["Charger", "Insérer les dimensions, puis les faits, dans le fichier SQLite. Exporter les CSV pour Power BI."],
        ], [90, WIDTH-90]),
        Spacer(1, 10), p("Pourquoi les totaux demandent de l'attention", "h2"),
        p("Si une table contient « Français : 100 », « Allemands : 200 » et « Total : 300 », la bonne somme est 300. Ajouter les trois lignes donnerait 600. Le programme garde le total à part pour vérifier les détails."),
        p("Deux exemples de prudence", "h2"),
        p("Une cellule vide ne devient pas 0. Un taux d'occupation de <b>109,8 %</b> est conservé dans la source et dans l'audit, mais son taux nettoyé reste vide en attendant une vérification."),
        p("La feuille Duree_Region contient deux blocs par région, sans leur libellé de population. Le programme les met à part au lieu de mélanger leurs durées."),
        p("Chaque ligne chargée garde sa source, sa feuille et son numéro de ligne. Le fichier audit_lignes.csv explique les exclusions. Beaucoup sont normales : un total exclu du détail n'est pas une erreur."))
    next_page()

    add(p("03 · Pourquoi une base de données ?", "h1"),
        p("Le DWH est le rangement commun que les graphiques utilisent.", "lead"),
        p("Une <b>dimension</b> dit quand, où ou de quel marché on parle. Une <b>table de faits</b> contient ce qu'on mesure : recettes, arrivées, lits, etc."),
        constellation(),
        p("Exemple : une ligne de capacité correspond à une année, une région et une catégorie d'hébergement. Une ligne de recette correspond seulement à un mois national."),
        table(["Table", "Ce que représente une ligne", "Lignes"], [
            ["fact_recettes", "Un mois de recettes nationales", "96"],
            ["fact_change", "Un mois pour une devise", "192"],
            ["fact_arrivees", "Une année pour un marché", "168"],
            ["fact_nuitees", "Une année pour un marché ou segment résident", "132"],
            ["fact_capacite", "2023, une région et une catégorie", "270"],
            ["fact_investissements", "2023, un gouvernorat", "24"],
            ["fact_previsions", "Un futur mois, modèle et indicateur", "0"],
        ], [130, WIDTH-190, 60]),
        Spacer(1, 9), p("Pourquoi SQLite ?", "h2"),
        p("SQLite stocke la base dans un fichier : tourisme.sqlite. Ton ami n'a pas besoin d'installer un serveur SQL. Les clés et les contraintes empêchent certains doublons et relations invalides."),
        p("Le schéma complet, les 13 dimensions et les autres tables de faits sont décrits dans docs/DWH.md et outputs/schema.sql. La validation du schéma par les encadrants reste à obtenir.", "small"))
    next_page()

    add(p("04 · Ce qu'on peut voir", "h1"),
        p("L'interface lit la base préparée, puis les filtres choisissent les observations à afficher.", "lead"),
        revenue_chart(con),
        table(["Écran", "Utilité"], [
            ["Vue d'ensemble", "Les principaux chiffres d'une année et les marchés importants."],
            ["Recettes et change", "Les 96 mois, les saisons et une conversion indicative en EUR ou USD."],
            ["Marchés et saisons", "Filtrer les marchés, les arrivées, les nuitées et les saisons."],
            ["Hébergement", "Choisir une région et une catégorie ; voir lits et taux détaillés."],
            ["Investissements et patrimoine", "Voir les gouvernorats, les sites, les agences et les restaurants."],
            ["Qualité et données", "Ouvrir les contrôles, explorer les tables et exporter des CSV."],
            ["Power BI / Prévisions", "Accéder au projet Microsoft et préparer l'étape IA de S5."],
        ], [155, WIDTH-155]),
        Spacer(1, 8), p("Exemple facile à montrer : choisir SOUSSE dans Hébergement. Le nombre de lits et le tableau changent. En 2019, les arrivées détaillées affichent n.d. : elles n'étaient pas fournies pour cette année.", "small"))
    next_page()

    add(p("05 · Installer sur un autre PC", "h1"),
        p("Le ZIP contient les sources, les données et une base déjà construite. L'installation peut tout reconstruire.", "lead"),
        p("Sur Windows", "h2"),
        p("<b>1.</b> Télécharger Python 3.12 64 bits sur python.org et cocher Add Python to PATH.<br/><b>2.</b> Extraire tout le ZIP dans un dossier accessible en écriture.<br/><b>3.</b> Ouvrir INSTALLER_WINDOWS.bat et attendre la fin.<br/><b>4.</b> Ouvrir LANCER_WINDOWS.bat, puis http://localhost:8501."),
        p("Ne pas lancer l'application depuis l'intérieur du ZIP. Garder la fenêtre de commande ouverte ; Ctrl+C arrête le serveur local."),
        table(["Bibliothèque", "Version testée", "Pourquoi elle est là"], [
            ["pandas", "2.2.3", "Manipuler et vérifier les tableaux."],
            ["openpyxl", "3.1.5", "Lire les fichiers Excel xlsx."],
            ["lxml", "6.1.1", "Lire le HTML du fichier BCT."],
            ["Streamlit", "1.67.0", "Afficher l'application et ses filtres."],
            ["Plotly", "7.1.0", "Tracer les graphiques interactifs."],
        ], [105, 90, WIDTH-195]),
        Spacer(1, 10), p("Ces versions sont dans requirements.txt. Pip installe aussi leurs dépendances. Une connexion Internet est nécessaire à cette première installation. Ensuite les graphiques locaux utilisent les fichiers du dossier."),
        p("Pour vérifier ou réparer", "h2"),
        p("TESTER_WINDOWS.bat installe les outils de test puis exécute les vérifications. Les commandes manuelles et les scripts macOS/Linux sont aussi inclus."),
        p("La vérification réalisée ici utilise Python 3.12 sous Linux. Les fichiers BAT sont fournis pour Windows ; leur exécution et Power BI Desktop doivent être vérifiés sur le PC destinataire.", "small"))
    next_page()

    add(p("06 · Le code, sans jargon", "h1"),
        p("Chaque fichier a un rôle précis. Il n'est pas nécessaire de tout apprendre ligne par ligne.", "lead"),
        table(["Fichier", "À quoi il sert"], [
            ["config.py", "Trouver les fichiers à partir du dossier du projet. Aucun chemin personnel n'est nécessaire pour Python."],
            ["cleaning.py", "Nettoyer les noms et les nombres, et lire le HTML BCT."],
            ["etl.py", "Construire la base, contrôler les résultats et produire les exports."],
            ["analytics.py", "Lire la base et calculer les sommes et variations affichées."],
            ["app.py", "Créer les écrans, les filtres et les graphiques de l'application."],
            ["configure_powerbi.py", "Générer le modèle, les relations, les mesures et les pages Power BI, avec le bon chemin CSV."],
            ["tests/", "Vérifier que les résultats et interactions attendus fonctionnent."],
        ], [150, WIDTH-150]),
        Spacer(1, 10), p("Trois idées à retenir", "h2"),
        p('<font face="'+MONO+'">pd.read_excel(...)</font> lit une feuille Excel. Cela évite de recopier les données à la main.'),
        p('<font face="'+MONO+'">merge(..., validate="one_to_one")</font> rapproche deux tables et signale les clés répétées quand une seule ligne par clé est attendue.'),
        p('<font face="'+MONO+'">None</font> devient une valeur manquante dans la base. Cela garde la différence entre « nous ne savons pas » et « la valeur est zéro ».'),
        p("Relancer sans doubler les données", "h2"),
        p("L'ETL reconstruit une base temporaire puis remplace l'ancienne après ses contrôles. Deux exécutions sur les mêmes fichiers donnent les mêmes observations. Si un contrôle échoue, la base précédente reste disponible."))
    next_page()

    add(p("07 · Power BI et les semaines", "h1"),
        p("L'application locale et le projet Power BI utilisent les mêmes données préparées.", "lead"),
        p("Le dossier powerbi contient un projet PBIP/PBIR avec <b>27 tables importées, 45 relations, 17 mesures DAX et cinq pages</b>. Les fichiers sont contrôlés selon les schémas publics Microsoft."),
        p("Pour l'ouvrir", "h2"),
        p("Après l'installation, ouvrir Tourisme_Tunisie.pbip dans Power BI Desktop, cliquer sur Actualiser et choisir 2023. Vérifier 6 920,6 MDT de recettes et 9 370 511 arrivées. Si le dossier change de place, relancer configure_powerbi.py."),
        p("L'ouverture native, les calculs DAX et l'apparence du rapport restent à vérifier sur Windows. Une définition JSON valide ne prouve pas le rendu Desktop. Le guide POWERBI.md donne aussi une méthode de repli avec les CSV et les mesures DAX."),
        p("L'intégrer dans l'interface", "h2"),
        p("La page Power BI accepte l'URL sécurisée d'un rapport publié dans votre propre espace Microsoft. Cette publication et son compte ne sont pas inclus. Sans URL, les autres écrans et les graphiques locaux fonctionnent déjà."),
        table(["Semaine", "Travail fourni"], [
            ["1", "Besoin métier, KPI, fiche de collecte, dictionnaire, échantillons et schéma."],
            ["2", "Modèle et ETL ; validation des encadrants à obtenir."],
            ["3", "Base alimentée, contrôles, traçabilité et définitions Power BI ; vérification Desktop à faire."],
            ["4", "Interface interactive, graphiques locaux et espace d'intégration Microsoft."],
            ["5 ensuite", "Prévisions et comparaison de modèles. L'espace et la table sont prêts mais vides."],
        ], [85, WIDTH-85]),
        Spacer(1, 8), p("Les modèles IA et le rapport final de S6 ne sont pas présentés comme déjà réalisés.", "small"))
    next_page()

    add(p("08 · Tests et présentation", "h1"),
        p(test_label + ". " + str(len(report["controles"])) + " contrôles ETL réussis sur les fichiers fournis.", "lead"),
        table(["Vérifié", "Résultat ou exemple"], [
            ["Installation Python neuve", "Dépendances installées ; aucune dépendance cassée détectée."],
            ["ETL et totaux", "6 920,6 MDT en 2023, 9 370 511 arrivées, 25 351 033 nuitées et 230 726 lits."],
            ["Qualité et relations", "96 mois réguliers, taux BCT concordants, clés valides et grains uniques."],
            ["Cas difficiles", "Doublon rejeté, valeur manquante conservée, taux aberrant isolé, base précédente conservée en cas d'échec."],
            ["Interface", "Huit écrans exécutés avec AppTest ; filtres année, région, devise et sélection vide testés."],
            ["Power BI", "Schémas JSON, relations et références vérifiés. Le moteur DAX et le rendu Windows restent à vérifier."],
        ], [140, WIDTH-140]),
        Spacer(1, 10), p("Ce que tu peux dire à l'oral", "h2"),
        p("« Notre projet rassemble les données touristiques de l'ONTT et les taux de change de la BCT. Python prépare les fichiers et enlève les doubles comptes. SQLite range les données dans des tables reliées. Streamlit et Power BI permettent de suivre les indicateurs et de changer les filtres. La prochaine étape sera de prévoir les recettes mensuelles. »"),
        p("Avant le dépôt", "h2"),
        p("Conserver le PDF ONTT original et compléter les métadonnées de collecte. Faire valider le schéma par les encadrants. Vérifier le PBIP sur Windows. Configurer l'URL Power BI si le rapport Microsoft doit apparaître dans l'interface."),
        p("Pour retrouver les détails : README.md, FICHE_COLLECTE.md, DWH.md, POWERBI.md et DEMONSTRATION.md. Les contrôles et les résultats de tests sont dans outputs/.", "small"),
        p('Sources : fichiers joints par le groupe ; ONTT, « Tourisme tunisien en chiffres - Extrait 2023 » ; BCT, cours interbancaires mensuels. Les liens officiels complets figurent dans FICHE_COLLECTE.md. Aucune licence ni date d\'extraction originale n\'est supposée.', "small"))
    doc.build(story)
    con.close()
    return path


if __name__ == "__main__":
    dictionary()
    print(build_pdf())
