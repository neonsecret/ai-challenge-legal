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
# Template 2 — Žaloba na zaplacení

# ---------------------------------------------------------------------------
# Template 3 — Smlouva o mlčenlivosti (NDA)
# ---------------------------------------------------------------------------

NDA_TEMPLATE = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Smluvní strany:}
\begin{itemize}
  \item {{strana_a_jmeno}}, {{strana_a_adresa}}, IČO {{strana_a_ico}}
  \item {{strana_b_jmeno}}, {{strana_b_adresa}}, IČO {{strana_b_ico}}
\end{itemize}

\vspace{1em}

\begin{center}
{\large\textbf{Dohoda o mlčenlivosti (NDA)}}
\end{center}

\vspace{1em}

\textbf{I. Předmět dohody}

{{predmet_jednani}}

\textbf{II. Definice důvěrných informací}

{{definice_duvernych_informaci}}

\textbf{III. Závazek mlčenlivosti}

{{zavazek_mlcenlivosti}}

\textbf{IV. Doba trvání}

{{doba_mlcenlivosti}}

\textbf{V. Sankce za porušení}

{{smluvni_pokuta}}

\vspace{2em}

\noindent V {{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
{{strana_a_jmeno}}

\vspace{2em}

\noindent\rule{8cm}{0.4pt}\\
{{strana_b_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 4 — Nájemní smlouva — prostory sloužící k podnikání (commercial lease)
# ---------------------------------------------------------------------------

COMMERCIAL_LEASE_TEMPLATE = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Smluvní strany:}
\begin{itemize}
  \item {{pronajimatel_jmeno}}, {{pronajimatel_adresa}}, IČO {{pronajimatel_ico}}
  \item {{najemce_jmeno}}, {{najemce_adresa}}, IČO {{najemce_ico}}
\end{itemize}

\vspace{1em}

\begin{center}
{\large\textbf{Nájemní smlouva – prostory sloužící k podnikání}}
\end{center}

\vspace{1em}

\textbf{I. Předmět nájmu}

{{predmet_najmu_adresa}}

{{predmet_najmu_popis}}

\textbf{II. Doba nájmu}

{{doba_najmu}}

\textbf{III. Nájemné a platební podmínky}

Měsíční nájemné: {{najemne_mesicne}} Kč.

Kauce: {{kauce}} Kč.

\textbf{IV. Práva a povinnosti stran}

{{prava_povinnosti}}

\textbf{V. Skončení nájmu}

{{vypovedni_doba}}

\vspace{2em}

\noindent V {{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
{{pronajimatel_jmeno}}

\vspace{2em}

\noindent\rule{8cm}{0.4pt}\\
{{najemce_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 5 — Souhlas se zpracováním osobních údajů (GDPR consent)
# ---------------------------------------------------------------------------

GDPR_CONSENT_TEMPLATE = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Správce:}
{{spravce_jmeno}}, {{spravce_adresa}}, IČO {{spravce_ico}}, kontakt {{spravce_kontakt}}

\noindent\textbf{Subjekt údajů:}
{{subjekt_jmeno}}, {{subjekt_adresa}}

\vspace{1em}

\begin{center}
{\large\textbf{Souhlas se zpracováním osobních údajů}}
\end{center}

\vspace{1em}

\textbf{I. Účel a kategorie zpracování}

{{ucel_zpracovani}}

\textbf{II. Právní základ}

{{pravni_zaklad}}

\textbf{III. Doba uchování}

{{doba_uchovavani}}

\textbf{IV. Práva subjektu}

{{prava_subjektu}}

\textbf{V. Příjemci údajů}

{{prijemci_udaju}}

\vspace{2em}

\noindent Datum souhlasu: {{datum_souhlasu}}

\noindent V {{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
{{spravce_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 6 — Výpověď z pracovního poměru ze strany zaměstnavatele (employer termination)
# ---------------------------------------------------------------------------

EMPLOYER_TERMINATION_TEMPLATE = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Zaměstnavatel:}
{{zamestnavatel_jmeno}}, {{zamestnavatel_adresa}}, IČO {{zamestnavatel_ico}}

\noindent\textbf{Zaměstnanec:}
{{zamestnanec_jmeno}}, {{zamestnanec_adresa}}, datum narození {{zamestnanec_datum_narozeni}}

\vspace{1em}

\begin{center}
{\large\textbf{Výpověď z pracovního poměru ze strany zaměstnavatele}}
\end{center}

\vspace{1em}

\textbf{I. Identifikace pracovního poměru}

Pozice: {{pracovni_pozice}}

Datum uzavření smlouvy: {{datum_uzavreni_smlouvy}}

\textbf{II. Výpověď a její důvod}

Paragraf výpovědi: {{paragraf_vypovedi}}

Důvod výpovědi: {{duvod_vypovedi}}

\textbf{III. Výpovědní doba}

{{vypovedni_doba}}

\textbf{IV. Poučení zaměstnance}\n\textit{(§ 72 ZP)}

{{poucenim}}

\vspace{2em}

\noindent V {{misto_podpisu}} dne {{datum_podpisu}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
{{zamestnavatel_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------
# Template 7 — Smlouva o převodu podílu ve s.r.o. (share transfer)
# ---------------------------------------------------------------------------

SHARE_TRANSFER_TEMPLATE = (
    _CZ_PREAMBLE
    + r"""
\begin{document}

\noindent\textbf{{{soud}}}

\vspace{2em}

\noindent\textbf{Převodce:}
{{prevodce_jmeno}}, {{prevodce_adresa}}, IČO {{prevodce_rc_ico}}

\noindent\textbf{Nabyvatel:}
{{nabyvatel_jmeno}}, {{nabyvatel_adresa}}, IČO {{nabyvatel_rc_ico}}

\vspace{1em}

\begin{center}
{\large\textbf{Smlouva o převodu podílu ve s.r.o.}}
\end{center}

\vspace{1em}

\textbf{I. Identifikace společnosti a podílu}

Název společnosti: {{nazev_spolecnosti}}

Sídlo: {{sidlo_spolecnosti}}

IČO: {{ico_spolecnosti}}

Podíl před převodem: {{vyse_podilu_pred}} %

Převáděný podíl: {{vyse_prevadeneho_podilu}} %

\textbf{II. Cena a platební podmínky}

Cena převodu: {{cena_prevodu}}

\textbf{III. Účinnost převodu vůči společnosti}

{{ucinnost}}

\textbf{IV. Prohlášení stran}

{{prohlaseni}}

\textbf{V. Závěrečná ustanovení}

{{zaverecna}}

\vspace{2em}

\noindent V {{misto_uzavreni}} dne {{datum_uzavreni}}

\vspace{3em}

\noindent\rule{8cm}{0.4pt}\\
{{prevodce_jmeno}}

\vspace{2em}

\noindent\rule{8cm}{0.4pt}\\
{{nabyvatel_jmeno}}

\end{document}
"""
)

# ---------------------------------------------------------------------------

NAJEMNI_SMLOUVA_PROSTORY_PODNIKANI = """
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


SMLOUVA_O_MLCENLIVOSTI_NDA = """
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


SMLOUVA_PREVOD_PODILU_SRO = """
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


SOUHLAS_ZPRACOVANI_OSOBNICH_UDAJU_GDPR = """
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


VYPOVED_PRACOVNIHO_POMERU_ZAMESTNAVATEL = """
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
