"""Interface locale. Lancer avec : python -m streamlit run app.py"""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from tourism import analytics as a
from tourism.config import DB, OUTPUT, ROOT
from tourism.etl import run_pipeline

st.set_page_config(page_title="Tourisme Tunisie", page_icon="🇹🇳", layout="wide")

st.markdown("""<style>
html,body,[class*="css"],.stApp {font-family:'DM Sans',sans-serif;}
.stApp {background:#f5f5ef;color:#182f2c;}
section[data-testid="stSidebar"] {background:#123d37;}
section[data-testid="stSidebar"] * {color:#eff5eb;}
section[data-testid="stSidebar"] [data-baseweb="select"] * {color:#182f2c;}
div[data-testid="stMetric"] {background:#fff;border:1px solid #e3e8df;border-radius:14px;padding:18px;}
div[data-testid="stMetricLabel"] {color:#627570;}
h1,h2,h3 {letter-spacing:-.035em;}
.eyebrow {font-size:12px;letter-spacing:.16em;color:#6b8077;text-transform:uppercase;}
.intro {font-size:17px;color:#61716a;max-width:900px;}
div[data-testid="stAlert"] {border-radius:12px;}
.block-container {padding-top:2.2rem;max-width:1500px;}
</style>""", unsafe_allow_html=True)

COLORS = ["#147d6c", "#da9561", "#6a8d90", "#315d6b", "#d0b26a"]
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = COLORS


def chart(fig, key):
    fig.update_layout(font_family="Arial", paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=20, t=30, b=10),
                      legend_title_text="", height=340)
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="#e2e6dd")
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False})


def download(frame, filename, key):
    st.download_button("Telecharger les donnees affichees (CSV)", frame.to_csv(index=False).encode("utf-8-sig"),
                       filename, "text/csv", key=key)


def title(kicker, heading, description):
    st.markdown(f'<div class="eyebrow">{kicker}</div>', unsafe_allow_html=True)
    st.title(heading)
    st.markdown(f'<div class="intro">{description}</div>', unsafe_allow_html=True)
    st.write("")


def year_select(label, values, key):
    values = sorted(set(int(v) for v in values))
    return st.selectbox(label, values, index=len(values) - 1, key=key)


def national_rate(year):
    refs = a.read_table("ref_controles_source")
    selected = refs[refs.SourceFeuille.eq("KPI_2023") & refs.AnneeKey.eq(year) & refs.Libelle.eq("Taux occupation moyen")]
    return None if selected.empty else float(selected.iloc[0].Valeur)


with st.sidebar:
    st.markdown("## TOURISME\n### Tunisie")
    st.caption("Observatoire local · ONTT + BCT")
    st.divider()
    page = st.radio("Navigation", ["Vue d'ensemble", "Recettes et change", "Marches et saisons",
                    "Hebergement", "Investissements et patrimoine", "Qualite et donnees",
                    "Power BI", "Previsions (S5)"], label_visibility="collapsed", key="nav")
    st.divider()
    st.caption("Donnees historiques 2016-2023\n\nProjet integre · Semaines 1 a 4")

if not DB.exists():
    st.info("La base doit etre construite une premiere fois a partir des fichiers fournis.")
    if st.button("Construire le DWH", key="build_missing"):
        with st.spinner("Lecture, nettoyage et controles..."):
            run_pipeline()
        st.rerun()
    st.stop()

