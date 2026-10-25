# -*- coding: utf-8 -*-
"""
ASC AFRICA — Plateforme de gestion associative
Version corrigée — bannière ASC AFRICA, pied de page YAM et navigation bleu/blanc animée
Version Supabase PostgreSQL : adhérents, cartes, cotisations, caisse, activités,
actualités, partenaires, rapports, exports et journal d'audit.
Lancer : streamlit run africa.py
"""
from pathlib import Path
from datetime import date, datetime
import sqlite3
import psycopg2
from psycopg2 import IntegrityError, sql as pg_sql
from psycopg2.extras import RealDictCursor, execute_values
from psycopg2.pool import ThreadedConnectionPool
import hashlib
import secrets
import urllib.parse
import html
import os
import base64

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
    from io import BytesIO
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

APP_DIR = Path(__file__).resolve().parent

# Les images ne sont plus intégrées au code : elles seront ajoutées séparément si nécessaire.
LEGACY_DB_PATH = APP_DIR / "asc_africa.db"  # ancienne base SQLite : import automatique et sécurisé au premier démarrage
LOGO_PATHS = [APP_DIR / "im3.png", APP_DIR / "logo_asc_africa.png", APP_DIR / "africa.png", APP_DIR / "logo.png"]
YAM_LOGO_PATHS = [APP_DIR / "Logo YAM(1).png", APP_DIR / "logo_yam.png", APP_DIR / "yam_logo.png"]
CLUB = "ASC AFRICA"
SLOGAN = "AFRICA KASSÉ, AFRICA REK"
# Compte principal d’administration : les identifiants restent dans secrets.toml,
# jamais dans le code source.
_APP_CONFIG = st.secrets.get("app", {})
ADMIN_USER = str(_APP_CONFIG.get("initial_admin_username", os.getenv("ASC_ADMIN_USER", "iy@2012")))
ADMIN_PASSWORD = str(_APP_CONFIG.get("initial_admin_password", os.getenv("ASC_ADMIN_PASSWORD", "")))
WHATSAPP_COUNTRY = "221"
CURRENCY = "FCFA"
BLUE = "#123B75"
LIGHT_BLUE = "#EAF2FC"
WHITE = "#FFFFFF"
GOLD = "#D7A62A"

