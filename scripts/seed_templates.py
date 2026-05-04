"""Seed the document_templates table with the initial set of Czech legal templates.

Idempotent: uses INSERT ... ON CONFLICT (slug) DO UPDATE, so re-running is safe.

Prerequisite: the document_templates table must exist.
  Run `uv run python scripts/seed_templates.py` after first backend startup
  (or after restarting the backend post NEO-846), which calls init_db() and
  creates the table automatically.

Usage:
    uv run python scripts/seed_templates.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import asyncpg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# LaTeX preamble shared by all formal Czech legal submissions
# ---------------------------------------------------------------------------

_CZ_PREAMBLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper, top=2.5cm, bottom=3.5cm, left=3cm, right=2.5cm]{geometry}
\usepackage{fancyhdr}
\usepackage{parskip}
\usepackage{setspace}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\textit{Vzor --- zkontrolujte a~upravte před podáním. Tento dokument není právním poradenstvím.}}
\fancyfoot[R]{\small\thepage}
\setstretch{1.3}
"""

# ---------------------------------------------------------------------------
# Template 1 — Žaloba na neplatnost výpovědi z pracovního poměru
# ---------------------------------------------------------------------------

ZALOBA_NEPLATNOST_VYPOVEDI = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Žalobce:} {{zalobce_jmeno}}, nar. {{zalobce_datum_narozeni}}, bytem {{zalobce_adresa}}

\noindent\textbf{Žalovaný:} {{zalovany_nazev}}, IČO: {{zalovany_ico}}, se sídlem {{zalovany_adresa}}

\vspace{2em}

\begin{center}
{\large\textbf{Žaloba na určení neplatnosti výpovědi z pracovního poměru}}

\medskip
\textit{podáno dle § 72 zákona č. 262/2006 Sb., zákoník práce, ve znění pozdějších předpisů}
\end{center}

\vspace{1.5em}

\textbf{I.\ Žalobní petit}

\medskip

Žalobce navrhuje, aby soud vydal tento rozsudek:

\begin{quote}
\textit{{{petit}}}
\end{quote}

Žalobce dále navrhuje, aby soud uložil žalovanému povinnost nahradit žalobci náklady řízení.

\vspace{1em}

\textbf{II.\ Skutková tvrzení}

\medskip

Žalobce byl zaměstnancem žalovaného. Dne {{datum_vypovedi}} mu byla doručena výpověď z pracovního poměru s uvedením důvodu: {{duvod_vypovedi}}.

\vspace{1em}

\textbf{III.\ Právní posouzení}

\medskip

{{oduvodneni}}

\vspace{1em}

\textbf{IV.\ Důkazní návrhy}

\medskip