if page == "Vue d'ensemble":
    title("Observatoire du tourisme", "Comprendre la reprise du tourisme.",
          "Les recettes, les marches et l'offre touristique, reunis dans un meme espace.")
    year = year_select("Annee d'analyse", range(2016, 2024), "overview_year")
    values = a.summary(year)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Recettes touristiques (MDT)", a.money(values["recettes"]),
              None if values["recettes_yoy"] is None else f"{values['recettes_yoy']:+.1f} % / an precedent")
    c2.metric("Arrivees des non-residents", a.money(values["arrivees"], 0))
    c3.metric("Nuitees, residents inclus", a.money(values["nuitees"], 0))
    c4.metric("Occupation nationale publiee", a.money(national_rate(year)) + (" %" if year == 2023 else ""))
    if year < 2021:
        st.caption("Les arrivees et les nuitees detaillees sont disponibles uniquement pour 2021-2023. n.d. signifie non disponible.")
    st.write("")
    left, right = st.columns([1.45, 1])
    monthly = a.monthly()
    annual = monthly.groupby("Annee", as_index=False).Recettes_MDT.sum()
    with left:
        st.subheader("Huit annees de recettes")
        chart(px.bar(annual, x="Annee", y="Recettes_MDT", labels={"Recettes_MDT": "Millions de dinars", "Annee": "Annee"}), "overview_revenue")
    with right:
        st.subheader(f"Principaux marches · {year}")
        arrivals = a.read_table("vw_arrivees")
        selected = arrivals[arrivals.AnneeKey.eq(year)].nlargest(7, "Arrivees").sort_values("Arrivees")
        if selected.empty:
            st.info("Aucun detail par marche pour cette annee.")
        else:
            chart(px.bar(selected, x="Arrivees", y="Marche", orientation="h", labels={"Arrivees": "Arrivees", "Marche": ""}), "overview_markets")
    st.caption("MDT = millions de dinars tunisiens. Les arrivees aux frontieres et les nuitees hotelieres couvrent des populations differentes.")

