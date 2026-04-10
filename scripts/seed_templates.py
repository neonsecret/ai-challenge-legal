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
\noindent{{zalobce_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 2 — Žaloba na zaplacení
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
\noindent{{zalobce_jmeno}}

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
\noindent{{navrhovatel_jmeno}}

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
\noindent{{odvolatel_jmeno}}

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
\noindent{{odpurce_jmeno}}

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
\noindent{{stizovatel_jmeno}}

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
\noindent{{navrhovatel_jmeno}}

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
\noindent{{zmocnitel_jmeno}}\\
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