{{dukazy}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{zalobce_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Commercial / founder lifecycle templates (Templates 3–7, NEO-142)
# ---------------------------------------------------------------------------

NAJEMNI_SMLOUVA_PROSTORY_PODNIKANI = r"""
\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper, top=2.5cm, bottom=3.5cm, left=3cm, right=2.5cm]{geometry}
\usepackage{fancyhdr}
\usepackage{parskip}
\usepackage{setspace}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\textit{Vzor --- zkontrolujte a~upravte před podáním. Tento dokument není právním poradenstvím.}}
\fancyfoot[R]{\small\thepage}
\setstretch{1.3}

\begin{document}

\begin{center}
{\large\textbf{Nájemní smlouva --- prostory sloužící k podnikání}}
\medskip
\textit{uzavřena dle § 2302--2331 zákona č. 89/2012 Sb., občanský zákoník (OZ)}
\end{center}

\vspace{1.5em}

\textbf{I. Smluvní strany}

\medskip

\noindent \textbf{Pronajímatel:} {{pronajimatel_jmeno}}, IČO: {{pronajimatel_ico}}, sídlo: {{pronajimatel_adresa}}

\noindent \textbf{Nájemce:} {{najemce_jmeno}}, IČO: {{najemce_ico}}, sídlo: {{najemce_adresa}}

\vspace{1em}

\textbf{II. Předmět a účel nájmu}

\medskip

Předmětem nájmu jsou nebytové prostory umístěné na adrese: {{predmet_najmu_adresa}}.

Popis prostor: {{predmet_najmu_popis}}.

Výměra pronajímaných prostor: {{vymera}} m².

Prostory budou používány k účelu: {{ucel_najmu}}.

\vspace{1em}

\textbf{III. Doba nájmu}

\medskip

Nájem se sjednává na {{doba_najmu}}.

Počátek nájmu: {{datum_zacatku}}.

{{datum_konce}}

\vspace{1em}

\textbf{IV. Nájemné a platební podmínky}

\medskip

Měsíční nájemné činí {{najemne_mesicne}} Kč.

Kauce: {{kauce}} Kč.

\vspace{1em}

\textbf{V. Kauce}

\medskip

Kauce slouží k zajištění nároků pronajímatele z nájemní smlouvy.

\vspace{1em}

\textbf{VI. Práva a povinnosti}

\medskip

Nájemce je povinen užívat prostory v souladu s účelem nájmu a řádně udržovat pronajaté prostory.

\vspace{1em}

\textbf{VII. Skončení nájmu}

\medskip

Výpovědní doba činí {{vypovedni_doba}} a počíná běžet prvním dnem měsíce následujícího po doručení výpovědi.

\vspace{1em}

\textbf{VIII. Závěrečná ustanovení}

\medskip

Tato smlouva se řídí českým právním řádem. Změny smlouvy vyžadují písemnou formu.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\qquad\rule{8cm}{0.4pt}\\
\noindent\textit{Pronajímatel}\qquad\qquad\qquad\qquad\qquad\qquad\textit{Nájemce}\\
\noindent{{pronajimatel_jmeno}}\qquad\qquad\qquad\qquad\qquad\qquad{{najemce_jmeno}}

\end{document}

"""


SMLOUVA_O_MLCENLIVOSTI_NDA = r"""
\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper, top=2.5cm, bottom=3.5cm, left=3cm, right=2.5cm]{geometry}
\usepackage{fancyhdr}
\usepackage{parskip}
\usepackage{setspace}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\textit{Vzor --- zkontrolujte a~upravte před podáním. Tento dokument není právním poradenstvím.}}
\fancyfoot[R]{\small\thepage}
\setstretch{1.3}

\begin{document}

\begin{center}
{\large\textbf{Smlouva o mlčenlivosti (NDA)}}
\medskip
\textit{uzavřena dle § 1730, § 504 a § 2985 zákona č. 89/2012 Sb., občanský zákoník (OZ)}
\end{center}

\vspace{1.5em}

\textbf{I. Smluvní strany}

\medskip

\noindent \textbf{Strana A:} {{strana_a_jmeno}}, IČO: {{strana_a_ico}}, sídlo/bydliště: {{strana_a_adresa}}

\noindent \textbf{Strana B:} {{strana_b_jmeno}}, IČO: {{strana_b_ico}}, sídlo/bydliště: {{strana_b_adresa}}

\vspace{1em}

\textbf{II. Předmět a účel}

\medskip

Předmětem této smlouvy je závazek obou stran zachovávat mlčenlivost o důvěrných informacích, které si navzájem sdělí v souvislosti s: {{predmet_jednani}}.

\vspace{1em}

\textbf{III. Důvěrné informace}

\medskip

Za důvěrné informace se považují veškeré údaje, dokumenty, technické specifikace, obchodní plány a jiné skutečnosti, které: {{definice_duvernych_informaci}}.

\vspace{1em}

\textbf{IV. Závazek mlčenlivosti}

\medskip

Každá ze stran se zavazuje, že bez předchozího písemného souhlasu druhé strany nezpřístupní důvěrné informace třetím osobám a nepoužije je k jiným účelům, než je účel této smlouvy.

\vspace{1em}

\textbf{V. Doba trvání}

\medskip

Závazek mlčenlivosti trvá po dobu {{doba_mlcenlivosti}} od podpisu této smlouvy.

\vspace{1em}

\textbf{VI. Smluvní pokuta}

\medskip

Poruší-li některá ze stran závazek mlčenlivosti, uhradí druhé straně smluvní pokutu ve výši {{smluvni_pokuta}} za každé jednotlivé porušení.

\vspace{1em}

\textbf{VII. Závěrečná ustanovení}

\medskip

Tato smlouva se řídí českým právním řádem. Případné spory budou řešeny u příslušného soudu v České republice.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\qquad\rule{8cm}{0.4pt}\\
\noindent\textit{Strana A}\qquad\qquad\qquad\qquad\qquad\qquad\textit{Strana B}\\
\noindent{{strana_a_jmeno}}\qquad\qquad\qquad\qquad\qquad\qquad{{strana_b_jmeno}}

\end{document}

"""


SMLOUVA_PREVOD_PODILU_SRO = r"""
\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper, top=2.5cm, bottom=3.5cm, left=3cm, right=2.5cm]{geometry}
\usepackage{fancyhdr}
\usepackage{parskip}
\usepackage{setspace}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\textit{Vzor --- zkontrolujte a~upravte před podáním. Tento dokument není právním poradenstvím.}}
\fancyfoot[R]{\small\thepage}
\setstretch{1.3}

\begin{document}

\begin{center}
{\large\textbf{Smlouva o převodu podílu ve společnosti s ručením omezeným}}
\medskip
\textit{uzavřena dle § 207--209 zákona č. 90/2012 Sb., o obchodních korporacích (ZOK)}
\end{center}

\vspace{1.5em}

\textbf{I. Smluvní strany}

\medskip

\noindent \textbf{Převodce:} {{prevodce_jmeno}}, {{prevodce_rc_ico}}, bytem/sídlem: {{prevodce_adresa}}

\noindent \textbf{Nabyvatel:} {{nabyvatel_jmeno}}, {{nabyvatel_rc_ico}}, bytem/sídlem: {{nabyvatel_adresa}}

\vspace{1em}

\textbf{II. Předmět smlouvy a převáděný podíl}

\medskip

Předmětem této smlouvy je převod podílu v obchodní společnosti:

\noindent \textbf{Název:} {{nazev_spolecnosti}}

\noindent \textbf{Sídlo:} {{sidlo_spolecnosti}}

\noindent \textbf{IČO:} {{ico_spolecnosti}}

Převodce vlastnil podíl ve výši {{vyse_podilu_pred}} před převodem.

Převodce tímto převádí podíl ve výši {{vyse_prevadeneho_podilu}} na nabyvatele.

\vspace{1em}

\textbf{III. Cena a platební podmínky}

\medskip

Cena převodu činí {{cena_prevodu}} Kč.

\vspace{1em}

\textbf{IV. Účinnost převodu vůči společnosti}

\medskip

Převod podílu nabývá účinnosti vůči společnosti dnem doručení této smlouvy společnosti dle § 209 ZOK.

\vspace{1em}

\textbf{V. Prohlášení stran}

\medskip

Strana převodce prohlašuje, že podíl není zatížen žádnými právy třetích osob.

Strana nabyvatel prohlašuje, že byl seznámen se stavem společnosti a účetní závěrkou.

\vspace{1em}

\textbf{VI. Závěrečná ustanovení}

\medskip

Tato smlouva vyžaduje k platnosti úřední ověření podpisů (§ 209 ZOK).

Tato smlouva se řídí českým právním řádem.

\vspace{3em}

\noindent V~{{misto_uzavreni}} dne {{datum_uzavreni}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\qquad\rule{8cm}{0.4pt}\\
\noindent\textit{Převodce}\qquad\qquad\qquad\qquad\qquad\qquad\textit{Nabyvatel}\\
\noindent{{prevodce_jmeno}}\qquad\qquad\qquad\qquad\qquad\qquad{{nabyvatel_jmeno}}

\noindent\begin{small}Podpisy musí být úředně ověřeny dle § 209 ZOK.\end{small}

\end{document}

"""


SOUHLAS_ZPRACOVANI_OSOBNICH_UDAJU_GDPR = r"""
\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper, top=2.5cm, bottom=3.5cm, left=3cm, right=2.5cm]{geometry}
\usepackage{fancyhdr}
\usepackage{parskip}
\usepackage{setspace}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\textit{Vzor --- zkontrolujte a~upravte před podáním. Tento dokument není právním poradenstvím.}}
\fancyfoot[R]{\small\thepage}
\setstretch{1.3}

\begin{document}

\begin{center}
{\large\textbf{Souhlas se zpracováním osobních údajů}}
\medskip
\textit{dle nařízení (EU) 2016/679 (GDPR), čl. 6 odst. 1 písm. a) a čl. 13; zákon č. 110/2019 Sb.}
\end{center}

\vspace{1.5em}

\textbf{I. Správce}

\medskip

\noindent \textbf{Správce:} {{spravce_jmeno}}, IČO: {{spravce_ico}}, sídlo: {{spravce_adresa}}

\noindent Kontakt: {{spravce_kontakt}}

\vspace{1em}

\textbf{II. Subjekt údajů}

\medskip

\noindent \textbf{Subjekt:} {{subjekt_jmeno}}, bytem: {{subjekt_adresa}}

\vspace{1em}

\textbf{III. Účel a kategorie zpracování}

\medskip

Účel zpracování: {{ucel_zpracovani}}.

Kategorie zpracovávaných údajů: {{kategorie_udaju}}.

Právní základ: {{pravni_zaklad}}.

\vspace{1em}

\textbf{IV. Doba uchovávání}

\medskip

Osobní údaje budou uchovávány po dobu {{doba_uchovavani}}.

\vspace{1em}

\textbf{V. Práva subjektu}

\medskip

Subjekt údajů má právo:
\begin{itemize}
    \item na přístup ke svým osobním údajům (čl. 15 GDPR)
    \item na opravu nepřesných údajů (čl. 16 GDPR)
    \item na výmaz údajů (čl. 17 GDPR)
    \item na omezení zpracování (čl. 18 GDPR)
    \item vznést námitku proti zpracování (čl. 21 GDPR)
    \item na přenositelnost údajů (čl. 20 GDPR)
    \item kdykoli odvolat souhlas (bez vlivu na zákonnost zpracování před odvoláním)
\end{itemize}

\vspace{1em}

\textbf{VI. Příjemci údajů}

\medskip

Osobní údaje mohou být předány: {{prijemci_udaju}}.

\vspace{1em}

\textbf{VII. Závěrečná ustanovení}

\medskip

Tímto uděluji svůj svobodný, konkrétní, informovaný a jednoznačný souhlas se zpracováním mých osobních údajů.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_souhlasu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent\textit{Subjekt údajů}\\
\noindent{{subjekt_jmeno}}

\end{document}

"""


VYPOVED_PRACOVNIHO_POMERU_ZAMESTNAVATEL = r"""
\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper, top=2.5cm, bottom=3.5cm, left=3cm, right=2.5cm]{geometry}
\usepackage{fancyhdr}
\usepackage{parskip}
\usepackage{setspace}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\textit{Vzor --- zkontrolujte a~upravte před podáním. Tento dokument není právním poradenstvím.}}
\fancyfoot[R]{\small\thepage}
\setstretch{1.3}

\begin{document}

\begin{center}
{\large\textbf{Výpověď z pracovního poměru}}
\medskip
\textit{dle § 50--54 a § 52 zákona č. 262/2006 Sb., zákoník práce (ZP)}
\end{center}

\vspace{1.5em}

\textbf{I. Identifikace stran a pracovního poměru}

\medskip

\noindent \textbf{Zaměstnavatel:} {{zamestnavatel_jmeno}}, IČO: {{zamestnavatel_ico}}, sídlo: {{zamestnavatel_adresa}}

\noindent \textbf{Zaměstnanec:} {{zamestnanec_jmeno}}, nar. {{zamestnanec_datum_narozeni}}, bytem: {{zamestnanec_adresa}}

\noindent Pracovní pozice: {{pracovni_pozice}}

\noindent Datum uzavření pracovní smlouvy: {{datum_uzavreni_smlouvy}}

\vspace{1em}

\textbf{II. Výpověď a její důvod}

\medskip

Zaměstnavatel tímto dává zaměstnanci výpověď z pracovního poměru dle {{paragraf_vypovedi}}.

Důvod výpovědi: {{duvod_vypovedi}}.

\vspace{1em}

\textbf{III. Výpovědní doba}

\medskip

Výpovědní doba činí 2 měsíce a počíná běžet prvním dnem měsíce následujícího po doručení této výpovědi zaměstnanci, tj. od {{datum_doruceni}}.

\vspace{1em}

\textbf{IV. Poučení zaměstnance}

\medskip

Zaměstnanci náleží právo podat žalobu na neplatnost výpovědi u soudu do 2 měsíců od doručení této výpovědi, a to dle § 72 ZP.

\vspace{1em}

\textbf{V. Závěrečná ustanovení}

\medskip

Tato výpověď se řídí českým právním řádem.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent\textit{Zaměstnavatel}\\
\noindent{{zamestnavatel_jmeno}}

\noindent\begin{small}Doručeno zaměstnanci dne: {{datum_doruceni}}\end{small}

\end{document}

"""

# Template records
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

ZALOBA_NA_ZAPLACENI = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Žalobce:} {{zalobce_jmeno}}, bytem {{zalobce_adresa}}

\noindent\textbf{Žalovaný:} {{zalovany_jmeno}}, bytem/se sídlem {{zalovany_adresa}}

\vspace{2em}

\begin{center}
{\large\textbf{Žaloba na zaplacení}}

\medskip
\textit{podáno dle § 79 odst. 1 zákona č. 99/1963 Sb., občanský soudní řád}
\end{center}

\vspace{1.5em}

\textbf{I.\ Žalobní petit}

\medskip

Žalobce navrhuje, aby soud vydal tento rozsudek:

\begin{quote}
\textit{{{petit}}}
\end{quote}

Žalobce dále navrhuje, aby soud uložil žalovanému povinnost nahradit žalobci náklady řízení.

\vspace{1em}

\textbf{II.\ Skutková tvrzení}

\medskip

Žalobce je věřitelem pohledávky vůči žalovanému ve výši {{castka}} {{mena}}.
Pohledávka vznikla na základě: {{duvod_pohledavky}}.

\vspace{1em}

\textbf{III.\ Právní posouzení}

\medskip

{{oduvodneni}}

\vspace{1em}

\textbf{IV.\ Důkazní návrhy}

\medskip

{{dukazy}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{zalobce_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 3 — Návrh na vydání platebního rozkazu
# ---------------------------------------------------------------------------

NAVRH_PLATEBNI_ROZKAZ = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Navrhovatel:} {{navrhovatel_jmeno}}, bytem/se sídlem {{navrhovatel_adresa}}

\noindent\textbf{Odpůrce:} {{odpurce_jmeno}}, bytem/se sídlem {{odpurce_adresa}}

\vspace{2em}

\begin{center}
{\large\textbf{Návrh na vydání platebního rozkazu}}

\medskip
\textit{podáno dle § 172 zákona č. 99/1963 Sb., občanský soudní řád}
\end{center}

\vspace{1.5em}

\textbf{I.\ Petit}

\medskip

Navrhovatel navrhuje, aby soud vydal platební rozkaz, jímž uloží odpůrci povinnost zaplatit
navrhovateli částku {{castka}} {{mena}} spolu se zákonným úrokem z prodlení ode dne
splatnosti do zaplacení a náhradu nákladů řízení, vše do 15 dnů od doručení platebního rozkazu.

\vspace{1em}

\textbf{II.\ Odůvodnění}

\medskip

Pohledávka navrhovatele vznikla na základě: {{duvod_pohledavky}}.

{{oduvodneni}}

\vspace{1em}

\textbf{III.\ Důkazní návrhy}

\medskip

{{dukazy}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{navrhovatel_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 4 — Odvolání proti rozsudku
# ---------------------------------------------------------------------------

ODVOLANI_PROTI_ROZSUDKU = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{odvolaci_soud}}}

\noindent\textit{prostřednictvím}

\noindent\textbf{{{prvostupnovy_soud}}}

\vspace{2em}

\noindent\textbf{Odvolatel:} {{odvolatel_jmeno}}, bytem {{odvolatel_adresa}}

\noindent\textbf{Protistrana:} {{protiodvolatel_jmeno}}, bytem/se sídlem {{protiodvolatel_adresa}}

\noindent\textbf{Věc:} sp. zn. {{cislo_jednaci}}

\vspace{2em}

\begin{center}
{\large\textbf{Odvolání proti rozsudku}}

\medskip
\textit{rozsudek ze dne {{datum_rozsudku}}, sp.\ zn.\ {{cislo_jednaci}}}

\medskip
\textit{podáno dle § 201 a násl.\ zákona č. 99/1963 Sb., občanský soudní řád}
\end{center}

\vspace{1.5em}

\textbf{I.\ Odvolací petit}

\medskip

Odvolatel navrhuje, aby odvolací soud napadený rozsudek:

\begin{quote}
\textit{{{petit_odvolani}}}
\end{quote}

\vspace{1em}

\textbf{II.\ Odvolací důvody}

\medskip

Odvolatel podává odvolání z těchto důvodů:

{{oduvodneni}}

\vspace{1em}

\textbf{III.\ Důkazní návrhy}

\medskip

{{dukazy}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{odvolatel_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 5 — Odpor proti platebnímu rozkazu
# ---------------------------------------------------------------------------

ODPOR_PLATEBNI_ROZKAZ = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Odpůrce:} {{odpurce_jmeno}}, bytem {{odpurce_adresa}}

\noindent\textbf{Navrhovatel:} {{navrhovatel_jmeno}}

\noindent\textbf{Věc:} Platební rozkaz sp. zn. {{cislo_jednaci_rozkazu}}

\vspace{2em}

\begin{center}
{\large\textbf{Odpor proti platebnímu rozkazu}}

\medskip
\textit{platební rozkaz doručen dne {{datum_doruceni}}}

\medskip
\textit{podáno dle § 172 odst. 3 zákona č. 99/1963 Sb., občanský soudní řád}
\end{center}

\vspace{1.5em}

Odpůrce tímto podává ve lhůtě odpor proti shora uvedenému platebnímu rozkazu a navrhuje,
aby soud platební rozkaz zrušil a věc projednal v řádném soudním řízení.

\vspace{1em}

\textbf{I.\ Odůvodnění odporu}

\medskip

{{oduvodneni}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{odpurce_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 6 — Stížnost na postup správního orgánu
# ---------------------------------------------------------------------------

STIZNOST_SPRAVNI_ORGAN = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{nadrizen_organ}}}

\vspace{2em}

\noindent\textbf{Stěžovatel:} {{stizovatel_jmeno}}, bytem {{stizovatel_adresa}}

\noindent\textbf{Stížnost na postup:} {{spravni_organ}}, {{spravni_organ_adresa}}

\vspace{2em}

\begin{center}
{\large\textbf{Stížnost na postup správního orgánu}}

\medskip
\textit{podáno dle § 175 zákona č. 500/2004 Sb., správní řád}
\end{center}

\vspace{1.5em}

\textbf{I.\ Předmět stížnosti}

\medskip

{{predmet_stiznosti}}

\vspace{1em}

\textbf{II.\ Popis pochybení}

\medskip

{{popis_pochybeni}}

\vspace{1em}

\textbf{III.\ Návrh na opatření}

\medskip

Stěžovatel navrhuje, aby nadřízený správní orgán:

{{navrh_opatreni}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{stizovatel_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 7 — Návrh na rozvod manželství
# ---------------------------------------------------------------------------

NAVRH_ROZVOD = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Navrhovatel:} {{navrhovatel_jmeno}}, nar. {{navrhovatel_datum_narozeni}}, bytem {{navrhovatel_adresa}}

\noindent\textbf{Odpůrce:} {{odpurce_jmeno}}, nar. {{odpurce_datum_narozeni}}, bytem {{odpurce_adresa}}

\vspace{2em}

\begin{center}
{\large\textbf{Návrh na rozvod manželství}}

\medskip
\textit{podáno dle § 755 a násl.\ zákona č. 89/2012 Sb., občanský zákoník}
\end{center}

\vspace{1.5em}

\textbf{I.\ Petit}

\medskip

Navrhovatel navrhuje, aby soud vydal tento rozsudek:

\begin{quote}
\textit{{{petit}}}
\end{quote}

\vspace{1em}

\textbf{II.\ Skutková tvrzení}

\medskip

Navrhovatel a odpůrce uzavřeli manželství dne {{datum_svadby}} v~{{misto_svadby}}.

\noindent\textbf{Nezletilé děti:} {{deti}}

\vspace{1em}

\textbf{III.\ Odůvodnění}

\medskip

{{oduvodneni}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{navrhovatel_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 8 — Plná moc obecná
# ---------------------------------------------------------------------------

PLNA_MOC_OBECNA = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\begin{center}
{\large\textbf{Plná moc}}
\end{center}

\vspace{2em}

\noindent Já, níže podepsaný/á

\noindent\textbf{{{zmocnitel_jmeno}}}\\
narozen/a: {{zmocnitel_datum_narozeni}}\\
bytem: {{zmocnitel_adresa}}

\vspace{1em}

\noindent (dále jen „zmocnitel")

\vspace{1em}

\noindent tímto uděluji plnou moc

\vspace{1em}

\noindent\textbf{{{zmocnenec_jmeno}}}\\
bytem/se sídlem: {{zmocnenec_adresa}}

\vspace{1em}

\noindent (dále jen „zmocněnec")

\vspace{1em}

\noindent k tomuto zastupování a jednání:

\vspace{0.5em}

\noindent {{rozsah_plne_moci}}

\vspace{2em}

\noindent Zmocněnec je oprávněn udělit substituční plnou moc pouze s mým výslovným souhlasem,
pokud to povaha zastupování nevylučuje.

\vspace{2em}

\noindent Tato plná moc je platná ode dne podpisu a trvá do jejího písemného odvolání.

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{zmocnitel_jmeno}}\\
\textit{zmocnitel}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 9 — Vlastní dokument (volný text)
# ---------------------------------------------------------------------------

VLASTNI_DOKUMENT = (
    r"""\documentclass[12pt,a4paper]{article}
\usepackage{fontspec}
\setmainfont{TeX Gyre Termes}
\usepackage[a4paper, top=2.5cm, bottom=3.5cm, left=3cm, right=2.5cm]{geometry}
\usepackage{fancyhdr}
\usepackage{parskip}
\usepackage{setspace}
\pagestyle{fancy}
\fancyhf{}
\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\textit{Vzor --- zkontrolujte a~upravte před podáním. Tento dokument není právním poradenstvím.}}
\fancyfoot[R]{\small\thepage}
\setstretch{1.3}

\begin{document}

\begin{center}
{\large\textbf{{{nazev}}}}
\end{center}

\vspace{2em}

{{obsah}}

\vspace{3em}

\noindent V~{{misto}} dne {{datum}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 9 — Smlouva o dílo
# ---------------------------------------------------------------------------

SMLOUVA_O_DILO = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\begin{center}
{\large\textbf{Smlouva o dílo}}

\medskip
\textit{uzavřená dle § 2586 a násl. zákona č. 89/2012 Sb., občanský zákoník, ve znění pozdějších předpisů}
\end{center}

\vspace{2em}

\textbf{I.\ Smluvní strany}

\medskip

\noindent\textbf{Zhotovitel:} {{zhotovitel_jmeno}}\\
Sídlo / bydliště: {{zhotovitel_adresa}}\\
IČO: {{zhotovitel_ico}}

\medskip

\noindent\textbf{Objednatel:} {{objednatel_jmeno}}\\
Sídlo / bydliště: {{objednatel_adresa}}

\vspace{1.5em}

\textbf{II.\ Předmět díla}

\medskip

Zhotovitel se zavazuje provést pro objednatele následující dílo:

\medskip
\begin{quote}
\textit{{{predmet_dila}}}
\end{quote}

\medskip
Místem plnění je: {{misto_plneni}}.

\vspace{1em}

\textbf{III.\ Cena díla a platební podmínky}

\medskip

Smluvní strany sjednávají cenu díla ve výši \textbf{{{cena}}}. Cena je splatná po předání a převzetí díla bez vad, nestanoví-li příloha jinak.

\vspace{1em}

\textbf{IV.\ Termín plnění}

\medskip

Zhotovitel se zavazuje předat dokončené dílo objednateli nejpozději dne \textbf{{{termin_dokonceni}}}.

\vspace{1em}

\textbf{V.\ Předání a převzetí díla}

\medskip

Dílo bude předáno písemným protokolem podepsaným oběma smluvními stranami. Objednatel je oprávněn odmítnout převzetí díla, které má vady bránící jeho řádnému užívání.

\vspace{1em}

\textbf{VI.\ Odpovědnost za vady}

\medskip

Zhotovitel odpovídá za vady díla dle § 2615 a násl. OZ. Záruční doba činí 24~měsíců ode dne předání díla, nebylo-li sjednáno jinak.

\vspace{1em}

\textbf{VII.\ Závěrečná ustanovení}

\medskip

Tato smlouva se řídí právním řádem České republiky. Případné spory budou řešeny příslušnými soudy ČR. Smlouva nabývá účinnosti dnem podpisu oběma smluvními stranami.

\vspace{3em}

\noindent V~{{misto_plneni}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\begin{tabular}{p{7cm}p{7cm}}
\rule{6cm}{0.4pt} & \rule{6cm}{0.4pt} \\
\textit{Zhotovitel} & \textit{Objednatel} \\
{{zhotovitel_jmeno}} & {{objednatel_jmeno}}
\end{tabular}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 10 — Zakladatelská listina / Společenská smlouva s.r.o.
# ---------------------------------------------------------------------------

SPOLECENSKA_SMLOUVA_SRO = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\begin{center}
{\large\textbf{Zakladatelská listina / Společenská smlouva}}

\medskip
\textit{společnosti s ručením omezeným}

\medskip
\textit{uzavřená dle § 146 a násl. zákona č. 90/2012 Sb., zákon o obchodních korporacích}
\end{center}

\vspace{2em}

\textbf{I.\ Zakladatel(é)}

\medskip

\noindent Jméno: \textbf{{{zakladatel_jmeno}}}\\
Adresa: {{zakladatel_adresa}}\\
RČ / IČO: {{zakladatel_rc_ico}}

\vspace{1.5em}

\textbf{II.\ Firma a sídlo společnosti}

\medskip

\noindent\textbf{Obchodní firma:} {{nazev_spolecnosti}}\\
\textbf{Sídlo:} {{sidlo}}

\vspace{1em}

\textbf{III.\ Předmět podnikání}

\medskip

Předmětem podnikání společnosti je:

\begin{quote}
\textit{{{predmet_podnikani}}}
\end{quote}

\vspace{1em}

\textbf{IV.\ Základní kapitál a vklady}

\medskip

Základní kapitál společnosti tvoří peněžitý vklad zakladatele ve výši \textbf{{{vklad}}}~Kč. Vklad bude splacen \textbf{{{splaceni}}}.

Minimální výše základního kapitálu s.r.o.\ činí 1~Kč (§ 142 ZOK).

\vspace{1em}

\textbf{V.\ Jednatelé}

\medskip

\noindent Jednatelem společnosti se jmenuje:

\noindent\textbf{{{jednatel_jmeno}}}\\
Adresa: {{jednatel_adresa}}

Jednatel je oprávněn jednat jménem společnosti samostatně ve všech věcech.

\vspace{1em}

\textbf{VI.\ Podíl a práva společníka}

\medskip

Zakladatel vlastní obchodní podíl odpovídající jeho vkladu ve výši \textbf{{{vklad}}}~Kč, tj.\ 100~\% základního kapitálu.

\vspace{1em}

\textbf{VII.\ Závěrečná ustanovení}

\medskip

Tato zakladatelská listina / společenská smlouva se řídí zákonem č. 90/2012 Sb. (ZOK) a zákonem č. 89/2012 Sb. (OZ). Společnost vzniká zápisem do obchodního rejstříku.

\vspace{3em}

\noindent V~{{sidlo}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent\textit{Zakladatel}\\
\noindent{{zakladatel_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Hiring templates (NEO-172) — pracovní smlouva, DPP, DPČ, konkurenční doložka
# ---------------------------------------------------------------------------

PRACOVNI_SMLOUVA = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\begin{center}
{\large\textbf{Pracovní smlouva}}

\medskip
\textit{uzavřená dle § 34, § 35, § 38 a § 305 zákona č. 262/2006 Sb., zákoník práce (ZP)}
\end{center}

\vspace{2em}

\textbf{I.\ Smluvní strany}

\medskip

\noindent\textbf{Zaměstnavatel:} {{zamestnavatel_jmeno}}, IČO: {{zamestnavatel_ico}}, sídlo: {{zamestnavatel_sidlo}}, zastoupený: {{zamestnavatel_organ}}

\medskip

\noindent\textbf{Zaměstnanec:} {{zamestnanec_jmeno}}, nar. {{zamestnanec_datum_narozeni}}, bytem: {{zamestnanec_bydliste}}

\vspace{1.5em}

\textbf{II.\ Druh práce, místo výkonu a den nástupu}

\medskip

Zaměstnanec nastupuje do pracovního poměru na druh práce: \textbf{{{druh_prace}}}.

Místem výkonu práce je: {{misto_vykonu_prace}}.

Pracovní poměr vzniká dnem nástupu do práce: \textbf{{{datum_nastupu}}}.

\vspace{1em}

\textbf{III.\ Mzda}

\medskip

Zaměstnanci náleží základní mzda ve výši \textbf{{{mzda_zakladni}}} Kč hrubého měsíčně.

{{mzda_bonus}}

Mzda je splatná v měsíci následujícím po měsíci, ve kterém vznikl nárok na mzdu.

\vspace{1em}

\textbf{IV.\ Pracovní doba}

\medskip

Pracovní doba je sjednána jako: {{pracovni_doba}}.

Stanovená týdenní pracovní doba činí 40 hodin.

\vspace{1em}

\textbf{V.\ Zkušební doba}

\medskip

Zkušební doba se sjednává v délce \textbf{{{zkusebni_doba}}} (§ 35 ZP; max. 3 měsíce, resp. 6 měsíců pro vedoucí zaměstnance).

\vspace{1em}

\textbf{VI.\ Dovolená}

\medskip

Zaměstnanci náleží dovolená v délce {{delka_dovolene}} týdnů za kalendářní rok (§ 212 a násl. ZP).

\vspace{1em}

\textbf{VII.\ Výpovědní doba}

\medskip

Výpovědní doba činí {{vypovedni_doba}} (§ 51 ZP) a počíná běžet prvním dnem měsíce následujícího po doručení výpovědi.

\vspace{1em}

\textbf{VIII.\ Závěrečná ustanovení}

\medskip

Zaměstnanec byl poučen o předpisech k zajištění bezpečnosti a ochrany zdraví při práci (BOZP) a byl seznámen se zpracováním osobních údajů zaměstnavatelem v souladu s GDPR.

Tato smlouva se řídí zákonem č. 262/2006 Sb., zákoník práce. Změny smlouvy vyžadují písemnou formu.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\begin{tabular}{p{7cm}p{7cm}}
\rule{6cm}{0.4pt} & \rule{6cm}{0.4pt} \\
\textit{Zaměstnavatel} & \textit{Zaměstnanec} \\
{{zamestnavatel_jmeno}} & {{zamestnanec_jmeno}}
\end{tabular}

\end{document}
"""
)

DOHODA_O_PROVEDENI_PRACE_DPP = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\begin{center}
{\large\textbf{Dohoda o provedení práce}}

\medskip
\textit{uzavřená dle § 75 zákona č. 262/2006 Sb., zákoník práce (ZP)}
\end{center}

\vspace{2em}

\textbf{I.\ Smluvní strany}

\medskip

\noindent\textbf{Zaměstnavatel:} {{zamestnavatel_jmeno}}, IČO: {{zamestnavatel_ico}}, sídlo: {{zamestnavatel_sidlo}}

\medskip

\noindent\textbf{Pracovník:} {{pracovnik_jmeno}}, nar. {{pracovnik_datum_narozeni}}, bytem: {{pracovnik_bydliste}}

\vspace{1.5em}

\textbf{II.\ Předmět dohody}

\medskip

Pracovník se zavazuje vykonat pro zaměstnavatele tuto práci: \textbf{{{predmet_dohody}}}.

Místo provedení: {{misto_provedeni}}.

\vspace{1em}

\textbf{III.\ Rozsah práce a termín provedení}

\medskip

Sjednaný rozsah práce: \textbf{{{rozsah_prace}}} hodin.

\textit{Upozornění: rozsah práce na základě DPP nesmí u téhož zaměstnavatele přesáhnout 300 hodin v kalendářním roce (§ 75 odst. 2 ZP).}

Termín provedení (splnění dohody): {{doba_provedeni}}.

\vspace{1em}

\textbf{IV.\ Odměna}

\medskip

Za řádně provedenou práci náleží pracovníkovi odměna ve výši \textbf{{{odmena}}} Kč.

\textit{Upozornění: příjem z DPP do výše 10 000 Kč měsíčně u jednoho zaměstnavatele nepodléhá odvodu sociálního a zdravotního pojištění (§ 6 zákona č. 586/1992 Sb., ZDP) --- platné pro rok 2026, hodnota je každoročně indexována.}

\vspace{1em}

\textbf{V.\ Závěrečná ustanovení}

\medskip

Tato dohoda se řídí zákonem č. 262/2006 Sb., zákoník práce. Změny vyžadují písemnou formu.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\begin{tabular}{p{7cm}p{7cm}}
\rule{6cm}{0.4pt} & \rule{6cm}{0.4pt} \\
\textit{Zaměstnavatel} & \textit{Pracovník} \\
{{zamestnavatel_jmeno}} & {{pracovnik_jmeno}}
\end{tabular}

\end{document}
"""
)

DOHODA_O_PRACOVNI_CINNOSTI_DPC = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\begin{center}
{\large\textbf{Dohoda o pracovní činnosti}}

\medskip
\textit{uzavřená dle § 76 zákona č. 262/2006 Sb., zákoník práce (ZP)}
\end{center}

\vspace{2em}

\textbf{I.\ Smluvní strany}

\medskip

\noindent\textbf{Zaměstnavatel:} {{zamestnavatel_jmeno}}, IČO: {{zamestnavatel_ico}}, sídlo: {{zamestnavatel_sidlo}}

\medskip

\noindent\textbf{Pracovník:} {{pracovnik_jmeno}}, nar. {{pracovnik_datum_narozeni}}, bytem: {{pracovnik_bydliste}}

\vspace{1.5em}

\textbf{II.\ Druh sjednané práce}

\medskip

Pracovník se zavazuje vykonávat pro zaměstnavatele práci druhu: \textbf{{{druh_prace}}}.

\vspace{1em}

\textbf{III.\ Rozsah pracovní doby}

\medskip

Sjednaný rozsah pracovní doby: \textbf{{{rozsah_pracovni_doby}}}.

\textit{Upozornění: rozsah práce na základě DPČ nesmí v průměru přesáhnout polovinu stanovené týdenní pracovní doby (§ 76 odst. 2 ZP). Průměr se posuzuje za celou dobu, na niž je DPČ sjednána, nejdéle za 52 týdnů.}

\vspace{1em}

\textbf{IV.\ Doba trvání dohody}

\medskip

Dohoda se uzavírá na dobu: \textbf{{{doba_trvani}}}.

\vspace{1em}

\textbf{V.\ Odměna}

\medskip

Za výkon práce náleží pracovníkovi odměna ve výši \textbf{{{odmena}}} Kč měsíčně.

\textit{Upozornění: odměna z DPČ podléhá odvodu sociálního a zdravotního pojištění při překročení rozhodného příjmu 4 500 Kč měsíčně (platné pro rok 2026 --- hodnota je každoročně indexována).}

\vspace{1em}

\textbf{VI.\ Výpovědní doba}

\medskip

Výpovědní doba činí {{vypovedni_doba}} (§ 76 odst. 5 ZP; nestanoví-li dohoda jinak, platí 15 dní).

\vspace{1em}

\textbf{VII.\ Závěrečná ustanovení}

\medskip

Tato dohoda se řídí zákonem č. 262/2006 Sb., zákoník práce. Změny vyžadují písemnou formu.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\begin{tabular}{p{7cm}p{7cm}}
\rule{6cm}{0.4pt} & \rule{6cm}{0.4pt} \\
\textit{Zaměstnavatel} & \textit{Pracovník} \\
{{zamestnavatel_jmeno}} & {{pracovnik_jmeno}}
\end{tabular}

\end{document}
"""
)

KONKURENCNI_DOLOZKA = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\begin{center}
{\large\textbf{Konkurenční doložka}}

\medskip
\textit{uzavřená dle § 310 zákona č. 262/2006 Sb., zákoník práce (ZP)}
\end{center}

\vspace{2em}

\textbf{I.\ Smluvní strany}

\medskip

\noindent\textbf{Zaměstnavatel:} {{zamestnavatel_jmeno}}, IČO: {{zamestnavatel_ico}}, sídlo: {{zamestnavatel_sidlo}}

\medskip

\noindent\textbf{Zaměstnanec:} {{zamestnanec_jmeno}}, nar. {{zamestnanec_datum_narozeni}}, bytem: {{zamestnanec_bydliste}}

\medskip

\noindent Tato doložka je součástí nebo dodatkem k pracovní smlouvě ze dne {{reference_pracovni_smlouvy}}.

\vspace{1.5em}

\textbf{II.\ Závazek zaměstnance}

\medskip

Po skončení pracovního poměru se zaměstnanec zavazuje zdržet se výkonu výdělečné činnosti, která by byla shodná s předmětem činnosti zaměstnavatele nebo která by měla vůči zaměstnavateli soutěžní povahu:

\begin{itemize}
    \item \textbf{Věcný rozsah:} {{vecny_rozsah}}
    \item \textbf{Geografický rozsah:} {{geograficky_rozsah}}
\end{itemize}

\vspace{1em}

\textbf{III.\ Doba trvání závazku}

\medskip

Závazek trvá po dobu \textbf{{{doba_trvani}}} po skončení pracovního poměru (§ 310 odst. 1 ZP; max. 1 rok).

\vspace{1em}

\textbf{IV.\ Peněžité vyrovnání}

\medskip

Zaměstnavatel se zavazuje poskytnout zaměstnanci za každý měsíc plnění závazku peněžité vyrovnání ve výši \textbf{{{penezite_vyrovnani}}} Kč (§ 310 odst. 1 ZP; musí být nejméně polovina průměrného měsíčního výdělku za každý měsíc plnění závazku).

\medskip

\noindent\textbf{\textit{Upozornění: Konkurenční doložka bez sjednaného peněžitého vyrovnání minimálně ve výši poloviny průměrného měsíčního výdělku za každý měsíc plnění závazku je neplatná (§ 310 odst. 1 ZP).}}

\vspace{1em}

\textbf{V.\ Smluvní pokuta}

\medskip

Poruší-li zaměstnanec závazek sjednaný v čl. II, je povinen zaplatit zaměstnavateli smluvní pokutu ve výši \textbf{{{smluvni_pokuta}}} Kč (§ 310 odst. 3 ZP; pokuta musí být přiměřená). Zaplacením smluvní pokuty závazek zaměstnance zaniká.

\vspace{1em}

\textbf{VI.\ Závěrečná ustanovení}

\medskip

Zaměstnavatel může od konkurenční doložky odstoupit, dokud pracovní poměr trvá. Zaměstnanec může od doložky odstoupit, nevyplatí-li zaměstnavatel peněžité vyrovnání do 15 dnů po jeho splatnosti (§ 310 odst. 4 ZP).

Tato doložka se řídí zákonem č. 262/2006 Sb., zákoník práce. Změny vyžadují písemnou formu.

\vspace{3em}

\noindent V~{{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\begin{tabular}{p{7cm}p{7cm}}
\rule{6cm}{0.4pt} & \rule{6cm}{0.4pt} \\
\textit{Zaměstnavatel} & \textit{Zaměstnanec} \\
{{zamestnavatel_jmeno}} & {{zamestnanec_jmeno}}
\end{tabular}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Czech tax templates (NEO-169)
# ---------------------------------------------------------------------------

ODVOLANI_PROTI_ROZHODNUTI_SPRAVCE_DANE = (
    _CZ_PREAMBLE + r"""
\begin{document}

\noindent\textbf{{{financni_urad}}}

\vspace{1em}

\noindent\textbf{Odvolatel:} {{dan_subjekt_jmeno}}, {{dan_subjekt_adresa}}, IČO/DIČ: {{dan_subjekt_ico_dic}}

\vspace{2em}

\begin{center}
{\large\textbf{Odvolání proti rozhodnutí správce daně}}
\medskip
\textit{podáno dle § 109 a násl. zákona č. 280/2009 Sb., daňový řád, ve znění pozdějších předpisů}
\end{center}

\vspace{1.5em}

\textbf{I.\ Identifikace napadeného rozhodnutí}

Odvolávám se proti rozhodnutí {{financni_urad}} ze dne {{datum_doruceni_rozhodnuti}},
č.\ j.\ {{cislo_jednaci_napadeneho_rozhodnuti}}, které mi bylo doručeno dne {{datum_doruceni_rozhodnuti}}.

Napadené výroky: {{napadene_vyroky}}

\vspace{1em}

\textbf{II.\ Odvolací důvody}

{{odvolaci_duvody}}

\vspace{1em}

\textbf{III.\ Petit}

Na základě výše uvedeného navrhuji, aby odvolací orgán:

{{petit}}

\vspace{1em}

\textbf{IV.\ Závěr}

Toto odvolání podávám v zákonné lhůtě 30 dnů ode dne doručení napadeného rozhodnutí (§ 109 odst.\ 2 DŘ).

\vspace{2em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{dan_subjekt_jmeno}}

\end{document}
"""
)

ZADOST_O_POSECKANI_UHRADY_DANE = (
    _CZ_PREAMBLE + r"""
\begin{document}

\noindent\textbf{{{financni_urad}}}

\vspace{1em}

\noindent\textbf{Žadatel:} {{dan_subjekt_jmeno}}, {{dan_subjekt_adresa}}, IČO/DIČ: {{dan_subjekt_ico_dic}}

\vspace{2em}

\begin{center}
{\large\textbf{Žádost o posečkání úhrady daně}}
\medskip
\textit{podána dle § 156 zákona č. 280/2009 Sb., daňový řád, ve znění pozdějších předpisů}
\end{center}

\vspace{1.5em}

\textbf{I.\ Předmět žádosti}

Žádám o posečkání úhrady daně: {{dan_a_obdobi}}

Dlužná částka: {{castka_dane}} Kč

Požadovaný termín úhrady: {{pozadovany_termin_uhrady}}

\vspace{1em}

\textbf{II.\ Odůvodnění žádosti}

{{oduvodneni_zadosti}}

\vspace{1em}

\textbf{III.\ Přílohy}

{{prilohy}}

\vspace{1em}

\textbf{IV.\ Závěr}

Prohlašuji, že všechny uvedené skutečnosti jsou pravdivé a úplné. Zavazuji se splnit daňovou povinnost
v požadovaném termínu a bezodkladně oznámit správci daně změny, které by mohly mít vliv na posečkání.

\vspace{2em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{dan_subjekt_jmeno}}

\end{document}
"""
)

ZADOST_O_VRACENI_PREPLATKU_NA_DANI = (
    _CZ_PREAMBLE + r"""
\begin{document}

\noindent\textbf{{{financni_urad}}}

\vspace{1em}

\noindent\textbf{Žadatel:} {{dan_subjekt_jmeno}}, {{dan_subjekt_adresa}}, IČO/DIČ: {{dan_subjekt_ico_dic}}

\vspace{2em}

\begin{center}
{\large\textbf{Žádost o vrácení přeplatku na dani}}
\medskip
\textit{podána dle § 155 zákona č. 280/2009 Sb., daňový řád, ve znění pozdějších předpisů}
\end{center}

\vspace{1.5em}

\textbf{I.\ Předmět žádosti}

Žádám o vrácení přeplatku na dani: {{dan_a_obdobi}}

Výše přeplatku: {{castka_preplatku}} Kč

\vspace{1em}

\textbf{II.\ Bankovní účet pro vrácení}

Přeplatek prosím vraťte na bankovní účet č.\ {{cislo_uctu_pro_vraceni}}.

\vspace{1em}

\textbf{III.\ Závěr}

Prohlašuji, že přeplatek vzniklý na výše uvedené dani dosud nebyl vrácen ani použit na úhradu jiných
daňových povinností. Žádám o jeho vrácení bez zbytečného odkladu v souladu s § 155 odst.\ 5 DŘ.

\vspace{2em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{dan_subjekt_jmeno}}

\end{document}
"""
)

VYJADRENI_K_VYZVE_K_ODSTRANENI_POCHYBNOSTI = (
    _CZ_PREAMBLE + r"""
\begin{document}

\noindent\textbf{{{financni_urad}}}

\vspace{1em}

\noindent\textbf{Daňový subjekt:} {{dan_subjekt_jmeno}}, {{dan_subjekt_adresa}}, IČO/DIČ: {{dan_subjekt_ico_dic}}

\vspace{2em}

\begin{center}
{\large\textbf{Vyjádření k výzvě k odstranění pochybností}}
\medskip
\textit{podáno dle § 89 a § 92 zákona č. 280/2009 Sb., daňový řád, ve znění pozdějších předpisů}
\end{center}

\vspace{1.5em}

\textbf{I.\ Identifikace výzvy}

Reaguji na výzvu {{financni_urad}} č.\ j.\ {{cislo_jednaci_vyzvy}}, doručenou dne {{datum_doruceni_vyzvy}},
týkající se daňového období: {{dotcene_obdobi}}.

\vspace{1em}

\textbf{II.\ Vyjádření k pochybnostem správce daně}

{{vyjadreni_k_pochybnostem}}

\vspace{1em}

\textbf{III.\ Předkládané důkazy a doklady}

{{predkladane_dukazy}}

\vspace{1em}

\textbf{IV.\ Závěr}

Jsem přesvědčen/a, že výše uvedené skutečnosti a důkazy pochybnosti správce daně odstraňují.
Prohlašuji, že všechna tvrzení jsou pravdivá a předložené doklady jsou autentické.

\vspace{2em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{dan_subjekt_jmeno}}

\end{document}
"""
)

PRIHLASKA_K_REGISTRACI_DPH = (
    _CZ_PREAMBLE + r"""
\begin{document}

\noindent\textbf{{{financni_urad}}}

\vspace{1em}

\noindent\textbf{Žadatel:} {{dan_subjekt_jmeno}}, {{dan_subjekt_adresa}}, IČO/DIČ: {{dan_subjekt_ico_dic}}

\vspace{2em}

\begin{center}
{\large\textbf{Přihláška k registraci k dani z přidané hodnoty}}
\medskip
\textit{podána dle § 94a zákona č. 235/2004 Sb., o dani z přidané hodnoty, ve znění pozdějších předpisů}
\end{center}

\vspace{1.5em}

\textbf{I.\ Identifikace žadatele}

Typ subjektu: {{dan_subjekt_typ}}

\vspace{1em}

\textbf{II.\ Důvod registrace}

{{duvod_registrace}}

Datum zahájení ekonomické činnosti: {{datum_zahajeni_ekon_cinnosti}}

Předpokládaný obrat za 12 po sobě jdoucích měsíců: {{predpoklad_obratu}} Kč

\vspace{1em}

\textbf{III.\ Bankovní účty používané pro ekonomickou činnost}

{{bankovni_ucty}}

\vspace{1em}

\textbf{IV.\ Čestné prohlášení}

Prohlašuji, že veškeré údaje uvedené v této přihlášce jsou správné a úplné. Zavazuji se neprodleně
oznámit správci daně veškeré změny rozhodných skutečností (§ 127 DŘ).

\vspace{2em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{dan_subjekt_jmeno}}

\end{document}
"""
)

OZNAMENI_UKONCENI_SAMOSTATNE_VYDELECNE_CINNOSTI = (
    _CZ_PREAMBLE + r"""
\begin{document}

\noindent\textbf{Příslušné úřady dle okruhu oznámení}

\vspace{1em}

\noindent\textbf{Oznamovatel:} {{dan_subjekt_jmeno}}, {{dan_subjekt_adresa}}, IČO/DIČ: {{dan_subjekt_ico_dic}}

\vspace{2em}

\begin{center}
{\large\textbf{Oznámení o ukončení samostatné výdělečné činnosti}}
\medskip
\textit{podáno dle zákona č. 589/1992 Sb. a zákona č. 48/1997 Sb., ve znění pozdějších předpisů}
\end{center}

\vspace{1.5em}

\textbf{I.\ Předmět oznámení}

Oznamuji ukončení samostatné výdělečné činnosti ke dni: \textbf{{{datum_ukonceni}}}

Okruh oznámení: {{okruh_oznameni}}

\vspace{1em}

\textbf{II.\ Sociální pojištění}

{{vc_socialniho_pojisteni}}

\vspace{1em}

\textbf{III.\ Zdravotní pojištění}

{{vc_zdravotniho_pojisteni}}

\vspace{1em}

\textbf{IV.\ Závěr}

Prohlašuji, že veškeré uvedené informace jsou pravdivé. Souhlasím s provedením případného
vyúčtování pojistného a závazků vyplývajících z ukončení výdělečné činnosti.

\vspace{2em}

\noindent V~{{misto}} dne {{datum}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
\noindent{}{{dan_subjekt_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template records
# ---------------------------------------------------------------------------

TEMPLATES: list[dict] = [
    {
        "slug": "zaloba_neplatnost_vypovedi",
        "name": "Žaloba na neplatnost výpovědi z pracovního poměru",
        "jurisdiction": "CZ",
        "category": "labor",
        "latex_template": ZALOBA_NEPLATNOST_VYPOVEDI,
        "required_fields": [
            "soud",
            "zalobce_jmeno",
            "zalobce_adresa",
            "zalobce_datum_narozeni",
            "zalovany_nazev",
            "zalovany_adresa",
            "zalovany_ico",
            "datum_vypovedi",
            "duvod_vypovedi",
            "petit",
            "oduvodneni",
            "dukazy",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "soud": "Název a adresa příslušného soudu",
            "zalobce_jmeno": "Jméno a příjmení žalobce",
            "zalobce_adresa": "Trvalé bydliště žalobce",
            "zalobce_datum_narozeni": "Datum narození žalobce",
            "zalovany_nazev": "Obchodní firma nebo název žalovaného zaměstnavatele",
            "zalovany_adresa": "Sídlo žalovaného",
            "zalovany_ico": "IČO žalovaného zaměstnavatele",
            "datum_vypovedi": "Datum doručení výpovědi žalobci",
            "duvod_vypovedi": "Důvod výpovědi uvedený žalovaným",
            "petit": "Žalobní petit — čeho se žalobce domáhá",
            "oduvodneni": "Právní a skutkové odůvodnění žaloby s citacemi zákonů a judikatury",
            "dukazy": "Seznam důkazních prostředků (listinné důkazy, svědci apod.)",
            "datum": "Datum podání žaloby",
            "misto": "Místo podání žaloby",
        },
        "description": (
            "Žaloba na určení neplatnosti výpovědi z pracovního poměru podané zaměstnavatelem. "
            "Vhodné pro případy výpovědi bez zákonného důvodu nebo s vadou formy."
        ),
    },
    {
        "slug": "zaloba_na_zaplaceni",
        "name": "Žaloba na zaplacení",
        "jurisdiction": "CZ",
        "category": "civil",
        "latex_template": ZALOBA_NA_ZAPLACENI,
        "required_fields": [
            "soud",
            "zalobce_jmeno",
            "zalobce_adresa",
            "zalovany_jmeno",
            "zalovany_adresa",
            "castka",
            "mena",
            "duvod_pohledavky",
            "petit",
            "oduvodneni",
            "dukazy",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "soud": "Název a adresa příslušného soudu",
            "zalobce_jmeno": "Jméno a příjmení nebo název žalobce",
            "zalobce_adresa": "Adresa bydliště nebo sídla žalobce",
            "zalovany_jmeno": "Jméno a příjmení nebo název žalovaného",
            "zalovany_adresa": "Adresa bydliště nebo sídla žalovaného",
            "castka": "Výše požadované částky (číslo)",
            "mena": "Měna (zpravidla Kč)",
            "duvod_pohledavky": "Právní důvod pohledávky (smlouva, bezdůvodné obohacení apod.)",
            "petit": "Žalobní petit — čeho se žalobce domáhá",
            "oduvodneni": "Skutkové a právní odůvodnění žaloby s příslušnými zákonnými citacemi",
            "dukazy": "Výčet navrhovaných důkazů",
            "datum": "Datum podání žaloby",
            "misto": "Místo podání žaloby",
        },
        "description": (
            "Žaloba na zaplacení peněžité pohledávky (dluh, náhrada škody, bezdůvodné obohacení). "
            "Pro nároky do 1 mil. Kč zvažte platební rozkaz."
        ),
    },
    {
        "slug": "navrh_platebni_rozkaz",
        "name": "Návrh na vydání platebního rozkazu",
        "jurisdiction": "CZ",
        "category": "civil",
        "latex_template": NAVRH_PLATEBNI_ROZKAZ,
        "required_fields": [
            "soud",
            "navrhovatel_jmeno",
            "navrhovatel_adresa",
            "odpurce_jmeno",
            "odpurce_adresa",
            "castka",
            "mena",
            "duvod_pohledavky",
            "oduvodneni",
            "dukazy",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "soud": "Název a adresa příslušného soudu",
            "navrhovatel_jmeno": "Jméno a příjmení nebo název navrhovatele (věřitele)",
            "navrhovatel_adresa": "Adresa navrhovatele",
            "odpurce_jmeno": "Jméno a příjmení nebo název odpůrce (dlužníka)",
            "odpurce_adresa": "Adresa odpůrce",
            "castka": "Výše vymáhané částky (číslo)",
            "mena": "Měna (zpravidla Kč)",
            "duvod_pohledavky": "Právní důvod pohledávky (faktura, smlouva apod.)",
            "oduvodneni": "Stručné odůvodnění nároku s citací právního základu",
            "dukazy": "Výčet přiložených listin dokládajících pohledávku",
            "datum": "Datum podání návrhu",
            "misto": "Místo podání návrhu",
        },
        "description": (
            "Zrychlené řízení pro nesporné peněžité pohledávky — soud vydá platební rozkaz "
            "bez nařízení jednání. Odpůrce může podat odpor do 15 dnů."
        ),
    },
    {
        "slug": "odvolani_proti_rozsudku",
        "name": "Odvolání proti rozsudku",
        "jurisdiction": "CZ",
        "category": "civil",
        "latex_template": ODVOLANI_PROTI_ROZSUDKU,
        "required_fields": [
            "odvolaci_soud",
            "prvostupnovy_soud",
            "odvolatel_jmeno",
            "odvolatel_adresa",
            "protiodvolatel_jmeno",
            "protiodvolatel_adresa",
            "cislo_jednaci",
            "datum_rozsudku",
            "petit_odvolani",
            "oduvodneni",
            "dukazy",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "odvolaci_soud": "Název odvolacího soudu",
            "prvostupnovy_soud": "Název soudu prvního stupně, jehož rozsudek se napadá",
            "odvolatel_jmeno": "Jméno odvolatele",
            "odvolatel_adresa": "Adresa odvolatele",
            "protiodvolatel_jmeno": "Jméno protistrany",
            "protiodvolatel_adresa": "Adresa protistrany",
            "cislo_jednaci": "Spisová značka napadeného rozsudku (sp. zn.)",
            "datum_rozsudku": "Datum vydání napadeného rozsudku",
            "petit_odvolani": "Odvolací petit — jak má odvolací soud rozhodnout",
            "oduvodneni": "Odvolací důvody — v čem spočívá nesprávnost napadeného rozsudku",
            "dukazy": "Nové důkazy navrhované v odvolacím řízení (je-li relevantní)",
            "datum": "Datum podání odvolání",
            "misto": "Místo podání odvolání",
        },
        "description": (
            "Odvolání proti rozsudku soudu prvního stupně podávané k soudu odvolacímu "
            "prostřednictvím soudu, který napadený rozsudek vydal. Lhůta 15 dnů od doručení."
        ),
    },
    {
        "slug": "odpor_platebni_rozkaz",
        "name": "Odpor proti platebnímu rozkazu",
        "jurisdiction": "CZ",
        "category": "civil",
        "latex_template": ODPOR_PLATEBNI_ROZKAZ,
        "required_fields": [
            "soud",
            "odpurce_jmeno",
            "odpurce_adresa",
            "navrhovatel_jmeno",
            "cislo_jednaci_rozkazu",
            "datum_doruceni",
            "oduvodneni",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "soud": "Název soudu, který platební rozkaz vydal",
            "odpurce_jmeno": "Jméno odpůrce podávajícího odpor",
            "odpurce_adresa": "Adresa odpůrce",
            "navrhovatel_jmeno": "Jméno navrhovatele (druhé strany)",
            "cislo_jednaci_rozkazu": "Spisová značka platebního rozkazu",
            "datum_doruceni": "Datum doručení platebního rozkazu odpůrci",
            "oduvodneni": "Důvody, proč odpůrce nárok odmítá — právní a skutkové argumenty",
            "datum": "Datum podání odporu",
            "misto": "Místo podání odporu",
        },
        "description": (
            "Odpor podaný do 15 dnů od doručení platebního rozkazu. Podáním odporu se platební "
            "rozkaz ruší a věc přechází do standardního sporného řízení."
        ),
    },
    {
        "slug": "stiznost_spravni_organ",
        "name": "Stížnost na postup správního orgánu",
        "jurisdiction": "CZ",
        "category": "administrative",
        "latex_template": STIZNOST_SPRAVNI_ORGAN,
        "required_fields": [
            "spravni_organ",
            "spravni_organ_adresa",
            "nadrizen_organ",
            "stizovatel_jmeno",
            "stizovatel_adresa",
            "predmet_stiznosti",
            "popis_pochybeni",
            "navrh_opatreni",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "spravni_organ": "Název správního orgánu, jehož postup je napadán",
            "spravni_organ_adresa": "Adresa dotčeného správního orgánu",
            "nadrizen_organ": "Nadřízený správní orgán, kterému se stížnost adresuje",
            "stizovatel_jmeno": "Jméno a příjmení stěžovatele",
            "stizovatel_adresa": "Adresa stěžovatele",
            "predmet_stiznosti": "Stručný popis předmětu stížnosti (o jakou věc jde)",
            "popis_pochybeni": "Podrobný popis nezákonného nebo nevhodného postupu orgánu",
            "navrh_opatreni": "Navrhované nápravné opatření nebo požadovaný výsledek",
            "datum": "Datum podání stížnosti",
            "misto": "Místo podání stížnosti",
        },
        "description": (
            "Stížnost adresovaná nadřízenému správnímu orgánu na nevhodný nebo nezákonný "
            "postup podřízeného orgánu dle § 175 správního řádu."
        ),
    },
    {
        "slug": "navrh_rozvod",
        "name": "Návrh na rozvod manželství",
        "jurisdiction": "CZ",
        "category": "civil",
        "latex_template": NAVRH_ROZVOD,
        "required_fields": [
            "soud",
            "navrhovatel_jmeno",
            "navrhovatel_adresa",
            "navrhovatel_datum_narozeni",
            "odpurce_jmeno",
            "odpurce_adresa",
            "odpurce_datum_narozeni",
            "datum_svadby",
            "misto_svadby",
            "deti",
            "oduvodneni",
            "petit",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "soud": "Název příslušného soudu (dle bydliště manželů)",
            "navrhovatel_jmeno": "Jméno a příjmení navrhovatele",
            "navrhovatel_adresa": "Adresa navrhovatele",
            "navrhovatel_datum_narozeni": "Datum narození navrhovatele",
            "odpurce_jmeno": "Jméno a příjmení odpůrce (druhého manžela)",
            "odpurce_adresa": "Adresa odpůrce",
            "odpurce_datum_narozeni": "Datum narození odpůrce",
            "datum_svadby": "Datum uzavření manželství",
            "misto_svadby": "Místo uzavření manželství",
            "deti": "Nezletilé děti manželů nebo informace o jejich neexistenci",
            "oduvodneni": "Důvody rozvratu manželství a právní argumenty",
            "petit": "Petit návrhu — co se navrhovatel domáhá (rozvod, péče o děti apod.)",
            "datum": "Datum podání návrhu",
            "misto": "Místo podání návrhu",
        },
        "description": (
            "Návrh na rozvod manželství dle § 755 a násl. OZ. "
            "Vhodné jak pro sporný rozvod, tak jako základ pro nesporný postup dle § 757 OZ."
        ),
    },
    {
        "slug": "plna_moc_obecna",
        "name": "Plná moc (obecná)",
        "jurisdiction": "CZ",
        "category": "other",
        "latex_template": PLNA_MOC_OBECNA,
        "required_fields": [
            "zmocnitel_jmeno",
            "zmocnitel_adresa",
            "zmocnitel_datum_narozeni",
            "zmocnenec_jmeno",
            "zmocnenec_adresa",
            "rozsah_plne_moci",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "zmocnitel_jmeno": "Jméno a příjmení zmocnitele (kdo plnou moc uděluje)",
            "zmocnitel_adresa": "Adresa trvalého bydliště zmocnitele",
            "zmocnitel_datum_narozeni": "Datum narození zmocnitele",
            "zmocnenec_jmeno": "Jméno a příjmení nebo název zmocněnce (kdo je zmocněn)",
            "zmocnenec_adresa": "Adresa bydliště nebo sídla zmocněnce",
            "rozsah_plne_moci": "Přesné vymezení úkonů, k nimž je zmocněnec oprávněn",
            "datum": "Datum podpisu plné moci",
            "misto": "Místo podpisu plné moci",
        },
        "description": (
            "Obecná plná moc pro zastupování fyzické osoby — vhodné pro soudní, správní "
            "i soukromoprávní jednání. Rozsah je třeba přesně specifikovat."
        ),
    },
    {
        "slug": "smlouva_o_dilo",
        "name": "Smlouva o dílo",
        "jurisdiction": "CZ",
        "category": "commercial",
        "latex_template": SMLOUVA_O_DILO,
        "required_fields": [
            "zhotovitel_jmeno",
            "zhotovitel_adresa",
            "zhotovitel_ico",
            "objednatel_jmeno",
            "objednatel_adresa",
            "predmet_dila",
            "cena",
            "termin_dokonceni",
            "misto_plneni",
            "datum_podpisu",
        ],
        "field_descriptions": {
            "zhotovitel_jmeno": "Jméno a příjmení nebo obchodní firma zhotovitele",
            "zhotovitel_adresa": "Sídlo nebo bydliště zhotovitele",
            "zhotovitel_ico": "IČO zhotovitele (fyzická osoba – podnikatel nebo právnická osoba)",
            "objednatel_jmeno": "Jméno a příjmení nebo obchodní firma objednatele",
            "objednatel_adresa": "Sídlo nebo bydliště objednatele",
            "predmet_dila": "Přesný popis výsledku, který se zhotovitel zavazuje vytvořit nebo dodat",
            "cena": "Sjednávaná cena díla včetně měny (např. 50 000 Kč bez DPH)",
            "termin_dokonceni": "Datum, do kdy musí být dílo dokončeno a předáno (formát DD.MM.RRRR)",
            "misto_plneni": "Místo, kde bude dílo provedeno nebo předáno",
            "datum_podpisu": "Datum uzavření smlouvy (formát DD.MM.RRRR)",
        },
        "description": (
            "Smlouva o dílo dle § 2586–2635 OZ pro freelancery, živnostníky i firmy. "
            "Vhodná pro zakázky v oblasti IT, stavebnictví, kreativních služeb nebo řemesel."
        ),
    },
    {
        "slug": "spolecenska_smlouva_sro",
        "name": "Zakladatelská listina / Společenská smlouva s.r.o.",
        "jurisdiction": "CZ",
        "category": "commercial",
        "latex_template": SPOLECENSKA_SMLOUVA_SRO,
        "required_fields": [
            "nazev_spolecnosti",
            "sidlo",
            "predmet_podnikani",
            "zakladatel_jmeno",
            "zakladatel_adresa",
            "zakladatel_rc_ico",
            "vklad",
            "splaceni",
            "jednatel_jmeno",
            "jednatel_adresa",
            "datum",
        ],
        "field_descriptions": {
            "nazev_spolecnosti": "Obchodní firma společnosti včetně označení s.r.o. (např. Acme Services s.r.o.)",
            "sidlo": "Úplná adresa sídla společnosti (ulice, čp., město, PSČ)",
            "predmet_podnikani": "Předmět podnikání — popis činností, které bude společnost provozovat",
            "zakladatel_jmeno": "Jméno a příjmení nebo obchodní firma zakladatele",
            "zakladatel_adresa": "Adresa trvalého bydliště nebo sídla zakladatele",
            "zakladatel_rc_ico": "Rodné číslo zakladatele (fyzická osoba) nebo IČO (právnická osoba)",
            "vklad": "Výše peněžitého vkladu zakladatele v Kč (min. 1 Kč dle § 142 ZOK)",
            "splaceni": "Způsob a termín splacení vkladu (např. před zápisem do OR, do 5 let)",
            "jednatel_jmeno": "Jméno a příjmení jednatele společnosti",
            "jednatel_adresa": "Adresa trvalého bydliště jednatele",
            "datum": "Datum podpisu zakladatelské listiny / společenské smlouvy (DD.MM.RRRR)",
        },
        "description": (
            "Zakladatelský dokument s.r.o. dle § 146–154 ZOK. "
            "Pro jednoho zakladatele slouží jako zakladatelská listina, pro více zakladatelů jako společenská smlouva. "
            "Nutno ověřit u notáře před zápisem do obchodního rejstříku."
        ),
    },
    {
        "slug": "vlastni_dokument",
        "name": "Vlastní dokument",
        "jurisdiction": "general",
        "category": "other",
        "latex_template": VLASTNI_DOKUMENT,
        "required_fields": [
            "nazev",
            "obsah",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "nazev": "Název dokumentu (zobrazí se jako nadpis)",
            "obsah": "Plný text dokumentu — AI vyplní na základě vašich pokynů",
            "datum": "Datum dokumentu",
            "misto": "Místo vydání dokumentu",
        },
        "description": (
            "Volný formát pro libovolný právní dokument. AI vygeneruje text na základě "
            "vašich pokynů. Vhodné pro nestandardní podání nebo interní dokumenty."
        ),
    },
    {
        "slug": "najemni_smlouva_prostory_podnikani",
        "name": "Nájemní smlouva — prostory sloužící k podnikání",
        "jurisdiction": "CZ",
        "category": "commercial",
        "latex_template": NAJEMNI_SMLOUVA_PROSTORY_PODNIKANI,
        "required_fields": [
        "pronajimatel_jmeno",
        "pronajimatel_adresa",
        "pronajimatel_ico",
        "najemce_jmeno",
        "najemce_adresa",
        "najemce_ico",
        "predmet_najmu_adresa",
        "predmet_najmu_popis",
        "vymera",
        "ucel_najmu",
        "najemne_mesicne",
        "kauce",
        "doba_najmu",
        "datum_zacatku",
        "vypovedni_doba",
        "misto_podpisu",
        "datum_podpisu"
],
        "field_descriptions": {
        "kauce": "Výše kauce v Kč",
        "vymera": "Výměra v m²",
        "doba_najmu": "Doba nájmu (určitá nebo neurčitá)",
        "ucel_najmu": "Účel nájmu (např. kanceláře, administrativa)",
        "najemce_ico": "IČO nájemce",
        "datum_podpisu": "Datum podpisu smlouvy (DD.MM.RRRR)",
        "datum_zacatku": "Datum počátku nájmu (DD.MM.RRRR)",
        "misto_podpisu": "Místo podpisu smlouvy",
        "najemce_jmeno": "Jméno a příjmení nebo obchodní firma nájemce",
        "najemce_adresa": "Sídlo nájemce",
        "vypovedni_doba": "Délka výpovědní doby (např. 3 měsíce)",
        "najemne_mesicne": "Měsíční nájemné v Kč",
        "pronajimatel_ico": "IČO pronajímatele",
        "pronajimatel_jmeno": "Jméno a příjmení nebo obchodní firma pronajímatele",
        "predmet_najmu_popis": "Popis prostor (patro, číslo místnosti, vybavení)",
        "pronajimatel_adresa": "Sídlo pronajímatele",
        "predmet_najmu_adresa": "Úplná adresa pronajímaných prostor"
},
        "description": "Nájemní smlouva na nebytové prostory pro podnikání dle § 2302–2331 OZ. Vhodná pro kanceláře, sklady, provozovny a další komerční prostory.",
    },
    {
        "slug": "smlouva_o_mlcenlivosti_nda",
        "name": "Smlouva o mlčenlivosti (NDA)",
        "jurisdiction": "CZ",
        "category": "commercial",
        "latex_template": SMLOUVA_O_MLCENLIVOSTI_NDA,
        "required_fields": [
        "strana_a_jmeno",
        "strana_a_adresa",
        "strana_a_ico",
        "strana_b_jmeno",
        "strana_b_adresa",
        "strana_b_ico",
        "predmet_jednani",
        "definice_duvernych_informaci",
        "doba_mlcenlivosti",
        "smluvni_pokuta",
        "misto_podpisu",
        "datum_podpisu"
],
        "field_descriptions": {
        "strana_a_ico": "IČO Strana A",
        "strana_b_ico": "IČO Strana B",
        "datum_podpisu": "Datum podpisu smlouvy (DD.MM.RRRR)",
        "misto_podpisu": "Místo podpisu smlouvy",
        "smluvni_pokuta": "Výše smluvní pokuty za porušení mlčenlivosti (např. 100 000 Kč)",
        "strana_a_jmeno": "Jméno a příjmení nebo obchodní firma Strana A",
        "strana_b_jmeno": "Jméno a příjmení nebo obchodní firma Strana B",
        "predmet_jednani": "Předmět jednání, kvůli kterému se sdělují důvěrné informace",
        "strana_a_adresa": "Sídlo nebo bydliště Strana A",
        "strana_b_adresa": "Sídlo nebo bydliště Strana B",
        "doba_mlcenlivosti": "Doba trvání mlčenlivosti (např. 5 let od podpisu)",
        "definice_duvernych_informaci": "Definice toho, co se považuje za důvěrné informace"
},
        "description": "Vzájemná smlouva o mlčenlivosti pro obchodní jednání, investiční pitch nebo spolupráci. Oba partneři se zavazují nezveřejnit důvěrné informace.",
    },
    {
        "slug": "smlouva_prevod_podilu_sro",
        "name": "Smlouva o převodu podílu ve s.r.o.",
        "jurisdiction": "CZ",
        "category": "commercial",
        "latex_template": SMLOUVA_PREVOD_PODILU_SRO,
        "required_fields": [
        "prevodce_jmeno",
        "prevodce_adresa",
        "prevodce_rc_ico",
        "nabyvatel_jmeno",
        "nabyvatel_adresa",
        "nabyvatel_rc_ico",
        "nazev_spolecnosti",
        "sidlo_spolecnosti",
        "ico_spolecnosti",
        "vyse_podilu_pred",
        "vyse_prevadeneho_podilu",
        "cena_prevodu",
        "misto_uzavreni",
        "datum_uzavreni"
],
        "field_descriptions": {
        "cena_prevodu": "Cena převodu v Kč (nebo bezúplatně)",
        "datum_uzavreni": "Datum uzavření smlouvy (DD.MM.RRRR)",
        "misto_uzavreni": "Místo uzavření smlouvy",
        "prevodce_jmeno": "Jméno a příjmení nebo obchodní firma převodce",
        "ico_spolecnosti": "IČO společnosti",
        "nabyvatel_jmeno": "Jméno a příjmení nebo obchodní firma nabyvatele",
        "prevodce_adresa": "Bydliště nebo sídlo převodce",
        "prevodce_rc_ico": "Rodné číslo (FO) nebo IČO (PO) převodce",
        "nabyvatel_adresa": "Bydliště nebo sídlo nabyvatele",
        "nabyvatel_rc_ico": "Rodné číslo (FO) nebo IČO (PO) nabyvatele",
        "vyse_podilu_pred": "Výše podílu před převodem (např. 50 %)",
        "nazev_spolecnosti": "Název společnosti s.r.o. včetně označení",
        "sidlo_spolecnosti": "Sídlo společnosti",
        "vyse_prevadeneho_podilu": "Výše převáděného podílu (např. 25 %)"
},
        "description": "Smlouva o převodu podílu ve s.r.o. dle § 207–209 ZOK. Vyžaduje úřední ověření podpisů a je účinná vůči společnosti po doručení.",
    },
    {
        "slug": "souhlas_zpracovani_osobnich_udaju_gdpr",
        "name": "Souhlas se zpracováním osobních údajů (GDPR)",
        "jurisdiction": "CZ",
        "category": "compliance",
        "latex_template": SOUHLAS_ZPRACOVANI_OSOBNICH_UDAJU_GDPR,
        "required_fields": [
        "spravce_jmeno",
        "spravce_adresa",
        "spravce_ico",
        "spravce_kontakt",
        "subjekt_jmeno",
        "subjekt_adresa",
        "ucel_zpracovani",
        "kategorie_udaju",
        "pravni_zaklad",
        "doba_uchovavani",
        "prijemci_udaju",
        "datum_souhlasu"
],
        "field_descriptions": {
        "spravce_ico": "IČO správce údajů",
        "pravni_zaklad": "Právní základ (např. souhlas dle čl. 6 odst. 1 písm. a) GDPR)",
        "spravce_jmeno": "Jméno a příjmení nebo obchodní firma správce údajů",
        "subjekt_jmeno": "Jméno a příjmení subjektu údajů",
        "datum_souhlasu": "Datum udělení souhlasu (DD.MM.RRRR)",
        "prijemci_udaju": "Kdo má přístup k údajům (např. pouze správce a zpracovatelé)",
        "spravce_adresa": "Sídlo správce údajů",
        "subjekt_adresa": "Bydliště subjektu údajů",
        "doba_uchovavani": "Doba uchovávání údajů (např. 3 roky od udělení souhlasu)",
        "kategorie_udaju": "Kategorie zpracovávaných údajů (jméno, email, telefon)",
        "spravce_kontakt": "Kontakt na správce (email, telefon, odpovědná osoba)",
        "ucel_zpracovani": "Účel zpracování (např. marketingová sdělení)"
},
        "description": "GDPR souhlas se zpracováním osobních údajů dle nařízení (EU) 2016/679. Obsahuje výčet práv subjektu údajů podle čl. 15–21 GDPR.",
    },
    {
        "slug": "vypoved_pracovniho_pomeru_zamestnavatel",
        "name": "Výpověď z pracovního poměru (zaměstnavatel)",
        "jurisdiction": "CZ",
        "category": "labor",
        "latex_template": VYPOVED_PRACOVNIHO_POMERU_ZAMESTNAVATEL,
        "required_fields": [
        "zamestnavatel_jmeno",
        "zamestnavatel_adresa",
        "zamestnavatel_ico",
        "zamestnanec_jmeno",
        "zamestnanec_adresa",
        "zamestnanec_datum_narozeni",
        "pracovni_pozice",
        "datum_uzavreni_smlouvy",
        "paragraf_vypovedi",
        "duvod_vypovedi",
        "datum_doruceni",
        "misto_podpisu",
        "datum_podpisu"
],
        "field_descriptions": {
        "datum_podpisu": "Datum podpisu výpovědi (DD.MM.RRRR)",
        "misto_podpisu": "Místo podpisu výpovědi",
        "datum_doruceni": "Datum doručení výpovědi zaměstnanci (DD.MM.RRRR)",
        "duvod_vypovedi": "Konkrétní důvod výpovědi podle § 52 ZP",
        "pracovni_pozice": "Pracovní pozice zaměstnance",
        "paragraf_vypovedi": "Paragraf výpovědi (např. § 52 písm. c) ZP)",
        "zamestnanec_jmeno": "Jméno a příjmení zaměstnance",
        "zamestnavatel_ico": "IČO zaměstnavatele",
        "zamestnanec_adresa": "Bydliště zaměstnance",
        "zamestnavatel_jmeno": "Jméno a příjmení nebo obchodní firma zaměstnavatele",
        "zamestnavatel_adresa": "Sídlo zaměstnavatele",
        "datum_uzavreni_smlouvy": "Datum uzavření pracovní smlouvy (DD.MM.RRRR)",
        "zamestnanec_datum_narozeni": "Datum narození zaměstnance (DD.MM.RRRR)"
},
        "description": "Výpověď z pracovního poměru daná zaměstnavatelem dle § 50–54 ZP. Obsahuje povinné poučení o právu na žalobu dle § 72 ZP.",
    },
    {
        "slug": "pracovni_smlouva",
        "name": "Pracovní smlouva",
        "jurisdiction": "CZ",
        "category": "labor",
        "latex_template": PRACOVNI_SMLOUVA,
        "required_fields": [
            "zamestnavatel_jmeno",
            "zamestnavatel_ico",
            "zamestnavatel_sidlo",
            "zamestnavatel_organ",
            "zamestnanec_jmeno",
            "zamestnanec_datum_narozeni",
            "zamestnanec_bydliste",
            "druh_prace",
            "misto_vykonu_prace",
            "datum_nastupu",
            "mzda_zakladni",
            "mzda_bonus",
            "pracovni_doba",
            "zkusebni_doba",
            "delka_dovolene",
            "vypovedni_doba",
            "misto_podpisu",
            "datum_podpisu",
        ],
        "field_descriptions": {
            "zamestnavatel_jmeno": "Obchodní firma zaměstnavatele (s.r.o. nebo a.s.)",
            "zamestnavatel_ico": "IČO zaměstnavatele",
            "zamestnavatel_sidlo": "Sídlo zaměstnavatele (ulice, čp., město, PSČ)",
            "zamestnavatel_organ": "Statutární orgán jednající za zaměstnavatele (jméno jednatele / představenstva)",
            "zamestnanec_jmeno": "Jméno a příjmení zaměstnance",
            "zamestnanec_datum_narozeni": "Datum narození zaměstnance (DD.MM.RRRR)",
            "zamestnanec_bydliste": "Adresa trvalého bydliště zaměstnance",
            "druh_prace": "Druh práce / název pracovní pozice (např. Softwarový inženýr)",
            "misto_vykonu_prace": "Místo výkonu práce (adresa nebo kraj)",
            "datum_nastupu": "Den nástupu do práce (DD.MM.RRRR) — § 34 odst. 1 písm. c) ZP",
            "mzda_zakladni": "Základní hrubá mzda v Kč měsíčně",
            "mzda_bonus": "Popis bonusové složky nebo odměn (nebo ponechat prázdné)",
            "pracovni_doba": "Druh pracovní doby (plný úvazek / zkrácený úvazek, počet hodin týdně)",
            "zkusebni_doba": "Délka zkušební doby (max. 3 měsíce, resp. 6 měsíců pro vedoucí — § 35 ZP)",
            "delka_dovolene": "Počet týdnů dovolené za rok (zákonné minimum 4 týdny — § 212 ZP)",
            "vypovedni_doba": "Délka výpovědní doby (zákonné minimum 2 měsíce — § 51 ZP)",
            "misto_podpisu": "Místo podpisu smlouvy",
            "datum_podpisu": "Datum podpisu smlouvy (DD.MM.RRRR)",
        },
        "description": (
            "Pracovní smlouva na dobu neurčitou nebo určitou pro zaměstnance s.r.o. dle § 34 a násl. ZP. "
            "Obsahuje všechny zákonné náležitosti: druh práce, místo výkonu, den nástupu, mzdu, "
            "pracovní dobu, zkušební dobu, dovolenou, výpovědní dobu, BOZP a GDPR poučení."
        ),
    },
    {
        "slug": "dohoda_o_provedeni_prace_dpp",
        "name": "Dohoda o provedení práce (DPP)",
        "jurisdiction": "CZ",
        "category": "labor",
        "latex_template": DOHODA_O_PROVEDENI_PRACE_DPP,
        "required_fields": [
            "zamestnavatel_jmeno",
            "zamestnavatel_ico",
            "zamestnavatel_sidlo",
            "pracovnik_jmeno",
            "pracovnik_datum_narozeni",
            "pracovnik_bydliste",
            "predmet_dohody",
            "rozsah_prace",
            "odmena",
            "doba_provedeni",
            "misto_provedeni",
            "misto_podpisu",
            "datum_podpisu",
        ],
        "field_descriptions": {
            "zamestnavatel_jmeno": "Obchodní firma zaměstnavatele (s.r.o. nebo a.s.)",
            "zamestnavatel_ico": "IČO zaměstnavatele",
            "zamestnavatel_sidlo": "Sídlo zaměstnavatele",
            "pracovnik_jmeno": "Jméno a příjmení pracovníka",
            "pracovnik_datum_narozeni": "Datum narození pracovníka (DD.MM.RRRR)",
            "pracovnik_bydliste": "Adresa trvalého bydliště pracovníka",
            "predmet_dohody": "Popis práce, která má být vykonána (§ 75 ZP)",
            "rozsah_prace": "Sjednaný rozsah práce v hodinách (max. 300 h/rok u téhož zaměstnavatele — § 75 ZP)",
            "odmena": "Celková sjednaná odměna v Kč (nebo hodinová sazba s výpočtem)",
            "doba_provedeni": "Termín provedení / splnění dohody (datum nebo popis)",
            "misto_provedeni": "Místo provedení práce",
            "misto_podpisu": "Místo podpisu dohody",
            "datum_podpisu": "Datum podpisu dohody (DD.MM.RRRR)",
        },
        "description": (
            "Dohoda o provedení práce dle § 75 ZP pro jednorázové nebo projektové práce. "
            "Limit 300 hodin ročně u téhož zaměstnavatele. Příjem do 10 000 Kč/měsíc "
            "nepodléhá odvodům sociálního a zdravotního pojištění (2026, indexováno)."
        ),
    },
    {
        "slug": "dohoda_o_pracovni_cinnosti_dpc",
        "name": "Dohoda o pracovní činnosti (DPČ)",
        "jurisdiction": "CZ",
        "category": "labor",
        "latex_template": DOHODA_O_PRACOVNI_CINNOSTI_DPC,
        "required_fields": [
            "zamestnavatel_jmeno",
            "zamestnavatel_ico",
            "zamestnavatel_sidlo",
            "pracovnik_jmeno",
            "pracovnik_datum_narozeni",
            "pracovnik_bydliste",
            "druh_prace",
            "rozsah_pracovni_doby",
            "doba_trvani",
            "odmena",
            "vypovedni_doba",
            "misto_podpisu",
            "datum_podpisu",
        ],
        "field_descriptions": {
            "zamestnavatel_jmeno": "Obchodní firma zaměstnavatele (s.r.o. nebo a.s.)",
            "zamestnavatel_ico": "IČO zaměstnavatele",
            "zamestnavatel_sidlo": "Sídlo zaměstnavatele",
            "pracovnik_jmeno": "Jméno a příjmení pracovníka",
            "pracovnik_datum_narozeni": "Datum narození pracovníka (DD.MM.RRRR)",
            "pracovnik_bydliste": "Adresa trvalého bydliště pracovníka",
            "druh_prace": "Druh sjednané práce (§ 76 ZP)",
            "rozsah_pracovni_doby": "Sjednaný rozsah pracovní doby (max. průměrně ½ stanovené týdenní PD — § 76 ZP, tj. max. 20 h/týden)",
            "doba_trvani": "Doba trvání dohody (určitá s datem ukončení nebo neurčitá)",
            "odmena": "Sjednaná odměna v Kč měsíčně (odvody při příjmu nad 4 500 Kč/měs. — 2026, indexováno)",
            "vypovedni_doba": "Výpovědní doba (zákonně 15 dní, lze sjednat jinak — § 76 odst. 5 ZP)",
            "misto_podpisu": "Místo podpisu dohody",
            "datum_podpisu": "Datum podpisu dohody (DD.MM.RRRR)",
        },
        "description": (
            "Dohoda o pracovní činnosti dle § 76 ZP pro opakující se práce do průměrně 20 hodin týdně. "
            "Má výpovědní dobu (zákonně 15 dní). Odvody pojistného vznikají při příjmu nad 4 500 Kč/měsíc (2026, indexováno)."
        ),
    },
    {
        "slug": "konkurencni_dolozka",
        "name": "Konkurenční doložka",
        "jurisdiction": "CZ",
        "category": "labor",
        "latex_template": KONKURENCNI_DOLOZKA,
        "required_fields": [
            "zamestnavatel_jmeno",
            "zamestnavatel_ico",
            "zamestnavatel_sidlo",
            "zamestnanec_jmeno",
            "zamestnanec_datum_narozeni",
            "zamestnanec_bydliste",
            "reference_pracovni_smlouvy",
            "vecny_rozsah",
            "geograficky_rozsah",
            "doba_trvani",
            "penezite_vyrovnani",
            "smluvni_pokuta",
            "misto_podpisu",
            "datum_podpisu",
        ],
        "field_descriptions": {
            "zamestnavatel_jmeno": "Obchodní firma zaměstnavatele (s.r.o. nebo a.s.)",
            "zamestnavatel_ico": "IČO zaměstnavatele",
            "zamestnavatel_sidlo": "Sídlo zaměstnavatele",
            "zamestnanec_jmeno": "Jméno a příjmení zaměstnance",
            "zamestnanec_datum_narozeni": "Datum narození zaměstnance (DD.MM.RRRR)",
            "zamestnanec_bydliste": "Adresa trvalého bydliště zaměstnance",
            "reference_pracovni_smlouvy": "Datum pracovní smlouvy, k níž je doložka sjednána (DD.MM.RRRR)",
            "vecny_rozsah": "Věcný rozsah omezení — popis zakázaných činností nebo odvětví",
            "geograficky_rozsah": "Geografický rozsah omezení (např. Česká republika, EU)",
            "doba_trvani": "Doba trvání závazku po skončení pracovního poměru (max. 1 rok — § 310 odst. 1 ZP)",
            "penezite_vyrovnani": "Výše měsíčního peněžitého vyrovnání v Kč (min. ½ průměrného měs. výdělku — § 310 odst. 1 ZP; bez tohoto vyrovnání je doložka neplatná)",
            "smluvni_pokuta": "Výše smluvní pokuty za porušení závazku v Kč (musí být přiměřená — § 310 odst. 3 ZP)",
            "misto_podpisu": "Místo podpisu doložky",
            "datum_podpisu": "Datum podpisu doložky (DD.MM.RRRR)",
        },
        "description": (
            "Konkurenční doložka dle § 310 ZP omezující zaměstnance v konkurenční činnosti po skončení pracovního poměru. "
            "Max. 1 rok. Vyžaduje peněžité vyrovnání min. ½ průměrného měsíčního výdělku za každý měsíc omezení — "
            "bez tohoto vyrovnání je doložka ze zákona neplatná."
        ),
    },
    {
        "slug": "odvolani_proti_rozhodnuti_spravce_dane",
        "name": "Odvolání proti rozhodnutí správce daně",
        "jurisdiction": "CZ",
        "category": "tax",
        "latex_template": ODVOLANI_PROTI_ROZHODNUTI_SPRAVCE_DANE,
        "required_fields": [
            "dan_subjekt_jmeno",
            "dan_subjekt_adresa",
            "dan_subjekt_ico_dic",
            "financni_urad",
            "cislo_jednaci_napadeneho_rozhodnuti",
            "datum_doruceni_rozhodnuti",
            "napadene_vyroky",
            "odvolaci_duvody",
            "petit",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "dan_subjekt_jmeno": "Jméno a příjmení nebo obchodní firma daňového subjektu",
            "dan_subjekt_adresa": "Adresa bydliště nebo sídla daňového subjektu",
            "dan_subjekt_ico_dic": "IČO nebo DIČ daňového subjektu",
            "financni_urad": "Název a adresa příslušného finančního úřadu",
            "cislo_jednaci_napadeneho_rozhodnuti": "Číslo jednací napadeného rozhodnutí správce daně",
            "datum_doruceni_rozhodnuti": "Datum doručení napadeného rozhodnutí (DD.MM.RRRR)",
            "napadene_vyroky": "Výroky rozhodnutí, proti nimž je odvolání směřováno",
            "odvolaci_duvody": "Konkrétní odvolací důvody — nesprávné posouzení skutkového stavu nebo právní vady",
            "petit": "Požadovaný výrok odvolacího orgánu (zrušení, změna rozhodnutí)",
            "datum": "Datum podání odvolání (DD.MM.RRRR)",
            "misto": "Místo podání odvolání",
        },
        "description": (
            "Odvolání proti rozhodnutí správce daně dle § 109–116 zákona č. 280/2009 Sb., daňový řád. "
            "Lhůta 30 dnů ode dne doručení rozhodnutí. Podává se u správce daně, který rozhodnutí vydal."
        ),
    },
    {
        "slug": "zadost_o_poseckani_uhrady_dane",
        "name": "Žádost o posečkání úhrady daně",
        "jurisdiction": "CZ",
        "category": "tax",
        "latex_template": ZADOST_O_POSECKANI_UHRADY_DANE,
        "required_fields": [
            "dan_subjekt_jmeno",
            "dan_subjekt_adresa",
            "dan_subjekt_ico_dic",
            "financni_urad",
            "dan_a_obdobi",
            "castka_dane",
            "pozadovany_termin_uhrady",
            "oduvodneni_zadosti",
            "prilohy",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "dan_subjekt_jmeno": "Jméno a příjmení nebo obchodní firma daňového subjektu",
            "dan_subjekt_adresa": "Adresa bydliště nebo sídla daňového subjektu",
            "dan_subjekt_ico_dic": "IČO nebo DIČ daňového subjektu",
            "financni_urad": "Název a adresa příslušného finančního úřadu",
            "dan_a_obdobi": "Druh daně a zdaňovací období, jehož se posečkání týká (např. DPH za Q1/2024)",
            "castka_dane": "Výše dlužné daně v Kč",
            "pozadovany_termin_uhrady": "Navrhovaný termín úhrady nebo splátkový kalendář (DD.MM.RRRR)",
            "oduvodneni_zadosti": "Důvody žádosti — doložení přechodných finančních potíží nebo jiných okolností",
            "prilohy": "Seznam přiložených dokladů prokazujících tvrzené skutečnosti",
            "datum": "Datum podání žádosti (DD.MM.RRRR)",
            "misto": "Místo podání žádosti",
        },
        "description": (
            "Žádost o posečkání úhrady daně dle § 156–157 zákona č. 280/2009 Sb., daňový řád. "
            "Správce daně může posečkání povolit při přechodných finančních obtížích nebo hrozbě závažné újmy."
        ),
    },
    {
        "slug": "zadost_o_vraceni_preplatku_na_dani",
        "name": "Žádost o vrácení přeplatku na dani",
        "jurisdiction": "CZ",
        "category": "tax",
        "latex_template": ZADOST_O_VRACENI_PREPLATKU_NA_DANI,
        "required_fields": [
            "dan_subjekt_jmeno",
            "dan_subjekt_adresa",
            "dan_subjekt_ico_dic",
            "financni_urad",
            "dan_a_obdobi",
            "castka_preplatku",
            "cislo_uctu_pro_vraceni",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "dan_subjekt_jmeno": "Jméno a příjmení nebo obchodní firma daňového subjektu",
            "dan_subjekt_adresa": "Adresa bydliště nebo sídla daňového subjektu",
            "dan_subjekt_ico_dic": "IČO nebo DIČ daňového subjektu",
            "financni_urad": "Název a adresa příslušného finančního úřadu",
            "dan_a_obdobi": "Druh daně a zdaňovací období, za které přeplatek vznikl",
            "castka_preplatku": "Výše přeplatku v Kč",
            "cislo_uctu_pro_vraceni": "Číslo bankovního účtu pro vrácení přeplatku (ve formátu předčíslí-číslo/kód banky)",
            "datum": "Datum podání žádosti (DD.MM.RRRR)",
            "misto": "Místo podání žádosti",
        },
        "description": (
            "Žádost o vrácení přeplatku na dani dle § 155 zákona č. 280/2009 Sb., daňový řád. "
            "Přeplatek nad 200 Kč se vrací automaticky do 30 dnů; nižší přeplatky pouze na žádost."
        ),
    },
    {
        "slug": "vyjadreni_k_vyzve_k_odstraneni_pochybnosti",
        "name": "Vyjádření k výzvě k odstranění pochybností",
        "jurisdiction": "CZ",
        "category": "tax",
        "latex_template": VYJADRENI_K_VYZVE_K_ODSTRANENI_POCHYBNOSTI,
        "required_fields": [
            "dan_subjekt_jmeno",
            "dan_subjekt_adresa",
            "dan_subjekt_ico_dic",
            "financni_urad",
            "cislo_jednaci_vyzvy",
            "datum_doruceni_vyzvy",
            "dotcene_obdobi",
            "vyjadreni_k_pochybnostem",
            "predkladane_dukazy",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "dan_subjekt_jmeno": "Jméno a příjmení nebo obchodní firma daňového subjektu",
            "dan_subjekt_adresa": "Adresa bydliště nebo sídla daňového subjektu",
            "dan_subjekt_ico_dic": "IČO nebo DIČ daňového subjektu",
            "financni_urad": "Název příslušného finančního úřadu, který výzvu vydal",
            "cislo_jednaci_vyzvy": "Číslo jednací výzvy k odstranění pochybností",
            "datum_doruceni_vyzvy": "Datum doručení výzvy (DD.MM.RRRR)",
            "dotcene_obdobi": "Zdaňovací období, jichž se výzva týká",
            "vyjadreni_k_pochybnostem": "Věcné vyjádření k jednotlivým pochybnostem správce daně",
            "predkladane_dukazy": "Seznam předkládaných důkazů a dokladů (faktury, smlouvy, výpisy atd.)",
            "datum": "Datum podání vyjádření (DD.MM.RRRR)",
            "misto": "Místo podání vyjádření",
        },
        "description": (
            "Vyjádření k výzvě k odstranění pochybností dle § 89 a § 92 zákona č. 280/2009 Sb., daňový řád. "
            "Reakce na výzvu vydanou při postupu k odstranění pochybností před zahájením daňové kontroly."
        ),
    },
    {
        "slug": "prihlaska_k_registraci_dph",
        "name": "Přihláška k registraci k DPH",
        "jurisdiction": "CZ",
        "category": "tax",
        "latex_template": PRIHLASKA_K_REGISTRACI_DPH,
        "required_fields": [
            "dan_subjekt_jmeno",
            "dan_subjekt_adresa",
            "dan_subjekt_ico_dic",
            "financni_urad",
            "dan_subjekt_typ",
            "duvod_registrace",
            "datum_zahajeni_ekon_cinnosti",
            "predpoklad_obratu",
            "bankovni_ucty",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "dan_subjekt_jmeno": "Jméno a příjmení nebo obchodní firma žadatele",
            "dan_subjekt_adresa": "Adresa bydliště nebo sídla žadatele",
            "dan_subjekt_ico_dic": "IČO žadatele (DIČ bude přiděleno po registraci)",
            "financni_urad": "Název a adresa místně příslušného finančního úřadu",
            "dan_subjekt_typ": "Typ subjektu: fyzická osoba / právnická osoba",
            "duvod_registrace": "Důvod registrace — překročení obratu 2 mil. Kč (§ 6 ZDPH), dobrovolná registrace (§ 94a ZDPH) apod.",
            "datum_zahajeni_ekon_cinnosti": "Datum zahájení ekonomické činnosti (DD.MM.RRRR)",
            "predpoklad_obratu": "Předpokládaný obrat za 12 po sobě jdoucích měsíců v Kč",
            "bankovni_ucty": "Čísla bankovních účtů používaných pro ekonomickou činnost",
            "datum": "Datum podání přihlášky (DD.MM.RRRR)",
            "misto": "Místo podání přihlášky",
        },
        "description": (
            "Přihláška k registraci k dani z přidané hodnoty dle § 6, § 6f a § 94a zákona č. 235/2004 Sb., ZDPH. "
            "Povinná registrace při překročení obratu 2 000 000 Kč za 12 měsíců; dobrovolná registrace kdykoli."
        ),
    },
    {
        "slug": "oznameni_ukonceni_samostatne_vydelecne_cinnosti",
        "name": "Oznámení o ukončení samostatné výdělečné činnosti",
        "jurisdiction": "CZ",
        "category": "tax",
        "latex_template": OZNAMENI_UKONCENI_SAMOSTATNE_VYDELECNE_CINNOSTI,
        "required_fields": [
            "dan_subjekt_jmeno",
            "dan_subjekt_adresa",
            "dan_subjekt_ico_dic",
            "okruh_oznameni",
            "datum_ukonceni",
            "vc_socialniho_pojisteni",
            "vc_zdravotniho_pojisteni",
            "datum",
            "misto",
        ],
        "field_descriptions": {
            "dan_subjekt_jmeno": "Jméno a příjmení OSVČ",
            "dan_subjekt_adresa": "Adresa trvalého bydliště OSVČ",
            "dan_subjekt_ico_dic": "IČO nebo DIČ OSVČ",
            "okruh_oznameni": "Okruh oznámení: finanční úřad / ČSSZ / zdravotní pojišťovna / živnostenský úřad",
            "datum_ukonceni": "Datum ukončení samostatné výdělečné činnosti (DD.MM.RRRR)",
            "vc_socialniho_pojisteni": "Informace k sociálnímu pojištění: ČSSZ, variabilní symbol, případná doplatková povinnost",
            "vc_zdravotniho_pojisteni": "Informace ke zdravotnímu pojištění: název pojišťovny, číslo smlouvy, doplatková povinnost",
            "datum": "Datum podání oznámení (DD.MM.RRRR)",
            "misto": "Místo podání oznámení",
        },
        "description": (
            "Oznámení o ukončení samostatné výdělečné činnosti dle zákona č. 589/1992 Sb. (sociální pojištění) "
            "a zákona č. 48/1997 Sb. (zdravotní pojištění). Lhůta 8 dnů od ukončení SVČ."
        ),
    },

]

# ---------------------------------------------------------------------------
# Seed logic
# ---------------------------------------------------------------------------


async def _ensure_tables_exist(conn: asyncpg.Connection) -> None:
    """Verify that document_templates exists; exit with guidance if not."""
    exists = await conn.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name = 'document_templates')"
    )
    if not exists:
        print(
            "ERROR: table 'document_templates' does not exist.\n"
            "Restart the backend (launchctl stop app.vitreon.backend && launchctl start app.vitreon.backend)\n"
            "to trigger init_db(), then re-run this script.",
            file=sys.stderr,
        )
        sys.exit(1)


async def seed(conn: asyncpg.Connection) -> None:
    """Upsert all templates into document_templates."""
    inserted = 0
    updated = 0

    for t in TEMPLATES:
        result = await conn.execute(
            """
            INSERT INTO document_templates
              (id, slug, name, jurisdiction, category, latex_template,
               required_fields, field_descriptions, description, created_at)
            VALUES
              ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, NOW())
            ON CONFLICT (slug) DO UPDATE SET
              name               = EXCLUDED.name,
              jurisdiction       = EXCLUDED.jurisdiction,
              category           = EXCLUDED.category,
              latex_template     = EXCLUDED.latex_template,
              required_fields    = EXCLUDED.required_fields,
              field_descriptions = EXCLUDED.field_descriptions,
              description        = EXCLUDED.description
            """,
            uuid.uuid4(),
            t["slug"],
            t["name"],
            t["jurisdiction"],
            t["category"],
            t["latex_template"],
            json.dumps(t["required_fields"], ensure_ascii=False),
            json.dumps(t["field_descriptions"], ensure_ascii=False),
            t["description"],
        )
        # asyncpg returns "INSERT 0 N" or "UPDATE N"
        tag = result.split()
        if tag[0] == "INSERT":
            inserted += 1
            print(f"  [INSERT] {t['slug']}")
        else:
            updated += 1
            print(f"  [UPDATE] {t['slug']}")

    print(f"\nDone. {inserted} inserted, {updated} updated.")


async def main() -> None:
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set in .env", file=sys.stderr)
        sys.exit(1)

    pg_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_url)
    try:
        await _ensure_tables_exist(conn)
        print(f"Seeding {len(TEMPLATES)} templates into document_templates...")
        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