elif page == "Recettes et change":
    title("Serie mensuelle", "Recettes et taux de change", "Explorez 96 mois d'historique. Les taux BCT correspondent aux dinars necessaires pour une unite de devise.")
    frame = a.monthly()
    years = st.multiselect("Annees", list(range(2016, 2024)), default=[2022, 2023], key="revenue_years")
    currency = st.selectbox("Affichage des recettes", ["MDT", "MEUR (estimation)", "MUSD (estimation)"], key="currency")
    selected = frame[frame.Annee.isin(years)].copy()
    column = {"MDT": "Recettes_MDT", "MEUR (estimation)": "Recettes_MEUR_estimees", "MUSD (estimation)": "Recettes_MUSD_estimees"}[currency]
    if selected.empty:
        st.info("Selectionnez au moins une annee.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric(f"Recettes ({currency})", a.money(a.safe_sum(selected[column])))
        c2.metric("Mois selectionnes", str(len(selected)))
        c3.metric("EUR/TND, moyenne des mois", a.money(selected.EUR_TND.mean(), 4))
        chart(px.line(selected, x="Date", y=column, markers=True, labels={column: currency}), "revenue_line")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Saisonnalite par mois")
            seasonal = selected.pivot(index="Annee", columns="Mois", values="Recettes_MDT").reindex(columns=range(1, 13))
            chart(px.imshow(seasonal, aspect="auto", labels={"x": "Mois", "y": "Annee", "color": "MDT"}, color_continuous_scale="Teal"), "heatmap")
        with c2:
            st.subheader("EUR et USD en dinars")
            rates = selected.melt(id_vars=["Date"], value_vars=["EUR_TND", "USD_TND"], var_name="Devise", value_name="TND")
            chart(px.line(rates, x="Date", y="TND", color="Devise"), "rates")
        if currency != "MDT":
            st.caption("Estimation : chaque recette mensuelle en MDT est divisee par le taux moyen du meme mois, puis les mois sont additionnes. Ce n'est pas une recette officielle publiee en devises.")
        with st.expander("Voir les valeurs mensuelles"):
            st.dataframe(selected, hide_index=True, width="stretch")
        download(selected, "recettes_change.csv", "download_revenue")

elif page == "Marches et saisons":
    title("Demande touristique", "D'ou viennent les visiteurs ?", "Comparez les arrivees, les nuitees et les saisons sur la periode 2021-2023.")
    year = year_select("Annee", [2021, 2022, 2023], "markets_year")
    frame = a.read_table("vw_arrivees")
    frame = frame[frame.AnneeKey.eq(year)].copy()
    markets = st.multiselect("Marches (vide = tous)", sorted(frame.Marche.unique()), key="markets")
    if markets:
        frame = frame[frame.Marche.isin(markets)]
    total = a.safe_sum(frame.Arrivees)
    st.metric("Arrivees dans la selection", a.money(total, 0))
    if not frame.empty:
        # Le denominateur est le total national de l'annee, pas la seule selection.
        all_arrivals = a.read_table("vw_arrivees")
        national = a.safe_sum(all_arrivals.loc[all_arrivals.AnneeKey.eq(year), "Arrivees"])
        frame["Part_nationale_pct"] = frame.Arrivees / national * 100
        chart(px.bar(frame.nlargest(15, "Arrivees").sort_values("Arrivees"), x="Arrivees", y="Marche", orientation="h"), "market_arrivals")
    seasonal = a.read_table("fact_arrivees_saison").merge(a.read_table("dim_Marche"), on="MarcheKey").merge(a.read_table("dim_Saison"), on="SaisonKey")
    seasonal = seasonal[seasonal.AnneeKey.eq(year)]
    if markets:
        seasonal = seasonal[seasonal.Marche.isin(markets)]
    grouped = seasonal.groupby("Saison", as_index=False).Arrivees.sum(min_count=1)
    st.subheader("Repartition par saison")
    chart(px.bar(grouped, x="Saison", y="Arrivees", color="Saison"), "market_seasons")
    st.caption("Haute_moyenne et Basse reprennent les saisons du tableau ONTT. Les groupes presents dans certains tableaux peuvent differer.")
    st.subheader("Nuitees par marche")
    nights = a.read_table("vw_nuitees")
    nights = nights[nights.AnneeKey.eq(year)]
    if markets:
        nights = nights[nights.Marche.isin(markets)]
    st.dataframe(nights[["Marche", "Nuitees"]].sort_values("Nuitees", ascending=False), hide_index=True, width="stretch")
    download(frame[["Marche", "AnneeKey", "Arrivees", "Part_nationale_pct"]], "marches.csv", "download_markets")

elif page == "Hebergement":
    title("Offre et utilisation", "L'hebergement touristique en 2023", "Un instantane par region et categorie. Les taux manquants restent vides.")
    capacity = a.read_table("vw_capacite")
    occupation = a.read_table("vw_occupation")
    c1, c2 = st.columns(2)
    regions = c1.multiselect("Regions (vide = toutes)", sorted(capacity.Region.unique()), key="hotel_regions")
    cats = c2.multiselect("Categories (vide = toutes)", sorted(capacity.Categorie.unique()), key="hotel_cats")
    if regions:
        capacity = capacity[capacity.Region.isin(regions)]
        occupation = occupation[occupation.Region.isin(regions)]
    if cats:
        capacity = capacity[capacity.Categorie.isin(cats)]
        occupation = occupation[occupation.Categorie.isin(cats)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Lits", a.money(a.safe_sum(capacity.Lits), 0))
    c2.metric("Etablissements", a.money(a.safe_sum(capacity.Etablissements), 0))
    c3.metric("Taux renseignes", f"{occupation.Taux_pct.notna().sum()} / {len(occupation)}")
    grouped = capacity.groupby("Region", as_index=False).Lits.sum(min_count=1).sort_values("Lits")
    chart(px.bar(grouped, x="Lits", y="Region", orientation="h"), "hotel_capacity")
    st.subheader("Taux d'occupation par region et categorie (%)")
    st.caption("Le taux national publie est 38,7 %. Une moyenne simple des taux detailles serait trompeuse : les capacites effectivement ouvertes ne sont pas fournies. La valeur source 109,8 % est isolee pour verification.")
    st.dataframe(occupation.pivot(index="Region", columns="Categorie", values="Taux_pct"), width="stretch")
    download(capacity[["Region", "Categorie", "Lits", "Etablissements", "AnneeKey"]], "capacite_2023.csv", "download_hotels")

elif page == "Investissements et patrimoine":
    title("Territoires", "Investissements et patrimoine", "Les investissements de 2023 et la frequentation des sites et musees de 2019 a 2023.")
    investments = a.read_table("vw_investissements")
    investments["Total_MDT"] = investments.Total_kTND / 1000
    c1, c2 = st.columns(2)
    c1.metric("Investissements touristiques 2023 (MDT)", a.money(a.safe_sum(investments.Total_MDT), 3))
    c2.metric("Gouvernorats", str(len(investments)))
    chart(px.bar(investments.sort_values("Total_MDT"), x="Total_MDT", y="Gouvernorat", orientation="h", labels={"Total_MDT": "Millions de dinars"}), "investments")
    st.caption("Les sources expriment les investissements en milliers de dinars. L'interface divise par 1 000 pour afficher des MDT.")
    st.subheader("Sites et musees")
    sites = a.read_table("vw_sites")
    year = year_select("Annee des visites", sites.AnneeKey, "sites_year")
    sites = sites[sites.AnneeKey.eq(year)]
    chart(px.bar(sites.nlargest(12, "Visiteurs").sort_values("Visiteurs"), x="Visiteurs", y="Site", orientation="h"), "sites")
    download(sites[["Site", "AnneeKey", "Visiteurs"]], "visiteurs_sites.csv", "download_sites")
    with st.expander("Agences et restaurants"):
        agencies = a.read_table("fact_agences").merge(a.read_table("dim_Region"), on="RegionKey").merge(a.read_table("dim_Licence"), on="LicenceKey")
        restaurants = a.read_table("fact_restaurants").merge(a.read_table("dim_Region"), on="RegionKey").merge(a.read_table("dim_ClasseRestaurant"), on="ClasseRestaurantKey")
        st.dataframe(agencies[["AnneeKey", "Region", "Licence", "Agences"]], hide_index=True, width="stretch")
        st.dataframe(restaurants[["AnneeKey", "Region", "ClasseRestaurant", "Restaurants"]], hide_index=True, width="stretch")

elif page == "Qualite et donnees":
    title("Tracabilite", "Voir et verifier les donnees", "Chaque observation conserve la source, la feuille et la ligne d'origine.")
    report = a.quality()
    c1, c2, c3 = st.columns(3)
    c1.metric("Controles reussis", f"{sum(c['Statut']=='OK' for c in report['controles'])} / {len(report['controles'])}")
    c2.metric("Serie mensuelle", "96 mois")
    c3.metric("Dernier ETL", report["execution_utc"][:10])
    st.caption("Les lignes d'audit incluent les exclusions normales de totaux et de pourcentages. Leur nombre ne correspond pas a un nombre d'erreurs.")
    for note in report["limites"]:
        st.caption(note)
    controls = pd.read_csv(OUTPUT / "controles.csv")
    st.dataframe(controls, hide_index=True, width="stretch")
    with st.expander("Lignes ecartees et valeurs manquantes"):
        audit = pd.read_csv(OUTPUT / "audit_lignes.csv")
        level = st.selectbox("Afficher", ["Tous", "ATTENTION", "INFO"], key="audit_level")
        st.dataframe(audit if level == "Tous" else audit[audit.Niveau.eq(level)], hide_index=True, width="stretch")
        download(audit, "audit_lignes.csv", "download_audit")
    table = st.selectbox("Explorer une table ou une vue", sorted(a.ALLOWED), key="explorer_table")
    frame = a.read_table(table)
    st.dataframe(frame, hide_index=True, width="stretch")
    download(frame, f"{table}.csv", "download_table")
    if st.button("Relancer l'ETL depuis les fichiers inclus", key="refresh_etl"):
        with st.spinner("Reconstruction et controles..."):
            run_pipeline()
        st.success("La base a ete reconstruite. Les pages utilisent les nouvelles valeurs.")
        st.rerun()

elif page == "Power BI":
    title("Tableaux de bord", "Power BI", "Le projet Power BI fourni utilise les tables exportees du DWH et des mesures DAX.")
    st.write("1. Apres extraction du ZIP, lancez INSTALLER_WINDOWS.bat puis ouvrez powerbi/Tourisme_Tunisie.pbip avec Power BI Desktop.")
    st.write("2. Cliquez sur Actualiser. Le chemin des fichiers CSV est configure automatiquement lors de l'installation.")
    st.write("3. Pour afficher le rapport ici apres publication dans votre espace Power BI, renseignez son URL d'integration securisee dans le fichier de configuration.")
    st.caption("Les fichiers Power BI sont fournis en format PBIP/PBIR. Les schemas JSON sont controles. L'ouverture et le rendu dans Power BI Desktop restent a verifier sous Windows.")
    config_path = ROOT / "config.local.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    url = os.environ.get("POWERBI_EMBED_URL", config.get("powerbi_embed_url", "")).strip()
    if url:
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname == "app.powerbi.com" and parsed.path.rstrip("/") == "/reportEmbed":
            components.iframe(url, height=760, scrolling=True)
            st.caption("L'acces depend de votre compte et des droits Power BI. Les filtres de cette page sont ceux du rapport integre.")
        else:
            st.error("Utilisez une URL HTTPS d'integration securisee app.powerbi.com/reportEmbed.")
    else:
        st.info("Le rapport Power BI peut etre utilise localement dans Desktop. L'integration dans cette page attend l'URL de votre rapport publie. Les autres pages de l'application fonctionnent deja sans compte Power BI.")
    st.subheader("Apercu local des memes donnees")
    frame = a.monthly()
    chart(px.line(frame, x="Date", y="Recettes_MDT", labels={"Recettes_MDT": "Recettes (MDT)"}), "powerbi_local")
    with st.expander("Mesures DAX incluses"):
        path = ROOT / "powerbi" / "mesures.dax"
        st.code(path.read_text(encoding="utf-8") if path.exists() else "Lancez python scripts/configure_powerbi.py", language="text")

else:
    title("Semaine 5", "Espace previsions", "L'interface et la table de stockage sont pretes pour l'etape IA du projet.")
    forecasts = a.read_table("fact_previsions")
    if forecasts.empty:
        st.info("Aucune prevision pour le moment. Le perimetre livre s'arrete a la semaine 4.")
        frame = a.monthly()
        chart(px.line(frame, x="Date", y="Recettes_MDT", labels={"Recettes_MDT": "Historique observe (MDT)"}), "forecast_history")
        st.write("La cible proposee est la recette touristique mensuelle. En semaine 5, il faudra comparer un modele statistique et un modele d'apprentissage, puis les evaluer sur une periode gardee a part.")
    else:
        calendar = a.read_table("dim_Mois")[["MoisKey", "Date"]]
        visible = forecasts.merge(calendar, on="MoisKey", validate="many_to_one")
        target = st.selectbox("Cible", sorted(visible.Cible.unique()), key="forecast_target")
        models = st.multiselect("Modeles", sorted(visible.Modele.unique()), default=sorted(visible.Modele.unique()), key="forecast_models")
        visible = visible[visible.Cible.eq(target) & visible.Modele.isin(models)]
        chart(px.line(visible, x="Date", y="Valeur_MDT", color="Modele", markers=True), "forecast_values")
        st.dataframe(visible, hide_index=True, width="stretch")
        download(visible, "previsions.csv", "download_forecasts")

st.divider()
st.caption("ONTT : tourisme tunisien en chiffres, extrait 2023 · BCT : cours interbancaires mensuels · Projet local, semaines 1 a 4")