# Utilise le véritable logo comme icône d’onglet/favori lorsqu’il est présent.
_FAVICON = next((p for p in LOGO_PATHS if p.exists()), None)
st.set_page_config(page_title="ASC AFRICA | Gestion & communauté",
                   page_icon=str(_FAVICON) if _FAVICON else "⚽",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
:root{{--club-blue:{BLUE};--club-light:{LIGHT_BLUE};--club-gold:{GOLD};}}
.stApp{{background:linear-gradient(180deg,#fff 0%,#f3f7fb 100%);color:#172033;}}
[data-testid="stHeader"],[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stStatusWidget"],[data-testid="stAppDeployButton"],#MainMenu,footer{{visibility:hidden;}}
.block-container{{padding-top:1.2rem;padding-bottom:0!important;max-width:1720px;}}
.hero{{position:relative;isolation:isolate;padding:clamp(22px,4vw,42px);border-radius:26px;color:#fff;background:radial-gradient(circle at 88% 10%,rgba(79,145,218,.72) 0,transparent 30%),linear-gradient(125deg,#07172e 0%,#123b75 58%,#087e8b 100%);box-shadow:0 18px 45px rgba(18,59,117,.16);margin-bottom:22px;overflow:hidden;border:1px solid rgba(255,255,255,.18);}}
.hero:before{{content:"";position:absolute;z-index:-1;width:230px;height:230px;right:-75px;bottom:-135px;border:1px solid rgba(255,255,255,.22);border-radius:50%;box-shadow:0 0 0 22px rgba(255,255,255,.035),0 0 0 46px rgba(255,255,255,.025);}}
.hero h1{{font-size:clamp(2.2rem,5vw,4.6rem);font-weight:950;letter-spacing:-.045em;margin:0;line-height:1.05;}}
.hero p{{font-size:clamp(1rem,2vw,1.22rem);margin:.8rem 0 0;max-width:850px;line-height:1.65;}}
.kicker{{font-size:.76rem;letter-spacing:.18em;text-transform:uppercase;font-weight:850;color:#f8d77b;margin-bottom:12px;}}
.card{{padding:20px;border-radius:20px;background:white;border:1px solid #e0e8f2;box-shadow:0 8px 24px #123b750b;}}
.card-label{{color:#64748b;font-size:.86rem;font-weight:750;}}
.card-value{{font-size:clamp(1.1rem,2vw,1.7rem);color:{BLUE};font-weight:900;margin-top:5px;}}
.section{{font-size:clamp(1.25rem,2vw,1.7rem);font-weight:900;color:{BLUE};margin:1rem 0;letter-spacing:-.02em;}}
.stButton>button,.stDownloadButton>button{{border-radius:12px;font-weight:800;min-height:2.7rem;}}
.stButton>button[kind="primary"]{{background:{BLUE};border:0;}}
div[data-testid="stMetric"]{{background:#fff;border:1px solid #dce7f7;border-radius:16px;padding:14px;}}
div[data-testid="stTabs"] button{{font-weight:800;}}
/* Navigation bleu & blanc : barre compacte, active visible et animée */
div[data-testid="stRadio"] div[role="radiogroup"]{{
  display:flex;align-items:stretch;gap:7px;flex-wrap:wrap;
  padding:8px;background:linear-gradient(110deg,#f7fbff,#e8f1ff);
  border:1px solid #c8daf4;border-radius:18px;
  box-shadow:0 8px 24px rgba(18,59,117,.10);position:relative;
}}
div[data-testid="stRadio"] div[role="radiogroup"] label{{
  position:relative;isolation:isolate;overflow:hidden;
  background:#fff;color:#123B75;border:1px solid #d5e3f7;
  padding:10px 15px;border-radius:12px;font-weight:850;
  transition:background .22s ease,color .22s ease,transform .22s ease,box-shadow .22s ease,border-color .22s ease;
  box-shadow:0 2px 5px rgba(18,59,117,.04);cursor:pointer;
}}
div[data-testid="stRadio"] div[role="radiogroup"] label:before{{
  content:"";position:absolute;z-index:-1;inset:0;
  background:linear-gradient(115deg,#123B75,#2368b7);
  transform:translateY(105%);transition:transform .24s ease;border-radius:inherit;
}}
div[data-testid="stRadio"] div[role="radiogroup"] label:hover{{
  color:#123B75;border-color:#6f9bd8;transform:translateY(-2px);
  box-shadow:0 7px 15px rgba(18,59,117,.13);
}}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){{
  color:#fff!important;background:#123B75;border-color:#123B75;
  box-shadow:0 7px 18px rgba(18,59,117,.24);transform:translateY(-1px);
}}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked):before{{transform:translateY(0)}}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p,
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) span{{color:#fff!important}}
div[data-testid="stRadio"] div[role="radiogroup"] input{{accent-color:#123B75}}
@keyframes navGlow{{0%,100%{{box-shadow:0 7px 18px rgba(18,59,117,.18)}}50%{{box-shadow:0 9px 24px rgba(35,104,183,.30)}}}}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){{animation:navGlow 2.8s ease-in-out infinite}}
@media(max-width:760px){{
  div[data-testid="stRadio"] div[role="radiogroup"]{{gap:6px;padding:7px;border-radius:14px}}
  div[data-testid="stRadio"] div[role="radiogroup"] label{{padding:8px 10px;font-size:.88rem}}
}}
@media(prefers-reduced-motion:reduce){{
  div[data-testid="stRadio"] div[role="radiogroup"] label,
  div[data-testid="stRadio"] div[role="radiogroup"] label:before{{transition:none;animation:none}}
}}
.news-ticker{{background:#0c294f;color:#fff;border-left:6px solid #f4bd38;padding:13px 17px;border-radius:12px;margin:12px 0 20px;font-weight:750;line-height:1.5;}}
.eyebrow{{text-transform:uppercase;letter-spacing:.13em;font-size:.72rem;font-weight:900;color:#0b8278;}}
.news-card{{background:#fff;border:1px solid #e2eaf3;border-radius:18px;padding:20px 22px;margin:12px 0;box-shadow:0 8px 22px #0c294f0a;}}
.news-card h3{{color:#123b75;margin:.45rem 0 .6rem;font-size:1.25rem;}}
.pill{{display:inline-block;background:#e7f6f2;color:#087e70;border-radius:30px;padding:5px 10px;font-size:.75rem;font-weight:850;}}
.feature-card{{background:linear-gradient(140deg,#fff,#eef5fb);border:1px solid #dbe7f2;border-radius:20px;padding:20px;height:100%;}}
.site-footer{{position:relative;margin-top:4px!important;padding:clamp(20px,3vw,32px) 18px 0;border-radius:24px 24px 0 0;background:radial-gradient(circle at 50% 0,rgba(58,122,192,.3),transparent 42%),linear-gradient(135deg,#07172e,#123b75 62%,#0b8278);color:#fff;text-align:center;overflow:hidden;border-top:4px solid #d7a62a;box-shadow:0 -8px 28px rgba(18,59,117,.07);}}
.site-footer .credit{{font-size:1.05rem;font-weight:850;line-height:1.6;}}
.site-footer .subcredit{{color:#d4e1f1;font-size:.88rem;line-height:1.7;}}\n.logo-band{{display:flex;align-items:center;justify-content:center;gap:22px;flex-wrap:wrap;margin:18px auto 8px;}}
.brand-lockup{{display:flex;align-items:center;gap:clamp(14px,3vw,32px);justify-content:center;flex-wrap:wrap;padding:20px 0 0;}}
.brand-lockup img{{width:auto;height:auto;max-width:min(220px,38vw);max-height:190px;object-fit:contain;filter:drop-shadow(0 10px 24px #0003);}}
/* Logo d'en-tête aligné sur la hauteur visuelle de la bannière */
div[data-testid="stImage"]{{display:flex;align-items:center;justify-content:center;height:100%;}}
div[data-testid="stImage"] img{{max-height:clamp(150px,18vw,230px);max-width:100%;width:auto;object-fit:contain;filter:drop-shadow(0 10px 24px rgba(18,59,117,.20));border-radius:20px;}}
@media(max-width:760px){{div[data-testid="stImage"] img{{max-height:150px;max-width:42vw}}}}

.brand-seal{{width:clamp(86px,12vw,150px);height:clamp(86px,12vw,150px);object-fit:contain;display:block;margin:0 auto 18px;}}
.public-nav-label{{font-size:clamp(.78rem,1vw,.95rem);text-transform:uppercase;letter-spacing:.12em;font-weight:950;color:#0b8278;margin:8px 0 8px;}}
.nav-help-mobile{{display:none;color:#526176;font-size:.86rem;line-height:1.45;margin:3px 0 8px;}}
[data-testid="stSelectbox"] [data-baseweb="select"]{{min-height:52px;border-radius:14px!important;border:2px solid #c8daf4!important;box-shadow:0 6px 18px rgba(18,59,117,.09);background:linear-gradient(120deg,#fff,#f2f7ff);}}
[data-testid="stSelectbox"] [data-baseweb="select"] *{{font-weight:850!important;color:#123b75!important;font-size:1rem!important;}}
@media(max-width:700px){{
 .public-nav-label{{font-size:.8rem;letter-spacing:.08em;margin-top:10px;}}
 .nav-help-mobile{{display:block;}}
 [data-testid="stSelectbox"] [data-baseweb="select"]{{min-height:56px!important;width:100%!important;}}
 [data-testid="stSelectbox"] [data-baseweb="select"] *{{font-size:1rem!important;}}
}}
.admin-banner{{border-radius:22px;padding:20px 24px;background:linear-gradient(115deg,#07172e,#123b75 70%,#0b8278);color:white;margin:10px 0 18px;box-shadow:0 18px 40px #123b7522;}}
.admin-banner h2{{margin:0;color:white;font-size:clamp(1.4rem,3vw,2.3rem);font-weight:950;}}
.admin-banner p{{margin:7px 0 0;color:#dce8f7;}}
.report-hero{{padding:24px;border-radius:22px;background:linear-gradient(125deg,#07172e,#123b75 65%,#0b8278);color:white;margin:12px 0 20px;border-bottom:5px solid #d7a62a;}}
.report-hero h2{{font-size:clamp(1.6rem,3vw,2.6rem);font-weight:950;color:#fff;margin:8px 0;}}
.report-hero p{{color:#dbe7f6;margin:0;}}
.report-stat{{border-radius:16px;padding:16px;background:#fff;border:1px solid #dbe5f2;border-top:4px solid #123b75;box-shadow:0 8px 20px #07172e0b;min-height:92px;}}
.report-stat.green{{border-top-color:#0b8278}}.report-stat.gold{{border-top-color:#d7a62a}}.report-stat.red{{border-top-color:#c2414b}}
.footer-bottom{{margin:14px -18px 0;padding:18px clamp(12px,3vw,36px);background:#061326;color:#cbd8e8;font-size:.92rem;font-weight:700;}}
.yam-activity-strip{{position:relative;display:block!important;visibility:visible!important;opacity:1!important;min-height:58px;overflow:hidden;margin:12px auto 0;padding:16px 0;border-top:1px solid #ffffff55;border-bottom:1px solid #ffffff55;background:#061326!important;color:#fff!important;z-index:2;}}
.yam-activity-track{{display:flex!important;align-items:center;width:max-content;min-width:200%;gap:34px;white-space:nowrap;animation:yamMarquee 26s linear infinite;font-weight:900;letter-spacing:.07em;font-size:clamp(.85rem,1.2vw,1rem);color:#fff!important;will-change:transform;}}
.yam-activity-track span{{display:inline-flex;align-items:center;gap:12px;}}
.yam-activity-track span{{flex:0 0 auto;color:#fff!important;}}.yam-activity-track b{{color:#f4bd38!important;}}@media(prefers-reduced-motion:reduce){{.yam-activity-strip{{overflow:visible}}.yam-activity-track{{min-width:0;width:100%;white-space:normal;justify-content:center;flex-wrap:wrap;animation:none!important;padding:0 12px}}}}
.yam-footer-logo{{max-width:clamp(120px,16vw,190px)!important;max-height:clamp(100px,12vw,150px)!important;padding:12px!important;}}
@keyframes yamMarquee{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
.site-footer{{padding-top:clamp(18px,2.5vw,30px)!important;margin-top:0!important;}}
.site-footer .credit{{font-size:clamp(1.25rem,2.8vw,2.25rem)!important;max-width:1100px;margin:14px auto!important;line-height:1.25!important;}}
.site-footer .subcredit{{font-size:clamp(.95rem,1.3vw,1.12rem);}}
@media(max-width:700px){{.yam-activity-track{{animation-duration:19s}}.yam-footer-logo{{max-width:115px!important;max-height:100px!important}}}}
@media(prefers-reduced-motion:reduce){{.yam-activity-track{{animation:none;white-space:normal;justify-content:center;flex-wrap:wrap;width:auto;padding:0 12px}}}}
@keyframes riseIn{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:translateY(0)}}}}
.hero,.news-card,.feature-card,.report-hero{{animation:riseIn .45s ease both}}\n.about-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:14px 0;}}
.hero:after{{content:"";display:block;height:3px;width:100%;margin-top:22px;background:linear-gradient(90deg,#f4bd38,rgba(255,255,255,.35),transparent);border-radius:8px}}
.stApp{{font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
.news-card{{transition:transform .18s ease,box-shadow .18s ease}}
.news-card:hover,.feature-card:hover{{transform:translateY(-2px);box-shadow:0 14px 32px #123b7517}}
.club-gallery-card{{border-radius:24px;overflow:hidden;background:#fff;border:1px solid #e1e9f4;box-shadow:0 16px 40px rgba(7,23,46,.12);padding:12px;height:100%;transition:transform .35s ease,box-shadow .35s ease;animation:clubRise .8s both;}}
.club-gallery-card:hover{{transform:translateY(-7px);box-shadow:0 22px 48px rgba(7,23,46,.19)}}
.club-gallery-card img{{width:100%;height:clamp(230px,29vw,430px);object-fit:cover;object-position:center;border-radius:17px;display:block;transition:transform .7s ease;}}
.club-gallery-card:hover img{{transform:scale(1.035)}}
.club-gallery-message{{padding:14px 8px 7px;color:#123b75;font-weight:850;font-size:clamp(1rem,1.4vw,1.18rem);line-height:1.4}}
.club-gallery-sub{{padding:0 8px 8px;color:#64748b;font-size:.94rem;line-height:1.55}}
@media(max-width:700px){{.club-gallery-card img{{height:clamp(220px,68vw,360px)}}}}
@media(prefers-reduced-motion:reduce){{.club-gallery-card,.club-gallery-card img{{animation:none!important;transition:none!important}}}}
.news-cover{{display:block;width:100%;height:clamp(300px,42vw,620px);max-height:none;object-fit:cover;object-position:center center;border-radius:20px;margin:14px 0 20px;box-shadow:0 14px 34px rgba(7,23,46,.16);border:1px solid rgba(18,59,117,.10);background:#eaf2fc}}
.news-card:has(.news-cover){{padding:clamp(18px,2.4vw,34px);overflow:hidden}}
.news-card:has(.news-cover) h3{{font-size:clamp(1.35rem,2.4vw,2rem);line-height:1.2}}
@media(max-width:700px){{.news-cover{{height:clamp(240px,70vw,390px);border-radius:15px}}}}
a{{overflow-wrap:anywhere}}
.stDownloadButton>button{{border:1px solid #cbd8e8}}
@media(prefers-reduced-motion:reduce){{*,*:before,*:after{{animation:none!important;transition:none!important;scroll-behavior:auto!important}}}}
@media(max-width:700px){{.hero{{padding:22px 18px;border-radius:18px;}}.block-container{{padding-left:.8rem;padding-right:.8rem;}}.news-card{{padding:16px;}}div[data-testid="stRadio"] div[role="radiogroup"]{{gap:5px;}}div[data-testid="stRadio"] div[role="radiogroup"] label{{padding:7px 9px;font-size:.82rem;}}}}
/* ASC AFRICA signature motion: contenus qui entrent progressivement au défilement */
@keyframes africaReveal{{from{{opacity:0;transform:translateY(34px) scale(.985);filter:blur(3px)}}to{{opacity:1;transform:translateY(0) scale(1);filter:blur(0)}}}}
@keyframes africaShimmer{{0%{{background-position:0% 50%}}100%{{background-position:200% 50%}}}}
.hero{{background-size:160% 160%;animation:africaReveal .45s cubic-bezier(.2,.75,.2,1) both;}}
.stButton>button{{transition:transform .22s ease,box-shadow .22s ease,filter .22s ease;}}
.stButton>button:hover{{transform:translateY(-2px);box-shadow:0 10px 24px rgba(18,59,117,.18);filter:saturate(1.12);}}
.news-cover{{transition:transform .65s cubic-bezier(.2,.7,.2,1),filter .5s ease;}}
.news-card:hover .news-cover{{transform:scale(1.018);filter:saturate(1.08);}}
@supports (animation-timeline: view()){{
  .news-card,.feature-card,.report-stat,.card,div[data-testid="stMetric"],.report-hero{{
    animation-name:africaReveal;animation-duration:1ms;animation-timing-function:linear;
    animation-fill-mode:both;animation-timeline:view();animation-range:entry 0% entry 38%;
  }}
  .news-card:nth-of-type(3n+2),.feature-card:nth-of-type(3n+2){{animation-range:entry 4% entry 42%;}}
  .news-card:nth-of-type(3n),.feature-card:nth-of-type(3n){{animation-range:entry 8% entry 46%;}}
}}
@media(prefers-reduced-motion:reduce){{.hero{{animation:none!important}}.news-cover{{transition:none!important}}}}


/* Identité visuelle signature : stade nocturne, or et vert, pensée pour toutes les tailles */
:root{{color-scheme:light;--club-ink:#07172e;--club-teal:#087e78;--club-gold:#f4bd38;--club-line:#dce7f4;}}
html{{scroll-behavior:smooth;-webkit-text-size-adjust:100%;}}
.stApp{{background:radial-gradient(ellipse at 4% 0%,rgba(215,166,42,.075),transparent 28%),radial-gradient(ellipse at 96% 18%,rgba(8,126,120,.07),transparent 25%),linear-gradient(180deg,#fff 0%,#f3f7fc 58%,#edf3f9 100%);}}
.block-container{{width:100%;max-width:1900px;padding-left:clamp(14px,2.4vw,42px);padding-right:clamp(14px,2.4vw,42px);padding-top:clamp(12px,1.8vw,28px);}}
.hero{{border-radius:clamp(18px,2vw,30px);border-bottom:4px solid var(--club-gold);}}
.hero h1{{font-size:clamp(2.15rem,5.2vw,5.2rem);overflow-wrap:anywhere;}}
.hero p{{font-size:clamp(.98rem,1.35vw,1.3rem);}}
.news-card,.feature-card,.card,.report-stat{{min-width:0;overflow-wrap:anywhere;}}
.news-card{{border-radius:clamp(15px,1.5vw,24px);box-shadow:0 10px 30px rgba(7,23,46,.055);}}
.news-card h3{{font-size:clamp(1.2rem,1.8vw,1.85rem);line-height:1.25;overflow-wrap:anywhere;}}
.news-cover{{width:100%;height:clamp(320px,46vw,760px);object-fit:cover;object-position:center;border-radius:clamp(14px,1.8vw,24px);background:#eaf2fc;}}
.stButton>button,.stDownloadButton>button{{min-height:44px;padding:.55rem 1rem;border-radius:13px;white-space:normal;line-height:1.25;}}
input,textarea,[data-baseweb="select"]{{border-radius:10px!important;}}
div[data-testid="stDataFrame"],div[data-testid="stTable"]{{max-width:100%;}}
div[data-testid="stDataFrame"]{{overflow-x:auto;}}
[data-testid="stTabs"] [role="tab"]{{min-height:44px;font-weight:800;}}
.site-footer{{margin-left:calc(-1 * clamp(14px,2.4vw,42px));margin-right:calc(-1 * clamp(14px,2.4vw,42px));}}

/* Grand écran / ordinateur de bureau */
@media(min-width:1500px){{
  .block-container{{max-width:1900px;padding-left:48px;padding-right:48px;}}
  .news-cover{{height:clamp(560px,40vw,820px);}}
  .news-card{{padding:clamp(24px,2vw,38px);}}
  .card,.feature-card{{padding:clamp(22px,1.8vw,34px);}}
}}
/* MacBook et petits ordinateurs portables */
@media(min-width:1024px) and (max-width:1499px){{
  .block-container{{padding-left:clamp(20px,2.2vw,32px);padding-right:clamp(20px,2.2vw,32px);}}
  .news-cover{{height:clamp(340px,36vw,560px);}}
  .hero{{padding:clamp(24px,3vw,38px);}}
}}
/* Tablettes en paysage et en portrait */
@media(min-width:701px) and (max-width:1023px){{
  .block-container{{padding-left:20px;padding-right:20px;}}
  .hero{{padding:26px 24px;}}
  .hero h1{{font-size:clamp(2.2rem,6vw,3.8rem);}}
  .news-cover{{height:clamp(300px,48vw,480px);}}
  .news-card,.feature-card,.card{{padding:18px;}}
  div[data-testid="stRadio"] div[role="radiogroup"]{{gap:6px;}}
  div[data-testid="stRadio"] div[role="radiogroup"] label{{padding:9px 11px;font-size:.9rem;}}
}}
/* Téléphones : zones tactiles généreuses, lecture confortable et aucune largeur débordante */
@media(max-width:700px){{
  .block-container{{padding:10px 12px 28px!important;}}
  .hero{{padding:24px 18px;border-radius:18px;margin-bottom:14px;}}
  .hero h1{{font-size:clamp(2.15rem,10vw,3.2rem);letter-spacing:-.04em;}}
  .hero p{{font-size:1rem;line-height:1.55;}}
  .kicker{{font-size:.68rem;letter-spacing:.12em;line-height:1.5;}}
  .news-ticker{{font-size:.88rem;padding:12px 13px;}}
  .news-card{{padding:15px;margin:10px 0;border-radius:16px;}}
  .news-cover{{height:clamp(250px,72vw,390px);border-radius:13px;margin:12px 0 16px;}}
  .news-card h3{{font-size:1.3rem;}}
  .feature-card,.card{{padding:16px;border-radius:16px;}}
  .section{{font-size:1.28rem;margin:.9rem 0;}}
  .site-footer{{padding-top:25px;}}
  div[data-testid="stImage"] img{{max-height:clamp(115px,32vw,170px);max-width:min(72vw,240px);}}
  div[data-testid="stRadio"] div[role="radiogroup"]{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:8px;}}
  div[data-testid="stRadio"] div[role="radiogroup"] label{{width:100%;min-width:0;justify-content:center;padding:10px 7px;font-size:.83rem;text-align:center;}}
  input,textarea{{font-size:16px!important;}}
  .stButton>button,.stDownloadButton>button{{width:100%;min-height:46px;}}
  [data-testid="stTabs"] [role="tab"]{{padding-left:10px;padding-right:10px;font-size:.86rem;}}
}}
@media(max-width:380px){{
  .block-container{{padding-left:8px!important;padding-right:8px!important;}}
  .hero{{padding:20px 14px;}}
  .hero h1{{font-size:2rem;}}
  .news-cover{{height:240px;}}
  div[data-testid="stRadio"] div[role="radiogroup"]{{grid-template-columns:minmax(0,1fr);}}
}}
@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto;}}}}

/* Bandeau signature ASC AFRICA : photos et textes couvrent toute la bannière supérieure */
.africa-topband{{position:relative;isolation:isolate;overflow:hidden;display:flex;align-items:center;justify-content:center;min-height:clamp(430px,55vw,680px);padding:clamp(30px,5vw,76px) clamp(18px,5vw,72px);border-radius:clamp(18px,2.2vw,32px);color:#fff;background:#061a3b;border:1px solid #b8d7ff;box-shadow:0 20px 50px #092b5b30;margin:0 0 22px;}}
.africa-topband:before{{content:"";position:absolute;inset:0;z-index:1;pointer-events:none;background:linear-gradient(90deg,#04142b88 0%,#061a3b48 48%,#061a3b18 100%),linear-gradient(0deg,#061a3b9c 0%,transparent 52%,#061a3b12 100%);}}
.africa-top-content{{position:relative;z-index:3;width:min(100%,1100px);text-align:center;margin:auto;padding:clamp(12px,3vw,34px) 0 75px;}}
.africa-topband h1{{font-size:clamp(3rem,8.5vw,7.5rem);line-height:.96;letter-spacing:-.055em;font-weight:1000;margin:14px 0 20px;color:#fff;text-shadow:0 5px 24px #00132f;}}
.africa-topband p{{font-size:clamp(1.05rem,2vw,1.55rem);line-height:1.65;color:#f2f7ff;margin:0 auto;max-width:900px;text-shadow:0 2px 12px #00132f;}}
.africa-topband .top-kicker{{font-size:clamp(.72rem,1.3vw,.95rem);text-transform:uppercase;letter-spacing:.2em;line-height:1.8;font-weight:950;color:#e2eeff;text-shadow:0 2px 10px #00132f;}}
.africa-topband .top-slogan{{display:inline-block;margin-top:24px;padding:12px 20px;border:1px solid #ffffffb0;border-radius:999px;background:#0b2d5db8;color:#fff;font-weight:950;letter-spacing:.045em;box-shadow:0 8px 28px #00132f55;}}
.africa-photo-stage{{position:absolute;z-index:0;inset:0;width:100%;height:100%;min-width:0;overflow:hidden;border-radius:inherit;background:#061a3b;isolation:isolate;}}
.africa-slide{{position:absolute;inset:0;opacity:0;animation:africaTopSlide 21s infinite;}}
.africa-slide img{{position:absolute;inset:0;display:block;width:100%;height:100%;max-width:100%;object-fit:cover;object-position:center;filter:brightness(1.08) contrast(1.04) saturate(1.06);transform:scale(1.015);animation:africaPhotoZoom 21s infinite;}}
.africa-slide:after{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,#061a3b08 0%,transparent 42%,#061a3b9e 100%);pointer-events:none;}}
.africa-slide-caption{{position:absolute;z-index:2;left:clamp(12px,2vw,28px);right:clamp(12px,2vw,28px);bottom:clamp(14px,2.2vw,30px);color:#fff;font-size:clamp(.9rem,1.6vw,1.3rem);font-weight:950;line-height:1.35;text-align:center;text-shadow:0 2px 10px #00132f;}}
.africa-slide-caption small{{display:block;margin-top:5px;font-size:clamp(.72rem,1vw,.88rem);font-weight:650;line-height:1.45;color:#edf5ff;}}
.africa-slide:nth-child(1){{animation-delay:0s}}.africa-slide:nth-child(1) img{{animation-delay:0s}}
.africa-slide:nth-child(2){{animation-delay:3s}}.africa-slide:nth-child(2) img{{animation-delay:3s}}
.africa-slide:nth-child(3){{animation-delay:6s}}.africa-slide:nth-child(3) img{{animation-delay:6s}}
.africa-slide:nth-child(4){{animation-delay:9s}}.africa-slide:nth-child(4) img{{animation-delay:9s}}
.africa-slide:nth-child(5){{animation-delay:12s}}.africa-slide:nth-child(5) img{{animation-delay:12s}}
.africa-slide:nth-child(6){{animation-delay:15s}}.africa-slide:nth-child(6) img{{animation-delay:15s}}
.africa-slide:nth-child(7){{animation-delay:18s}}.africa-slide:nth-child(7) img{{animation-delay:18s}}
@keyframes africaTopSlide{{0%{{opacity:0}} 2%,13%{{opacity:1}} 16%,100%{{opacity:0}}}}
@keyframes africaPhotoZoom{{0%{{transform:scale(1.015)}} 13%{{transform:scale(1.07)}} 16%,100%{{transform:scale(1.07)}}}}
@media(max-width:760px){{.africa-topband{{min-height:clamp(500px,120vw,650px);padding:25px 17px;border-radius:18px}}.africa-top-content{{padding:10px 0 95px}}.africa-topband h1{{font-size:clamp(2.8rem,13vw,5rem)}}.africa-topband p{{font-size:1.02rem;line-height:1.6}}.africa-topband .top-kicker{{letter-spacing:.12em}}.africa-topband .top-slogan{{line-height:1.5;border-radius:16px}}.africa-slide-caption{{font-size:1rem;bottom:13px}}}}
@media(max-width:380px){{.africa-topband{{min-height:520px;padding:20px 13px;border-radius:15px}}.africa-topband .top-slogan{{font-size:.78rem;line-height:1.5;border-radius:15px}}.africa-top-content{{padding-bottom:105px}}}}
@media(prefers-reduced-motion:reduce){{.africa-slide,.africa-slide img{{animation:none}}.africa-slide{{opacity:0}}.africa-slide:first-child{{opacity:1}}.africa-slide img{{transform:none}}}}

/* Défilement XXL : navigation lisible, panneaux dynamiques et contenu révélé au scroll */
:root{{scroll-padding-top:18px;}}
[data-testid="stMainBlockContainer"]{{scroll-behavior:smooth;}}
/* Rubriques publiques : barre de navigation bien visible pendant la lecture */
div[data-testid="stRadio"]:has(input){{position:relative;z-index:20;}}
div[data-testid="stRadio"] div[role="radiogroup"]{{backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);}}
div[data-testid="stRadio"] div[role="radiogroup"] label{{min-height:44px;justify-content:center;}}
/* Onglets de l'administration : défilement horizontal sur petit écran */
div[data-testid="stTabs"] [data-baseweb="tab-list"]{{gap:8px;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin;scrollbar-color:#8aaedb #eaf2fc;padding:7px 4px 12px;}}
div[data-testid="stTabs"] [data-baseweb="tab"]{{flex:0 0 auto;border-radius:13px 13px 8px 8px;padding:10px 16px;border:1px solid #d8e5f5;background:linear-gradient(180deg,#fff,#f3f7fc);transition:transform .22s ease,background .22s ease,box-shadow .22s ease;}}
div[data-testid="stTabs"] [data-baseweb="tab"]:hover{{transform:translateY(-2px);box-shadow:0 8px 18px #123b751a;}}
div[data-testid="stTabs"] button[aria-selected="true"]{{background:linear-gradient(120deg,#123b75,#087e78)!important;color:#fff!important;border-color:#123b75!important;box-shadow:0 8px 20px #123b7528;}}
div[data-testid="stTabs"] button[aria-selected="true"] p{{color:#fff!important;}}
/* Chaque carte entre avec une transition douce ; animation désactivée si l’utilisateur le demande */
@keyframes scrollLift{{from{{opacity:0;transform:translateY(26px) scale(.99)}}to{{opacity:1;transform:translateY(0) scale(1)}}}}
.news-card,.feature-card,.club-gallery-card,.report-stat,.card{{transition:transform .28s ease,box-shadow .28s ease,border-color .28s ease;}}
.news-card:hover,.feature-card:hover,.club-gallery-card:hover,.report-stat:hover,.card:hover{{border-color:#b7cdea;box-shadow:0 16px 36px rgba(18,59,117,.12);}}
@supports (animation-timeline: view()){{
  .club-gallery-card{{animation:scrollLift .7s ease both;animation-timeline:view();animation-range:entry 0% entry 35%;}}
  .about-grid .feature-card{{animation:scrollLift .65s ease both;animation-timeline:view();animation-range:entry 0% entry 40%;}}
}}
/* Confort tactile et lisibilité XXL sur téléphone */
@media(max-width:700px){{
  div[data-testid="stTabs"] [data-baseweb="tab-list"]{{gap:6px;}}
  div[data-testid="stTabs"] [data-baseweb="tab"]{{padding:9px 12px;font-size:.88rem;}}
  div[data-testid="stRadio"] div[role="radiogroup"]{{scrollbar-width:thin;}}
}}
@media(prefers-reduced-motion:reduce){{
  .news-card,.feature-card,.club-gallery-card,.report-stat,.card{{transition:none!important;animation:none!important;}}
  div[data-testid="stTabs"] [data-baseweb="tab"]{{transition:none!important;}}
}}
</style>
""", unsafe_allow_html=True)

# Couche responsive XXL complémentaire : téléphone, tablette, ordinateur et grands écrans.
st.markdown(r"""
<style>
/* Le contenu utilise réellement la largeur disponible, sans débordement horizontal. */
.stApp, [data-testid="stAppViewContainer"], section.main { width:100%; max-width:100%; }
.block-container { width:100%; max-width:1900px!important; padding-left:clamp(12px,2.4vw,42px)!important; padding-right:clamp(12px,2.4vw,42px)!important; }
[data-testid="stHorizontalBlock"] { gap:clamp(10px,1.6vw,26px)!important; align-items:stretch; }
[data-testid="stVerticalBlock"] { min-width:0; }
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li { overflow-wrap:anywhere; }
.hero { width:100%; padding:clamp(20px,4vw,58px)!important; border-radius:clamp(16px,2vw,30px)!important; }
.hero h1 { font-size:clamp(2rem,5.2vw,5.2rem)!important; line-height:1.02!important; }
.hero p { font-size:clamp(1rem,1.5vw,1.35rem)!important; }
.card, .news-card, .feature-card, .report-stat { min-width:0; box-sizing:border-box; }
.card { padding:clamp(14px,1.6vw,26px)!important; }
.news-card { padding:clamp(14px,1.8vw,28px)!important; }
.stButton>button, .stDownloadButton>button, [data-testid="stFormSubmitButton"] button { min-height:46px; padding:10px 16px; white-space:normal; overflow-wrap:anywhere; }
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea, [data-testid="stSelectbox"] div[role="combobox"] { font-size:16px!important; }
[data-testid="stDataFrame"], [data-testid="stTable"] { max-width:100%; overflow-x:auto; }
[data-testid="stTabs"] [data-baseweb="tab-list"] { max-width:100%; overflow-x:auto!important; flex-wrap:nowrap!important; scroll-snap-type:x proximity; }
[data-testid="stTabs"] [data-baseweb="tab"] { flex:0 0 auto!important; scroll-snap-align:start; }
.yam-domain-grid { grid-template-columns:repeat(3,minmax(0,1fr)); }
.site-footer { width:100%; box-sizing:border-box; }

/* Tablettes portrait et paysage */
@media (min-width:701px) and (max-width:1100px) {
  .block-container { padding-left:18px!important; padding-right:18px!important; }
  .hero h1 { font-size:clamp(2.3rem,5vw,3.8rem)!important; }
  .yam-domain-grid { grid-template-columns:repeat(2,minmax(0,1fr))!important; }
  [data-testid="stHorizontalBlock"] { gap:12px!important; }
  .card-value { font-size:clamp(1.15rem,2.2vw,1.65rem)!important; }
}

/* Téléphones : taille de texte confortable, contrôles tactiles et aucun élément coupé. */
@media (max-width:700px) {
  .block-container { padding-top: .65rem!important; padding-left:12px!important; padding-right:12px!important; padding-bottom:0!important; }
  .hero { padding:20px 16px!important; margin-bottom:14px!important; }
  .hero h1 { font-size:clamp(2rem,9vw,3rem)!important; letter-spacing:-.035em!important; }
  .hero p { font-size:1rem!important; line-height:1.55!important; }
  .kicker, .eyebrow { font-size:.68rem!important; letter-spacing:.1em!important; }
  .section { font-size:1.35rem!important; line-height:1.25!important; }
  .card, .feature-card, .news-card, .report-hero { border-radius:15px!important; padding:15px!important; }
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap!important; gap:10px!important; }
  [data-testid="stHorizontalBlock"] > [data-testid="column"] { min-width:100%!important; width:100%!important; flex:1 1 100%!important; }
  div[data-testid="stRadio"] div[role="radiogroup"] { display:flex!important; flex-wrap:nowrap!important; overflow-x:auto!important; gap:7px!important; padding:7px!important; }
  div[data-testid="stRadio"] div[role="radiogroup"] label { flex:0 0 auto!important; min-height:44px!important; padding:10px 13px!important; font-size:.9rem!important; }
  [data-testid="stTabs"] [data-baseweb="tab-list"] { gap:6px!important; padding:6px 2px 10px!important; }
  [data-testid="stTabs"] [data-baseweb="tab"] { padding:10px 12px!important; min-height:44px!important; font-size:.88rem!important; }
  .yam-domain-grid { grid-template-columns:1fr!important; gap:9px!important; }
  .yam-domain-card { min-height:0!important; padding:13px!important; }
  .yam-domain-card p { font-size:.92rem!important; line-height:1.5!important; }
  .yam-footer-headline { font-size:clamp(1.35rem,6vw,2rem)!important; }
  .yam-footer-intro { font-size:.95rem!important; line-height:1.6!important; }
  .yam-activity-strip { margin-left:-12px!important; margin-right:-12px!important; }
  .footer-bottom { font-size:.78rem!important; line-height:1.5!important; overflow-wrap:anywhere; }
  .stButton>button, .stDownloadButton>button { width:100%; }
  [data-testid="stImage"] img { max-width:100%!important; max-height:170px!important; }
}

/* Très petits téléphones */
@media (max-width:380px) {
  .block-container { padding-left:8px!important; padding-right:8px!important; }
  .hero { padding:16px 12px!important; }
  .hero h1 { font-size:1.85rem!important; }
  .card-value { font-size:1.15rem!important; }
  .yam-domain-card { grid-template-columns:30px minmax(0,1fr)!important; }
}
@media (prefers-reduced-motion:reduce) {
  *, *::before, *::after { scroll-behavior:auto!important; animation-duration:.01ms!important; animation-iteration-count:1!important; transition-duration:.01ms!important; }
}
</style>
""", unsafe_allow_html=True)

components.html("""
<script>
(function () {
  function installReveal() {
    try {
      const doc = window.parent.document;
      if (!doc || doc.documentElement.dataset.ascRevealReady === "1") return;
      doc.documentElement.dataset.ascRevealReady = "1";
      const style = doc.createElement("style");
      style.textContent = `
        .asc-scroll-reveal { opacity: 0; transform: translateY(34px) scale(.985);
          filter: none; transition: opacity .35s ease, transform .35s ease; }
        .asc-scroll-reveal.asc-visible { opacity: 1; transform: translateY(0) scale(1); filter: none; }
        .asc-scroll-reveal.asc-visible:hover { transform: translateY(-4px); }
        @media (prefers-reduced-motion: reduce) {
          .asc-scroll-reveal, .asc-scroll-reveal.asc-visible { opacity: 1; transform: none;
            filter: none; transition: none; }
        }`;
      doc.head.appendChild(style);
      const selectors = ".news-card, .feature-card, .club-gallery-card, .report-stat, .card, .report-hero, div[data-testid='stMetric'], div[data-testid='stDataFrame'], div[data-testid='stTable']";
      const seen = new WeakSet();
      let observer = null;
      if ("IntersectionObserver" in window.parent) {
        observer = new window.parent.IntersectionObserver(entries => {
          entries.forEach(entry => {
            if (entry.isIntersecting) {
              entry.target.classList.add("asc-visible");
              observer.unobserve(entry.target);
            }
          });
        }, { threshold: 0.08, rootMargin: "0px 0px -35px 0px" });
      }
      function scan() {
        doc.querySelectorAll(selectors).forEach(el => {
          if (seen.has(el)) return;
          seen.add(el);
          el.classList.add("asc-scroll-reveal");
          if (observer) observer.observe(el);
          else el.classList.add("asc-visible");
        });
      }
      scan();
      let scanQueued = false;
      new window.parent.MutationObserver(() => {
        if (scanQueued) return;
        scanQueued = true;
        window.parent.requestAnimationFrame(() => { scanQueued = false; scan(); });
      }).observe(doc.body, {childList:true,subtree:true});
    } catch (e) { /* Les styles CSS de secours restent actifs. */ }
  }
  installReveal();
})();
</script>
""", height=0, scrolling=False)

class PgCompatConnection:
    """Adaptateur léger pour conserver les appels SQL existants tout en utilisant PostgreSQL."""
    def __init__(self, raw, pool):
        self.raw = raw
        self.pool = pool
        self.closed = False

    @staticmethod
    def _sql(sql):
        # Les requêtes de l'application utilisent des paramètres DB-API « ? ».
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        cur = self.raw.cursor(cursor_factory=RealDictCursor)
        cur.execute(self._sql(sql), tuple(params or ()))
        return cur

    def executescript(self, script):
        """Exécute le schéma en un seul aller-retour réseau PostgreSQL.

        L'ancienne boucle envoyait chaque CREATE/ALTER/INDEX séparément au serveur,
        ce qui multipliait la latence Supabase au démarrage. Ici le script DDL sans
        paramètres est envoyé en une seule commande multi-instructions.
        """
        cur = self.raw.cursor()
        try:
            cur.execute(script)
        finally:
            cur.close()

    def table_columns(self, table):
        cur = self.raw.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s", (table,))
        rows = cur.fetchall()
        cur.close()
        return {row["name"] for row in rows}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self.close()
        return False

    def close(self):
        if not self.closed:
            self.closed = True
            self.pool.putconn(self.raw)

@st.cache_resource
def _pg_pool():
    cfg = st.secrets.get("database", {})
    def setting(key, env_name, default=None):
        return cfg.get(key, os.getenv(env_name, default))
    host = setting("host", "SUPABASE_DB_HOST")
    port = setting("port", "SUPABASE_DB_PORT", "5432")
    dbname = setting("database", "SUPABASE_DB_NAME", "postgres")
    user = setting("user", "SUPABASE_DB_USER")
    password = setting("password", "SUPABASE_DB_PASSWORD")
    if not all([host, user, password]):
        raise RuntimeError("Configuration Supabase manquante. Renseignez .streamlit/secrets.toml ou les variables d’environnement.")
    return ThreadedConnectionPool(1, 10, host=host, port=int(port), dbname=dbname, user=user, password=password, sslmode="require", connect_timeout=8, application_name="ASC-AFRICA")

def connect():
    pool = _pg_pool()
    return PgCompatConnection(pool.getconn(), pool)

def pw_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000).hex()
    return f"{salt}${digest}"

def verify_password(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 180_000).hex() == expected
    except Exception:
        return False

# Schéma intégré au programme : aucune dépendance à un fichier schema.sql séparé.
# CREATE TABLE/INDEX IF NOT EXISTS et ALTER TABLE IF NOT EXISTS rendent l'initialisation
# répétable sans supprimer les données déjà présentes.
DATABASE_SCHEMA = r"""
CREATE TABLE IF NOT EXISTS admins(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, username TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL, full_name TEXT NOT NULL, active INTEGER DEFAULT 1,
 created_at TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'admin');
CREATE TABLE IF NOT EXISTS members(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, member_no TEXT UNIQUE, full_name TEXT NOT NULL,
 phone TEXT, neighborhood TEXT, birth_date TEXT, membership_date TEXT NOT NULL,
 role TEXT DEFAULT 'Supporter', status TEXT DEFAULT 'Actif', notes TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS payments(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, receipt_no TEXT UNIQUE NOT NULL,
 member_id BIGINT REFERENCES members(id) ON DELETE SET NULL, payment_date TEXT NOT NULL,
 payment_type TEXT NOT NULL, amount DOUBLE PRECISION NOT NULL CHECK(amount>0), period TEXT,
 method TEXT DEFAULT 'Espèces', note TEXT, created_by TEXT, created_at TEXT NOT NULL,
 payer_name TEXT DEFAULT '', payer_phone TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS cash_entries(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, entry_date TEXT NOT NULL,
 direction TEXT NOT NULL CHECK(direction IN ('Entrée','Sortie')), category TEXT NOT NULL,
 label TEXT NOT NULL, amount DOUBLE PRECISION NOT NULL CHECK(amount>0), method TEXT DEFAULT 'Espèces',
 reference TEXT, note TEXT, created_by TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activities(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, title TEXT NOT NULL, activity_type TEXT,
 start_date TEXT NOT NULL, end_date TEXT, location TEXT, description TEXT, budget DOUBLE PRECISION DEFAULT 0,
 status TEXT DEFAULT 'Prévue', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS news(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, title TEXT NOT NULL, category TEXT,
 publish_date TEXT NOT NULL, content TEXT NOT NULL, published INTEGER DEFAULT 1, created_at TEXT NOT NULL,
 subtitle TEXT DEFAULT '', author TEXT DEFAULT '', cover_url TEXT DEFAULT '', featured INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sponsors(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, name TEXT NOT NULL, contact TEXT, phone TEXT,
 contribution DOUBLE PRECISION DEFAULT 0, partnership_type TEXT, start_date TEXT, end_date TEXT,
 notes TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_logs(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, created_at TEXT NOT NULL, actor TEXT NOT NULL,
 action TEXT NOT NULL, entity TEXT, entity_id BIGINT, details TEXT);
CREATE TABLE IF NOT EXISTS public_messages(
 id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY, created_at TEXT NOT NULL, full_name TEXT NOT NULL,
 contact TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Nouveau',
 admin_note TEXT DEFAULT '', handled_by TEXT DEFAULT '', handled_at TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS site_settings(setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS idx_public_messages_status ON public_messages(status, created_at);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(payment_date);
CREATE INDEX IF NOT EXISTS idx_cash_date ON cash_entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_members_name ON members(full_name);
CREATE INDEX IF NOT EXISTS idx_payments_member ON payments(member_id);
CREATE INDEX IF NOT EXISTS idx_payments_date_id ON payments(payment_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_cash_date_id ON cash_entries(entry_date DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_activities_start ON activities(start_date);
CREATE INDEX IF NOT EXISTS idx_news_public_date ON news(published, publish_date);
ALTER TABLE payments ADD COLUMN IF NOT EXISTS payer_name TEXT DEFAULT '';
ALTER TABLE payments ADD COLUMN IF NOT EXISTS payer_phone TEXT DEFAULT '';
ALTER TABLE news ADD COLUMN IF NOT EXISTS subtitle TEXT DEFAULT '';
ALTER TABLE news ADD COLUMN IF NOT EXISTS author TEXT DEFAULT '';
ALTER TABLE news ADD COLUMN IF NOT EXISTS cover_url TEXT DEFAULT '';
ALTER TABLE news ADD COLUMN IF NOT EXISTS featured INTEGER DEFAULT 0;
ALTER TABLE admins ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'admin';
"""

def _auto_migrate_legacy_sqlite(pg_connection):
    """Importe automatiquement l'ancienne base SQLite une seule fois, si elle est présente.

    La migration ne supprime jamais la base source. Elle s'arrête si les principales
    tables PostgreSQL contiennent déjà des données afin d'éviter une fusion hasardeuse.
    Les conflits de clés/contraintes sont ignorés et les séquences d'identifiants sont recalées.
    """
    if not LEGACY_DB_PATH.is_file():
        return

    source = None
    try:
        source = sqlite3.connect(f"file:{LEGACY_DB_PATH}?mode=ro", uri=True, timeout=5)
        source.row_factory = sqlite3.Row
        source_tables = {row[0] for row in source.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        order = ["admins", "members", "payments", "cash_entries", "activities", "news",
                 "sponsors", "audit_logs", "public_messages", "site_settings"]
        marker_key = "legacy_sqlite_migration_v1"
        with pg_connection.cursor() as cur:
            cur.execute("SELECT setting_value FROM site_settings WHERE setting_key=%s", (marker_key,))
            if cur.fetchone():
                return
            # Les données administratives existantes ne doivent jamais être mélangées
            # automatiquement avec une ancienne base : l'utilisateur peut faire une fusion contrôlée.
            for table in ("members", "payments", "cash_entries", "activities", "news", "sponsors", "public_messages"):
                cur.execute(pg_sql.SQL("SELECT EXISTS (SELECT 1 FROM {} LIMIT 1)").format(pg_sql.Identifier(table)))
                if cur.fetchone()[0]:
                    print(f"ASC AFRICA : migration SQLite ignorée, la table PostgreSQL {table} contient déjà des données.")
                    return

            imported = {}
            for table in order:
                if table not in source_tables:
                    continue
                source_info = source.execute(f'PRAGMA table_info("{table}")').fetchall()
                source_cols = [row[1] for row in source_info]
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position", (table,))
                target_cols = [row[0] for row in cur.fetchall()]
                cols = [col for col in source_cols if col in target_cols]
                if not cols:
                    continue
                quoted_cols = ", ".join('"' + col.replace('"', '""') + '"' for col in cols)
                rows = source.execute(f'SELECT {quoted_cols} FROM "{table}"').fetchall()
                insert_stmt = pg_sql.SQL("INSERT INTO {} ({}) VALUES %s ON CONFLICT DO NOTHING").format(
                    pg_sql.Identifier(table), pg_sql.SQL(",").join(map(pg_sql.Identifier, cols)))
                inserted = 0
                with pg_connection.cursor() as insert_cur:
                    for offset in range(0, len(rows), 500):
                        batch = [tuple(row[col] for col in cols) for row in rows[offset:offset + 500]]
                        if batch:
                            execute_values(insert_cur, insert_stmt.as_string(pg_connection), batch, page_size=500)
                            inserted += max(insert_cur.rowcount, 0)
                imported[table] = (len(rows), inserted)

            # Recaler les séquences pour que les prochaines insertions n'entrent pas en collision.
            for table in order:
                if table == "site_settings" or table not in source_tables:
                    continue
                cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
                seq = cur.fetchone()[0]
                if seq:
                    cur.execute(pg_sql.SQL("SELECT setval(%s::regclass, COALESCE((SELECT MAX(id) FROM {}), 1), EXISTS (SELECT 1 FROM {}))").format(
                        pg_sql.Identifier(table), pg_sql.Identifier(table)), (seq,))

            summary = "; ".join(f"{name}: {read} lues/{inserted} importées" for name, (read, inserted) in imported.items())
            cur.execute("INSERT INTO site_settings(setting_key, setting_value) VALUES(%s, %s) ON CONFLICT(setting_key) DO NOTHING",
                        (marker_key, f"{datetime.now().isoformat(timespec='seconds')} | {summary}"))
        print("ASC AFRICA : migration SQLite automatique terminée. " + (summary or "Aucune table source compatible."))
    finally:
        if source is not None:
            source.close()


@st.cache_resource(show_spinner=False)
def init_db():
    """Initialise PostgreSQL une seule fois par processus Streamlit.

    Streamlit réexécute le script à chaque interaction : sans ce cache, chaque clic
    relançait tous les CREATE/ALTER/INDEX, la vérification de migration SQLite et
    le hachage PBKDF2 du mot de passe administrateur (180 000 itérations).
    """
    with connect() as c:
        c.executescript(DATABASE_SCHEMA)
        _auto_migrate_legacy_sqlite(c.raw)
        now = datetime.now().isoformat(timespec="seconds")
        current_admin = c.execute("SELECT id FROM admins WHERE username=?", (ADMIN_USER,)).fetchone()
        if current_admin:
            # Le compte principal demandé est synchronisé avec la configuration sécurisée.
            if ADMIN_PASSWORD:
                c.execute("UPDATE admins SET password_hash=?, full_name=?, active=1, role='admin' WHERE username=?",
                          (pw_hash(ADMIN_PASSWORD), "Administrateur principal ASC AFRICA", ADMIN_USER))
            else:
                c.execute("UPDATE admins SET full_name=?, active=1, role='admin' WHERE username=?",
                          ("Administrateur principal ASC AFRICA", ADMIN_USER))
        elif ADMIN_PASSWORD:
            c.execute("INSERT INTO admins(username,password_hash,full_name,active,created_at,role) VALUES(?,?,?,?,?,?)",
                      (ADMIN_USER, pw_hash(ADMIN_PASSWORD), "Administrateur principal ASC AFRICA", 1, now, "admin"))
        else:
            # Pas de création d'un compte administrateur sans mot de passe configuré.
            pass

def audit(action, entity="", entity_id=None, details=""):
    with connect() as c:
        c.execute("INSERT INTO audit_logs(created_at,actor,action,entity,entity_id,details) VALUES(?,?,?,?,?,?)",
                  (datetime.now().isoformat(timespec="seconds"), st.session_state.get("actor","Visiteur"),
                   action, entity, entity_id, str(details)[:2000]))
    _query_df_cached.clear()

@st.cache_data(ttl=30, show_spinner=False)
def _query_df_cached(sql, params):
    """Cache court les lectures PostgreSQL pour limiter les allers-retours réseau."""
    with connect() as c:
        cur = c.execute(sql, params)
        rows = cur.fetchall()
        columns = [d.name if hasattr(d, "name") else d[0] for d in (cur.description or [])]
        cur.close()
    return pd.DataFrame(rows, columns=columns)

def query_df(sql, params=()):
    # params devient un tuple hashable pour le cache Streamlit.
    safe_params = tuple(params or ())
    try:
        return _query_df_cached(sql, safe_params)
    except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
        # Installation neuve ou schéma ancien : on initialise seulement si une
        # lecture prouve que le schéma manque, jamais systématiquement au portail.
        init_db()
        _query_df_cached.clear()
        return _query_df_cached(sql, safe_params)

def execute(sql, params=()):
    with connect() as c:
        statement = sql.strip().rstrip(";")
        if statement.lstrip().upper().startswith("INSERT INTO ") and " RETURNING " not in statement.upper():
            cur = c.execute(statement + " RETURNING id", params)
            row = cur.fetchone()
            cur.close()
            result = row["id"] if row else None
        else:
            cur = c.execute(statement, params)
            result = cur.rowcount
            cur.close()
    # Toute écriture invalide les lectures mises en cache pour éviter d'afficher
    # des données anciennes après une modification ou une suppression.
    _query_df_cached.clear()
    return result

def money(v):
    try: return f"{float(v or 0):,.0f}".replace(",", " ") + " FCFA"
    except Exception: return "0 FCFA"

def receipt_no(prefix="AF"):
    return f"{prefix}-{datetime.now():%Y%m%d}-{secrets.randbelow(90000)+10000}"

def fmt_date(value):
    try: return datetime.fromisoformat(str(value)[:10]).strftime("%d/%m/%Y")
    except Exception: return str(value or "—")

def whatsapp_url(phone, message):
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if digits.startswith("0"): digits = WHATSAPP_COUNTRY + digits[1:]
    elif digits and not digits.startswith(WHATSAPP_COUNTRY): digits = WHATSAPP_COUNTRY + digits
    return "https://wa.me/" + digits + "?text=" + urllib.parse.quote(message) if digits else ""

def pdf_bytes(title, df, subtitle="ASC AFRICA — Document interne", metrics=None):
    if not REPORTLAB_OK: return None
    buf = BytesIO()
    logo = next((p for p in LOGO_PATHS if p.exists()), None)
    yam_logo = next((p for p in YAM_LOGO_PATHS if p.exists()), None)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ClubTitleXXL", parent=styles["Title"], textColor=colors.HexColor(BLUE), fontSize=25, leading=29, alignment=1, spaceAfter=5))
    styles.add(ParagraphStyle(name="ClubSubXXL", parent=styles["Normal"], textColor=colors.HexColor("#526176"), fontSize=10, leading=14, alignment=1))
    styles.add(ParagraphStyle(name="TableHeadXXL", parent=styles["BodyText"], textColor=colors.white, fontSize=8, leading=10, fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle(name="TableCellXXL", parent=styles["BodyText"], textColor=colors.HexColor("#172033"), fontSize=7.5, leading=9))
    def page_decor(canvas, doc):
        canvas.saveState()
        w,h=doc.pagesize
        canvas.setFillColor(colors.HexColor(BLUE)); canvas.rect(0,h-7*mm,w,7*mm,fill=1,stroke=0)
        canvas.setFillColor(colors.HexColor(GOLD)); canvas.rect(0,h-8*mm,w,1.2*mm,fill=1,stroke=0)
        canvas.setStrokeColor(colors.HexColor("#D7A62A")); canvas.setLineWidth(.7); canvas.line(12*mm,12*mm,w-12*mm,12*mm)
        canvas.setFont("Helvetica",7); canvas.setFillColor(colors.HexColor("#526176"))
        canvas.drawString(12*mm,7*mm,"ASC AFRICA · Saint-Louis, Sénégal · Confidentiel si données nominatives")
        canvas.drawRightString(w-12*mm,7*mm,f"Page {doc.page}")
        canvas.restoreState()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), rightMargin=13*mm,leftMargin=13*mm,topMargin=16*mm,bottomMargin=18*mm, title=title, author="ASC AFRICA")
    story=[]
    logos=[]
    for path in [logo,yam_logo]:
        if path:
            try:
                im=RLImage(str(path),width=27*mm,height=27*mm,kind="proportional")
                logos.append(im)
            except Exception: pass
    if logos:
        logo_cells=[logos[0], Paragraph("<font color='#123B75'><b>ASC AFRICA</b></font><br/><font color='#D7A62A'>RAPPORT OFFICIEL</font>",styles["ClubSubXXL"]), logos[1] if len(logos)>1 else ""]
        head=Table([logo_cells],colWidths=[32*mm,doc.width-64*mm,32*mm],rowHeights=[29*mm])
        head.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
        story.append(head)
    else:
        story.append(Paragraph("ASC AFRICA · SAINT-LOUIS, SÉNÉGAL",styles["ClubTitleXXL"]))
    story += [Spacer(1,2*mm),Paragraph(html.escape(title),styles["ClubTitleXXL"]),Paragraph(html.escape(subtitle),styles["ClubSubXXL"]),Spacer(1,5*mm)]
    if metrics:
        cells=[]
        for label,value,color in metrics:
            cells.append(Paragraph(f"<font color='{color}' size='8'><b>{html.escape(str(label).upper())}</b></font><br/><font color='#123B75' size='15'><b>{html.escape(str(value))}</b></font>",styles["BodyText"]))
        tab=Table([cells],colWidths=[doc.width/max(1,len(cells))]*len(cells))
        tab.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#F2F6FC")),("BOX",(0,0),(-1,-1),.7,colors.HexColor("#D7E2F0")),("INNERGRID",(0,0),(-1,-1),.5,colors.HexColor("#D7E2F0")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("ALIGN",(0,0),(-1,-1),"CENTER"),("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9)]))
        story += [tab,Spacer(1,6*mm)]
    story.append(Paragraph("SYNTHÈSE DES DONNÉES",ParagraphStyle(name="SectXXL",parent=styles["Heading2"],textColor=colors.HexColor(BLUE),fontSize=13,leading=16,spaceAfter=6)))
    if df.empty:
        story.append(Paragraph("Aucune donnée à afficher pour la période sélectionnée.",styles["Normal"]))
    else:
        safe=df.fillna("").astype(str)
        data=[[Paragraph(html.escape(str(col)),styles["TableHeadXXL"]) for col in safe.columns]]
        for row in safe.values.tolist():
            data.append([Paragraph(html.escape(str(v)).replace("\n","<br/>")[:1000],styles["TableCellXXL"]) for v in row])
        available=doc.width
        widths=[available/len(safe.columns)]*len(safe.columns)
        table=Table(data,colWidths=widths,repeatRows=1,hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor(BLUE)),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.35,colors.HexColor("#CBD5E1")),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F2F6FC")]),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
        story.append(table)
    story += [Spacer(1,7*mm),Paragraph("Document généré par la plateforme de gestion ASC AFRICA. Vérifier les chiffres et pièces justificatives avant diffusion externe.",styles["Italic"])]
    doc.build(story,onFirstPage=page_decor,onLaterPages=page_decor)
    return buf.getvalue()



def receipt_pdf_bytes(row):
    """Génère un reçu individuel élégant, lisible sur téléphone et imprimable."""
    if not REPORTLAB_OK:
        return None
    buf = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReceiptBrand", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=colors.HexColor(BLUE), alignment=1, spaceAfter=4))
    styles.add(ParagraphStyle(name="ReceiptSub", parent=styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#526176"), alignment=1))
    styles.add(ParagraphStyle(name="ReceiptLabel", parent=styles["Normal"], fontSize=9, leading=13, textColor=colors.HexColor("#526176")))
    styles.add(ParagraphStyle(name="ReceiptValue", parent=styles["Normal"], fontSize=11, leading=15, textColor=colors.HexColor("#172033")))
    styles.add(ParagraphStyle(name="ReceiptAmount", parent=styles["Title"], fontSize=24, leading=29, textColor=colors.white, alignment=1, spaceAfter=0))
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm, topMargin=18*mm, bottomMargin=18*mm, title=f"Reçu {row['receipt_no']}", author=CLUB)
    def decor(canvas, doc):
        canvas.saveState(); w,h=doc.pagesize
        canvas.setFillColor(colors.HexColor(BLUE)); canvas.rect(0,h-10*mm,w,10*mm,fill=1,stroke=0)
        canvas.setFillColor(colors.HexColor(GOLD)); canvas.rect(0,h-11.5*mm,w,1.5*mm,fill=1,stroke=0)
        canvas.setStrokeColor(colors.HexColor("#D7A62A")); canvas.setLineWidth(1); canvas.roundRect(13*mm,13*mm,w-26*mm,h-28*mm,5*mm,stroke=1,fill=0)
        canvas.setFont("Helvetica",8); canvas.setFillColor(colors.HexColor("#64748b")); canvas.drawCentredString(w/2,8*mm,"ASC AFRICA · Saint-Louis, Sénégal · Merci pour votre soutien")
        canvas.restoreState()
    story = [Spacer(1,5*mm), Paragraph("ASC AFRICA", styles["ReceiptBrand"]), Paragraph(html.escape(SLOGAN), styles["ReceiptSub"]), Spacer(1,8*mm)]
    header = Table([[Paragraph("REÇU DE PAIEMENT", ParagraphStyle(name="ReceiptType", parent=styles["Heading2"], textColor=colors.white, alignment=1, fontSize=15)), Paragraph("N° <b>"+html.escape(str(row['receipt_no']))+"</b><br/>Date : "+html.escape(fmt_date(row['payment_date'])), ParagraphStyle(name="ReceiptNo", parent=styles["Normal"], textColor=colors.white, alignment=2, fontSize=9, leading=14))]], colWidths=[doc.width*.58,doc.width*.42])
    header.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor(BLUE)),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),14),("BOTTOMPADDING",(0,0),(-1,-1),14)])); story += [header,Spacer(1,8*mm)]
    fields = [("Reçu de", row.get("payer_name") or row.get("full_name") or "Membre non renseigné"),("Téléphone",row.get("payer_phone") or row.get("phone") or "—"),("Objet du paiement",row.get("payment_type") or "—"),("Période concernée",row.get("period") or "—"),("Mode de paiement",row.get("method") or "—"),("Observation",row.get("note") or "—")]
    rows=[]
    for label,value in fields:
        rows.append([Paragraph(html.escape(label),styles["ReceiptLabel"]),Paragraph(html.escape(str(value)),styles["ReceiptValue"])])
    detail=Table(rows,colWidths=[doc.width*.34,doc.width*.66],hAlign="LEFT")
    detail.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.white),("LINEBELOW",(0,0),(-1,-1),.5,colors.HexColor("#DCE7F4")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),("TOPPADDING",(0,0),(-1,-1),11),("BOTTOMPADDING",(0,0),(-1,-1),11)])); story += [detail,Spacer(1,8*mm)]
    amount=Table([[Paragraph("MONTANT REÇU",ParagraphStyle(name="AmountLabel",parent=styles["Normal"],textColor=colors.HexColor("#FFE49A"),alignment=1,fontSize=10)),Paragraph(html.escape(money(row.get("amount",0))),styles["ReceiptAmount"])]],colWidths=[doc.width*.38,doc.width*.62])
    amount.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),colors.HexColor(BLUE)),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),12),("RIGHTPADDING",(0,0),(-1,-1),12),("TOPPADDING",(0,0),(-1,-1),16),("BOTTOMPADDING",(0,0),(-1,-1),16)])); story += [amount,Spacer(1,12*mm),Paragraph("Arrêté le : "+datetime.now().strftime("%d/%m/%Y à %H:%M"),styles["ReceiptSub"]),Spacer(1,14*mm)]
    sign=Table([["Signature / cachet de l’association", "Signature du bénéficiaire"]],colWidths=[doc.width/2]*2,rowHeights=[18*mm]); sign.setStyle(TableStyle([("LINEABOVE",(0,0),(-1,-1),.7,colors.HexColor("#AAB8CA")),("TEXTCOLOR",(0,0),(-1,-1),colors.HexColor("#526176")),("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),8),("VALIGN",(0,0),(-1,-1),"TOP"),("TOPPADDING",(0,0),(-1,-1),7)])); story.append(sign)
    doc.build(story,onFirstPage=decor,onLaterPages=decor)
    return buf.getvalue()

def header():
    'Bannière ASC AFRICA XXL avec sept diapositives, slogans et zoom automatique.'
    slogan = html.escape(SLOGAN)
    base_images = [
        ("https://ascafrica.streamlit.app/~/+/media/33733a2315e25a96fe358d9fa825e7c7.png", "LA PASSION NOUS RASSEMBLE", "Chaque supporter fait battre le cœur de l’ASC AFRICA."),
        ("https://ascafrica.streamlit.app/~/+/media/18111d99c568fbdb39115fa1aefd7542.png", "UNE ÉQUIPE, UNE FAMILLE", "Sur le terrain comme dans la vie, avançons ensemble."),
        ("https://ascafrica.streamlit.app/~/+/media/0e88e77cba6179f735a05cf91ba9537e.jpg", "SAINT-LOUIS, NOTRE FIERTÉ", "Un club enraciné dans sa ville, tourné vers l’avenir."),
    ]
    messages = [
        ("LA PASSION NOUS RASSEMBLE", "Chaque supporter fait battre le cœur de l’ASC AFRICA."),
        ("UNE ÉQUIPE, UNE FAMILLE", "Sur le terrain comme dans la vie, avançons ensemble."),
        ("SAINT-LOUIS, NOTRE FIERTÉ", "Portons haut les couleurs de notre ville et de notre club."),
        ("NOS SUPPORTERS, NOTRE FORCE", "La voix des tribunes donne de l’énergie à chaque génération."),
        ("SOLIDAIRES DANS L’EFFORT", "Respect, entraide et engagement : notre victoire se construit ensemble."),
        ("UNE IDENTITÉ, UNE AMBITION", "AFRICA KASSÉ, AFRICA REK — unis pour aller plus loin."),
        ("L’AVENIR SE CONSTRUIT ENSEMBLE", "Mobilisons-nous pour un club vivant, fier et solidaire."),
    ]
    slides = []
    for index, (title, message) in enumerate(messages, start=1):
        local_path = APP_DIR / f"im{index}.png"
        fallback_url, _, _ = base_images[(index - 1) % len(base_images)]
        local_uri = _logo_data_uri(local_path) if local_path.exists() else ""
        src = local_uri or fallback_url
        alt = f"{title} — ASC AFRICA, Saint-Louis Sénégal"
        slides.append(
            '<div class="africa-slide">'
            f'<img src="{html.escape(src, quote=True)}" alt="{html.escape(alt, quote=True)}" '
            f'loading="{'eager' if index == 1 else 'lazy'}" decoding="async" referrerpolicy="no-referrer" '
            '>'
            f'<div class="africa-slide-caption">{html.escape(title)}'
            f'<small>{html.escape(message)}</small></div></div>'
        )
    stage = '<div class="africa-photo-stage" aria-label="Carrousel de sept diapositives ASC AFRICA">' + ''.join(slides) + '</div>'
    st.markdown(f'''<section class="africa-topband" role="banner" aria-label="Présentation de l’ASC AFRICA">
      {stage}<div class="africa-top-content"><div class="top-kicker">SAINT-LOUIS • SÉNÉGAL • CLUB • SOLIDARITÉ</div>
      <h1>ASC AFRICA</h1>
      <p>Plus qu’un club, une famille et une fierté partagée. Retrouvez les actualités, les activités et les initiatives de celles et ceux qui font vivre l’ASC AFRICA.</p>
      <span class="top-slogan">{slogan}</span></div></section>''', unsafe_allow_html=True)


def bottom_message():
    st.markdown("<div class='news-ticker'>📣 MESSAGE À LA COMMUNAUTÉ — Retrouvez ici les nouvelles officielles, les activités à venir, l’histoire et les informations utiles de l’ASC AFRICA. AFRICA KASSÉ, AFRICA REK !</div>", unsafe_allow_html=True)


def _logo_data_uri(path):
    if not path or not path.exists():
        return ""
    try:
        ext=path.suffix.lower()
        mime="image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"
        return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    except Exception:
        return ""


def yam_footer():
    """Pied de page présentant le don de la plateforme par YAM et ses neuf domaines."""
    club_logo = next((p for p in LOGO_PATHS if p.exists()), None)
    yam_logo = next((p for p in YAM_LOGO_PATHS if p.exists()), None)
    club_uri = _logo_data_uri(club_logo)
    yam_uri = _logo_data_uri(yam_logo)
    club_img = (f"<img class='yam-footer-logo' src='{club_uri}' alt='Logo ASC AFRICA'>"
                if club_uri else "<div class='yam-brand-fallback'>⚽ ASC AFRICA</div>")
    yam_img = (f"<img class='yam-footer-logo' src='{yam_uri}' alt='Logo YAM Group'>"
               if yam_uri else "<div class='yam-brand-fallback yam-gold'>YAM<br>GROUP</div>")
    domains = [
        ("🌱", "Agriculture", "Solutions agricoles durables, production et valorisation."),
        ("🩺", "Santé", "Services de santé, amélioration des soins et bien-être."),
        ("🎓", "Éducation", "Formation, soutien scolaire et renforcement des compétences."),
        ("⚡", "Énergie", "Énergies renouvelables et infrastructures de distribution."),
        ("🏗️", "BTP", "Construction, ingénierie et aménagement des infrastructures."),
        ("💻", "Information", "Technologies, communication, médias et systèmes numériques."),
        ("📊", "Consultancy", "Conseil stratégique et accompagnement opérationnel."),
        ("📈", "Économie", "Ingénierie financière, investissement et gestion de projets."),
        ("🤝", "Commerce", "Négociation, distribution et commerce général."),
    ]
    cards = "".join(
        f"<article class='yam-domain-card'><div class='yam-domain-icon'>{icon}</div><h4>{html.escape(name)}</h4><p>{html.escape(desc)}</p></article>"
        for icon, name, desc in domains
    )
    ticker_items = "".join(
        f"<span>✦ DON DE <b>YAM GROUP</b> · FILIALE <b>YAM CONSULTANCY</b> · {icon} <b>{html.escape(name.upper())}</b> · {html.escape(desc.split(',')[0].rstrip('.').upper())}</span>"
        for icon, name, desc in domains
    )
    st.markdown(f"""
    <style>
    .site-footer{{margin-top:0!important;margin-bottom:0!important;padding:clamp(18px,2.8vw,32px) clamp(12px,2vw,28px) 0!important;border-radius:18px 18px 0 0!important;background:radial-gradient(circle at 50% 0,rgba(58,122,192,.28),transparent 42%),linear-gradient(135deg,#07172e,#123b75 62%,#0b8278);color:#fff;text-align:center;overflow:hidden;border-top:4px solid #d7a62a;box-shadow:0 -5px 22px rgba(18,59,117,.08);}}
    .yam-footer-headline{{font-size:clamp(1.35rem,2.8vw,2.3rem);font-weight:950;line-height:1.2;margin:8px auto 10px;max-width:1100px;color:#fff;}}
    .yam-footer-slogan{{font-size:clamp(1rem,1.8vw,1.3rem);font-weight:850;color:#f4bd38;line-height:1.5;margin:8px auto;max-width:1100px;}}
    .yam-footer-intro{{max-width:1100px;margin:0 auto;color:#dce8f7;line-height:1.7;font-size:clamp(.9rem,1.25vw,1.05rem);}}
    .yam-brand-fallback{{font-size:clamp(1.6rem,3vw,2.5rem);font-weight:950;color:#fff;padding:12px;}}
    .yam-gold{{color:#f4bd38!important;}}
    .yam-footer-logo{{max-width:clamp(95px,13vw,155px)!important;max-height:clamp(85px,10vw,125px)!important;object-fit:contain;padding:6px!important;}}
    .yam-domain-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:1350px;margin:18px auto 8px;text-align:left;}}
    .yam-domain-card{{padding:14px 15px;border-radius:15px;border:1px solid #ffffff27;background:linear-gradient(135deg,#ffffff13,#ffffff08);box-shadow:0 8px 22px #00000012;min-height:120px;transition:transform .22s ease,border-color .22s ease,background .22s ease;}}
    .yam-domain-card:hover{{transform:translateY(-4px);border-color:#f4bd38;background:#ffffff1c;}}
    .yam-domain-icon{{font-size:1.55rem;margin-bottom:4px;}}
    .yam-domain-card h4{{color:#f4bd38!important;font-size:1rem;margin:0 0 5px;font-weight:900;}}
    .yam-domain-card p{{color:#e2ebf7!important;font-size:.86rem;line-height:1.5;margin:0;}}
    .yam-activity-strip{{position:relative;display:block!important;visibility:visible!important;opacity:1!important;min-height:54px;overflow:hidden;margin:14px -18px 0;padding:15px 0;border-top:1px solid #ffffff55;border-bottom:1px solid #ffffff55;background:#061326!important;color:#fff!important;z-index:2;}}
    .yam-activity-track{{display:flex!important;align-items:center;width:max-content;min-width:200%;gap:30px;white-space:nowrap;animation:yamMarquee 38s linear infinite;font-weight:900;letter-spacing:.04em;font-size:clamp(.82rem,1.1vw,.98rem);color:#fff!important;will-change:transform;}}
    .yam-activity-track span{{display:inline-flex;align-items:center;gap:8px;flex:0 0 auto;color:#fff!important;}}
    .yam-activity-track b{{color:#f4bd38!important;}}
    .footer-bottom{{margin:0 -18px 0;padding:13px clamp(12px,3vw,36px);background:#041020;color:#cbd8e8;font-size:.86rem;font-weight:700;}}
    @keyframes yamMarquee{{from{{transform:translateX(0)}}to{{transform:translateX(-50%)}}}}
    @media(max-width:800px){{.yam-domain-grid{{grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;}}.yam-domain-card{{padding:12px;min-height:0;}}.yam-domain-card p{{font-size:.82rem;}}.yam-activity-track{{animation-duration:27s;}}}}
    @media(max-width:460px){{.yam-domain-grid{{grid-template-columns:1fr;}}.yam-domain-card{{display:grid;grid-template-columns:34px 1fr;column-gap:8px;align-items:start;}}.yam-domain-icon{{grid-row:span 2;}}.yam-domain-card h4{{margin-top:2px;}}}}
    @media(prefers-reduced-motion:reduce){{.yam-domain-card{{transition:none;}}.yam-domain-card:hover{{transform:none;}}.yam-activity-track{{animation:none;min-width:0;width:100%;white-space:normal;justify-content:center;flex-wrap:wrap;padding:0 12px;}}}}
    </style>
    <footer class='site-footer' aria-label='Don de la plateforme par YAM Group'>
      <div class='eyebrow' style='color:#f4bd38;font-size:.8rem'>UN ENGAGEMENT POUR LE DÉVELOPPEMENT · YAM GROUP</div>
      <div class='yam-footer-headline'>UN DON NUMÉRIQUE DE YAM GROUP À L’ASC AFRICA</div>
      <div class='yam-footer-intro'>Cette plateforme a été offerte à l’ASC AFRICA par <strong style='color:#f4bd38'>YAM Group, à travers sa filiale YAM Consultancy</strong>, pour soutenir la vie associative, améliorer l’accès à l’information et accompagner la transformation numérique des organisations. YAM Consultancy met son savoir-faire au service des projets, des entreprises et des communautés.</div>
      <div class='yam-footer-slogan'>« Ensemble pour un Sénégal plus fort : Agir aujourd’hui, bâtir demain »</div>
      <div style='display:flex;align-items:center;justify-content:center;gap:clamp(18px,5vw,65px);flex-wrap:wrap;margin:12px auto 8px'>{club_img}<span style='color:#f4bd38;font-size:clamp(1.5rem,3vw,2.5rem);font-weight:950'>×</span>{yam_img}</div>
      <div style='font-weight:900;color:#fff;font-size:clamp(1rem,1.5vw,1.2rem);margin:8px auto'>YAM intervient dans neuf domaines clés</div>
      <div class='yam-domain-grid'>{cards}</div>
      <div class='yam-activity-strip' aria-label='Défilement des domaines de YAM'><div class='yam-activity-track'>{ticker_items}{ticker_items}</div></div>
      <div class='footer-bottom'>© {date.today().year} ASC AFRICA · Saint-Louis, Sénégal · Portail officiel d’information et de vie associative<br><strong style='color:#f4bd38'>Une réalisation offerte par YAM Group · Filiale YAM Consultancy</strong> — Conseil, accompagnement opérationnel et solutions numériques.</div>
    </footer>
    """, unsafe_allow_html=True)


def metric_row():
    members = query_df("SELECT COUNT(*) n FROM members WHERE status='Actif'").iloc[0,0]
    month = date.today().strftime("%Y-%m")
    paid = query_df("SELECT COALESCE(SUM(amount),0) n FROM payments WHERE substr(payment_date,1,7)=?",(month,)).iloc[0,0]
    income = query_df("SELECT COALESCE(SUM(amount),0) n FROM cash_entries WHERE direction='Entrée'").iloc[0,0]
    expense = query_df("SELECT COALESCE(SUM(amount),0) n FROM cash_entries WHERE direction='Sortie'").iloc[0,0]
    c1,c2,c3,c4 = st.columns(4)
    for col,label,value in [(c1,"Membres actifs",f"{members}"),(c2,"Encaissements du mois",money(paid)),(c3,"Entrées caisse",money(income)),(c4,"Solde caisse",money(income-expense))]:
        with col: st.markdown(f'<div class="card"><div class="card-label">{label}</div><div class="card-value">{value}</div></div>',unsafe_allow_html=True)

def login():
    header()
    if st.button("← Retour au portail public", key="return_public_portal"):
        st.session_state.show_admin_login = False
        st.rerun()
    left,right=st.columns([1.1,1])
    with left:
        st.markdown("""<div class="card"><h2 style="color:#123B75">Bienvenue à l'ASC AFRICA</h2>
        <p>La plateforme accompagne la vie associative, les adhésions, les cotisations, les cartes, la caisse, les activités et la transparence financière.</p>
        <hr><b>Portail public et communautaire</b><br>Actualités • Agenda • Partenaires • Adhésion<br><br>
        <b>Espace de gestion</b><br>Accès réservé aux responsables autorisés.</div>""",unsafe_allow_html=True)
    with right:
        st.subheader("🔐 Connexion à l'administration")
        with st.form("login_form"):
            username=st.text_input("Identifiant",value="")
            password=st.text_input("Mot de passe",type="password")
            ok=st.form_submit_button("Se connecter",type="primary",use_container_width=True)
        if ok:
            with connect() as c: admin=c.execute("SELECT * FROM admins WHERE username=? AND active=1",(username.strip(),)).fetchone()
            if admin and verify_password(password,admin["password_hash"]):
                st.session_state.authenticated=True; st.session_state.actor=admin["full_name"]; st.session_state.actor_username=admin["username"]; st.session_state.actor_role=admin["role"] if "role" in admin.keys() else "admin"; st.session_state.login_at=datetime.now().isoformat()
                audit("Connexion","administration",admin["id"],"Connexion réussie")
                st.rerun()
            else: st.error("Identifiant ou mot de passe incorrect.")
        st.caption("Connexion avec le compte principal configuré dans .streamlit/secrets.toml.")
        st.info("Les responsables disposent désormais d’accès séparés selon leur bureau : Finances globales ou Affaires administratives.")

def public_page():
    header()
    bottom_message()
    st.markdown("<div class='public-nav-label'>MENU DU SITE · Choisissez une rubrique</div>",unsafe_allow_html=True)
    menu_options = ["🏠 Accueil", "📰 Actualités", "📖 À propos", "🏛️ Bureau", "🕰️ Historique", "📅 Agenda", "🤝 Partenaires", "📄 Documents utiles", "📍 Contact", "📝 Rejoindre le club"]
    # Menu explicite et accessible : la liste déroulante évite les onglets serrés sur téléphone.
    menu = st.selectbox("Ouvrir une rubrique", menu_options, index=0, key="public_navigation_select", label_visibility="collapsed")
    st.markdown("<div class='nav-help-mobile'>👇 Touchez le menu ci-dessus pour choisir Accueil, Actualités, Agenda, Contact ou une autre rubrique.</div><div style='height:4px;background:linear-gradient(90deg,#123b75,#0b8278,#f4bd38);border-radius:5px;margin:8px 0 18px'></div>", unsafe_allow_html=True)

    if menu == "🏠 Accueil":
        latest = query_df("SELECT title,subtitle,author,cover_url,featured,category,publish_date,content FROM news WHERE published=1 ORDER BY featured DESC,publish_date DESC,id DESC LIMIT 4")
        activities = query_df("SELECT title,activity_type,start_date,end_date,location,description,status FROM activities WHERE status!='Annulée' AND start_date>=? ORDER BY start_date LIMIT 4", (date.today().isoformat(),))
        members = int(query_df("SELECT COUNT(*) n FROM members WHERE status='Actif'").iloc[0,0])
        partners = int(query_df("SELECT COUNT(*) n FROM sponsors").iloc[0,0])
        st.markdown("<div class='eyebrow'>Le journal de la vie associative</div><h2 style='font-size:clamp(1.8rem,4vw,3rem);font-weight:950;color:#123b75;line-height:1.1'>L’actualité du club,<br>la vie de notre communauté.</h2><p style='font-size:1.08rem;max-width:850px;color:#526176;line-height:1.7'>Retrouvez les informations, annonces, événements et actions communautaires de l’ASC AFRICA dans un espace clair, vivant et accessible à tous.</p>", unsafe_allow_html=True)
        # Galerie officielle : portraits de supporters, équipe et emblème du club.
        gallery_items = [
            (APP_DIR / "im1.png", "https://ascafrica.streamlit.app/~/+/media/33733a2315e25a96fe358d9fa825e7c7.png", "LA PASSION NOUS RASSEMBLE", "Chaque supporter fait battre le cœur de l’ASC AFRICA."),
            (APP_DIR / "im2.png", "https://ascafrica.streamlit.app/~/+/media/18111d99c568fbdb39115fa1aefd7542.png", "UN GROUPE, UNE FAMILLE", "Ensemble sur le terrain, unis dans la vie."),
            (APP_DIR / "im3.png", "https://ascafrica.streamlit.app/~/+/media/0e88e77cba6179f735a05cf91ba9537e.jpg", "UNE IDENTITÉ, UNE FIERTÉ", "AFRICA KASSÉ, AFRICA REK — Saint-Louis, Sénégal."),
        ]
        st.markdown("<div class='section'>💙 Notre fierté, notre famille, notre histoire</div><p style='color:#526176;line-height:1.7'>Des tribunes au terrain, l’ASC AFRICA vit grâce à celles et ceux qui portent ses couleurs.</p>", unsafe_allow_html=True)
        gcols = st.columns(3, gap="large")
        for col, (img_path, fallback_url, title, message) in zip(gcols, gallery_items):
            with col:
                st.markdown("<div class='club-gallery-card'>", unsafe_allow_html=True)
                if img_path.exists():
                    st.image(str(img_path), use_container_width=True)
                else:
                    st.markdown(f"<img src='{html.escape(fallback_url, quote=True)}' alt='{html.escape(title, quote=True)}' style='display:block;width:100%;height:250px;object-fit:cover;border-radius:15px' loading='lazy' referrerpolicy='no-referrer'>", unsafe_allow_html=True)
                st.markdown(f"<div class='club-gallery-message'>{html.escape(title)}</div><div class='club-gallery-sub'>{html.escape(message)}</div></div>", unsafe_allow_html=True)
        c1,c2,c3=st.columns(3)
        c1.metric("Membres actifs", members); c2.metric("Activités à venir", len(activities)); c3.metric("Partenaires", partners)
        left,right=st.columns([1.5,1], gap="large")
        with left:
            st.markdown("<div class='section'>📰 À la une</div>", unsafe_allow_html=True)
            if latest.empty:
                st.markdown("<div class='news-card'><span class='pill'>Bienvenue</span><h3>La rubrique actualités démarre ici</h3><p>Les annonces et articles publiés par l’équipe de communication apparaîtront dans cet espace.</p></div>", unsafe_allow_html=True)
            else:
                for _,r in latest.iterrows():
                    cover = str(r.get("cover_url") or "").strip()
                    cover_html = f"<img class='news-cover' src='{html.escape(cover, quote=True)}' alt='Illustration de l’actualité' loading='lazy'>" if cover.startswith(("https://", "http://")) else ""
                    badge = "<span class='pill'>À LA UNE</span> " if int(r.get("featured") or 0) else ""
                    subtitle = f"<p><b>{html.escape(str(r.get('subtitle') or ''))}</b></p>" if r.get("subtitle") else ""
                    author = f"<span> • {html.escape(str(r.get('author') or ''))}</span>" if r.get("author") else ""
                    body = html.escape(str(r['content'])[:650])
                    st.markdown(f"<div class='news-card'>{badge}<span class='pill'>{html.escape(str(r['category'] or 'Actualité'))}</span>{cover_html}<div style='color:#718096;font-size:.82rem;margin-top:10px'>{fmt_date(r['publish_date'])}{author}</div><h3>{html.escape(str(r['title']))}</h3>{subtitle}<p style='white-space:pre-wrap;line-height:1.65'>{body}{'…' if len(str(r['content']))>650 else ''}</p></div>", unsafe_allow_html=True)
        with right:
            st.markdown("<div class='section'>📅 Prochains rendez-vous</div>", unsafe_allow_html=True)
            if activities.empty: st.info("Les prochaines activités seront annoncées ici.")
            else:
                for _,r in activities.iterrows():
                    st.markdown(f"<div class='feature-card' style='margin-bottom:12px'><div class='eyebrow'>{fmt_date(r['start_date'])} • {r['activity_type'] or 'Activité'}</div><h3 style='color:#123b75;margin:.5rem 0'>{r['title']}</h3><div>📍 {r['location'] or 'Lieu à préciser'}</div><p style='line-height:1.5'>{str(r['description'] or '')[:220]}</p><span class='pill'>{r['status']}</span></div>", unsafe_allow_html=True)
        st.markdown("<div class='section'>🌍 Nos engagements</div>", unsafe_allow_html=True)
        a,b,c=st.columns(3)
        for col,icon,title,desc in [(a,"⚽","Sport & jeunesse","Promouvoir le sport, l’esprit d’équipe et l’épanouissement des jeunes."),(b,"🤝","Solidarité","Valoriser les initiatives citoyennes, l’entraide et les actions sociales."),(c,"📢","Information","Diffuser des annonces utiles et partager les temps forts de la communauté.")]:
            with col: st.markdown(f"<div class='feature-card'><div style='font-size:2rem'>{icon}</div><h3 style='color:#123b75'>{title}</h3><p style='line-height:1.6'>{desc}</p></div>", unsafe_allow_html=True)

    elif menu == "📰 Actualités":
        st.markdown("<div class='section'>📰 Toutes les actualités</div>", unsafe_allow_html=True)
        news=query_df("SELECT title,subtitle,author,cover_url,featured,category,publish_date,content FROM news WHERE published=1 ORDER BY featured DESC,publish_date DESC,id DESC")
        if news.empty: st.info("Aucune actualité n’a encore été publiée. Revenez bientôt.")
        else:
            search=st.text_input("🔎 Rechercher une actualité", placeholder="Mot-clé, rubrique, sujet…")
            if search: news=news[news.astype(str).apply(lambda col:col.str.contains(search,case=False,na=False)).any(axis=1)]
            st.caption(f"{len(news)} publication(s)")
            for _,r in news.iterrows():
                cover = str(r.get("cover_url") or "").strip()
                cover_html = f"<img class='news-cover' src='{html.escape(cover, quote=True)}' alt='Illustration de l’actualité' loading='lazy'>" if cover.startswith(("https://", "http://")) else ""
                badge = "<span class='pill'>À LA UNE</span> " if int(r.get("featured") or 0) else ""
                subtitle = f"<p><b>{html.escape(str(r.get('subtitle') or ''))}</b></p>" if r.get("subtitle") else ""
                author = f"<span> • {html.escape(str(r.get('author') or ''))}</span>" if r.get("author") else ""
                st.markdown(f"<div class='news-card'>{badge}<span class='pill'>{html.escape(str(r['category'] or 'Actualité'))}</span>{cover_html}<div style='color:#718096;font-size:.82rem;margin-top:10px'>{fmt_date(r['publish_date'])}{author}</div><h3>{html.escape(str(r['title']))}</h3>{subtitle}<p style='white-space:pre-wrap;line-height:1.75'>{html.escape(str(r['content']))}</p></div>", unsafe_allow_html=True)

    elif menu == "📖 À propos":
        st.markdown("<div class='section'>📖 À propos de l’ASC AFRICA</div>", unsafe_allow_html=True)
        st.markdown("<div class='news-card'><span class='pill'>Identité du club</span><h3>ASC AFRICA — Saint-Louis</h3><p style='line-height:1.8'>L’ASC AFRICA est une association sportive et communautaire. Cet espace présente ses activités, ses membres, ses initiatives et ses informations officielles. Le bureau peut enrichir cette page avec la date de création, les fondateurs, les couleurs officielles, les disciplines et les objectifs validés par le club.</p><p><b>Devise :</b> AFRICA KASSÉ, AFRICA REK</p></div>", unsafe_allow_html=True)
        x,y,z=st.columns(3)
        with x: st.markdown("<div class='feature-card'><div style='font-size:2rem'>⚽</div><h3 style='color:#123b75'>Sport</h3><p>Encourager la pratique sportive, le respect, la discipline et l’esprit d’équipe.</p></div>",unsafe_allow_html=True)
        with y: st.markdown("<div class='feature-card'><div style='font-size:2rem'>🤝</div><h3 style='color:#123b75'>Solidarité</h3><p>Favoriser l’entraide, l’inclusion et les actions positives au sein de la communauté.</p></div>",unsafe_allow_html=True)
        with z: st.markdown("<div class='feature-card'><div style='font-size:2rem'>🌱</div><h3 style='color:#123b75'>Jeunesse</h3><p>Créer des occasions d’engagement, d’apprentissage et de participation citoyenne.</p></div>",unsafe_allow_html=True)
        st.info("Les éléments historiques ou statutaires qui n’ont pas encore été fournis ne sont pas inventés : ils pourront être ajoutés par le club.")

    elif menu == "🏛️ Bureau":
        st.markdown("<div class='section'>🏛️ Le bureau et les responsables</div>", unsafe_allow_html=True)
        st.write("Les responsables enregistrés comme « Dirigeant » dans le registre des membres sont présentés ci-dessous.")
        bureau=query_df("SELECT full_name,role,status,neighborhood FROM members WHERE status='Actif' AND (role LIKE '%Dirigeant%' OR role LIKE '%Président%' OR role LIKE '%Secrétaire%' OR role LIKE '%Trésorier%' OR role LIKE '%Responsable%') ORDER BY full_name")
        if bureau.empty:
            st.info("La liste du bureau n’est pas encore renseignée. Pour afficher les responsables, ajoutez-les dans l’administration des membres avec leur fonction et le statut « Actif ».")
        else:
            cols=st.columns(3)
            for i,(_,r) in enumerate(bureau.iterrows()):
                with cols[i%3]:
                    st.markdown(f"<div class='feature-card' style='margin-bottom:14px'><div style='font-size:2rem'>👤</div><h3 style='color:#123b75'>{r['full_name']}</h3><span class='pill'>{r['role']}</span><p style='margin-top:10px'>ASC AFRICA • Saint-Louis</p></div>",unsafe_allow_html=True)
        st.caption("Pour afficher les fonctions correctement, utilisez les rôles Président, Secrétaire général, Trésorier, Responsable sportif, Responsable communication ou Dirigeant dans le registre des membres.")

    elif menu == "🕰️ Historique":
        st.markdown("<div class='section'>🕰️ Histoire de l’ASC AFRICA</div>", unsafe_allow_html=True)
        st.markdown("<div class='news-card'><h3>Une histoire à raconter et à transmettre</h3><p style='line-height:1.8'>Cette rubrique est destinée à conserver la mémoire du club : sa création, ses fondateurs, les générations de joueurs, les saisons marquantes, les titres, les anciens dirigeants, les grands matchs et les actions réalisées à Saint-Louis.</p><p>Pour publier une chronologie fiable, le bureau peut fournir les dates, noms et événements vérifiés. Aucun palmarès ni date de fondation n’est affiché sans confirmation.</p></div>",unsafe_allow_html=True)
        st.markdown("<div class='section'>📚 Les archives du club</div>",unsafe_allow_html=True)
        hist_news=query_df("SELECT title,category,publish_date,content FROM news WHERE published=1 AND (category LIKE '%Historique%' OR category LIKE '%Archive%' OR title LIKE '%histoire%' OR title LIKE '%anniversaire%' OR title LIKE '%palmarès%') ORDER BY publish_date DESC")
        if hist_news.empty:
            st.info("Les articles d’histoire et d’archives apparaîtront ici lorsqu’ils seront publiés dans la rubrique « Historique » ou « Archives ».")
        else:
            for _,r in hist_news.iterrows():
                st.markdown(f"<div class='news-card'><div class='eyebrow'>{fmt_date(r['publish_date'])}</div><h3>{r['title']}</h3><p style='white-space:pre-wrap;line-height:1.7'>{r['content']}</p></div>",unsafe_allow_html=True)

    elif menu == "📅 Agenda":
        st.markdown("<div class='section'>📅 Agenda communautaire</div>", unsafe_allow_html=True)
        acts=query_df("SELECT title,activity_type,start_date,end_date,location,description,status FROM activities WHERE status!='Annulée' ORDER BY start_date")
        if acts.empty: st.info("Aucune activité annoncée pour le moment.")
        else:
            for _,r in acts.iterrows():
                st.markdown(f"<div class='news-card'><span class='pill'>{r['status']}</span><div class='eyebrow' style='margin-top:10px'>{r['activity_type'] or 'Activité'}</div><h3>{r['title']}</h3><p>🗓️ Du {fmt_date(r['start_date'])} au {fmt_date(r['end_date']) if r['end_date'] else fmt_date(r['start_date'])} • 📍 {r['location'] or 'Lieu à préciser'}</p><p style='line-height:1.7'>{r['description'] or ''}</p></div>", unsafe_allow_html=True)

    elif menu == "🤝 Partenaires":
        st.markdown("<div class='section'>🤝 Nos partenaires et soutiens</div>", unsafe_allow_html=True)
        sp=query_df("SELECT name,partnership_type,notes FROM sponsors ORDER BY name")
        if sp.empty: st.info("Les partenaires et mécènes seront présentés ici dès leur publication.")
        else:
            cols=st.columns(2)
            for i,(_,r) in enumerate(sp.iterrows()):
                with cols[i%2]: st.markdown(f"<div class='feature-card' style='margin-bottom:14px'><span class='pill'>{r['partnership_type'] or 'Partenaire'}</span><h3 style='color:#123b75'>{r['name']}</h3><p style='line-height:1.65'>{r['notes'] or 'Partenaire de la vie associative.'}</p></div>", unsafe_allow_html=True)

    elif menu == "📄 Documents utiles":
        st.markdown("<div class='section'>📄 Documents et informations utiles</div>", unsafe_allow_html=True)
        st.markdown("<div class='about-grid'><div class='feature-card'><h3 style='color:#123b75'>📜 Statuts & règlement</h3><p>Les statuts et le règlement intérieur pourront être mis à disposition après validation par le bureau.</p></div><div class='feature-card'><h3 style='color:#123b75'>📆 Calendrier sportif</h3><p>Consultez la rubrique Agenda pour les activités, rencontres et événements annoncés.</p></div><div class='feature-card'><h3 style='color:#123b75'>🤝 Partenariat</h3><p>Les organisations souhaitant soutenir le club peuvent prendre contact avec les responsables.</p></div></div>",unsafe_allow_html=True)
        st.info("Les fichiers statutaires ne sont pas encore joints au projet. Cette rubrique est prête à les accueillir lorsqu’ils seront fournis.")

    elif menu == "📍 Contact":
        st.markdown("<div class='section'>📍 Contact & informations</div>", unsafe_allow_html=True)
        st.markdown("<div class='news-card'><h3>ASC AFRICA — Saint-Louis, Sénégal</h3><p>Pour les informations officielles, les demandes de partenariat, les adhésions et les activités, utilisez le formulaire ci-dessous. Les coordonnées publiques (téléphone, e-mail, réseaux sociaux et adresse) pourront être ajoutées dès qu’elles seront confirmées.</p></div>",unsafe_allow_html=True)
        with st.form("public_contact"):
            cname=st.text_input("Votre nom *")
            cphone=st.text_input("Téléphone ou e-mail *")
            subject=st.selectbox("Objet",["Demande d’information","Partenariat / sponsoring","Presse / communication","Activité sportive","Autre"])
            message=st.text_area("Votre message *",height=130)
            send=st.form_submit_button("Préparer mon message",type="primary",use_container_width=True)
        if send:
            if not cname.strip() or not cphone.strip() or not message.strip():
                st.error("Veuillez remplir le nom, un moyen de contact et le message.")
            else:
                mid=execute("INSERT INTO public_messages(created_at,full_name,contact,subject,message,status) VALUES(?,?,?,?,?,'Nouveau')",
                    (datetime.now().isoformat(timespec="seconds"),cname.strip(),cphone.strip(),subject,message.strip()))
                audit("Message reçu","message_public",mid,subject)
                st.success("Votre message a été transmis au registre de l’administration de l’ASC AFRICA. Merci.")

    elif menu == "📝 Rejoindre le club":
        st.markdown("<div class='section'>📝 Rejoindre la communauté ASC AFRICA</div>", unsafe_allow_html=True)
        st.write("Envoyez votre demande d’adhésion. Le bureau du club pourra ensuite vérifier les informations et vous recontacter.")
        with st.form("public_join"):
            name=st.text_input("Nom complet *"); phone=st.text_input("Téléphone *")
            neighborhood=st.text_input("Quartier"); role=st.selectbox("Profil",["Supporter","Membre","Ancien joueur","Dirigeant","Sympathisant"])
            notes=st.text_area("Message (facultatif)")
            submit=st.form_submit_button("Envoyer ma demande d’adhésion",type="primary",use_container_width=True)
        if submit:
            if not name.strip() or not phone.strip(): st.error("Le nom et le téléphone sont obligatoires.")
            else:
                execute("INSERT INTO members(member_no,full_name,phone,neighborhood,membership_date,role,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(receipt_no("MEM"),name.strip(),phone.strip(),neighborhood.strip(),date.today().isoformat(),role,"À valider",notes.strip(),datetime.now().isoformat(timespec="seconds"),datetime.now().isoformat(timespec="seconds")))
                audit("Demande d'adhésion","membre",None,name.strip())
                st.success("Votre demande a été enregistrée. Le bureau de l’ASC AFRICA pourra la vérifier.")

    bottom_message()
    st.markdown("<div style='margin:2px auto 0;max-width:900px;text-align:center;padding:12px 16px 5px;border:1px solid #dbe7f2;border-radius:16px 16px 0 0;background:linear-gradient(135deg,#ffffff,#f1f6fc)'><div class='eyebrow'>Accès réservé</div><h3 style='color:#123b75;margin:.25rem 0'>Vous faites partie de l’équipe de gestion ?</h3><p style='color:#526176;margin:0'>Accès à l’espace d’administration du portail.</p></div>", unsafe_allow_html=True)
    if st.button("🔐 Accéder à l’administration", key="bottom_admin_access", type="secondary", use_container_width=True):
        st.session_state.show_admin_login = True
        st.rerun()

    # Bandeau de collaboration placé juste après l'accès réservé pour remplir
    # visuellement la zone vide sans créer un grand espace artificiel.
    st.markdown("""
    <style>
    .yam-africa-collab{box-sizing:border-box;width:100%;margin:10px auto 12px;padding:clamp(18px,3vw,30px);border-radius:18px;border:1px solid #d7e4f2;background:linear-gradient(120deg,#ffffff 0%,#edf5ff 52%,#e9f8f5 100%);box-shadow:0 8px 24px rgba(18,59,117,.08);text-align:center;overflow:hidden;}
    .yam-africa-collab .collab-kicker{font-size:.78rem;letter-spacing:.12em;font-weight:900;color:#0b8278;text-transform:uppercase;margin-bottom:7px;}
    .yam-africa-collab h3{font-size:clamp(1.2rem,2.4vw,1.8rem);line-height:1.2;color:#123b75;font-weight:950;margin:0 auto 10px;}
    .yam-africa-collab p{max-width:980px;margin:0 auto;color:#40536b;font-size:clamp(.92rem,1.35vw,1.06rem);line-height:1.7;}
    .yam-africa-pills{display:flex;justify-content:center;align-items:center;gap:8px;flex-wrap:wrap;margin-top:15px;}
    .yam-africa-pills span{display:inline-flex;align-items:center;justify-content:center;padding:8px 13px;border-radius:999px;background:#123b75;color:white;font-size:.82rem;font-weight:850;}
    .yam-africa-pills span:nth-child(2){background:#0b8278}.yam-africa-pills span:nth-child(3){background:#a87500}
    div[data-testid='stVerticalBlock'] div[data-testid='stElementContainer']:has(.yam-africa-collab){margin-top:0!important;margin-bottom:0!important;padding-top:0!important;padding-bottom:0!important;}
    div[data-testid='stVerticalBlock'] div[data-testid='stElementContainer']:has(.site-footer){margin-top:0!important;padding-top:0!important;}
    div[data-testid='stVerticalBlock'] div[data-testid='stElementContainer']:has(.site-footer) p{margin-bottom:0!important;}
    .block-container{padding-bottom:0!important;}
    @media(max-width:600px){.yam-africa-collab{padding:17px 13px;margin:8px auto 10px;border-radius:14px}.yam-africa-pills{gap:6px}.yam-africa-pills span{font-size:.76rem;padding:7px 10px}}
    @media(prefers-reduced-motion:no-preference){.yam-africa-collab{animation:collabFadeIn .7s ease both}@keyframes collabFadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}}
    </style>
    <section class="yam-africa-collab" aria-label="Collaboration YAM et ASC AFRICA">
      <div class="collab-kicker">Une collaboration au service de la communauté</div>
      <h3>YAM × ASC AFRICA : ensemble, accélérons le numérique local</h3>
      <p>Pour soutenir la vie associative et faciliter l’accès à l’information, <strong>YAM Group, à travers sa filiale YAM Consultancy, offre cette plateforme à l’ASC AFRICA</strong>. Cette initiative illustre une ambition commune : mettre les solutions numériques au service des clubs, des organisations et des communautés, avec une vision tournée vers l’action, la proximité et le développement durable.</p>
      <div class="yam-africa-pills"><span>⚽ Vie associative</span><span>💻 Solutions numériques</span><span>🤝 Engagement communautaire</span></div>
    </section>
    """, unsafe_allow_html=True)

    # Bandeau YAM compact, placé immédiatement après le panneau de collaboration.
    # On évite ici le grand pied de page détaillé qui repoussait la barre au bas de l'écran.
    st.markdown("""
    <style>
      .yam-compact-credit{width:100%;box-sizing:border-box;margin:8px 0 0;padding:11px 12px;background:#07172e;color:#fff;border-top:3px solid #d7a62a;border-radius:8px 8px 0 0;overflow:hidden;text-align:center;}
      .yam-compact-credit .yam-credit-title{font-size:clamp(.86rem,1.5vw,1.05rem);font-weight:950;line-height:1.45;color:#fff;margin-bottom:4px;}
      .yam-compact-credit .yam-credit-copy{font-size:clamp(.72rem,1.1vw,.88rem);line-height:1.5;color:#dce8f7;margin-bottom:8px;}
      .yam-compact-track-window{width:100%;overflow:hidden;background:#041020;border-radius:0 0 8px 8px;padding:10px 0;}
      .yam-compact-track{display:flex;align-items:center;width:max-content;gap:26px;white-space:nowrap;animation:yamCompactMarquee 34s linear infinite;color:#fff;font-size:clamp(.72rem,1vw,.86rem);font-weight:900;}
      .yam-compact-track span{flex:0 0 auto;}
      .yam-compact-track b{color:#f4bd38;}
      @keyframes yamCompactMarquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
      @media(max-width:600px){.yam-compact-credit{padding:10px 8px}.yam-compact-track{animation-duration:25s;gap:18px}}
      @media(prefers-reduced-motion:reduce){.yam-compact-track{animation:none;width:100%;white-space:normal;flex-wrap:wrap;justify-content:center;padding:0 8px;box-sizing:border-box}}
      div[data-testid='stVerticalBlock'] div[data-testid='stElementContainer']:has(.yam-compact-credit){margin-top:0!important;margin-bottom:0!important;padding-top:0!important;padding-bottom:0!important;}
    </style>
    <div class="yam-compact-credit">
      <div class="yam-credit-title">UN DON NUMÉRIQUE DE YAM GROUP À L’ASC AFRICA</div>
      <div class="yam-credit-copy">Plateforme offerte par <strong>YAM Group, à travers sa filiale YAM Consultancy</strong> — conseil, accompagnement opérationnel et solutions numériques.<br>« Ensemble pour un Sénégal plus fort : Agir aujourd’hui, bâtir demain »</div>
    </div>
    <div class="yam-compact-track-window" aria-label="Domaines d’activité de YAM Group"><div class="yam-compact-track">
      <span>🌱 <b>YAM GROUP</b> · AGRICULTURE</span><span>✦ DON DE <b>YAM GROUP</b> · FILIALE <b>YAM CONSULTANCY</b></span><span>🩺 SANTÉ</span><span>🎓 ÉDUCATION</span><span>⚡ ÉNERGIE</span><span>🏗️ BTP</span><span>💻 INFORMATION</span><span>📊 CONSULTANCY</span><span>📈 ÉCONOMIE</span><span>🤝 COMMERCE</span>
      <span>🌱 <b>YAM GROUP</b> · AGRICULTURE</span><span>✦ DON DE <b>YAM GROUP</b> · FILIALE <b>YAM CONSULTANCY</b></span><span>🩺 SANTÉ</span><span>🎓 ÉDUCATION</span><span>⚡ ÉNERGIE</span><span>🏗️ BTP</span><span>💻 INFORMATION</span><span>📊 CONSULTANCY</span><span>📈 ÉCONOMIE</span><span>🤝 COMMERCE</span>
    </div></div>
    """, unsafe_allow_html=True)

def members_page():
    st.markdown('<div class="section">👥 Membres & adhésions</div>',unsafe_allow_html=True)
    pending_count=int(query_df("SELECT COUNT(*) n FROM members WHERE status='À valider'").iloc[0,0])
    st.markdown(f"<div class='admin-banner'><div class='kicker'>Espace de gestion · Communauté</div><h2>Adhésions & registre des membres</h2><p>{pending_count} demande(s) d’adhésion en attente de validation · Les formulaires publics sont centralisés ici.</p></div>",unsafe_allow_html=True)
    t1,t2,t3=st.tabs(["Ajouter un membre","Registre des membres",f"Demandes publiques ({pending_count})"])
    with t1:
        with st.form("member_add",clear_on_submit=True):
            a,b=st.columns(2)
            name=a.text_input("Nom complet *"); phone=b.text_input("Téléphone *")
            neighborhood=a.text_input("Quartier"); role=b.selectbox("Profil",["Membre","Supporter","Ancien joueur","Dirigeant","Sympathisant"])
            member_date=a.date_input("Date d'adhésion",value=date.today()); status=b.selectbox("Statut",["Actif","À valider","Suspendu","Ancien membre"])
            notes=st.text_area("Observations")
            save=st.form_submit_button("Enregistrer le membre",type="primary")
        if save:
            if not name.strip() or not phone.strip(): st.error("Nom et téléphone obligatoires.")
            else:
                no=receipt_no("MEM")
                mid=execute("INSERT INTO members(member_no,full_name,phone,neighborhood,membership_date,role,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (no,name.strip(),phone.strip(),neighborhood.strip(),member_date.isoformat(),role,status,notes.strip(),datetime.now().isoformat(timespec="seconds"),datetime.now().isoformat(timespec="seconds")))
                audit("Création","membre",mid,f"{no} — {name}")
                st.success(f"Membre enregistré : {no}"); st.rerun()
    with t2:
        df=query_df("SELECT id,member_no,full_name,phone,neighborhood,membership_date,role,status,notes FROM members ORDER BY full_name")
        search=st.text_input("Rechercher par nom, numéro ou téléphone")
        if search: df=df[df.astype(str).apply(lambda col:col.str.contains(search,case=False,na=False)).any(axis=1)]
        st.dataframe(df.rename(columns={"member_no":"N° membre","full_name":"Nom complet","phone":"Téléphone","neighborhood":"Quartier","membership_date":"Adhésion","role":"Profil","status":"Statut","notes":"Notes"}),use_container_width=True,hide_index=True)
        if not df.empty:
            ids=df["id"].tolist(); selected=st.selectbox("Membre à modifier / supprimer",ids,format_func=lambda i:f"{i} — {df.loc[df.id==i,'full_name'].iloc[0]}")
            row=query_df("SELECT * FROM members WHERE id=?",(selected,)).iloc[0]
            with st.form("member_edit"):
                name=st.text_input("Nom",str(row.full_name)); phone=st.text_input("Téléphone",str(row.phone or ""))
                neighborhood=st.text_input("Quartier",str(row.neighborhood or "")); role=st.selectbox("Profil",["Membre","Supporter","Ancien joueur","Dirigeant","Sympathisant"],index=["Membre","Supporter","Ancien joueur","Dirigeant","Sympathisant"].index(row.role) if row.role in ["Membre","Supporter","Ancien joueur","Dirigeant","Sympathisant"] else 0)
                status=st.selectbox("Statut",["Actif","À valider","Suspendu","Ancien membre"],index=["Actif","À valider","Suspendu","Ancien membre"].index(row.status) if row.status in ["Actif","À valider","Suspendu","Ancien membre"] else 0)
                notes=st.text_area("Notes",str(row.notes or "")); save=st.form_submit_button("Enregistrer les modifications")
            if save:
                execute("UPDATE members SET full_name=?,phone=?,neighborhood=?,role=?,status=?,notes=?,updated_at=? WHERE id=?",(name.strip(),phone.strip(),neighborhood.strip(),role,status,notes,datetime.now().isoformat(timespec="seconds"),int(selected)))
                audit("Modification","membre",int(selected),name); st.success("Membre mis à jour."); st.rerun()
            if st.button("Supprimer ce membre",type="secondary"):
                execute("DELETE FROM members WHERE id=?",(int(selected),)); audit("Suppression","membre",int(selected),str(row.full_name)); st.warning("Membre supprimé."); st.rerun()
        st.download_button("Exporter les membres en CSV",df.to_csv(index=False).encode("utf-8-sig"),"asc_africa_membres.csv","text/csv")

    with t3:
        pending=query_df("SELECT id,member_no,full_name,phone,neighborhood,membership_date,role,notes,created_at FROM members WHERE status='À valider' ORDER BY created_at DESC")
        st.subheader("Demandes reçues depuis le portail public")
        if pending.empty:
            st.success("Aucune demande en attente.")
        else:
            st.dataframe(pending.drop(columns=["id"]),use_container_width=True,hide_index=True)
            pid=st.selectbox("Demande à traiter",pending.id.tolist(),format_func=lambda i:f"{i} — {pending.loc[pending.id==i,'full_name'].iloc[0]}")
            a,b=st.columns(2)
            if a.button("✅ Valider l’adhésion",type="primary",use_container_width=True):
                execute("UPDATE members SET status='Actif',updated_at=? WHERE id=?",(datetime.now().isoformat(timespec="seconds"),int(pid)))
                audit("Validation adhésion publique","membre",int(pid)); st.success("Demande validée."); st.rerun()
            if b.button("↩️ Refuser / classer",use_container_width=True):
                execute("UPDATE members SET status='Ancien membre',updated_at=? WHERE id=?",(datetime.now().isoformat(timespec="seconds"),int(pid)))
                audit("Classement demande publique","membre",int(pid)); st.rerun()
            st.download_button("Exporter les demandes CSV",pending.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),"asc_africa_demandes_adhesion.csv","text/csv")

def payments_page():
    st.markdown('<div class="section">💳 Cotisations, cartes & reçus</div>', unsafe_allow_html=True)
    st.markdown("<div class='admin-banner'><div class='kicker'>Encaissements · justificatifs</div><h2>Centre des paiements</h2><p>Enregistrez les cotisations des membres et contributions des partenaires, consultez les sommes reçues par mode de paiement et téléchargez les reçus PDF. Interface adaptée aux téléphones.</p></div>", unsafe_allow_html=True)
    members = query_df("SELECT id,member_no,full_name,phone FROM members ORDER BY full_name")
    t1, t2 = st.tabs(["➕ Nouvel encaissement", "🧾 Historique & reçus"])
    with t1:
        payer_kind = st.radio("Qui effectue le paiement ?", ["Membre", "Partenaire"], horizontal=True, key="payment_payer_kind")
        if payer_kind == "Membre" and members.empty:
            st.warning("Ajoutez d'abord les membres ou validez les demandes d'adhésion.")
        else:
            opts = {f"{r.member_no or r.id} — {r.full_name} ({r.phone or 'sans téléphone'})": int(r.id) for _, r in members.iterrows()} if not members.empty else {}
            with st.form("payment_form", clear_on_submit=True):
                if payer_kind == "Membre":
                    member_label = st.selectbox("Membre", list(opts))
                    payer_name = opts[member_label]
                    payer_phone = ""
                else:
                    partner_name = st.text_input("Nom du partenaire / organisme", placeholder="Nom du partenaire")
                    partner_phone = st.text_input("Téléphone du partenaire (facultatif)", placeholder="77 xxx xx xx")
                    payer_name = None
                    payer_phone = partner_phone
                ptype = st.selectbox("Type de paiement", ["Cotisation membre — 2 000 FCFA", "Cotisation partenaire (montant variable)", "Carte membre — 500 FCFA", "Carte de soutien — 1 000 FCFA", "Don", "Contribution événementielle", "Autre"])
                default = 2000 if ptype.startswith("Cotisation membre") else 500 if ptype.startswith("Carte membre") else 1000 if ptype.startswith("Carte de soutien") else 0
                amount = st.number_input("Montant encaissé (FCFA)", min_value=0, step=500, value=default)
                if ptype.startswith("Cotisation partenaire"):
                    st.caption("Le montant de la cotisation partenaire est libre et dépend de la contribution convenue.")
                d = st.date_input("Date du paiement", value=date.today())
                period = st.text_input("Période concernée", placeholder="Ex. Octobre 2026")
                method = st.selectbox("Mode de paiement", ["Espèces", "Wave", "Orange Money", "Virement", "Chèque", "Autre"])
                note = st.text_input("Observation")
                save = st.form_submit_button("✅ Valider et générer le reçu", type="primary", use_container_width=True)
            if save:
                if amount <= 0:
                    st.error("Le montant doit être supérieur à zéro.")
                elif payer_kind == "Partenaire" and not partner_name.strip():
                    st.error("Veuillez renseigner le nom du partenaire.")
                else:
                    rn = receipt_no("ASC")
                    member_id = opts[member_label] if payer_kind == "Membre" else None
                    stored_name = (opts and next((r.full_name for _, r in members.iterrows() if int(r.id)==member_id), "")) if member_id else partner_name.strip()
                    stored_phone = (next((r.phone or "" for _, r in members.iterrows() if int(r.id)==member_id), "")) if member_id else payer_phone.strip()
                    pid = execute("INSERT INTO payments(receipt_no,member_id,payment_date,payment_type,amount,period,method,note,created_by,created_at,payer_name,payer_phone) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (rn, member_id, d.isoformat(), ptype, float(amount), period, method, note, st.session_state.actor, datetime.now().isoformat(timespec="seconds"), stored_name, stored_phone))
                    execute("INSERT INTO cash_entries(entry_date,direction,category,label,amount,method,reference,note,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (d.isoformat(), "Entrée", ptype, f"Paiement {rn} — {stored_name}", float(amount), method, rn, note, st.session_state.actor, datetime.now().isoformat(timespec="seconds")))
                    audit("Encaissement", "paiement", pid, f"{rn} — {stored_name} — {money(amount)} — {method}")
                    st.session_state["last_receipt_no"] = rn
                    st.success(f"Paiement enregistré. Numéro de reçu : {rn}")
                    st.rerun()
            last_no = st.session_state.get("last_receipt_no")
            if last_no:
                last = query_df("SELECT p.*,COALESCE(NULLIF(p.payer_name,''),m.full_name,'Membre') AS full_name,COALESCE(NULLIF(p.payer_phone,''),m.phone,'') AS phone FROM payments p LEFT JOIN members m ON m.id=p.member_id WHERE p.receipt_no=?", (last_no,))
                if not last.empty:
                    r = last.iloc[0]
                    st.markdown(f"<div class='card'><div class='eyebrow'>Paiement confirmé</div><h3 style='color:#123b75'>{html.escape(str(r.full_name or 'Membre'))}</h3><div class='card-value'>{money(r.amount)}</div><p>N° reçu : <b>{html.escape(str(r.receipt_no))}</b> · {fmt_date(r.payment_date)} · {html.escape(str(r.method or ''))}</p></div>", unsafe_allow_html=True)
                    pdf = receipt_pdf_bytes(r)
                    if pdf: st.download_button("📄 Télécharger le reçu PDF officiel", pdf, f"recu_{r.receipt_no}.pdf", "application/pdf", use_container_width=True)
                    url = whatsapp_url(r.phone, f"ASC AFRICA — Reçu {r.receipt_no}\nPayeur : {r.full_name}\nObjet : {r.payment_type}\nMontant : {money(r.amount)}\nDate : {fmt_date(r.payment_date)}\nMode : {r.method}\nMerci pour votre soutien !")
                    if url: st.link_button("📲 Partager les détails sur WhatsApp", url, use_container_width=True)
    with t2:
        df = query_df("SELECT p.id,p.receipt_no,p.payment_date,COALESCE(NULLIF(p.payer_name,''),m.full_name,'Membre') AS full_name,COALESCE(NULLIF(p.payer_phone,''),m.phone,'') AS phone,p.payment_type,p.amount,p.period,p.method,p.note FROM payments p LEFT JOIN members m ON m.id=p.member_id ORDER BY p.payment_date DESC,p.id DESC")
        if df.empty:
            st.info("Aucun paiement enregistré pour le moment.")
        else:
            q = st.text_input("🔎 Rechercher un reçu, un membre ou un numéro", placeholder="Nom, ASC-2026…")
            view = df[df.astype(str).apply(lambda col: col.str.contains(q, case=False, na=False)).any(axis=1)] if q.strip() else df
            st.caption(f"{len(view)} reçu(s) affiché(s) · sommes calculées sur les résultats affichés")
            total = float(view["amount"].sum()) if not view.empty else 0
            st.metric("💰 Total reçu", money(total))
            methods_order = ["Espèces", "Wave", "Orange Money", "Virement", "Chèque", "Autre"]
            method_totals = view.groupby("method", dropna=False)["amount"].agg(["sum", "count"]).reset_index() if not view.empty else pd.DataFrame(columns=["method", "sum", "count"])
            method_totals["method"] = method_totals["method"].fillna("Non précisé")
            cols = st.columns(3)
            summary = {str(row["method"]): (float(row["sum"]), int(row["count"])) for _, row in method_totals.iterrows()}
            for i, m in enumerate(methods_order):
                value, count = summary.get(m, (0, 0))
                with cols[i % 3]:
                    st.metric(f"{m} · {count} paiement(s)", money(value))
            for _, row in method_totals.iterrows():
                m = str(row["method"])
                if m not in methods_order:
                    st.metric(f"{m} · {int(row['count'])} paiement(s)", money(row["sum"]))
            st.dataframe(view.rename(columns={"receipt_no":"N° reçu","payment_date":"Date","full_name":"Payeur / membre","phone":"Téléphone","payment_type":"Objet","amount":"Montant FCFA","period":"Période","method":"Mode","note":"Observation"}), use_container_width=True, hide_index=True)
            chosen = st.selectbox("Choisir le reçu à télécharger ou partager", view["receipt_no"].tolist()) if not view.empty else None
            if chosen:
                r = view[view.receipt_no == chosen].iloc[0]
                st.markdown(f"<div class='card'><div class='eyebrow'>Aperçu du reçu</div><h3 style='color:#123b75'>ASC AFRICA · {html.escape(str(r.receipt_no))}</h3><p><b>Bénéficiaire :</b> {html.escape(str(r.full_name or '—'))}</p><p><b>Objet :</b> {html.escape(str(r.payment_type))}</p><div class='card-value'>{money(r.amount)}</div><p><b>Date :</b> {fmt_date(r.payment_date)} &nbsp; · &nbsp; <b>Mode :</b> {html.escape(str(r.method or '—'))}</p></div>", unsafe_allow_html=True)
                receipt_row = r.copy()
                receipt_row["payer_name"] = r.full_name
                receipt_row["payer_phone"] = r.phone
                pdf = receipt_pdf_bytes(receipt_row)
                if pdf: st.download_button("📄 Télécharger le reçu PDF", pdf, f"recu_{r.receipt_no}.pdf", "application/pdf", use_container_width=True)
                message = f"ASC AFRICA — Reçu {r.receipt_no}\nMembre / partenaire : {r.full_name}\nObjet : {r.payment_type}\nMontant : {money(r.amount)}\nDate : {fmt_date(r.payment_date)}\nMode : {r.method}"
                url = whatsapp_url(r.phone, message)
                if url: st.link_button("📲 Envoyer / relancer sur WhatsApp", url, use_container_width=True)
            st.download_button("📥 Exporter l'historique en CSV", view.to_csv(index=False).encode("utf-8-sig"), "asc_africa_paiements.csv", "text/csv", use_container_width=True)
            with st.expander("🗑️ Supprimer un paiement", expanded=False):
                if not view.empty:
                    delete_receipt = st.selectbox(
                        "Paiement à supprimer", view["receipt_no"].tolist(), key="payment_delete_receipt",
                        format_func=lambda value: f"{value} — {view.loc[view.receipt_no == value, 'full_name'].iloc[0]} — {money(view.loc[view.receipt_no == value, 'amount'].iloc[0])}"
                    )
                    confirm_payment_delete = st.checkbox("Je confirme la suppression définitive de ce paiement", key="confirm_payment_delete")
                    if st.button("Confirmer la suppression du paiement", key="delete_payment_btn", type="secondary"):
                        if not confirm_payment_delete:
                            st.error("Cochez la confirmation avant de supprimer.")
                        else:
                            payment_row = view[view.receipt_no == delete_receipt].iloc[0]
                            # Supprime aussi l'écriture de caisse créée automatiquement pour ce reçu.
                            execute("DELETE FROM cash_entries WHERE reference=? AND label LIKE ?", (str(delete_receipt), f"Paiement {delete_receipt} —%"))
                            execute("DELETE FROM payments WHERE receipt_no=?", (str(delete_receipt),))
                            audit("Suppression", "paiement", int(payment_row.id), f"{delete_receipt} — {payment_row.full_name} — {money(payment_row.amount)}")
                            st.session_state.pop("last_receipt_no", None)
                            st.success("Paiement et écriture de caisse associée supprimés.")
                            st.rerun()
    if not REPORTLAB_OK:
        st.info("Pour générer les reçus PDF, installez ReportLab : pip install reportlab")

def cash_page():
    st.markdown('<div class="section">💰 Trésorerie & caisse</div>',unsafe_allow_html=True)
    entries=query_df("SELECT * FROM cash_entries ORDER BY entry_date DESC,id DESC")
    income=entries.loc[entries.direction=="Entrée","amount"].sum() if not entries.empty else 0
    expense=entries.loc[entries.direction=="Sortie","amount"].sum() if not entries.empty else 0
    a,b,c=st.columns(3); a.metric("Total entrées",money(income)); b.metric("Total sorties",money(expense)); c.metric("Solde théorique",money(income-expense))
    with st.expander("➕ Enregistrer une entrée ou une sortie",expanded=True):
        with st.form("cash_form"):
            x,y=st.columns(2); d=x.date_input("Date",value=date.today()); direction=y.selectbox("Sens",["Entrée","Sortie"])
            cat=x.selectbox("Catégorie",["Cotisations","Cartes","Dons","Sponsoring","Événement","Transport","Équipement sportif","Logistique","Communication","Action sociale","Autre"])
            label=y.text_input("Libellé *"); amount=x.number_input("Montant (FCFA)",min_value=0,step=500); method=y.selectbox("Mode",["Espèces","Wave","Orange Money","Virement","Chèque","Autre"])
            reference=x.text_input("Référence (facultatif)"); note=st.text_area("Justificatif / observation")
            save=st.form_submit_button("Enregistrer l'opération",type="primary")
        if save:
            if not label.strip() or amount<=0: st.error("Le libellé et un montant positif sont obligatoires.")
            else:
                eid=execute("INSERT INTO cash_entries(entry_date,direction,category,label,amount,method,reference,note,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (d.isoformat(),direction,cat,label.strip(),float(amount),method,reference,note,st.session_state.actor,datetime.now().isoformat(timespec="seconds")))
                audit("Opération de caisse","caisse",eid,f"{direction} — {label} — {money(amount)}"); st.success("Opération enregistrée."); st.rerun()
    st.subheader("Journal de caisse")
    if entries.empty: st.info("Aucune opération de caisse.")
    else:
        st.dataframe(entries.rename(columns={"entry_date":"Date","direction":"Sens","category":"Catégorie","label":"Libellé","amount":"Montant FCFA","method":"Mode","reference":"Référence","note":"Observation","created_by":"Saisi par"}),use_container_width=True,hide_index=True)
        st.download_button("Exporter la caisse en CSV",entries.to_csv(index=False).encode("utf-8-sig"),"asc_africa_caisse.csv","text/csv")
        with st.expander("🗑️ Supprimer une opération de caisse", expanded=False):
            eid=st.selectbox("Opération à supprimer",entries.id.tolist(),key="cash_delete_id",format_func=lambda i:f"#{i} — {entries.loc[entries.id==i,'entry_date'].iloc[0]} — {entries.loc[entries.id==i,'label'].iloc[0]} — {money(entries.loc[entries.id==i,'amount'].iloc[0])}")
            confirm_cash_delete=st.checkbox("Je confirme la suppression définitive de cette opération",key="cash_delete_confirm")
            if st.button("Confirmer la suppression de l'opération",key="cash_delete_button",type="secondary"):
                if not confirm_cash_delete:
                    st.error("Cochez la confirmation avant de supprimer.")
                else:
                    details=query_df("SELECT label,direction,amount FROM cash_entries WHERE id=?",(int(eid),))
                    execute("DELETE FROM cash_entries WHERE id=?",(int(eid),))
                    label=str(details.iloc[0].label) if not details.empty else "Opération de caisse"
                    audit("Suppression","caisse",int(eid),label)
                    st.success("Opération de caisse supprimée.")
                    st.rerun()

def activities_page():
    st.markdown('<div class="section">📅 Agenda & activités ASC AFRICA</div>',unsafe_allow_html=True)
    with st.expander("➕ Ajouter une activité",expanded=True):
        with st.form("activity_form"):
            title=st.text_input("Nom de l'activité *"); typ=st.selectbox("Type",["Navétanes","Tournoi","72H ASC AFRICA","Africa Social & Solidaire","Africa New Look","Set-Setal","Réunion","Action communautaire","Autre"])
            a,b=st.columns(2); start=a.date_input("Date de début",value=date.today()); end=b.date_input("Date de fin",value=date.today())
            loc=a.text_input("Lieu"); budget=b.number_input("Budget prévisionnel (FCFA)",min_value=0,step=5000)
            desc=st.text_area("Description"); status=st.selectbox("Statut",["Prévue","En préparation","En cours","Réalisée","Annulée"])
            save=st.form_submit_button("Enregistrer l'activité",type="primary")
        if save:
            if not title.strip(): st.error("Le nom de l'activité est obligatoire.")
            else:
                aid=execute("INSERT INTO activities(title,activity_type,start_date,end_date,location,description,budget,status,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (title.strip(),typ,start.isoformat(),end.isoformat(),loc,desc,float(budget),status,datetime.now().isoformat(timespec="seconds")))
                audit("Création","activité",aid,title); st.success("Activité enregistrée."); st.rerun()
    df=query_df("SELECT * FROM activities ORDER BY start_date DESC")
    st.dataframe(df.rename(columns={"title":"Activité","activity_type":"Type","start_date":"Début","end_date":"Fin","location":"Lieu","description":"Description","budget":"Budget FCFA","status":"Statut"}),use_container_width=True,hide_index=True)
    if not df.empty:
        with st.expander("Modifier le statut d'une activité"):
            aid=st.selectbox("Activité",df.id.tolist(),format_func=lambda i:f"{i} — {df.loc[df.id==i,'title'].iloc[0]}")
            status=st.selectbox("Nouveau statut",["Prévue","En préparation","En cours","Réalisée","Annulée"])
            if st.button("Mettre à jour le statut"):
                execute("UPDATE activities SET status=? WHERE id=?",(status,int(aid))); audit("Modification statut","activité",int(aid),status); st.rerun()
        with st.expander("🗑️ Supprimer une activité", expanded=False):
            delete_aid=st.selectbox("Activité à supprimer",df.id.tolist(),key="activity_delete_id",format_func=lambda i:f"#{i} — {df.loc[df.id==i,'title'].iloc[0]}")
            confirm_activity_delete=st.checkbox("Je confirme la suppression définitive de cette activité",key="confirm_activity_delete")
            if st.button("Confirmer la suppression de l'activité",key="delete_activity_button",type="secondary"):
                if not confirm_activity_delete:
                    st.error("Cochez la confirmation avant de supprimer.")
                else:
                    title_deleted=str(df.loc[df.id==delete_aid,"title"].iloc[0])
                    execute("DELETE FROM activities WHERE id=?",(int(delete_aid),))
                    audit("Suppression","activité",int(delete_aid),title_deleted)
                    st.success("Activité supprimée.")
                    st.rerun()

def news_sponsors_page():
    st.markdown('<div class="section">📰 Communication, actualités & partenaires</div>',unsafe_allow_html=True)
    t1,t2,t3,t4=st.tabs(["Publier une actualité","Partenaires & mécènes","Registres","Messages publics"])
    with t1:
        with st.form("news_form"):
            title=st.text_input("Titre *")
            subtitle=st.text_input("Sous-titre (facultatif)")
            category=st.selectbox("Rubrique",["Communiqué officiel","Actualité","Équipe première","Jeunes et formation","Matchs et compétitions","Résultats et classements","Portrait de joueur","Interview et témoignage","Vie associative","Action sociale","Historique","Archives","Palmarès","Annonce","Partenaires","Autre"])
            a,b=st.columns(2)
            d=a.date_input("Date de publication",value=date.today())
            author=b.text_input("Auteur / service")
            cover_url=st.text_input("Lien HTTPS de l’image de couverture (facultatif)")
            content=st.text_area("Contenu *",height=220)
            a,b=st.columns(2)
            published=a.checkbox("Publier sur le portail public",value=True)
            featured=b.checkbox("Mettre cette actualité à la une")
            save=st.form_submit_button("Enregistrer la publication",type="primary")
        if save:
            if not title.strip() or not content.strip(): st.error("Le titre et le contenu sont obligatoires.")
            else:
                if cover_url.strip() and not cover_url.strip().startswith(("https://", "http://")):
                    st.error("Le lien de couverture doit commencer par https:// ou http://.")
                else:
                    if featured:
                        execute("UPDATE news SET featured=0")
                    nid=execute("INSERT INTO news(title,category,publish_date,content,published,created_at,subtitle,author,cover_url,featured) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (title.strip(),category,d.isoformat(),content.strip(),int(published),datetime.now().isoformat(timespec="seconds"),subtitle.strip(),author.strip(),cover_url.strip(),int(featured)))
                    audit("Publication","actualité",nid,title); st.success("Actualité enregistrée."); st.rerun()
    with t2:
        with st.form("sponsor_form"):
            name=st.text_input("Nom du partenaire / mécène *"); typ=st.selectbox("Type",["Partenaire officiel","Sponsor événementiel","Mécène","Partenaire institutionnel","Partenaire média","Autre"])
            a,b=st.columns(2); contact=a.text_input("Personne à contacter"); phone=b.text_input("Téléphone / email")
            amount=a.number_input("Contribution (FCFA)",min_value=0,step=10000); start=b.date_input("Début partenariat",value=date.today())
            end=b.date_input("Fin partenariat",value=date.today()); notes=st.text_area("Présentation / engagements")
            save=st.form_submit_button("Enregistrer le partenaire",type="primary")
        if save:
            if not name.strip(): st.error("Le nom du partenaire est obligatoire.")
            else:
                sid=execute("INSERT INTO sponsors(name,contact,phone,contribution,partnership_type,start_date,end_date,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?)",(name.strip(),contact,phone,float(amount),typ,start.isoformat(),end.isoformat(),notes,datetime.now().isoformat(timespec="seconds")))
                audit("Création","partenaire",sid,name); st.success("Partenaire enregistré.")
    with t3:
        st.subheader("Actualités")
        n=query_df("SELECT id,title,subtitle,category,publish_date,published,featured FROM news ORDER BY featured DESC,publish_date DESC")
        st.dataframe(n,use_container_width=True,hide_index=True)
        if not n.empty:
            nid=st.selectbox("Actualité à publier / dépublier",n.id.tolist())
            if st.button("Basculer publication"):
                old=int(n.loc[n.id==nid,"published"].iloc[0]); execute("UPDATE news SET published=? WHERE id=?",(0 if old else 1,int(nid))); audit("Publication modifiée","actualité",int(nid)); st.rerun()
            with st.expander("🗑️ Supprimer une actualité", expanded=False):
                delete_nid=st.selectbox("Actualité à supprimer",n.id.tolist(),key="news_delete_id",format_func=lambda i:f"#{i} — {n.loc[n.id==i,'title'].iloc[0]}")
                confirm_news_delete=st.checkbox("Je confirme la suppression définitive de cette actualité",key="confirm_news_delete")
                if st.button("Confirmer la suppression de l'actualité",key="delete_news_button",type="secondary"):
                    if not confirm_news_delete:
                        st.error("Cochez la confirmation avant de supprimer.")
                    else:
                        title_deleted=str(n.loc[n.id==delete_nid,"title"].iloc[0])
                        execute("DELETE FROM news WHERE id=?",(int(delete_nid),))
                        audit("Suppression","actualité",int(delete_nid),title_deleted)
                        st.success("Actualité supprimée.")
                        st.rerun()
        st.subheader("Partenaires")
        sp=query_df("SELECT * FROM sponsors ORDER BY name")
        st.dataframe(sp,use_container_width=True,hide_index=True)
        st.download_button("Exporter les partenaires CSV",sp.to_csv(index=False).encode("utf-8-sig"),"asc_africa_partenaires.csv","text/csv")
        if not sp.empty:
            with st.expander("🗑️ Supprimer un partenaire", expanded=False):
                delete_sid=st.selectbox("Partenaire à supprimer",sp.id.tolist(),key="sponsor_delete_id",format_func=lambda i:f"#{i} — {sp.loc[sp.id==i,'name'].iloc[0]}")
                confirm_sponsor_delete=st.checkbox("Je confirme la suppression définitive de ce partenaire",key="confirm_sponsor_delete")
                if st.button("Confirmer la suppression du partenaire",key="delete_sponsor_button",type="secondary"):
                    if not confirm_sponsor_delete:
                        st.error("Cochez la confirmation avant de supprimer.")
                    else:
                        sponsor_name=str(sp.loc[sp.id==delete_sid,"name"].iloc[0])
                        execute("DELETE FROM sponsors WHERE id=?",(int(delete_sid),))
                        audit("Suppression","partenaire",int(delete_sid),sponsor_name)
                        st.success("Partenaire supprimé.")
                        st.rerun()

    with t4:
        st.markdown("<div class='admin-banner'><div class='kicker'>Espace public → administration</div><h2>Messages reçus</h2><p>Les demandes envoyées depuis Contact sont enregistrées dans la base et consultables ici.</p></div>",unsafe_allow_html=True)
        msgs=query_df("SELECT id,created_at,full_name,contact,subject,message,status,admin_note FROM public_messages ORDER BY created_at DESC")
        if msgs.empty:
            st.info("Aucun message reçu pour le moment.")
        else:
            st.dataframe(msgs.drop(columns=["message","admin_note"]),use_container_width=True,hide_index=True)
            mid=st.selectbox("Ouvrir un message",msgs.id.tolist(),format_func=lambda i:f"#{i} — {msgs.loc[msgs.id==i,'full_name'].iloc[0]} · {msgs.loc[msgs.id==i,'subject'].iloc[0]}")
            msg=msgs.loc[msgs.id==mid].iloc[0]
            st.markdown(f"<div class='news-card'><div class='eyebrow'>{html.escape(str(msg.subject))} · {html.escape(str(msg.created_at))}</div><h3>{html.escape(str(msg.full_name))}</h3><p><b>Contact :</b> {html.escape(str(msg.contact))}</p><p style='white-space:pre-wrap;line-height:1.75'>{html.escape(str(msg.message))}</p></div>",unsafe_allow_html=True)
            with st.form("message_admin_update"):
                status=st.selectbox("Statut",["Nouveau","En cours","Traité","Archivé"],index=["Nouveau","En cours","Traité","Archivé"].index(msg.status) if msg.status in ["Nouveau","En cours","Traité","Archivé"] else 0)
                note=st.text_area("Note interne",str(msg.admin_note or ""))
                save_msg=st.form_submit_button("Enregistrer le suivi")
            if save_msg:
                execute("UPDATE public_messages SET status=?,admin_note=?,handled_by=?,handled_at=? WHERE id=?",(status,note,st.session_state.get("actor","Admin"),datetime.now().isoformat(timespec="seconds"),int(mid)))
                audit("Suivi message public","message_public",int(mid),status); st.success("Suivi enregistré."); st.rerun()
            st.download_button("Exporter les messages CSV",msgs.to_csv(index=False).encode("utf-8-sig"),"asc_africa_messages_publics.csv","text/csv")
            with st.expander("🗑️ Supprimer un message public", expanded=False):
                confirm_message_delete=st.checkbox("Je confirme la suppression définitive de ce message",key="confirm_message_delete")
                if st.button("Supprimer le message ouvert",key="delete_public_message_button",type="secondary"):
                    if not confirm_message_delete:
                        st.error("Cochez la confirmation avant de supprimer.")
                    else:
                        message_name=f"{msg.full_name} — {msg.subject}"
                        execute("DELETE FROM public_messages WHERE id=?",(int(mid),))
                        audit("Suppression","message_public",int(mid),message_name)
                        st.success("Message public supprimé.")
                        st.rerun()

def reports_page():
    st.markdown("<div class='report-hero'><div class='kicker'>Pilotage · Transparence · Assemblée générale</div><h2>Centre de rapports XXL</h2><p>Des documents structurés, identifiables et prêts à être partagés, avec identité graphique ASC AFRICA et signature YAM Consultance.</p></div>",unsafe_allow_html=True)
    start=st.date_input("Du",value=date(date.today().year,1,1),key="report_start")
    end=st.date_input("Au",value=date.today(),key="report_end")
    if start>end: st.error("La date de début doit précéder la date de fin."); return
    p=query_df("""SELECT p.receipt_no,p.payment_date,m.full_name,p.payment_type,p.amount,p.period,p.method
    FROM payments p LEFT JOIN members m ON m.id=p.member_id WHERE p.payment_date BETWEEN ? AND ? ORDER BY p.payment_date""",(start.isoformat(),end.isoformat()))
    cash=query_df("SELECT entry_date,direction,category,label,amount,method,reference,note FROM cash_entries WHERE entry_date BETWEEN ? AND ? ORDER BY entry_date",(start.isoformat(),end.isoformat()))
    inc=cash.loc[cash.direction=="Entrée","amount"].sum() if not cash.empty else 0
    out=cash.loc[cash.direction=="Sortie","amount"].sum() if not cash.empty else 0
    a,b,c,d=st.columns(4)
    for col,label,value,cls in [(a,"Paiements enregistrés",f"{len(p):,}".replace(","," "),""),(b,"Total paiements",money(p.amount.sum() if not p.empty else 0),"green"),(c,"Entrées caisse",money(inc),"gold"),(d,"Sorties caisse",money(out),"red")]:
        col.markdown(f"<div class='report-stat {cls}'><div class='card-label'>{label}</div><div class='card-value'>{value}</div></div>",unsafe_allow_html=True)
    st.subheader("Registre des paiements"); st.dataframe(p,use_container_width=True,hide_index=True)
    st.subheader("Journal de caisse"); st.dataframe(cash,use_container_width=True,hide_index=True)
    st.download_button("📥 Exporter paiements Excel",excel_bytes({"Paiements":p,"Caisse":cash}),"rapport_asc_africa.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("📥 Exporter paiements CSV",p.to_csv(index=False).encode("utf-8-sig"),"rapport_paiements.csv","text/csv")
    if REPORTLAB_OK:
        pdf=pdf_bytes(f"Rapport financier ASC AFRICA — {start:%d/%m/%Y} au {end:%d/%m/%Y}",cash,"Trésorerie et encaissements consolidés",[("Paiements",len(p),BLUE),("Total paiements",money(p.amount.sum() if not p.empty else 0),"#0B8278"),("Entrées caisse",money(inc),"#D7A62A"),("Sorties caisse",money(out),"#C2414B")])
        if pdf: st.download_button("📄 Télécharger le rapport PDF",pdf,"rapport_financier_asc_africa.pdf","application/pdf")
        news_period=query_df("SELECT title,category,publish_date,author,published,featured FROM news WHERE publish_date BETWEEN ? AND ? ORDER BY publish_date DESC",(start.isoformat(),end.isoformat()))
        activities_period=query_df("SELECT title,activity_type,start_date,end_date,location,status,budget FROM activities WHERE start_date BETWEEN ? AND ? ORDER BY start_date",(start.isoformat(),end.isoformat()))
        members_period=query_df("SELECT member_no,full_name,phone,neighborhood,membership_date,role,status FROM members WHERE membership_date BETWEEN ? AND ? ORDER BY membership_date DESC",(start.isoformat(),end.isoformat()))
        st.markdown("<div class='section'>Autres sous-rapports</div>",unsafe_allow_html=True)
        x1,x2,x3=st.columns(3)
        for col,label,data,filename in [(x1,"Communication & actualités",news_period,"rapport_communication.pdf"),(x2,"Activités du club",activities_period,"rapport_activites.pdf"),(x3,"Adhésions & membres",members_period,"rapport_membres.pdf")]:
            with col:
                st.markdown(f"<div class='feature-card'><h3>{label}</h3><p>{len(data)} enregistrement(s) sur la période.</p></div>",unsafe_allow_html=True)
                if REPORTLAB_OK:
                    payload=pdf_bytes(label,data,f"Période du {start:%d/%m/%Y} au {end:%d/%m/%Y}",[("Enregistrements",len(data),BLUE),("Du",start.strftime("%d/%m/%Y"),"#0B8278"),("Au",end.strftime("%d/%m/%Y"),"#D7A62A")])
                    st.download_button(f"📄 Télécharger",payload,filename,"application/pdf",key=f"download_{filename}",use_container_width=True)
                st.download_button("Excel / CSV",data.to_csv(index=False).encode("utf-8-sig"),filename.replace(".pdf",".csv"),"text/csv",key=f"csv_{filename}",use_container_width=True)
    else: st.info("Pour les PDF : installez reportlab avec pip install reportlab")

def excel_bytes(sheets):
    from io import BytesIO
    try:
        buf=BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as writer:
            for name,df in sheets.items(): df.to_excel(writer,index=False,sheet_name=name[:31])
        return buf.getvalue()
    except Exception:
        return b""

def audit_page():
    st.markdown('<div class="section">🛡️ Journal d’audit & traçabilité</div>',unsafe_allow_html=True)
    df=query_df("SELECT created_at,actor,action,entity,entity_id,details FROM audit_logs ORDER BY id DESC LIMIT 2000")
    st.dataframe(df,use_container_width=True,hide_index=True)
    st.download_button("Exporter le journal CSV",df.to_csv(index=False).encode("utf-8-sig"),"asc_africa_audit.csv","text/csv")

def settings_page():
    st.markdown('<div class="section">⚙️ Paramètres, sécurité & gestion des accès</div>',unsafe_allow_html=True)
    st.info("La base de données est hébergée sur Supabase PostgreSQL. Configurez des sauvegardes automatiques côté Supabase et testez régulièrement la restauration.")
    st.subheader("Créer ou modifier un accès de bureau")
    st.write("Le compte **Africa** conserve l’accès général. Les autres comptes peuvent être affectés à un bureau et leurs droits peuvent être modifiés ici.")
    roles = {
        "admin": "Administrateur général — tous les bureaux",
        "finance": "Finances globales — tableau de bord, paiements, trésorerie, rapports",
        "affaires": "Coordination administrative — membres, activités, communication",
        "secretariat": "Secrétariat & membres — adhésions et dossiers des membres",
        "activites": "Bureau des activités — calendrier, événements et suivi",
        "communication": "Communication — actualités, partenaires et messages publics"
    }
    accounts = query_df("SELECT id,username,full_name,active,role,created_at FROM admins ORDER BY username")
    if not accounts.empty:
        st.dataframe(accounts.assign(role=accounts.role.map(roles).fillna(accounts.role), active=accounts.active.map({1:"Actif",0:"Désactivé"})),use_container_width=True,hide_index=True)
    account_names = ["➕ Créer un nouvel accès"] + (accounts.username.tolist() if not accounts.empty else [])
    selected_account = st.selectbox("Compte à créer ou modifier", account_names, key="access_account_select")
    is_new = selected_account == "➕ Créer un nouvel accès"
    current = None if is_new else accounts.loc[accounts.username == selected_account].iloc[0]
    with st.form("access_account_form"):
        username = st.text_input("Identifiant", value="" if is_new else str(current.username), disabled=(not is_new))
        full_name = st.text_input("Nom du responsable / bureau", value="" if is_new else str(current.full_name))
        role_keys = list(roles.keys())
        current_role = "admin" if is_new else (str(current.role) if str(current.role) in roles else "admin")
        role = st.selectbox("Bureau et niveau d’accès", role_keys, index=role_keys.index(current_role), format_func=lambda x: roles[x], disabled=(not is_new and str(current.username)==ADMIN_USER))
        password = st.text_input("Nouveau mot de passe" + (" (obligatoire)" if is_new else " (laisser vide pour ne pas changer)"), type="password")
        active = st.checkbox("Accès actif", value=True if is_new else bool(int(current.active)), disabled=(not is_new and str(current.username)==ADMIN_USER))
        save = st.form_submit_button("Créer l’accès" if is_new else "Enregistrer les modifications", type="primary", use_container_width=True)
    if save:
        uname = username.strip()
        fullname = full_name.strip()
        if not uname or not fullname:
            st.error("Renseignez l’identifiant et le nom du responsable.")
        elif is_new and not password:
            st.error("Choisissez un mot de passe pour ce nouvel accès.")
        elif is_new and int(query_df("SELECT COUNT(*) AS n FROM admins WHERE username=?", (uname,)).iloc[0]["n"]) > 0:
            st.error("Cet identifiant existe déjà.")
        else:
            try:
                if is_new:
                    execute("INSERT INTO admins(username,password_hash,full_name,active,created_at,role) VALUES(?,?,?,?,?,?)",
                            (uname,pw_hash(password),fullname,int(active),datetime.now().isoformat(timespec="seconds"),role))
                    audit("Création accès administration","admin",None,f"{uname} · {role}")
                    st.success("Accès créé. Le responsable peut se connecter avec ses identifiants.")
                else:
                    execute("UPDATE admins SET full_name=?,role=?,active=? WHERE username=?",(fullname,role,int(active),uname))
                    if password:
                        execute("UPDATE admins SET password_hash=? WHERE username=?",(pw_hash(password),uname))
                    audit("Modification accès administration","admin",int(current.id),f"{uname} · rôle={role} · actif={active}")
                    st.success("Accès et droits mis à jour.")
                st.rerun()
            except IntegrityError:
                st.error("Impossible d’enregistrer : cet identifiant est déjà utilisé.")
    st.caption("Conseil : créez un compte pour le responsable des Finances et un autre pour les Affaires administratives. Vous pourrez modifier leur rôle, leur nom, leur mot de passe ou désactiver leur accès.")
    st.subheader("Sauvegardes")
    st.caption("La sauvegarde se gère dans Supabase (backups/PITR selon le forfait). Ne stockez pas les mots de passe ni les clés d’accès dans le dépôt Git.")


st.markdown(r"""<style>
/* Administration XXL : lisibilité et ergonomie renforcées */
.admin-banner{padding:clamp(22px,3vw,42px)!important;border-radius:clamp(18px,2vw,28px)!important}
.admin-banner h2{font-size:clamp(1.7rem,3.6vw,3rem)!important;line-height:1.12!important}
.admin-banner p{font-size:clamp(1rem,1.4vw,1.2rem)!important;line-height:1.6!important}
[data-testid="stForm"]{padding:clamp(12px,2vw,24px);border:1px solid #dce7f4;border-radius:18px;background:#fff;box-shadow:0 8px 24px #123b750a}
[data-testid="stTextInput"] label,[data-testid="stNumberInput"] label,[data-testid="stSelectbox"] label,[data-testid="stDateInput"] label,[data-testid="stTextArea"] label{font-weight:800!important;color:#123b75!important}
[data-testid="stDataFrame"]{border:1px solid #dce7f4;border-radius:14px}
@media(max-width:700px){
 .admin-banner{padding:20px 16px!important;margin:8px 0 14px!important}
 [data-testid="stForm"]{padding:12px!important;border-radius:15px}
 [data-testid="stSelectbox"] [data-baseweb="select"]{min-height:52px!important}
 [data-testid="stMetric"]{padding:12px!important}
 [data-testid="stDataFrame"]{font-size:.85rem!important}
}
</style>""",unsafe_allow_html=True)


def whatsapp_reminders_page():
    """Liste les membres sans cotisation enregistrée pour une période et prépare les rappels WhatsApp."""
    st.markdown('<div class="section">📲 Rappels de cotisation par WhatsApp</div>', unsafe_allow_html=True)
    st.markdown(
        "<div class='admin-banner'><div class='kicker'>Suivi des cotisations · Relance respectueuse</div>"
        "<h2>Membres à relancer</h2><p>Repérez les membres dont la cotisation n’est pas enregistrée pour la période choisie, "
        "puis préparez un message personnalisé en français et en wolof. Chaque bouton ouvre WhatsApp avec le texte prérempli.</p></div>",
        unsafe_allow_html=True
    )
    mois_fr = ["janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
    periode_defaut = f"{mois_fr[date.today().month - 1].capitalize()} {date.today().year}"
    a, b = st.columns([1, 2])
    with a:
        periode = st.text_input("Période de cotisation à vérifier", value=periode_defaut,
                               help="Utilisez la même période que celle enregistrée lors de l’encaissement, par exemple « Octobre 2026 ».")
    with b:
        st.caption("Le contrôle compare la période au champ « Période concernée » des encaissements de type « Cotisation membre ». "
                   "Vérifiez que les paiements ont bien été enregistrés pour éviter les relances erronées.")
    if not periode.strip():
        st.warning("Veuillez préciser une période.")
        return

    unpaid = query_df("""
        SELECT m.id, m.member_no, m.full_name, m.phone
        FROM members m
        WHERE COALESCE(m.status, 'Actif') = 'Actif'
          AND NOT EXISTS (
              SELECT 1 FROM payments p
              WHERE p.member_id = m.id
                AND LOWER(COALESCE(p.payment_type, '')) LIKE 'cotisation membre%'
                AND LOWER(TRIM(COALESCE(p.period, ''))) = LOWER(TRIM(?))
          )
        ORDER BY m.full_name
    """, (periode.strip(),))
    total = len(unpaid)
    sans_tel = int(unpaid["phone"].fillna("").astype(str).str.strip().eq("").sum()) if total else 0
    m1, m2, m3 = st.columns(3)
    m1.metric("Membres actifs à relancer", total)
    m2.metric("Avec numéro renseigné", total - sans_tel)
    m3.metric("Sans téléphone", sans_tel)

    message_defaut = (
        "Asalaam aleykoum {prenom} 🙏🏾\n\n"
        "Naka nga def ? Nous espérons que tu vas bien. Petit rappel amical concernant ta cotisation ASC AFRICA "
        "pour la période de {periode}. Souniou club mooy sunu famille, et chaque contribution compte pour faire avancer nos activités.\n\n"
        "Bu fekkee nga fayoon ba pare, jërëjëf te baal nu — tu peux ignorer ce message. Sinon, merci de régulariser "
        "dès que possible ou de contacter l’administration si tu as une question.\n\n"
        "Jërëjëf ci sa ndimbal ak sa ngor. Ensemble, AFRICA KASSÉ, AFRICA REK ! ⚽💙"
    )
    with st.expander("✍️ Personnaliser le message de rappel", expanded=True):
        template = st.text_area("Message WhatsApp (variables : {prenom}, {nom}, {periode})",
                                value=message_defaut, height=210)
        st.caption("Le message reste courtois et prévoit le cas où le membre aurait déjà payé. L’envoi est effectué par l’administrateur dans WhatsApp.")
    if unpaid.empty:
        st.success(f"Tous les membres actifs ont une cotisation enregistrée pour « {periode} ».")
        return

    st.dataframe(
        unpaid[["member_no", "full_name", "phone"]].rename(
            columns={"member_no": "N° membre", "full_name": "Nom complet", "phone": "Téléphone"}
        ), use_container_width=True, hide_index=True
    )
    st.markdown("### Préparer les rappels individuels")
    for _, member in unpaid.iterrows():
        name = str(member.get("full_name") or "Membre")
        phone = str(member.get("phone") or "").strip()
        prenom = name.split()[0] if name.split() else name
        try:
            msg = template.format(prenom=prenom, nom=name, periode=periode.strip())
        except (KeyError, ValueError):
            st.error("Le modèle contient une variable inconnue ou des accolades incorrectes. Utilisez uniquement {prenom}, {nom} et {periode}.")
            break
        left, right = st.columns([3, 1])
        with left:
            st.write(f"**{name}** · {phone or 'Téléphone non renseigné'}")
        with right:
            url = whatsapp_url(phone, msg)
            if url:
                st.link_button("💬 Ouvrir WhatsApp", url, use_container_width=True)
            else:
                st.button("Numéro manquant", disabled=True, key=f"wa_missing_{int(member.id)}", use_container_width=True)
    st.info("Pour des raisons de sécurité et de respect des membres, ces boutons n’envoient pas automatiquement les messages : "
            "ils ouvrent WhatsApp avec le message prérempli, que l’administrateur peut vérifier puis envoyer.")

def main():
    if "authenticated" not in st.session_state: st.session_state.authenticated=False
    if not st.session_state.authenticated:
        if st.session_state.get("show_admin_login", False):
            # Initialisation complète uniquement à l'ouverture de l'espace admin.
            # Le portail public ne doit pas attendre les DDL, la migration SQLite
            # ni la préparation du compte administrateur avant d'afficher son contenu.
            init_db()
            login()
        else:
            public_page()
        return
    # Un utilisateur authentifié garde le comportement normal, avec init_db en cache.
    init_db()
    header()
    st.markdown(f"<div class='admin-banner'><div class='kicker'>ASC AFRICA · Administration sécurisée</div><h2>Centre de pilotage du club</h2><p>Connecté : <b>{html.escape(str(st.session_state.actor))}</b> · Les données publiques et administratives sont reliées à Supabase PostgreSQL.</p></div>",unsafe_allow_html=True)
    role = st.session_state.get("actor_role", "admin")
    is_admin = role == "admin"
    finance_sections = ["🏠 Tableau de bord financier", "💳 Cotisations & cartes", "📲 Rappels WhatsApp", "💰 Trésorerie", "📊 Rapports & exports"]
    affairs_sections = ["👥 Membres", "📅 Activités", "📰 Communication"]
    if is_admin:
        bureau_options = ["💰 Finances globales", "🏛️ Affaires administratives", "🛡️ Contrôle & paramètres"]
    elif role == "finance":
        bureau_options = ["💰 Finances globales"]
    else:
        bureau_options = ["🏛️ Affaires administratives"]
    st.markdown("<div class='public-nav-label'>BUREAUX DE L’ADMINISTRATION</div><div class='nav-help-mobile'>Choisissez d’abord le bureau, puis son sous-service.</div>",unsafe_allow_html=True)
    bureau = st.selectbox("Choisir un bureau", bureau_options, key="admin_bureau_select")
    if bureau == "💰 Finances globales":
        st.info("**Contenu du bureau financier :** suivi global des encaissements, cotisations des membres et partenaires, cartes, reçus, historique par mode de paiement, entrées/sorties de caisse et rapports financiers exportables.")
        nav = st.selectbox("Sous-services financiers", finance_sections, key="admin_finance_navigation")
    elif bureau == "🏛️ Affaires administratives":
        if role in ("admin", "affaires"):
            st.info("**Contenu du bureau administratif :** secrétariat et dossiers des membres, organisation des activités, communication officielle, actualités, partenaires et messages du public.")
        if role == "secretariat":
            permitted_affairs = ["👥 Membres"]
        elif role == "activites":
            permitted_affairs = ["📅 Activités"]
        elif role == "communication":
            permitted_affairs = ["📰 Communication"]
        else:
            permitted_affairs = affairs_sections
        nav = st.selectbox("Sous-bureau administratif", permitted_affairs, key="admin_affairs_navigation")
    else:
        nav = st.selectbox("Contrôle et configuration", ["🛡️ Audit", "⚙️ Paramètres & accès"], key="admin_control_navigation")
    if st.button("Se déconnecter",key="logout"):
        audit("Déconnexion","administration"); st.session_state.authenticated=False
        for key in ("actor", "actor_username", "actor_role", "login_at"):
            st.session_state.pop(key, None)
        st.rerun()
    st.divider()
    if nav in ("🏠 Tableau de bord financier", "🏠 Tableau de bord"):
        metric_row()
        st.markdown('<div class="section">Pilotage financier de l’ASC AFRICA</div>',unsafe_allow_html=True)
        p=query_df("SELECT payment_date,payment_type,amount,method,COALESCE(NULLIF(payer_name,''),m.full_name,'Partenaire') AS payeur FROM payments p LEFT JOIN members m ON m.id=p.member_id ORDER BY p.id DESC LIMIT 12")
        cash=query_df("SELECT entry_date,direction,category,label,amount,method FROM cash_entries ORDER BY id DESC LIMIT 12")
        a,b=st.columns(2)
        with a:
            st.subheader("Derniers encaissements")
            st.dataframe(p,use_container_width=True,hide_index=True)
        with b:
            st.subheader("Dernières opérations de caisse")
            st.dataframe(cash,use_container_width=True,hide_index=True)
        st.info("Le bureau des Finances suit les cotisations, contributions partenaires, recettes, dépenses, modes de paiement, justificatifs et rapports périodiques.")
    elif nav=="👥 Membres": members_page()
    elif nav=="💳 Cotisations & cartes": payments_page()
    elif nav=="📲 Rappels WhatsApp": whatsapp_reminders_page()
    elif nav=="💰 Trésorerie": cash_page()
    elif nav=="📅 Activités": activities_page()
    elif nav=="📰 Communication": news_sponsors_page()
    elif nav=="📊 Rapports & exports": reports_page()
    elif nav=="🛡️ Audit": audit_page()
    elif nav in ("⚙️ Paramètres", "⚙️ Paramètres & accès"):
        if is_admin: settings_page()
        else: st.error("Votre compte n’a pas accès à la gestion des paramètres.")
    st.divider()
    st.caption("ASC AFRICA • Saint-Louis, Sénégal • Plateforme de gestion associative — Supabase PostgreSQL")
    yam_footer()

if __name__=="__main__":
    main()
