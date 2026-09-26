import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import base64
import re
from pathlib import Path

pio.templates.default = "plotly_dark"

_unit_code_pattern = re.compile(r'(\d{3}-\d{3})\s*$')
def _unit_label(name):
    if not isinstance(name, str):
        return name
    m = _unit_code_pattern.search(name)
    code = m.group(1) if m else "?"
    return f"{code} — {name}"


# ---------------------------------------------------------------
# PENCOCOKAN UNIT antar sumber data (Pemeliharaan/Sparepart -> data BKMS)
# ---------------------------------------------------------------
# Nama unit di file Pemeliharaan/Sparepart sering BEDA penulisan dgn data BKMS, mis.
#   "EXCAVATOR HITACHI ZX48U-5A (331-004)"  vs  "EXCAVATOR MINI 331-004"
#   "POMPA MITSUBISHI 6D14 422-007"          vs  "Pompa Air" (kode_unit 4207)
# Jadi pencocokan pakai KODE UNIT (format 3-3 digit), bukan nama lengkap. Urutan prioritas:
#   1) (lokasi, kode unit)  -- kode yg sama bisa dipakai di beberapa site (mis. 312-014 ada di 3 site)
#   2) kode unit saja       -- HANYA kalau nilainya tdk ambigu (sama di semua site)
#   3) nama unit persis     -- cara lama, sbg cadangan terakhir
_KODE_UNIT_PAT = re.compile(r'(\d{3})\s*-\s*(\d{3})')


def _kode_dari_teks(v):
    """Ambil kode unit 'ddd-ddd' TERAKHIR dari teks (nama unit biasanya diakhiri kode). None kalau tdk ada."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    found = _KODE_UNIT_PAT.findall(str(v))
    if found:
        a, b = found[-1]
        return f"{a}-{b}"
    return None


def _kode_unit_ref(kode, nama=None):
    """Normalisasi kode unit di data BKMS ke format 'ddd-ddd'."""
    k = _kode_dari_teks(kode) or _kode_dari_teks(nama)
    if k:
        return k
    if kode is None or (isinstance(kode, float) and pd.isna(kode)):
        return None
    s = str(kode).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if re.fullmatch(r"\d{6}", s):          # 331004 -> 331-004
        return f"{s[:3]}-{s[3:]}"
    if re.fullmatch(r"42\d{2}", s):        # Pompa KUMAI: kode 4201..4209 di BKMS = 422-001..422-009 di Pemeliharaan
        return f"422-0{s[2:]}"
    return None


def lookup_atribut_unit(target_df, ref_df, cols):
    """Isi atribut unit (mis. kategori, jenis_unit, id_unit, kelompok_unit) utk target_df dari ref_df (data BKMS),
    dicocokkan via KODE UNIT (lihat penjelasan di atas). Mengembalikan DataFrame dgn index = target_df.index."""
    out = pd.DataFrame(index=target_df.index)
    cols = [c for c in cols if c in ref_df.columns]
    if target_df.empty or ref_df.empty or "nama_unit" not in target_df.columns or "nama_unit" not in ref_df.columns:
        for c in cols:
            out[c] = None
        return out
    # Baris tanpa nama_unit TETAP dipakai (mis. CRANE KUMAI 2902 nama_unit-nya kosong di data BKMS) --
    # selama kode unitnya ada, unit tsb masih bisa dicocokkan.
    ref = ref_df[ref_df["nama_unit"].notna() | (ref_df["kode_unit"].notna() if "kode_unit" in ref_df.columns else False)].copy()
    kode_col = ref["kode_unit"] if "kode_unit" in ref.columns else pd.Series([None] * len(ref), index=ref.index)
    ref["_kode"] = [_kode_unit_ref(k, n) for k, n in zip(kode_col, ref["nama_unit"])]
    ref["_nama"] = ref["nama_unit"].fillna("").astype(str).str.strip().str.upper()
    ref["_lok"] = ref["lokasi"] if "lokasi" in ref.columns else None

    t_kode = target_df["nama_unit"].map(_kode_dari_teks)
    t_nama = target_df["nama_unit"].astype(str).str.strip().str.upper()
    t_lok = target_df["lokasi"] if "lokasi" in target_df.columns else pd.Series([None] * len(target_df), index=target_df.index)

    for c in cols:
        rc = ref.dropna(subset=[c])
        by_lok_kode = rc.dropna(subset=["_kode"]).drop_duplicates(["_lok", "_kode"]).set_index(["_lok", "_kode"])[c].to_dict()
        _nuniq = rc.dropna(subset=["_kode"]).groupby("_kode")[c].nunique()
        _unik = set(_nuniq[_nuniq == 1].index)
        by_kode = (rc[rc["_kode"].isin(_unik)].drop_duplicates("_kode").set_index("_kode")[c].to_dict())
        by_nama = rc[rc["_nama"] != ""].drop_duplicates("_nama").set_index("_nama")[c].to_dict()
        vals = []
        for lok, kd, nm in zip(t_lok, t_kode, t_nama):
            v = None
            if kd is not None:
                v = by_lok_kode.get((lok, kd))
                if v is None:
                    v = by_kode.get(kd)
            if v is None:
                v = by_nama.get(nm)
            vals.append(v)
        out[c] = vals
    return out

def style_fig(fig):
    """Make chart background transparent so it blends with the black page,
    and keep text light/readable."""
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#F3F4F6"),
        legend=dict(font=dict(color="#F3F4F6")),
    )
    fig.update_xaxes(gridcolor="#2D333B", zerolinecolor="#2D333B")
    fig.update_yaxes(gridcolor="#2D333B", zerolinecolor="#2D333B")
    return fig

# ---------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Operational Review | PT BKMS",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------
# STYLE
# ---------------------------------------------------------------
PRIMARY = "#0B3D2E"      # forest green (used for banner/backgrounds)
CHART_GREEN = "#3FA772"  # brighter green for readable bars/lines on black
GOLD = "#C9A227"         # gold accent
RED = "#E4574C"          # brighter red for readability on black
GREY = "#9CA3AF"         # lighter grey for readability on black
EMOJI_FONT = "Segoe UI Emoji"  # font khusus utk karakter emoji, supaya render benar di PowerPoint asli
                                # (Calibri/font teks biasa tidak punya glyph emoji -> muncul kotak/silang)

DARK_BG = "#000000"
CARD_BG = "#161B22"
BORDER = "#2D333B"
TEXT_LIGHT = "#F3F4F6"
TEXT_MUTED = "#9CA3AF"

st.markdown(f"""
<style>
    html, body, [data-testid="stAppViewContainer"], .main {{
        background-color: {DARK_BG} !important;
    }}
    [data-testid="stHeader"] {{ background-color: rgba(0,0,0,0) !important; }}
    [data-testid="stSidebar"] {{ background-color: {CARD_BG} !important; border-right: 1px solid {BORDER}; }}
    [data-testid="stSidebar"] * {{ color: {TEXT_LIGHT} !important; }}
    .block-container {{ padding-top: 1.5rem; }}

    div[data-testid="stMetric"] {{
        background: {CARD_BG} !important;
        border: 1px solid {BORDER};
        border-left: 5px solid {GOLD};
        border-radius: 10px;
        padding: 14px 16px 10px 16px;
    }}
    div[data-testid="stMetricLabel"] * {{ color: {TEXT_MUTED} !important; font-weight: 600; }}
    div[data-testid="stMetricValue"] * {{ color: {TEXT_LIGHT} !important; font-weight: 700; }}
    div[data-testid="stMetricDelta"] * {{ font-weight: 600; }}

    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown {{ color: {TEXT_LIGHT} !important; }}
    h1, h2, h3 {{ color: {GOLD} !important; }}

    .header-banner {{
        background: linear-gradient(90deg, {PRIMARY} 0%, #145C43 100%);
        padding: 22px 200px 22px 28px;
        border-radius: 12px;
        margin-bottom: 18px;
        border: 1px solid {BORDER};
        position: relative;
        min-height: 160px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }}
    .header-banner h1 {{ color: white !important; margin: 0; font-size: 26px; }}
    .header-banner p {{ color: {GOLD} !important; margin: 2px 0 0 0; font-size: 14px; letter-spacing: 0.5px; }}
    .header-logo {{
        position: absolute;
        top: 50%;
        right: 28px;
        transform: translateY(-50%);
        height: 170px;
        width: auto;
    }}
    .section-title {{
        padding-left: 4px;
        margin-top: 6px;
        color: {TEXT_LIGHT} !important;
    }}
    .insight-box {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-left: 5px solid {CHART_GREEN};
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 10px;
    }}
    .insight-box li {{ margin-bottom: 8px; line-height: 1.5; }}

    /* KPI cards (icon + big number + status pill), styled after the RTM report format */
    .kpi-card {{
        background: {CARD_BG};
        border: 1px solid {BORDER};
        border-top: 4px solid var(--accent, {GOLD});
        border-radius: 12px;
        padding: 18px 18px 16px 18px;
        height: 100%;
    }}
    .kpi-icon {{
        width: 40px; height: 40px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 19px; margin-bottom: 10px;
    }}
    .kpi-label {{ color: {TEXT_MUTED} !important; font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
    .kpi-value {{ color: {TEXT_LIGHT} !important; font-size: 28px; font-weight: 800; line-height: 1.15; margin-bottom: 6px; }}
    .kpi-budget {{ color: {TEXT_MUTED} !important; font-size: 12.5px; margin-bottom: 10px; }}
    .kpi-pill {{
        display: inline-block; padding: 5px 12px; border-radius: 20px;
        font-size: 12.5px; font-weight: 700;
    }}
    .kpi-pill-green {{ background: rgba(63,167,114,0.18); color: #6EE7A8 !important; }}
    .kpi-pill-red {{ background: rgba(228,87,76,0.18); color: #FF9A91 !important; }}
    .kpi-pill-amber {{ background: rgba(201,162,39,0.18); color: {GOLD} !important; }}

    .ringkasan-table {{
        width: 100%; border-collapse: collapse; border-radius: 10px; overflow: hidden;
        border: 1px solid {BORDER};
    }}
    .ringkasan-table th {{
        background: {PRIMARY}; color: white !important; text-align: left;
        padding: 10px 14px; font-size: 13px;
    }}
    .ringkasan-table td {{
        padding: 10px 14px; font-size: 13.5px; color: {TEXT_LIGHT} !important;
        border-top: 1px solid {BORDER}; background: {CARD_BG};
    }}
    .ringkasan-table tr:nth-child(even) td {{ background: #1B212B; }}

    .ringkasan-table-sm {{
        width: 100%; border-collapse: separate; border-spacing: 0; border-radius: 8px;
        border: 1px solid {BORDER};
    }}
    .ringkasan-table-sm th {{
        background: {PRIMARY}; color: white !important; text-align: left;
        padding: 8px 12px; font-size: 12.5px; white-space: nowrap;
        position: sticky; top: 0; z-index: 2;
    }}
    .ringkasan-table-sm td {{
        padding: 8px 12px; font-size: 13px; color: {TEXT_LIGHT} !important;
        border-top: 1px solid {BORDER}; background: {CARD_BG}; white-space: nowrap;
    }}
    .ringkasan-table-sm tr:nth-child(even) td {{ background: #1B212B; }}
    .rk-badge {{
        display: inline-block; padding: 4px 10px; border-radius: 14px;
        font-size: 12.5px; font-weight: 700; text-align: center; min-width: 55px;
    }}
    .rk-green {{ background: rgba(63,167,114,0.20); color: #6EE7A8 !important; }}
    .rk-red {{ background: rgba(228,87,76,0.20); color: #FF9A91 !important; }}
    .rk-badge-sm {{
        display: inline-block; padding: 3px 10px; border-radius: 12px;
        font-size: 12px; font-weight: 700; text-align: center; min-width: 48px;
    }}
    .rk-grey {{ background: rgba(156,163,175,0.20); color: {TEXT_MUTED} !important; }}

    [data-testid="stDataFrame"] {{ background-color: {CARD_BG} !important; }}
    .stTextInput input {{ background-color: {CARD_BG} !important; color: {TEXT_LIGHT} !important; }}
</style>
""", unsafe_allow_html=True)

def kpi_card(icon, icon_bg, accent, label, value, budget_text, pill_text, pill_style):
    """Render one KPI card matching the RTM-report visual style (icon circle, big number, status pill)."""
    return f"""
    <div class="kpi-card" style="--accent:{accent}">
        <div class="kpi-icon" style="background:{icon_bg}">{icon}</div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-budget">{budget_text}</div>
        <span class="kpi-pill {pill_style}">{pill_text}</span>
    </div>
    """

def achievement_pill(pct, higher_is_better=True, target_label="Target"):
    """Return (pill_text, pill_style) for a metric vs its target/budget."""
    if pct is None:
        return (f"{target_label} = 0", "kpi-pill-amber")
    if higher_is_better:
        if pct >= 100:
            return (f"✓ {pct:.1f}% — Tercapai", "kpi-pill-green")
        return (f"✗ {pct:.1f}% vs {target_label}", "kpi-pill-red")
    else:
        if pct <= 100:
            return (f"✓ {pct:.1f}% — Under Budget", "kpi-pill-green")
        return (f"✗ {pct:.1f}% — Over Budget", "kpi-pill-red")

# ---------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------
DATA_PATH = Path(__file__).parent / "data_bkms.csv"
MAINT_DATA_PATH = Path(__file__).parent / "data_maintenance.csv"
SPAREPART_DATA_PATH = Path(__file__).parent / "data_sparepart.csv"
SASARAN_MUTU_PATH = Path(__file__).parent / "data_sasaran_mutu.csv"
MTTR_DATA_PATH = Path(__file__).parent / "data_mttr.csv"
METODOLOGI_PPT_PATH = Path(__file__).parent / "Metodologi_Laporan_RTM_BKMS.pptx"
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
KATEGORI_LABEL = {"AB": "Alat Berat (AB)", "TR": "Transportasi (TR)"}


def _file_mtime(path):
    """Waktu modifikasi file -- dipakai sbg bagian KUNCI cache loader CSV di bawah. Tanpa ini, @st.cache_data
    cuma mengenali nama file, jadi kalau isi file di-update (mis. commit baru ke GitHub) aplikasi TETAP
    memakai isi lama dari cache sampai di-reboot."""
    try:
        return Path(path).stat().st_mtime
    except Exception:
        return None


@st.cache_data
def load_data(file, mtime=None) -> pd.DataFrame:
    return pd.read_csv(file)

@st.cache_data
def load_maintenance_data(file, mtime=None) -> pd.DataFrame:
    if not Path(file).exists():
        return pd.DataFrame()
    return pd.read_csv(file)

@st.cache_data
def load_sparepart_data(file, mtime=None) -> pd.DataFrame:
    if not Path(file).exists():
        return pd.DataFrame()
    return pd.read_csv(file)

@st.cache_data
def load_sasaran_mutu_data(file, mtime=None) -> pd.DataFrame:
    if not Path(file).exists():
        return pd.DataFrame()
    return pd.read_csv(file, dtype={"id_unit": str})

@st.cache_data
def load_mttr_data(file, mtime=None) -> pd.DataFrame:
    if not Path(file).exists():
        return pd.DataFrame()
    return pd.read_csv(file)

def load_from_upload(uploaded_file) -> pd.DataFrame:
    """Parse an uploaded 'Gabungan.xlsx' file with the same fixed layout used to build data_bkms.csv.
    Layout (1-indexed columns): A=ID Unit, B=Kode Unit, C=Nama Unit, D=Nilai Asset,
    E=Kriteria Unit, F=Jenis Unit, G-H=Prestasi (R/B), I-J=Pendapatan (R/B), K-L=Upah (R/B),
    M-N=Qty BBM (R/B), O-P=Harga BBM (R/B), Q-R=Biaya BBM (R/B), S-T=Maintenance (R/B),
    U-V=Penyusutan (R/B), W-X=Lainnya (R/B), Y-Z=Biaya Langsung (R/B), AA-AB=Biaya Tdk Langsung (R/B),
    AC-AD=Total Biaya (R/B), AE=Lokasi, AF=Status, AG=Kategori."""
    import openpyxl
    wb = openpyxl.load_workbook(uploaded_file, data_only=True)
    ws = wb[wb.sheetnames[0]]
    month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                 'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
    rows = []
    for r in range(5, ws.max_row + 1):
        id_unit = ws.cell(row=r, column=1).value
        if not id_unit:
            continue
        lokasi = ws.cell(row=r, column=31).value
        bulan_nama = ws.cell(row=r, column=32).value
        kategori = ws.cell(row=r, column=33).value
        if not lokasi or not bulan_nama:
            continue
        rows.append(dict(
            id_unit=id_unit, kode_unit=ws.cell(row=r, column=2).value,
            nama_unit=ws.cell(row=r, column=3).value, nilai_asset=ws.cell(row=r, column=4).value or 0,
            kriteria_unit=ws.cell(row=r, column=5).value, jenis_unit=ws.cell(row=r, column=6).value,
            lokasi=lokasi, bulan=bulan_nama, bulan_no=month_map.get(bulan_nama, 0), kategori=kategori,
            prestasi_realisasi=ws.cell(row=r, column=7).value or 0, prestasi_budget=ws.cell(row=r, column=8).value or 0,
            pendapatan_realisasi=ws.cell(row=r, column=9).value or 0, pendapatan_budget=ws.cell(row=r, column=10).value or 0,
            upah_realisasi=ws.cell(row=r, column=11).value or 0, upah_budget=ws.cell(row=r, column=12).value or 0,
            qty_bbm_realisasi=ws.cell(row=r, column=13).value or 0, qty_bbm_budget=ws.cell(row=r, column=14).value or 0,
            harga_bbm_realisasi=ws.cell(row=r, column=15).value or 0, harga_bbm_budget=ws.cell(row=r, column=16).value or 0,
            biaya_bbm_realisasi=ws.cell(row=r, column=17).value or 0, biaya_bbm_budget=ws.cell(row=r, column=18).value or 0,
            maintenance_realisasi=ws.cell(row=r, column=19).value or 0, maintenance_budget=ws.cell(row=r, column=20).value or 0,
            penyusutan_realisasi=ws.cell(row=r, column=21).value or 0, penyusutan_budget=ws.cell(row=r, column=22).value or 0,
            lainnya_realisasi=ws.cell(row=r, column=23).value or 0, lainnya_budget=ws.cell(row=r, column=24).value or 0,
            biaya_langsung_realisasi=ws.cell(row=r, column=25).value or 0, biaya_langsung_budget=ws.cell(row=r, column=26).value or 0,
            biaya_tidak_langsung_realisasi=ws.cell(row=r, column=27).value or 0, biaya_tidak_langsung_budget=ws.cell(row=r, column=28).value or 0,
            total_biaya_realisasi=ws.cell(row=r, column=29).value or 0, total_biaya_budget=ws.cell(row=r, column=30).value or 0,
        ))
    return pd.DataFrame(rows)

def load_from_upload_realisasi(uploaded_file, base_df) -> pd.DataFrame:
    """Parse file upload Realisasi bulanan per site & kategori (mis. 'AB_Tanjung_Juli_2026.xls').
    Format asli: baris 1=header grup, baris 2=nama kolom, data mulai baris 3, baris TOTAL di akhir (ID Unit kosong).
    Kolom Status & Kategori di dalam file SENGAJA KOSONG -- bulan & kategori diambil dari NAMA FILE
    (format: {KATEGORI}_{SITE}_{BulanIndonesia}_{Tahun}.xls[x]). Nilai yg diupload MENGGABUNG (update)
    ke base_df berdasarkan (id_unit, bulan_no) -- HANYA kolom realisasi yg diperbarui, kolom budget &
    baris/bulan lain yg tidak ada di file upload TETAP UTUH tidak berubah."""
    import re as _re

    # --- 1. Ekstrak Kategori & Bulan dari nama file ---
    fname = Path(getattr(uploaded_file, "name", "")).stem  # tanpa ekstensi
    # Mapping SEMUA alias yg mungkin (singkatan Inggris, nama lengkap Indonesia, singkatan Indonesia) -> kode bulan Inggris
    MONTH_ALIASES = {
        "jan": "Jan", "januari": "Jan",
        "feb": "Feb", "februari": "Feb",
        "mar": "Mar", "maret": "Mar",
        "apr": "Apr", "april": "Apr",
        "may": "May", "mei": "May",
        "jun": "Jun", "juni": "Jun",
        "jul": "Jul", "juli": "Jul",
        "aug": "Aug", "agt": "Aug", "agustus": "Aug",
        "sep": "Sep", "sept": "Sep", "september": "Sep",
        "oct": "Oct", "okt": "Oct", "oktober": "Oct",
        "nov": "Nov", "november": "Nov",
        "dec": "Dec", "des": "Dec", "desember": "Dec",
    }
    month_no_map = {'Jan':1,'Feb':2,'Mar':3,'Apr':4,'May':5,'Jun':6,'Jul':7,'Aug':8,'Sep':9,'Oct':10,'Nov':11,'Dec':12}
    bulan_en = None
    tokens = _re.split(r"[_\-\s]+", fname)
    for tok in tokens:
        match = MONTH_ALIASES.get(tok.strip().lower())
        if match:
            bulan_en = match
            break
    kategori_file = None
    if _re.search(r"(^|[_\s])AB([_\s]|$)", fname, _re.IGNORECASE):
        kategori_file = "AB"
    elif _re.search(r"(^|[_\s])TR([_\s]|$)", fname, _re.IGNORECASE):
        kategori_file = "TR"
    if bulan_en is None:
        raise ValueError(f"Tidak bisa mendeteksi nama bulan dari nama file '{fname}'. Pastikan nama file memuat nama/singkatan bulan (mis. Jan, Juli, Agustus) dipisah underscore.")

    # --- Override lokasi utk ID Unit yg kodenya kebetulan sama dgn unit di site LAIN (duplikasi kode unit
    # antar site) -- supaya realisasinya diarahkan ke site yg benar, bukan ikut site asal file upload ---
    LOKASI_OVERRIDE = {
        "312005": "AMPAH", "312006": "AMPAH", "312025": "AMPAH",
        "342013": "SUNGAI DANAU", "342016": "BUHUT",
    }

    # --- 2. Baca isi file (pakai pandas.read_excel spy kompatibel .xls maupun .xlsx sekaligus) ---
    raw = pd.read_excel(uploaded_file, header=None, sheet_name=0)
    rows = []
    for r in range(2, len(raw)):
        id_unit_raw = raw.iat[r, 0]
        if pd.isna(id_unit_raw) or str(id_unit_raw).strip() == "":
            continue  # lewati baris TOTAL/kosong di akhir
        kode_unit = str(id_unit_raw).strip()
        if kode_unit.endswith(".0"):  # kalau ID Unit terbaca sbg angka float oleh pandas
            kode_unit = kode_unit[:-2]
        id_unit = kode_unit.replace("-", "")
        # Normalisasi format kode_unit: SELALU pakai tanda "-" (3 digit pertama - 3 digit sisanya), tdk peduli
        # apakah di file Excel aslinya sdh pakai strip atau tidak (mis. "331004" ditulis polos tanpa strip di
        # source file) -- spy konsisten dgn format kode_unit yg sudah ada di data lain ("331-004").
        if "-" not in kode_unit and kode_unit.isdigit() and len(kode_unit) >= 4:
            kode_unit = kode_unit[:3] + "-" + kode_unit[3:]
        lokasi_cell = raw.iat[r, 14]
        lokasi_final = LOKASI_OVERRIDE.get(id_unit, str(lokasi_cell).strip().upper() if not pd.isna(lokasi_cell) else None)
        def _cell(col):
            v = raw.iat[r, col]
            return 0 if pd.isna(v) else v
        rows.append(dict(
            id_unit=id_unit, kode_unit=kode_unit,
            nama_unit=raw.iat[r, 1],
            lokasi=lokasi_final,
            bulan=bulan_en, bulan_no=month_no_map[bulan_en],
            kategori=kategori_file,
            prestasi_realisasi=_cell(2), pendapatan_realisasi=_cell(3), upah_realisasi=_cell(4),
            qty_bbm_realisasi=_cell(5), harga_bbm_realisasi=_cell(6), biaya_bbm_realisasi=_cell(7),
            maintenance_realisasi=_cell(8), penyusutan_realisasi=_cell(9), lainnya_realisasi=_cell(10),
            biaya_langsung_realisasi=_cell(11), biaya_tidak_langsung_realisasi=_cell(12), total_biaya_realisasi=_cell(13),
        ))
    upload_df = pd.DataFrame(rows)
    if upload_df.empty:
        return base_df, 0, 0

    realisasi_cols = ["prestasi_realisasi", "pendapatan_realisasi", "upah_realisasi", "qty_bbm_realisasi",
                       "harga_bbm_realisasi", "biaya_bbm_realisasi", "maintenance_realisasi", "penyusutan_realisasi",
                       "lainnya_realisasi", "biaya_langsung_realisasi", "biaya_tidak_langsung_realisasi", "total_biaya_realisasi"]

    result = base_df.copy()
    result["id_unit"] = result["id_unit"].astype(str)
    upload_df["id_unit"] = upload_df["id_unit"].astype(str)
    # PENTING: kunci gabung HARUS menyertakan Lokasi juga, bukan cuma (id_unit, bulan_no) --
    # ID Unit ternyata BISA SAMA/bertabrakan antar site berbeda (mis. "312005" muncul di AMPAH & di file
    # upload Tanjung) -- kalau cuma pakai (id_unit, bulan_no), data bisa salah ke-update ke site yg keliru.
    result = result.set_index(["id_unit", "lokasi", "bulan_no"])
    upload_idx = upload_df.set_index(["id_unit", "lokasi", "bulan_no"])

    matched_keys = result.index.intersection(upload_idx.index)
    for col in realisasi_cols:
        result.loc[matched_keys, col] = upload_idx.loc[matched_keys, col]
    n_updated = len(matched_keys)

    # --- Unit yg BELUM ADA di data existing (blm py budget) -- ditambahkan sbg baris BARU, bukan dilewati,
    # supaya realisasinya tetap tercatat (Budget & kolom lain yg blm diketahui diisi 0/NaN sbg placeholder) ---
    unmatched_keys = upload_idx.index.difference(result.index)
    n_unmatched = len(unmatched_keys)
    new_rows_detail = pd.DataFrame()  # dikembalikan jg ke pemanggil, spy bisa DITAMPILKAN di layar (bukan cuma dihitung)
    if n_unmatched:
        budget_cols = ["prestasi_budget", "pendapatan_budget", "upah_budget", "qty_bbm_budget", "harga_bbm_budget",
                       "biaya_bbm_budget", "maintenance_budget", "penyusutan_budget", "lainnya_budget",
                       "biaya_langsung_budget", "biaya_tidak_langsung_budget", "total_biaya_budget"]
        new_rows = upload_df[upload_df.set_index(["id_unit", "lokasi", "bulan_no"]).index.isin(unmatched_keys)].copy()
        for col in budget_cols:
            new_rows[col] = 0
        # --- Lookup metadata (kelompok_unit, kriteria_unit, jenis_unit, kategori) dari bulan LAIN yg sudah ada
        # utk unit yg SAMA (kode_unit+lokasi) -- spy unit yg sudah dikenal di bulan lain TIDAK kehilangan
        # info kelompok/kriteria/jenis-nya cuma krn baris bulan ini baru pertama kali ditambahkan. Kalau
        # benar2 unit BARU (tdk ditemukan di bulan manapun), baru diisi None (perlu dilengkapi manual). ---
        _meta_cols = ["kelompok_unit", "kriteria_unit", "jenis_unit"]
        _meta_lookup = (base_df.dropna(subset=["kode_unit"])
                         .drop_duplicates(subset=["kode_unit", "lokasi"], keep="last")
                         .set_index(["kode_unit", "lokasi"])[_meta_cols])
        for col in _meta_cols:
            new_rows[col] = None
        for idx in new_rows.index:
            _key = (new_rows.at[idx, "kode_unit"], new_rows.at[idx, "lokasi"])
            if _key in _meta_lookup.index:
                for col in _meta_cols:
                    new_rows.at[idx, col] = _meta_lookup.loc[_key, col]
        new_rows_detail = new_rows[["id_unit", "nama_unit", "lokasi", "bulan", "kategori", "pendapatan_realisasi", "total_biaya_realisasi"]].copy()
        result = result.reset_index()
        result = pd.concat([result, new_rows], ignore_index=True, sort=False)
        result = result.set_index(["id_unit", "lokasi", "bulan_no"])

    result = result.reset_index()
    return result, n_updated, n_unmatched, new_rows_detail


def load_from_upload_maintenance(uploaded_file) -> pd.DataFrame:
    """Parse an uploaded maintenance detail file (e.g. 'Pemeliharaan_sd_Bulan.xls').
    DESCRIPTION format: 'PEMELIHARAAN (RUTIN|NON RUTIN) (kategori) (tipe biaya) (PLANTATION|MINING) (site) - (unit)'
    """
    raw = pd.read_excel(uploaded_file, sheet_name=0, header=0)
    pattern = re.compile(
        r'^PEMELIHARAAN\s+(RUTIN|NON RUTIN)\s+(.*?)\s+(SPAREPART|ALOKASI WORKSHOP|SERVICE LUAR|LAIN-LAIN)\s+(PLANTATION|MINING)\s+(.*?)\s+-\s+(.*)$'
    )
    month_id_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                     7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    raw["FDATE"] = pd.to_datetime(raw["FDATE"], errors="coerce")
    raw = raw.dropna(subset=["FDATE", "DESCRIPTION", "FAMOUNT_RP"])
    raw = raw[raw["FDATE"].dt.year >= 2000]

    rows = []
    for _, r in raw.iterrows():
        desc = str(r["DESCRIPTION"]).strip()
        m = pattern.match(desc)
        if not m:
            continue
        jenis, kategori_sparepart, tipe_biaya, kelompok, lokasi, unit = m.groups()
        dt = r["FDATE"]
        rows.append(dict(
            tanggal=dt.date().isoformat(), bulan=month_id_map.get(dt.month, ''), bulan_no=dt.month,
            lokasi=lokasi.strip(), kelompok=kelompok.strip(),
            jenis_pemeliharaan=jenis.strip(), kategori_sparepart=kategori_sparepart.strip(),
            tipe_biaya=tipe_biaya.strip(), nama_unit=unit.strip(),
            biaya=float(r["FAMOUNT_RP"]),
            keterangan=str(r["FREMARK"]) if pd.notna(r["FREMARK"]) else '',
        ))
    return pd.DataFrame(rows)

@st.cache_data
def build_perhitungan_detail_excel(df_raw, sasaran_mutu_raw, mttr_raw, maint_data_raw, site_list, month_list, kat_list) -> bytes:
    """Bangun Excel 'Perhitungan Detail PPT' dgn 3 sheet Ringkasan (Plantation-TR, Plantation-AB, Mining) yang
    ANGKANYA berupa FORMULA EXCEL (SUMIFS/AVERAGEIFS) merujuk ke sheet detail data mentah -- termasuk rincian
    per Site & Jenis Unit utk Slide 1 (Prestasi/Utilisasi/Availability), Slide 2 (BTL & Analisa BBM),
    Slide 3 (Gap Maintenance & Rutin/Non-Rutin), Slide 4 (Downtime & Kategori Sparepart)."""
    import io as _io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    HEADER_FILL = PatternFill(start_color="1A2744", end_color="1A2744", fill_type="solid")
    HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    SECTION_FILL = PatternFill(start_color="C98A1E", end_color="C98A1E", fill_type="solid")
    SUB_FILL = PatternFill(start_color="E8ECF3", end_color="E8ECF3", fill_type="solid")
    NORMAL_FONT = Font(name="Arial", size=10)
    BOLD_FONT = Font(name="Arial", size=10, bold=True)
    thin = Side(style="thin", color="D9D9D9")
    BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

    MINING_SITES = ["TANJUNG", "BUHUT", "BUHUT LHL", "AMPAH"]
    PLANTATION_SITES = ["SUNGAI DANAU", "KUMAI"]
    BLOK_TR = "PLANTATION - TRANSPORTASI"
    BLOK_AB = "PLANTATION - ALAT BERAT"
    BLOK_MINING = "MINING"

    def bbm_valid_mask(d):
        bad_r = (d["qty_bbm_realisasi"] > 0) & (d["biaya_bbm_realisasi"].fillna(0) == 0)
        bad_b = (d["qty_bbm_budget"] > 0) & (d["biaya_bbm_budget"].fillna(0) == 0)
        return ~(bad_r | bad_b)

    # =============== 1. SIAPKAN DATA UTAMA (terapkan filter & aturan Mining=AB) ===============
    data_all = df_raw[
        df_raw["lokasi"].isin(site_list) & df_raw["bulan"].isin(month_list) & df_raw["kategori"].isin(kat_list)
    ].copy() if (site_list and month_list and kat_list) else pd.DataFrame()
    sasaran_all = sasaran_mutu_raw[
        sasaran_mutu_raw["lokasi"].isin(site_list) & sasaran_mutu_raw["bulan"].isin(month_list) & sasaran_mutu_raw["kategori"].isin(kat_list)
    ].copy() if (sasaran_mutu_raw is not None and not sasaran_mutu_raw.empty and site_list and month_list and kat_list) else pd.DataFrame()
    mttr_all = mttr_raw[mttr_raw["lokasi"].isin(site_list)].copy() if (mttr_raw is not None and not mttr_raw.empty and "lokasi" in mttr_raw.columns and site_list) else pd.DataFrame()
    maint_all = maint_data_raw[maint_data_raw["lokasi"].isin(site_list)].copy() if (maint_data_raw is not None and not maint_data_raw.empty and "lokasi" in maint_data_raw.columns and site_list) else pd.DataFrame()
    if not maint_all.empty and "bulan" in maint_all.columns:
        maint_all = maint_all[maint_all["bulan"].isin(month_list)]

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    if data_all.empty:
        ws_empty = wb.create_sheet("Ringkasan")
        ws_empty["A1"] = "Tidak ada data untuk filter Site/Bulan/Kategori yang dipilih."
        buf = _io.BytesIO(); wb.save(buf); return buf.getvalue()

    data_all.loc[data_all["lokasi"].isin(MINING_SITES), "kategori"] = "AB"
    if not sasaran_all.empty:
        sasaran_all.loc[sasaran_all["lokasi"].isin(MINING_SITES), "kategori"] = "AB"

    data_all["_blok"] = None
    data_all.loc[data_all["lokasi"].isin(MINING_SITES), "_blok"] = BLOK_MINING
    data_all.loc[(data_all["lokasi"].isin(PLANTATION_SITES)) & (data_all["kategori"] == "TR"), "_blok"] = BLOK_TR
    data_all.loc[(data_all["lokasi"].isin(PLANTATION_SITES)) & (data_all["kategori"] == "AB"), "_blok"] = BLOK_AB

    if not sasaran_all.empty:
        # Kriteria unit (Floating Tarif / Tarif Tetap) dari data BKMS -- sama dgn slide KPI PPT
        sasaran_all = tandai_kriteria_sasaran_mutu(sasaran_all, df_raw)
        sasaran_all["_blok"] = None
        sasaran_all.loc[sasaran_all["lokasi"].isin(MINING_SITES), "_blok"] = BLOK_MINING
        sasaran_all.loc[(sasaran_all["lokasi"].isin(PLANTATION_SITES)) & (sasaran_all["kategori"] == "TR"), "_blok"] = BLOK_TR
        sasaran_all.loc[(sasaran_all["lokasi"].isin(PLANTATION_SITES)) & (sasaran_all["kategori"] == "AB"), "_blok"] = BLOK_AB

    if not mttr_all.empty:
        mttr_all["_blok"] = None
        if "kategori" in mttr_all.columns:
            mttr_cat = mttr_all["kategori"].where(~mttr_all["lokasi"].isin(MINING_SITES), "AB")
            mttr_all.loc[mttr_all["lokasi"].isin(MINING_SITES), "_blok"] = BLOK_MINING
            mttr_all.loc[(mttr_all["lokasi"].isin(PLANTATION_SITES)) & (mttr_cat == "TR"), "_blok"] = BLOK_TR
            mttr_all.loc[(mttr_all["lokasi"].isin(PLANTATION_SITES)) & (mttr_cat == "AB"), "_blok"] = BLOK_AB
        else:
            mttr_all.loc[mttr_all["lokasi"].isin(MINING_SITES), "_blok"] = BLOK_MINING
            mttr_all.loc[mttr_all["lokasi"].isin(PLANTATION_SITES), "_blok"] = BLOK_TR

    # Lookup jenis_unit, kategori & kelompok_unit via nama_unit utk maint_all (data_maintenance.csv tdk selalu py kolom2 ini langsung)
    if not maint_all.empty:
        _lk_all = lookup_atribut_unit(maint_all, data_all, [c for c in ["jenis_unit", "_blok", "kelompok_unit"] if c in data_all.columns])
        if "jenis_unit" not in maint_all.columns or maint_all["jenis_unit"].isna().all():
            maint_all["jenis_unit"] = _lk_all["jenis_unit"] if "jenis_unit" in _lk_all.columns else None
        maint_all["_blok"] = _lk_all["_blok"] if "_blok" in _lk_all.columns else None
        if "kelompok_unit" in _lk_all.columns:
            maint_all["kelompok_unit"] = _lk_all["kelompok_unit"]
        maint_all = maint_all.dropna(subset=["jenis_unit", "_blok"]) if "jenis_unit" in maint_all.columns else pd.DataFrame()

    blok_list = [b for b in [BLOK_TR, BLOK_AB, BLOK_MINING] if (data_all["_blok"] == b).any()]

    def uniq_lokasi_jenis(df_, blok):
        if df_ is None or df_.empty or "_blok" not in df_.columns or "jenis_unit" not in df_.columns:
            return []
        sub = df_[df_["_blok"] == blok]
        if sub.empty:
            return []
        combos = sub.dropna(subset=["jenis_unit"])[["lokasi", "jenis_unit"]].drop_duplicates()
        return sorted(combos.itertuples(index=False, name=None))

    def uniq_lokasi_kelompok(df_, blok, exclude_tarif_tetap=True, exclude_unit_sewa=True):
        """Sama spt uniq_lokasi_jenis tapi berbasis KELOMPOK UNIT, & scr default MENGECUALIKAN unit berkriteria
        'Tarif Tetap' (kolom kriteria_unit ATAU jenis_unit=='Tarif Tetap' di Sasaran Mutu) dan unit_sewa=True --
        krn pendapatannya tdk terpengaruh Utilisasi/Availability/Downtime, jadi tdk relevan dibandingkan."""
        if df_ is None or df_.empty or "_blok" not in df_.columns or "kelompok_unit" not in df_.columns:
            return []
        sub = df_[df_["_blok"] == blok]
        if sub.empty:
            return []
        if exclude_tarif_tetap:
            if "kriteria_unit" in sub.columns:
                sub = sub[sub["kriteria_unit"] != "Tarif Tetap"]
            elif "jenis_unit" in sub.columns:
                sub = sub[sub["jenis_unit"] != "Tarif Tetap"]
        if exclude_unit_sewa and "unit_sewa" in sub.columns:
            sub = sub[sub["unit_sewa"] != True]
        combos = sub.dropna(subset=["kelompok_unit"])[["lokasi", "kelompok_unit"]].drop_duplicates()
        # Urutkan berdasarkan KELOMPOK UNIT dulu, baru LOKASI -- spy site dgn kelompok unit yg sama berdampingan
        return sorted(combos.itertuples(index=False, name=None), key=lambda x: (x[1], x[0]))

    # =============== 2. SHEET DETAIL: Prestasi ===============
    ws_prestasi = wb.create_sheet("Detail - Prestasi")
    cols_prestasi = ["Blok", "Lokasi", "Kode Unit", "Nama Unit", "Jenis Unit", "Kriteria Unit", "Bulan",
                      "Prestasi Realisasi", "Prestasi Budget", "Kelompok Unit"]
    for c, h in enumerate(cols_prestasi, start=1):
        cell = ws_prestasi.cell(row=1, column=c, value=h)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
    _kelompok_col_bkms = "kelompok_unit" if "kelompok_unit" in data_all.columns else None
    prestasi_src = data_all[data_all["_blok"].notna()][["_blok", "lokasi", "kode_unit", "nama_unit", "jenis_unit", "kriteria_unit", "bulan", "prestasi_realisasi", "prestasi_budget"]].copy()
    prestasi_src["kelompok_unit"] = data_all.loc[data_all["_blok"].notna(), _kelompok_col_bkms] if _kelompok_col_bkms else None
    for ri, row in enumerate(prestasi_src.itertuples(index=False), start=2):
        for ci, val in enumerate(row, start=1):
            cell = ws_prestasi.cell(row=ri, column=ci, value=(None if pd.isna(val) else val))
            cell.border = BORDER; cell.font = NORMAL_FONT
    ws_prestasi.freeze_panes = "A2"; ws_prestasi.auto_filter.ref = ws_prestasi.dimensions

    # =============== 3. SHEET DETAIL: Sasaran Mutu ===============
    ws_sm = wb.create_sheet("Detail - Sasaran Mutu")
    cols_sm = ["Blok", "Lokasi", "Jenis Unit", "Bulan", "Utilisasi Realisasi", "Utilisasi Target",
               "Availability Realisasi", "Availability Target", "Downtime Realisasi", "Downtime Target",
               "ID Unit", "Kode Unit", "Nama Unit", "Kelompok Unit", "Unit Sewa",
               "Efektif (HM/KM)", "Standby (HM/KM)", "Breakdown (HM/KM)", "Tersedia (HM/KM)", "Ideal (HM/KM)",
               "Kriteria Unit"]
    for c, h in enumerate(cols_sm, start=1):
        cell = ws_sm.cell(row=1, column=c, value=h)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
    if not sasaran_all.empty:
        sm_src = sasaran_all[sasaran_all["_blok"].notna()].copy()
        sm_src["downtime_pct"] = sm_src["downtime_pct"].fillna(0)
        for col in ["id_unit", "kode_unit", "nama_unit", "kelompok_unit", "unit_sewa",
                    "efektif_hm_km_realisasi", "standby_hm_km_realisasi", "breakdown_hm_km_realisasi",
                    "tersedia_hm_km_realisasi", "hm_km_ideal_target", "kriteria_unit"]:
            if col not in sm_src.columns:
                sm_src[col] = None
        sm_src = sm_src[["_blok", "lokasi", "jenis_unit", "bulan", "utilisasi_pct", "utilisasi_target",
                          "availability_pct", "availability_target", "downtime_pct", "downtime_target",
                          "id_unit", "kode_unit", "nama_unit", "kelompok_unit", "unit_sewa",
                          "efektif_hm_km_realisasi", "standby_hm_km_realisasi", "breakdown_hm_km_realisasi",
                          "tersedia_hm_km_realisasi", "hm_km_ideal_target", "kriteria_unit"]]
        for ri, row in enumerate(sm_src.itertuples(index=False), start=2):
            for ci, val in enumerate(row, start=1):
                cell = ws_sm.cell(row=ri, column=ci, value=(None if pd.isna(val) else val))
                cell.border = BORDER; cell.font = NORMAL_FONT
    ws_sm.freeze_panes = "A2"; ws_sm.auto_filter.ref = ws_sm.dimensions

    # =============== 4. SHEET DETAIL: Biaya (+ Jenis Unit utk breakdown Maintenance) ===============
    ws_biaya = wb.create_sheet("Detail - Biaya")
    cols_biaya = ["Blok", "Lokasi", "Kode Unit", "Nama Unit", "Jenis Unit", "Bulan",
                  "Total Biaya Realisasi", "Total Biaya Budget",
                  "Maintenance Realisasi", "Maintenance Budget",
                  "Upah Realisasi", "Upah Budget",
                  "Lainnya Realisasi", "Lainnya Budget",
                  "Biaya Langsung Realisasi", "Biaya Langsung Budget",
                  "Biaya T.Langsung Realisasi", "Biaya T.Langsung Budget", "Kelompok Unit",
                  "Pendapatan Realisasi", "Pendapatan Budget"]
    for c, h in enumerate(cols_biaya, start=1):
        cell = ws_biaya.cell(row=1, column=c, value=h)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
    biaya_src = data_all[data_all["_blok"].notna()][["_blok", "lokasi", "kode_unit", "nama_unit", "jenis_unit", "bulan",
        "total_biaya_realisasi", "total_biaya_budget", "maintenance_realisasi", "maintenance_budget",
        "upah_realisasi", "upah_budget", "lainnya_realisasi", "lainnya_budget",
        "biaya_langsung_realisasi", "biaya_langsung_budget", "biaya_tidak_langsung_realisasi", "biaya_tidak_langsung_budget",
        "pendapatan_realisasi", "pendapatan_budget"]].copy()
    biaya_src.insert(18, "kelompok_unit", data_all.loc[data_all["_blok"].notna(), _kelompok_col_bkms] if _kelompok_col_bkms else None)
    for ri, row in enumerate(biaya_src.itertuples(index=False), start=2):
        for ci, val in enumerate(row, start=1):
            cell = ws_biaya.cell(row=ri, column=ci, value=(None if pd.isna(val) else val))
            cell.border = BORDER; cell.font = NORMAL_FONT
    ws_biaya.freeze_panes = "A2"; ws_biaya.auto_filter.ref = ws_biaya.dimensions

    # =============== 5. SHEET DETAIL: BBM (valid saja) ===============
    ws_bbm = wb.create_sheet("Detail - BBM (Valid)")
    cols_bbm = ["Blok", "Lokasi", "Kode Unit", "Nama Unit", "Jenis Unit", "Bulan",
                "Qty BBM Realisasi", "Qty BBM Budget", "Biaya BBM Realisasi", "Biaya BBM Budget",
                "Prestasi Realisasi", "Prestasi Budget"]
    for c, h in enumerate(cols_bbm, start=1):
        cell = ws_bbm.cell(row=1, column=c, value=h)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
    data_bbm_valid = data_all[data_all["_blok"].notna() & bbm_valid_mask(data_all)]
    bbm_src = data_bbm_valid[["_blok", "lokasi", "kode_unit", "nama_unit", "jenis_unit", "bulan",
                               "qty_bbm_realisasi", "qty_bbm_budget", "biaya_bbm_realisasi", "biaya_bbm_budget",
                               "prestasi_realisasi", "prestasi_budget"]]
    for ri, row in enumerate(bbm_src.itertuples(index=False), start=2):
        for ci, val in enumerate(row, start=1):
            cell = ws_bbm.cell(row=ri, column=ci, value=(None if pd.isna(val) else val))
            cell.border = BORDER; cell.font = NORMAL_FONT
    ws_bbm.freeze_panes = "A2"; ws_bbm.auto_filter.ref = ws_bbm.dimensions

    # =============== 5b. SHEET DETAIL: BBM utk Analisa Kenaikan (aturan filter & rumus BEDA dari di atas,
    # PERSIS mengikuti kode PPT: Qty/Biaya/Prestasi per baris HARUS lengkap ketiganya (realisasi & budget
    # dicek terpisah) -- kalau cuma sebagian yg terisi, qty & prestasi baris itu di-NOL-kan, bukan dibuang) ===
    ws_bbm3 = wb.create_sheet("Detail - BBM Analisa Konsumsi")
    cols_bbm3 = ["Blok", "Lokasi", "Kategori", "Kode Unit", "Nama Unit", "Jenis Unit", "Bulan",
                 "Qty BBM Realisasi", "Qty BBM Budget", "Prestasi Realisasi", "Prestasi Budget",
                 "Biaya BBM Realisasi", "Biaya BBM Budget", "Kelompok Unit"]
    for c, h in enumerate(cols_bbm3, start=1):
        cell = ws_bbm3.cell(row=1, column=c, value=h)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
    data_bbm3 = data_all[data_all["_blok"].notna()].copy()
    valid_r3 = (data_bbm3["qty_bbm_realisasi"].fillna(0) > 0) & (data_bbm3["biaya_bbm_realisasi"].fillna(0) > 0) & (data_bbm3["prestasi_realisasi"].fillna(0) > 0)
    partial_r3 = (~valid_r3) & ((data_bbm3["qty_bbm_realisasi"].fillna(0) > 0) | (data_bbm3["prestasi_realisasi"].fillna(0) > 0))
    data_bbm3.loc[partial_r3, ["qty_bbm_realisasi", "prestasi_realisasi"]] = 0
    valid_b3 = (data_bbm3["qty_bbm_budget"].fillna(0) > 0) & (data_bbm3["biaya_bbm_budget"].fillna(0) > 0) & (data_bbm3["prestasi_budget"].fillna(0) > 0)
    partial_b3 = (~valid_b3) & ((data_bbm3["qty_bbm_budget"].fillna(0) > 0) | (data_bbm3["prestasi_budget"].fillna(0) > 0))
    data_bbm3.loc[partial_b3, ["qty_bbm_budget", "prestasi_budget"]] = 0
    bbm3_src = data_bbm3[["_blok", "lokasi", "kategori", "kode_unit", "nama_unit", "jenis_unit", "bulan",
                           "qty_bbm_realisasi", "qty_bbm_budget", "prestasi_realisasi", "prestasi_budget",
                           "biaya_bbm_realisasi", "biaya_bbm_budget"]].copy()
    bbm3_src["kelompok_unit"] = data_bbm3[_kelompok_col_bkms] if _kelompok_col_bkms else None
    for ri, row in enumerate(bbm3_src.itertuples(index=False), start=2):
        for ci, val in enumerate(row, start=1):
            cell = ws_bbm3.cell(row=ri, column=ci, value=(None if pd.isna(val) else val))
            cell.border = BORDER; cell.font = NORMAL_FONT
    ws_bbm3.freeze_panes = "A2"; ws_bbm3.auto_filter.ref = ws_bbm3.dimensions

    # =============== 6. SHEET DETAIL: MTTR ===============
    ws_mttr = wb.create_sheet("Detail - MTTR")
    cols_mttr = ["Blok", "Lokasi", "Kode Unit", "Nama Unit", "Bulan", "Jumlah Jam"]
    for c, h in enumerate(cols_mttr, start=1):
        cell = ws_mttr.cell(row=1, column=c, value=h)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
    if not mttr_all.empty and "jumlah_jam" in mttr_all.columns:
        mttr_src = mttr_all[mttr_all["_blok"].notna()].copy()
        for col in ["kode_unit", "nama_unit", "bulan"]:
            if col not in mttr_src.columns:
                mttr_src[col] = None
        mttr_src = mttr_src[["_blok", "lokasi", "kode_unit", "nama_unit", "bulan", "jumlah_jam"]]
        for ri, row in enumerate(mttr_src.itertuples(index=False), start=2):
            for ci, val in enumerate(row, start=1):
                cell = ws_mttr.cell(row=ri, column=ci, value=(None if pd.isna(val) else val))
                cell.border = BORDER; cell.font = NORMAL_FONT
    ws_mttr.freeze_panes = "A2"; ws_mttr.auto_filter.ref = ws_mttr.dimensions

    # =============== 7. SHEET DETAIL: Maintenance Log (Rutin/NonRutin & Sparepart) ===============
    ws_ml = wb.create_sheet("Detail - Maintenance Log")
    cols_ml = ["Blok", "Lokasi", "Jenis Unit", "Bulan", "Jenis Pemeliharaan", "Kategori Sparepart", "Biaya", "Kelompok Unit"]
    for c, h in enumerate(cols_ml, start=1):
        cell = ws_ml.cell(row=1, column=c, value=h)
        cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
    if not maint_all.empty:
        ml_cols = ["_blok", "lokasi", "jenis_unit", "bulan", "jenis_pemeliharaan", "kategori_sparepart", "biaya"]
        ml_cols = [c for c in ml_cols if c in maint_all.columns]
        ml_src = maint_all[ml_cols].copy()
        ml_src["kelompok_unit"] = maint_all["kelompok_unit"] if "kelompok_unit" in maint_all.columns else None
        for ri, row in enumerate(ml_src.itertuples(index=False), start=2):
            for ci, val in enumerate(row, start=1):
                cell = ws_ml.cell(row=ri, column=ci, value=(None if pd.isna(val) else val))
                cell.border = BORDER; cell.font = NORMAL_FONT
    ws_ml.freeze_panes = "A2"; ws_ml.auto_filter.ref = ws_ml.dimensions

    # =============== 8. SHEET RINGKASAN (formula-driven) x3 ===============
    SHEET_PRESTASI = "'Detail - Prestasi'"
    SHEET_SM = "'Detail - Sasaran Mutu'"
    SHEET_BIAYA = "'Detail - Biaya'"
    SHEET_BBM = "'Detail - BBM (Valid)'"
    SHEET_BBM3 = "'Detail - BBM Analisa Konsumsi'"
    SHEET_MTTR = "'Detail - MTTR'"
    SHEET_ML = "'Detail - Maintenance Log'"

    def build_ringkasan_sheet(sheet_title, blok_name, has_data):
        ws = wb.create_sheet(sheet_title)
        r = [1]
        B = blok_name.replace('"', '""')

        def sect(title):
            row = r[0]
            ws.cell(row=row, column=1, value=title)
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            c = ws.cell(row=row, column=1)
            c.fill = SECTION_FILL; c.font = Font(name="Arial", bold=True, color="FFFFFF", size=12)
            c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
            ws.row_dimensions[row].height = 22
            r[0] += 2

        def subsect(title):
            row = r[0]
            ws.cell(row=row, column=1, value=title)
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
            c = ws.cell(row=row, column=1)
            c.fill = SUB_FILL; c.font = Font(name="Arial", bold=True, color="1A2744", size=10.5)
            c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
            r[0] += 1

        def header(cols=("Metrik", "Realisasi", "Budget", "Hasil")):
            row = r[0]
            for c, h in enumerate(cols, start=1):
                cell = ws.cell(row=row, column=c, value=h)
                cell.fill = HEADER_FILL; cell.font = HEADER_FONT; cell.border = BORDER
            r[0] += 1

        def metric_row(nama, formula_real, formula_budget, fmt_real=None, fmt_hasil='0.0"%"', hasil_formula=None):
            row = r[0]
            ws.cell(row=row, column=1, value=nama).font = NORMAL_FONT
            # Bungkus otomatis dgn IFERROR(...,0) supaya tdk muncul #DIV/0!/#N/A kalau tdk ada data yg cocok
            fr = formula_real[1:] if formula_real.startswith("=") else formula_real
            fb = formula_budget[1:] if formula_budget.startswith("=") else formula_budget
            c_real = ws.cell(row=row, column=2, value=f'=IFERROR({fr},0)'); c_real.font = NORMAL_FONT
            c_budget = ws.cell(row=row, column=3, value=f'=IFERROR({fb},0)'); c_budget.font = NORMAL_FONT
            hf = hasil_formula if hasil_formula else f'=IFERROR(B{row}/C{row}*100,"-")'
            c_hasil = ws.cell(row=row, column=4, value=hf); c_hasil.font = BOLD_FONT
            if fmt_real: c_real.number_format = fmt_real; c_budget.number_format = fmt_real
            if fmt_hasil: c_hasil.number_format = fmt_hasil
            for c in range(1, 5):
                ws.cell(row=row, column=c).border = BORDER
                ws.cell(row=row, column=c).alignment = Alignment(vertical="center")
            r[0] += 1

        if not has_data:
            ws.cell(row=1, column=1, value=f"Tidak ada data untuk blok {blok_name} sesuai filter yang dipilih.")
            return

        # ============ SLIDE 1: KPI Dashboard ============
        sect(f"\U0001F4CA {blok_name} \u2014 KPI Dashboard (Slide 1)")
        header()
        metric_row("Capaian Prestasi",
            f'=SUMIFS({SHEET_PRESTASI}!H:H,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!F:F,"Floating Tarif")',
            f'=SUMIFS({SHEET_PRESTASI}!I:I,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!F:F,"Floating Tarif")', fmt_real="#,##0")

        def write_grouped_target_metric(nama_metrik, realisasi_col, target_col, target_series, fmt_real="0.00"):
            """Metodologi Capaian Utilisasi/Availability/Downtime yg BENAR: kelompokkan per nilai TARGET unik
            (bukan average langsung semua baris, krn 1 blok bisa py BEBERAPA target berbeda & average langsung
            akan bias ke target dgn jumlah unit terbanyak). Realisasi tiap kelompok di-average dulu, Capaian
            dihitung per kelompok, baru hasil akhir = average SEDERHANA dari nilai per-kelompok (bobot sama)."""
            unique_targets = sorted(target_series.dropna().unique().tolist()) if target_series is not None else []
            main_row = r[0]
            r[0] += 1  # baris utama ditulis di akhir, reserve dulu nomor barisnya
            group_rows = []
            if unique_targets:
                for tval in unique_targets:
                    row = r[0]
                    tval_disp = int(tval) if float(tval).is_integer() else tval
                    ws.cell(row=row, column=1, value=f"   \u21B3 Kelompok Target = {tval_disp}").font = Font(name="Arial", size=9.5, italic=True, color="6B7480")
                    c_r = ws.cell(row=row, column=2, value=f'=AVERAGEIFS({SHEET_SM}!{realisasi_col}:{realisasi_col},{SHEET_SM}!A:A,"{B}",{SHEET_SM}!{target_col}:{target_col},{tval})')
                    c_t = ws.cell(row=row, column=3, value=tval)
                    c_h = ws.cell(row=row, column=4, value=f'=IFERROR(B{row}/C{row}*100,"-")')
                    c_r.number_format = fmt_real; c_t.number_format = fmt_real; c_h.number_format = '0.0"%"'
                    _small_font = Font(name="Consolas", size=9, color="6B7480")
                    c_r.font = _small_font; c_t.font = Font(name="Consolas", size=9, color="6B7480")
                    c_h.font = Font(name="Consolas", size=9, italic=True, color="6B7480")
                    for c in range(1, 5):
                        ws.cell(row=row, column=c).border = BORDER
                    group_rows.append(row)
                    r[0] += 1
            # Tulis baris utama: Realisasi & Target ditampilkan = AVERAGE dari nilai per-kelompok (bkn semua baris),
            # Capaian = AVERAGE dari Capaian tiap kelompok (kolom D pada baris2 kelompok di atas)
            ws.cell(row=main_row, column=1, value=nama_metrik).font = NORMAL_FONT
            if group_rows:
                refs = ",".join(f"B{gr}" for gr in group_rows)
                refs_t = ",".join(f"C{gr}" for gr in group_rows)
                refs_h = ",".join(f"D{gr}" for gr in group_rows)
                c_real = ws.cell(row=main_row, column=2, value=f'=AVERAGE({refs})')
                c_budget = ws.cell(row=main_row, column=3, value=f'=AVERAGE({refs_t})')
                c_hasil = ws.cell(row=main_row, column=4, value=f'=IFERROR(AVERAGE({refs_h}),"-")')
            else:
                c_real = ws.cell(row=main_row, column=2, value=0)
                c_budget = ws.cell(row=main_row, column=3, value=0)
                c_hasil = ws.cell(row=main_row, column=4, value="-")
            c_real.font = NORMAL_FONT; c_budget.font = NORMAL_FONT; c_hasil.font = BOLD_FONT
            c_real.number_format = fmt_real; c_budget.number_format = fmt_real; c_hasil.number_format = '0.0"%"'
            for c in range(1, 5):
                ws.cell(row=main_row, column=c).border = BORDER

        def write_grouped_kelompok_metric(nama_metrik, efektif_col, ideal_col, target_col, site_kelompok_list, fmt_real="0.00", floating_only=False):
            """Metodologi Capaian Utilisasi/Availability/Downtime yg BARU & KONSISTEN dgn PPT (capaian_per_kelompok_unit):
            kelompokkan per KOMBINASI SITE + KELOMPOK UNIT (mis. 'KUMAI-Dump Truck' & 'S.DANAU-Dump Truck' dihitung
            TERPISAH, tdk digabung lintas site), Realisasi dihitung dari FORMULA data mentah (Sum Efektif/Tersedia/
            Breakdown / Sum Ideal) DI DALAM kombinasi Site+Kelompok itu saja. Target = average target di dlm
            kombinasi itu. Capaian = Realisasi/Target. Hasil akhir = average SEDERHANA dari nilai per-kombinasi
            Site+Kelompok (PERSIS SAMA dgn baris2 breakdown per Site & Kelompok Unit di bawahnya)."""
            main_row = r[0]
            r[0] += 1  # baris utama ditulis di akhir, reserve dulu nomor barisnya
            group_rows = []
            EXCL = f'{SHEET_SM}!C:C,"<>Tarif Tetap",{SHEET_SM}!O:O,"<>TRUE"'
            if floating_only:
                # Utilisasi/Availability: KHUSUS Floating Tarif (kolom U = Kriteria Unit dari data BKMS), sama dgn
                # kartu & chart slide KPI PPT. Downtime TIDAK pakai ini (floating_only=False).
                EXCL += f',{SHEET_SM}!U:U,"Floating Tarif"'
            for lok, kel in site_kelompok_list:
                lok_e = lok.replace('"', '""'); kel_e = str(kel).replace('"', '""')
                row = r[0]
                ws.cell(row=row, column=1, value=f"   \u21B3 {lok} \u2014 {kel}").font = Font(name="Arial", size=9.5, italic=True, color="6B7480")
                crit = f'{SHEET_SM}!A:A,"{B}",{SHEET_SM}!B:B,"{lok_e}",{SHEET_SM}!N:N,"{kel_e}",{EXCL}'
                c_r = ws.cell(row=row, column=2, value=f'=IFERROR(SUMIFS({SHEET_SM}!{efektif_col}:{efektif_col},{crit})/SUMIFS({SHEET_SM}!{ideal_col}:{ideal_col},{crit})*100,0)')
                c_t = ws.cell(row=row, column=3, value=f'=AVERAGEIFS({SHEET_SM}!{target_col}:{target_col},{crit})')
                c_h = ws.cell(row=row, column=4, value=f'=IFERROR(B{row}/C{row}*100,"-")')
                c_r.number_format = fmt_real; c_t.number_format = fmt_real; c_h.number_format = '0.0"%"'
                _small_font = Font(name="Consolas", size=9, color="6B7480")
                c_r.font = _small_font; c_t.font = Font(name="Consolas", size=9, color="6B7480")
                c_h.font = Font(name="Consolas", size=9, italic=True, color="6B7480")
                for c in range(1, 5):
                    ws.cell(row=row, column=c).border = BORDER
                group_rows.append(row)
                r[0] += 1
            ws.cell(row=main_row, column=1, value=nama_metrik).font = NORMAL_FONT
            if group_rows:
                refs = ",".join(f"B{gr}" for gr in group_rows)
                refs_t = ",".join(f"C{gr}" for gr in group_rows)
                refs_h = ",".join(f"D{gr}" for gr in group_rows)
                c_real = ws.cell(row=main_row, column=2, value=f'=AVERAGE({refs})')
                c_budget = ws.cell(row=main_row, column=3, value=f'=AVERAGE({refs_t})')
                c_hasil = ws.cell(row=main_row, column=4, value=f'=IFERROR(AVERAGE({refs_h}),"-")')
            else:
                c_real = ws.cell(row=main_row, column=2, value=0)
                c_budget = ws.cell(row=main_row, column=3, value=0)
                c_hasil = ws.cell(row=main_row, column=4, value="-")
            c_real.font = NORMAL_FONT; c_budget.font = NORMAL_FONT; c_hasil.font = BOLD_FONT
            c_real.number_format = fmt_real; c_budget.number_format = fmt_real; c_hasil.number_format = '0.0"%"'
            for c in range(1, 5):
                ws.cell(row=main_row, column=c).border = BORDER

        _sm_blok = sasaran_all[sasaran_all["_blok"] == blok_name] if not sasaran_all.empty else pd.DataFrame()
        # Daftar utk DOWNTIME: penyaringan lama (jenis_unit & unit_sewa) -- kolom kriteria_unit sengaja dibuang dulu
        # spy daftar ini TIDAK berubah (Utilisasi/Availability pakai daftar khusus Floating Tarif di bawah).
        _sm_blok_dt = _sm_blok.drop(columns=["kriteria_unit"], errors="ignore") if not _sm_blok.empty else _sm_blok
        _kelompok_list_blok = sorted(uniq_lokasi_kelompok(_sm_blok_dt.assign(_blok=blok_name) if not _sm_blok_dt.empty else _sm_blok_dt, blok_name)) if not _sm_blok_dt.empty else []
        _sm_blok_floating = (_sm_blok[_sm_blok["kriteria_unit"] == "Floating Tarif"]
                             if (not _sm_blok.empty and "kriteria_unit" in _sm_blok.columns) else _sm_blok)
        _kelompok_list_floating = (sorted(uniq_lokasi_kelompok(_sm_blok_floating.assign(_blok=blok_name), blok_name))
                                   if not _sm_blok_floating.empty else [])
        write_grouped_kelompok_metric("Capaian Utilisasi", "P", "T", "F", _kelompok_list_floating, floating_only=True)
        write_grouped_kelompok_metric("Capaian Availability", "S", "T", "H", _kelompok_list_floating, floating_only=True)
        row_bl = r[0]
        metric_row("Biaya Langsung / Prestasi",
            f'=IFERROR(SUMIFS({SHEET_BIAYA}!O:O,{SHEET_BIAYA}!A:A,"{B}")/SUMIFS({SHEET_PRESTASI}!H:H,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!F:F,"Floating Tarif"),"-")',
            f'=IFERROR(SUMIFS({SHEET_BIAYA}!P:P,{SHEET_BIAYA}!A:A,"{B}")/SUMIFS({SHEET_PRESTASI}!I:I,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!F:F,"Floating Tarif"),"-")',
            fmt_real="#,##0", hasil_formula=f'=IFERROR(B{row_bl}/C{row_bl}*100,"-")')
        row_btl = r[0]
        metric_row("Biaya T.Langsung / Prestasi",
            f'=IFERROR(SUMIFS({SHEET_BIAYA}!Q:Q,{SHEET_BIAYA}!A:A,"{B}")/SUMIFS({SHEET_PRESTASI}!H:H,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!F:F,"Floating Tarif"),"-")',
            f'=IFERROR(SUMIFS({SHEET_BIAYA}!R:R,{SHEET_BIAYA}!A:A,"{B}")/SUMIFS({SHEET_PRESTASI}!I:I,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!F:F,"Floating Tarif"),"-")',
            fmt_real="#,##0", hasil_formula=f'=IFERROR(B{row_btl}/C{row_btl}*100,"-")')
        r[0] += 1

        # --- Breakdown per Site & KELOMPOK UNIT (Chart Slide 1) ---
        # Realisasi Utilisasi/Availability dihitung dari FORMULA data mentah (Efektif atau Tersedia / Ideal),
        # BUKAN average kolom persentase yg sudah jadi -- konsisten dgn metodologi kartu KPI & chart PPT.
        # Unit berkriteria "Tarif Tetap" & unit_sewa=TRUE dikecualikan (pendapatannya tdk terpengaruh metrik ini).
        subsect("\u25B8 Per Site & Kelompok Unit (exclude Tarif Tetap & Unit Sewa) \u2014 Prestasi / Utilisasi / Availability")
        header(("Site \u2014 Kelompok Unit", "Cap. Prestasi", "Cap. Utilisasi", "Cap. Availability"))
        prestasi_floating = data_all[(data_all["_blok"] == blok_name) & (data_all["kriteria_unit"] != "Tarif Tetap")]
        combos1 = uniq_lokasi_kelompok(prestasi_floating, blok_name)
        for lok, kel in combos1:
            lok_e = lok.replace('"', '""'); kel_e = str(kel).replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=f"{lok} \u2014 {kel}").font = NORMAL_FONT
            f_prest = (f'=IFERROR(SUMIFS({SHEET_PRESTASI}!H:H,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!B:B,"{lok_e}",{SHEET_PRESTASI}!J:J,"{kel_e}",{SHEET_PRESTASI}!F:F,"<>Tarif Tetap")'
                       f'/SUMIFS({SHEET_PRESTASI}!I:I,{SHEET_PRESTASI}!A:A,"{B}",{SHEET_PRESTASI}!B:B,"{lok_e}",{SHEET_PRESTASI}!J:J,"{kel_e}",{SHEET_PRESTASI}!F:F,"<>Tarif Tetap")*100,"-")')
            sm_crit = (f'{SHEET_SM}!A:A,"{B}",{SHEET_SM}!B:B,"{lok_e}",{SHEET_SM}!N:N,"{kel_e}",'
                       f'{SHEET_SM}!C:C,"<>Tarif Tetap",{SHEET_SM}!O:O,"<>TRUE",{SHEET_SM}!U:U,"Floating Tarif"')
            f_util = f'=IFERROR(SUMIFS({SHEET_SM}!P:P,{sm_crit})/SUMIFS({SHEET_SM}!T:T,{sm_crit})*100,"-")'
            f_avail = f'=IFERROR(SUMIFS({SHEET_SM}!S:S,{sm_crit})/SUMIFS({SHEET_SM}!T:T,{sm_crit})*100,"-")'
            for ci, f in enumerate([f_prest, f_util, f_avail], start=2):
                cell = ws.cell(row=row, column=ci, value=f); cell.font = NORMAL_FONT; cell.number_format = '0.0"%"'
            for c in range(1, 5):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        # --- Laporan Pendapatan, Biaya Langsung, Biaya T.Langsung & Laba Operasional per Site & Kelompok Unit ---
        subsect("\u25B8 Laporan Pendapatan & Laba Operasional \u2014 per Site & Kelompok Unit (Realisasi vs Budget)")
        header(("Site \u2014 Kelompok Unit", "Pendapatan R", "Pendapatan B", "Biaya Langsung R", "Biaya Langsung B",
                "Biaya T.Langsung R", "Biaya T.Langsung B", "Laba Operasional R", "Laba Operasional B"))
        combos_laba = uniq_lokasi_kelompok(data_all[data_all["_blok"] == blok_name], blok_name, exclude_tarif_tetap=False, exclude_unit_sewa=False)
        for lok, kel in combos_laba:
            lok_e = lok.replace('"', '""'); kel_e = str(kel).replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=f"{lok} \u2014 {kel}").font = NORMAL_FONT
            crit_laba = f'{SHEET_BIAYA}!A:A,"{B}",{SHEET_BIAYA}!B:B,"{lok_e}",{SHEET_BIAYA}!S:S,"{kel_e}"'
            c_pr = ws.cell(row=row, column=2, value=f'=SUMIFS({SHEET_BIAYA}!T:T,{crit_laba})')
            c_pb = ws.cell(row=row, column=3, value=f'=SUMIFS({SHEET_BIAYA}!U:U,{crit_laba})')
            c_blr = ws.cell(row=row, column=4, value=f'=SUMIFS({SHEET_BIAYA}!O:O,{crit_laba})')
            c_blb = ws.cell(row=row, column=5, value=f'=SUMIFS({SHEET_BIAYA}!P:P,{crit_laba})')
            c_btr = ws.cell(row=row, column=6, value=f'=SUMIFS({SHEET_BIAYA}!Q:Q,{crit_laba})')
            c_btb = ws.cell(row=row, column=7, value=f'=SUMIFS({SHEET_BIAYA}!R:R,{crit_laba})')
            c_labar = ws.cell(row=row, column=8, value=f'=B{row}-D{row}-F{row}')
            c_labab = ws.cell(row=row, column=9, value=f'=C{row}-E{row}-G{row}')
            for c in [c_pr, c_pb, c_blr, c_blb, c_btr, c_btb]:
                c.number_format = '"Rp"#,##0'; c.font = NORMAL_FONT
            for c in [c_labar, c_labab]:
                c.number_format = '"Rp"#,##0'; c.font = BOLD_FONT
            for c in range(1, 10):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        # ============ SLIDE 2: Biaya Operasional ============
        sect(f"\U0001F4B0 {blok_name} \u2014 Biaya Operasional (Slide 2)")
        header()
        metric_row("Total Biaya",
            f'=SUMIFS({SHEET_BIAYA}!G:G,{SHEET_BIAYA}!A:A,"{B}")',
            f'=SUMIFS({SHEET_BIAYA}!H:H,{SHEET_BIAYA}!A:A,"{B}")', fmt_real='"Rp"#,##0')
        metric_row("Biaya Maintenance",
            f'=SUMIFS({SHEET_BIAYA}!I:I,{SHEET_BIAYA}!A:A,"{B}")',
            f'=SUMIFS({SHEET_BIAYA}!J:J,{SHEET_BIAYA}!A:A,"{B}")', fmt_real='"Rp"#,##0')
        metric_row("Biaya BBM",
            f'=SUMIFS({SHEET_BBM}!I:I,{SHEET_BBM}!A:A,"{B}")',
            f'=SUMIFS({SHEET_BBM}!J:J,{SHEET_BBM}!A:A,"{B}")', fmt_real='"Rp"#,##0')
        row_cf = r[0]
        metric_row("\u21B3 Cap. Fisik BBM (Qty)",
            f'=SUMIFS({SHEET_BBM}!G:G,{SHEET_BBM}!A:A,"{B}")',
            f'=SUMIFS({SHEET_BBM}!H:H,{SHEET_BBM}!A:A,"{B}")', fmt_real="#,##0")
        metric_row("Upah Operator",
            f'=SUMIFS({SHEET_BIAYA}!K:K,{SHEET_BIAYA}!A:A,"{B}")',
            f'=SUMIFS({SHEET_BIAYA}!L:L,{SHEET_BIAYA}!A:A,"{B}")', fmt_real='"Rp"#,##0')
        metric_row("Biaya Lainnya",
            f'=SUMIFS({SHEET_BIAYA}!M:M,{SHEET_BIAYA}!A:A,"{B}")',
            f'=SUMIFS({SHEET_BIAYA}!N:N,{SHEET_BIAYA}!A:A,"{B}")', fmt_real='"Rp"#,##0')
        r[0] += 1

        subsect("\u25B8 BTL (Biaya Tidak Langsung) per Site")
        header(("Lokasi", "Budget", "Aktual", "% Target"))
        btl_lokasi = sorted(data_all[data_all["_blok"] == blok_name]["lokasi"].dropna().unique().tolist())
        for lok in btl_lokasi:
            lok_e = lok.replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=lok).font = NORMAL_FONT
            c_b = ws.cell(row=row, column=2, value=f'=SUMIFS({SHEET_BIAYA}!R:R,{SHEET_BIAYA}!A:A,"{B}",{SHEET_BIAYA}!B:B,"{lok_e}")')
            c_a = ws.cell(row=row, column=3, value=f'=SUMIFS({SHEET_BIAYA}!Q:Q,{SHEET_BIAYA}!A:A,"{B}",{SHEET_BIAYA}!B:B,"{lok_e}")')
            c_h = ws.cell(row=row, column=4, value=f'=IFERROR(C{row}/B{row}*100,"-")')
            c_b.number_format = '"Rp"#,##0'; c_a.number_format = '"Rp"#,##0'; c_h.number_format = '0.0"%"'
            for c in [c_b, c_a]: c.font = NORMAL_FONT
            c_h.font = BOLD_FONT
            for c in range(1, 5):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        subsect("\u25B8 Analisa Kenaikan Biaya BBM per Site & Kelompok Unit")
        header(("Site \u2014 Kelompok Unit", "Qty Realisasi", "Qty Budget", "Rate Realisasi", "Rate Budget", "Cap. Konsumsi", "Harga Realisasi (Rp/Ltr)", "Harga Budget (Rp/Ltr)", "Cap. Harga BBM"))
        data_bbm3_blok = data_bbm3[(data_bbm3["_blok"] == blok_name) & ((data_bbm3["qty_bbm_realisasi"] > 0) | (data_bbm3["qty_bbm_budget"] > 0))]
        combos_bbm = uniq_lokasi_kelompok(data_bbm3_blok, blok_name, exclude_tarif_tetap=False, exclude_unit_sewa=False) if not data_bbm3_blok.empty else []
        kategori_lookup_bbm3 = data_bbm3_blok.drop_duplicates(subset=["lokasi", "kelompok_unit"]).set_index(["lokasi", "kelompok_unit"])["kategori"].to_dict()
        for lok, kel in combos_bbm:
            lok_e = lok.replace('"', '""'); kel_e = str(kel).replace('"', '""')
            kat_unit = kategori_lookup_bbm3.get((lok, kel), "TR")
            row = r[0]
            ws.cell(row=row, column=1, value=f"{lok} \u2014 {kel}" + (" (Ltr/HM)" if kat_unit == "AB" else " (KM/Ltr)")).font = NORMAL_FONT
            crit = f'{SHEET_BBM3}!A:A,"{B}",{SHEET_BBM3}!B:B,"{lok_e}",{SHEET_BBM3}!N:N,"{kel_e}"'
            c_r = ws.cell(row=row, column=2, value=f'=SUMIFS({SHEET_BBM3}!H:H,{crit})')
            c_b = ws.cell(row=row, column=3, value=f'=SUMIFS({SHEET_BBM3}!I:I,{crit})')
            # Rate & Cap. Konsumsi = rasio EFISIENSI (bukan sekedar Qty R/B) -- persis rumus di PPT:
            # TR = (Prestasi/Qty) KM per Liter; AB = (Qty/Prestasi) Liter per HM. Rate ditampilkan EKSPLISIT
            # (kolom D & E) spy Capaian bisa langsung ditelusuri dari angka Realisasi/Budget di baris yg sama.
            sum_prestasi_r = f'SUMIFS({SHEET_BBM3}!J:J,{crit})'
            sum_prestasi_b = f'SUMIFS({SHEET_BBM3}!K:K,{crit})'
            if kat_unit == "AB":
                rate_r_expr = f'IFERROR(B{row}/{sum_prestasi_r},0)'
                rate_b_expr = f'IFERROR(C{row}/{sum_prestasi_b},0)'
            else:
                rate_r_expr = f'IFERROR({sum_prestasi_r}/B{row},0)'
                rate_b_expr = f'IFERROR({sum_prestasi_b}/C{row},0)'
            c_rate_r = ws.cell(row=row, column=4, value=f'={rate_r_expr}')
            c_rate_b = ws.cell(row=row, column=5, value=f'={rate_b_expr}')
            c_h = ws.cell(row=row, column=6, value=f'=IFERROR(D{row}/E{row}*100,"-")')
            c_hr = ws.cell(row=row, column=7, value=f'=IFERROR(SUMIFS({SHEET_BBM3}!L:L,{crit})/B{row},0)')
            c_hb = ws.cell(row=row, column=8, value=f'=IFERROR(SUMIFS({SHEET_BBM3}!M:M,{crit})/C{row},0)')
            c_ch = ws.cell(row=row, column=9, value=f'=IFERROR(G{row}/H{row}*100,"-")')
            c_r.number_format = "#,##0"; c_b.number_format = "#,##0"
            c_rate_r.number_format = "0.00"; c_rate_b.number_format = "0.00"
            c_h.number_format = '0.0"%"'
            c_hr.number_format = '"Rp"#,##0'; c_hb.number_format = '"Rp"#,##0'; c_ch.number_format = '0.0"%"'
            for c in [c_r, c_b, c_rate_r, c_rate_b, c_hr, c_hb]: c.font = NORMAL_FONT
            c_h.font = BOLD_FONT; c_ch.font = BOLD_FONT
            for c in range(1, 10):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        # ============ SLIDE 3: Analisis Biaya Maintenance ============
        sect(f"\U0001F527 {blok_name} \u2014 Analisis Biaya Maintenance (Slide 3)")
        subsect("\u25B8 Gap Biaya Maintenance (Realisasi \u2212 Budget) per Site & Kelompok Unit")
        header(("Site \u2014 Kelompok Unit", "Realisasi", "Budget", "Gap (Rp)"))
        combos_maint = uniq_lokasi_kelompok(data_all[data_all["_blok"] == blok_name], blok_name, exclude_tarif_tetap=False, exclude_unit_sewa=False)
        for lok, kel in combos_maint:
            lok_e = lok.replace('"', '""'); kel_e = str(kel).replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=f"{lok} \u2014 {kel}").font = NORMAL_FONT
            c_r = ws.cell(row=row, column=2, value=f'=SUMIFS({SHEET_BIAYA}!I:I,{SHEET_BIAYA}!A:A,"{B}",{SHEET_BIAYA}!B:B,"{lok_e}",{SHEET_BIAYA}!S:S,"{kel_e}")')
            c_b = ws.cell(row=row, column=3, value=f'=SUMIFS({SHEET_BIAYA}!J:J,{SHEET_BIAYA}!A:A,"{B}",{SHEET_BIAYA}!B:B,"{lok_e}",{SHEET_BIAYA}!S:S,"{kel_e}")')
            c_g = ws.cell(row=row, column=4, value=f'=B{row}-C{row}')
            for c in [c_r, c_b, c_g]:
                c.number_format = '"Rp"#,##0'; c.font = NORMAL_FONT
            for c in range(1, 5):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        subsect("\u25B8 Maintenance Rutin vs Non-Rutin per Site & Kelompok Unit")
        header(("Site \u2014 Kelompok Unit", "Biaya Rutin", "Biaya Non-Rutin", "% Rutin"))
        combos_ml = uniq_lokasi_kelompok(maint_all, blok_name, exclude_tarif_tetap=False, exclude_unit_sewa=False) if not maint_all.empty else []
        for lok, kel in combos_ml:
            lok_e = lok.replace('"', '""'); kel_e = str(kel).replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=f"{lok} \u2014 {kel}").font = NORMAL_FONT
            c_rt = ws.cell(row=row, column=2, value=f'=SUMIFS({SHEET_ML}!G:G,{SHEET_ML}!A:A,"{B}",{SHEET_ML}!B:B,"{lok_e}",{SHEET_ML}!H:H,"{kel_e}",{SHEET_ML}!E:E,"RUTIN")')
            c_nr = ws.cell(row=row, column=3, value=f'=SUMIFS({SHEET_ML}!G:G,{SHEET_ML}!A:A,"{B}",{SHEET_ML}!B:B,"{lok_e}",{SHEET_ML}!H:H,"{kel_e}",{SHEET_ML}!E:E,"NON RUTIN")')
            c_h = ws.cell(row=row, column=4, value=f'=IFERROR(B{row}/(B{row}+C{row})*100,"-")')
            c_rt.number_format = '"Rp"#,##0'; c_nr.number_format = '"Rp"#,##0'; c_h.number_format = '0.0"%"'
            for c in [c_rt, c_nr]: c.font = NORMAL_FONT
            c_h.font = BOLD_FONT
            for c in range(1, 5):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        # ============ SLIDE 4: Key Insights Downtime ============
        sect(f"\u23F1 {blok_name} \u2014 Key Insights Downtime (Slide 4)")
        header()
        write_grouped_kelompok_metric("% Capaian Realisasi Downtime", "R", "T", "J", _kelompok_list_blok)
        r[0] += 1

        subsect("\u25B8 MTTR (Mean Time To Repair) \u2014 format berbeda dari Capaian %")
        header(("Metrik", "Nilai", "", ""))
        row_mttr = r[0]
        ws.cell(row=row_mttr, column=1, value="MTTR (rata-rata jam per kejadian)").font = NORMAL_FONT
        c_mttr = ws.cell(row=row_mttr, column=2, value=f'=IFERROR(SUMIFS({SHEET_MTTR}!F:F,{SHEET_MTTR}!A:A,"{B}")/COUNTIFS({SHEET_MTTR}!A:A,"{B}"),"-")')
        c_mttr.number_format = "0.0"; c_mttr.font = BOLD_FONT
        for c in range(1, 5):
            ws.cell(row=row_mttr, column=c).border = BORDER
        r[0] += 1
        row_kej = r[0]
        ws.cell(row=row_kej, column=1, value="Jumlah Kejadian Perbaikan").font = NORMAL_FONT
        c_kej = ws.cell(row=row_kej, column=2, value=f'=COUNTIFS({SHEET_MTTR}!A:A,"{B}")')
        c_kej.number_format = "#,##0"; c_kej.font = BOLD_FONT
        for c in range(1, 5):
            ws.cell(row=row_kej, column=c).border = BORDER
        r[0] += 2

        # --- Breakdown PER SITE (bukan per Site+Kelompok Unit) utk 3 metrik KPI Slide 4 -- persis spt subtitle
        # kartu KPI di PPT, supaya angka subtitle itu bisa ditelusuri di Excel ---
        _site_list_blok4 = sorted(set(lok for lok, _ in _kelompok_list_blok)) if _kelompok_list_blok else []

        subsect("\u25B8 % Capaian Realisasi Downtime \u2014 per Site")
        header(("Site", "Realisasi", "Target", "Cap. Downtime"))
        # Metodologi BENAR (bukan average per unit/baris individual):
        #   Target site = average dari TARGET tiap Kelompok Unit di site itu (mis. KUMAI py kelompok dgn target
        #     0.5 & 2.5 -> diaverage jadi 1.5, BUKAN average tiap baris unit yg bisa bias krn jml unit tdk sama).
        #   Realisasi site = average dari Capaian REALISASI tiap Kelompok Unit (Sum Breakdown kelompok / Sum
        #     Ideal kelompok), dihitung PER KELOMPOK dulu baru diaverage -- bukan average langsung semua baris.
        EXCL_DT4 = f'{SHEET_SM}!C:C,"<>Tarif Tetap",{SHEET_SM}!O:O,"<>TRUE"'
        for lok in _site_list_blok4:
            lok_e = lok.replace('"', '""')
            kelompok_di_site4 = sorted(set(kel for lk, kel in _kelompok_list_blok if lk == lok))
            main_row_dt4 = r[0]
            r[0] += 1  # reserve baris utama, isi belakangan setelah baris kelompok ditulis
            group_rows_dt4 = []
            for kel in kelompok_di_site4:
                kel_e = str(kel).replace('"', '""')
                row = r[0]
                ws.cell(row=row, column=1, value=f"   \u21B3 {kel}").font = Font(name="Arial", size=9.5, italic=True, color="6B7480")
                crit_kel4 = f'{SHEET_SM}!A:A,"{B}",{SHEET_SM}!B:B,"{lok_e}",{SHEET_SM}!N:N,"{kel_e}",{EXCL_DT4}'
                c_r = ws.cell(row=row, column=2, value=f'=IFERROR(SUMIFS({SHEET_SM}!R:R,{crit_kel4})/SUMIFS({SHEET_SM}!T:T,{crit_kel4})*100,0)')
                c_t = ws.cell(row=row, column=3, value=f'=AVERAGEIFS({SHEET_SM}!J:J,{crit_kel4})')
                c_h = ws.cell(row=row, column=4, value=f'=IFERROR(B{row}/C{row}*100,"-")')
                c_r.number_format = "0.00"; c_t.number_format = "0.00"; c_h.number_format = '0.0"%"'
                _sf4 = Font(name="Consolas", size=9, color="6B7480")
                c_r.font = _sf4; c_t.font = Font(name="Consolas", size=9, color="6B7480")
                c_h.font = Font(name="Consolas", size=9, italic=True, color="6B7480")
                for c in range(1, 5):
                    ws.cell(row=row, column=c).border = BORDER
                group_rows_dt4.append(row)
                r[0] += 1
            ws.cell(row=main_row_dt4, column=1, value=lok).font = NORMAL_FONT
            if group_rows_dt4:
                refs_r4 = ",".join(f"B{gr}" for gr in group_rows_dt4)
                refs_t4 = ",".join(f"C{gr}" for gr in group_rows_dt4)
                c_real4 = ws.cell(row=main_row_dt4, column=2, value=f'=AVERAGE({refs_r4})')
                c_budget4 = ws.cell(row=main_row_dt4, column=3, value=f'=AVERAGE({refs_t4})')
                c_hasil4 = ws.cell(row=main_row_dt4, column=4, value=f'=IFERROR(B{main_row_dt4}/C{main_row_dt4}*100,"-")')
            else:
                c_real4 = ws.cell(row=main_row_dt4, column=2, value=0)
                c_budget4 = ws.cell(row=main_row_dt4, column=3, value=0)
                c_hasil4 = ws.cell(row=main_row_dt4, column=4, value="-")
            c_real4.font = NORMAL_FONT; c_budget4.font = NORMAL_FONT; c_hasil4.font = BOLD_FONT
            c_real4.number_format = "0.00"; c_budget4.number_format = "0.00"; c_hasil4.number_format = '0.0"%"'
            for c in range(1, 5):
                ws.cell(row=main_row_dt4, column=c).border = BORDER
        r[0] += 1

        subsect("\u25B8 MTTR (Mean Time To Repair) \u2014 per Site")
        header(("Site", "Total Jam", "Jumlah Kejadian", "MTTR (jam)"))
        for lok in _site_list_blok4:
            lok_e = lok.replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=lok).font = NORMAL_FONT
            c_jam = ws.cell(row=row, column=2, value=f'=SUMIFS({SHEET_MTTR}!F:F,{SHEET_MTTR}!A:A,"{B}",{SHEET_MTTR}!B:B,"{lok_e}")')
            c_n = ws.cell(row=row, column=3, value=f'=COUNTIFS({SHEET_MTTR}!A:A,"{B}",{SHEET_MTTR}!B:B,"{lok_e}")')
            c_mttr_site = ws.cell(row=row, column=4, value=f'=IFERROR(B{row}/C{row},"-")')
            c_jam.number_format = "#,##0.0"; c_n.number_format = "#,##0"
            for c in [c_jam, c_n]: c.font = NORMAL_FONT
            c_mttr_site.number_format = "0.0"; c_mttr_site.font = BOLD_FONT
            for c in range(1, 5):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        subsect("\u25B8 Maintenance Rutin vs Non-Rutin \u2014 per Site (%)")
        header(("Site", "Biaya Rutin", "Biaya Non-Rutin", "% Rutin", "% Non-Rutin"))
        for lok in _site_list_blok4:
            lok_e = lok.replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=lok).font = NORMAL_FONT
            c_rt = ws.cell(row=row, column=2, value=f'=SUMIFS({SHEET_ML}!G:G,{SHEET_ML}!A:A,"{B}",{SHEET_ML}!B:B,"{lok_e}",{SHEET_ML}!E:E,"RUTIN")')
            c_nr = ws.cell(row=row, column=3, value=f'=SUMIFS({SHEET_ML}!G:G,{SHEET_ML}!A:A,"{B}",{SHEET_ML}!B:B,"{lok_e}",{SHEET_ML}!E:E,"NON RUTIN")')
            c_pr = ws.cell(row=row, column=4, value=f'=IFERROR(B{row}/(B{row}+C{row})*100,"-")')
            c_pnr = ws.cell(row=row, column=5, value=f'=IFERROR(C{row}/(B{row}+C{row})*100,"-")')
            c_rt.number_format = '"Rp"#,##0'; c_nr.number_format = '"Rp"#,##0'
            for c in [c_rt, c_nr]: c.font = NORMAL_FONT
            c_pr.number_format = '0.0"%"'; c_pr.font = BOLD_FONT
            c_pnr.number_format = '0.0"%"'; c_pnr.font = BOLD_FONT
            for c in range(1, 6):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        subsect("\u25B8 % Downtime per Site & Kelompok Unit")
        header(("Site \u2014 Jenis Unit", "Realisasi", "Target", "Cap. Downtime"))
        combos_dt = uniq_lokasi_jenis(sasaran_all, blok_name)
        for lok, ju in combos_dt:
            lok_e = lok.replace('"', '""'); ju_e = str(ju).replace('"', '""')
            row = r[0]
            ws.cell(row=row, column=1, value=f"{lok} \u2014 {ju}").font = NORMAL_FONT
            c_r = ws.cell(row=row, column=2, value=f'=IFERROR(AVERAGEIFS({SHEET_SM}!I:I,{SHEET_SM}!A:A,"{B}",{SHEET_SM}!B:B,"{lok_e}",{SHEET_SM}!C:C,"{ju_e}"),0)')
            c_t = ws.cell(row=row, column=3, value=f'=IFERROR(AVERAGEIFS({SHEET_SM}!J:J,{SHEET_SM}!A:A,"{B}",{SHEET_SM}!B:B,"{lok_e}",{SHEET_SM}!C:C,"{ju_e}"),0)')
            c_h = ws.cell(row=row, column=4, value=f'=IFERROR(B{row}/C{row}*100,"-")')
            c_r.number_format = "0.00"; c_t.number_format = "0.00"; c_h.number_format = '0.0"%"'
            for c in [c_r, c_t]: c.font = NORMAL_FONT
            c_h.font = BOLD_FONT
            for c in range(1, 5):
                ws.cell(row=row, column=c).border = BORDER
            r[0] += 1
        r[0] += 1

        subsect("\u25B8 Kategori Sparepart per Site (Site sebagai kolom)")
        sp_col_count = 4
        if not maint_all.empty:
            ml_blok = maint_all[maint_all["_blok"] == blok_name]
            sp_lokasi_list = sorted(ml_blok["lokasi"].dropna().unique().tolist()) if "lokasi" in ml_blok.columns else []
            sp_kategori_list = sorted(ml_blok.dropna(subset=["kategori_sparepart"])["kategori_sparepart"].unique().tolist()) if "kategori_sparepart" in ml_blok.columns else []
            if sp_lokasi_list and sp_kategori_list:
                header_row = r[0]
                ws.cell(row=header_row, column=1, value="Kategori Sparepart").fill = HEADER_FILL
                ws.cell(row=header_row, column=1).font = HEADER_FONT
                for ci, lok in enumerate(sp_lokasi_list, start=2):
                    cell = ws.cell(row=header_row, column=ci, value=lok)
                    cell.fill = HEADER_FILL; cell.font = HEADER_FONT
                total_col = len(sp_lokasi_list) + 2
                cell = ws.cell(row=header_row, column=total_col, value="Total")
                cell.fill = HEADER_FILL; cell.font = HEADER_FONT
                for c in range(1, total_col + 1):
                    ws.cell(row=header_row, column=c).border = BORDER
                r[0] += 1
                for kat in sp_kategori_list:
                    kat_e = str(kat).replace('"', '""')
                    row = r[0]
                    ws.cell(row=row, column=1, value=kat).font = NORMAL_FONT
                    site_cell_refs = []
                    for ci, lok in enumerate(sp_lokasi_list, start=2):
                        lok_e = lok.replace('"', '""')
                        col_letter = get_column_letter(ci)
                        cell = ws.cell(row=row, column=ci, value=f'=SUMIFS({SHEET_ML}!G:G,{SHEET_ML}!A:A,"{B}",{SHEET_ML}!B:B,"{lok_e}",{SHEET_ML}!F:F,"{kat_e}")')
                        cell.number_format = '"Rp"#,##0'; cell.font = NORMAL_FONT
                        site_cell_refs.append(f"{col_letter}{row}")
                    total_cell = ws.cell(row=row, column=total_col, value=f'={"+".join(site_cell_refs)}')
                    total_cell.number_format = '"Rp"#,##0'; total_cell.font = BOLD_FONT
                    for c in range(1, total_col + 1):
                        ws.cell(row=row, column=c).border = BORDER
                    r[0] += 1
                sp_col_count = total_col
        max_col_used = max(7, sp_col_count)
        col_widths_final = [42] + [16] * (max_col_used - 1)
        for i, w in enumerate(col_widths_final, start=1):
            ws.column_dimensions[get_column_letter(i)].width = w

    build_ringkasan_sheet("1. Ringkasan - Plantation TR", BLOK_TR, BLOK_TR in blok_list)
    build_ringkasan_sheet("2. Ringkasan - Plantation AB", BLOK_AB, BLOK_AB in blok_list)
    build_ringkasan_sheet("3. Ringkasan - Mining", BLOK_MINING, BLOK_MINING in blok_list)

    order = ["1. Ringkasan - Plantation TR", "2. Ringkasan - Plantation AB", "3. Ringkasan - Mining",
             "Detail - Prestasi", "Detail - Sasaran Mutu", "Detail - Biaya", "Detail - BBM (Valid)",
             "Detail - BBM Analisa Konsumsi", "Detail - MTTR", "Detail - Maintenance Log"]
    wb._sheets = [wb[name] for name in order if name in wb.sheetnames]

    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

@st.cache_data
@st.cache_data
def build_sasaran_mutu_excel(sasaran_mutu_df) -> bytes:
    """Bangun file Excel 'Data Sasaran Mutu' -- Semua Data + per-site, dgn baris kuning menandai yg belum
    py data detail (Efektif/Standby/Breakdown/Ideal) supaya gampang dilacak yg masih perlu dilengkapi."""
    import io as _io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    HEADER_FILL = PatternFill(start_color="1A2744", end_color="1A2744", fill_type="solid")
    HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=9)
    NORMAL_FONT = Font(name="Arial", size=9)
    MISSING_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    thin = Side(style="thin", color="D9D9D9")
    BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def write_sheet(sheet_name, data):
        ws = wb.create_sheet(sheet_name[:31])
        if data is None or data.empty:
            ws.cell(row=1, column=1, value="Data belum tersedia.")
            return
        cols = list(data.columns)
        highlight_col = "efektif_hm_km_realisasi" if "efektif_hm_km_realisasi" in cols else None
        highlight_idx = cols.index(highlight_col) if highlight_col else None
        for c, h in enumerate(cols, start=1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.fill = HEADER_FILL; cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for r_i, row in enumerate(data.itertuples(index=False), start=2):
            is_missing = pd.isna(row[highlight_idx]) if highlight_idx is not None else False
            for c_i, val in enumerate(row, start=1):
                cell = ws.cell(row=r_i, column=c_i, value=(None if pd.isna(val) else val))
                cell.font = NORMAL_FONT
                cell.border = BORDER
                if rupiah_cols and cols[c_i - 1] in rupiah_cols:
                    cell.number_format = "#,##0"
                if is_missing:
                    cell.fill = MISSING_FILL
        for c_i, col in enumerate(cols, start=1):
            sample = data[col].astype(str).head(200)
            maxlen = max([len(str(col))] + [len(str(v)) for v in sample])
            ws.column_dimensions[get_column_letter(c_i)].width = min(max(maxlen + 2, 8), 38)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    write_sheet("Semua Data", sasaran_mutu_df)
    if sasaran_mutu_df is not None and not sasaran_mutu_df.empty and "lokasi" in sasaran_mutu_df.columns:
        for lokasi in sorted(sasaran_mutu_df["lokasi"].dropna().unique()):
            sub = sasaran_mutu_df[sasaran_mutu_df["lokasi"] == lokasi].copy()
            write_sheet(lokasi.replace(" ", "_"), sub)

    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

@st.cache_data
def build_database_laporan_excel(data_df, sasaran_mutu_df, mttr_df, maint_df=None) -> bytes:
    """Bangun 1 file Excel 'Database Laporan' -- isinya sama dgn export data_bkms (Semua Data + per-site),
    ditambah sheet Sasaran Mutu & MTTR. Dipakai utk tombol download di sidebar."""
    import io as _io
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    HEADER_FILL = PatternFill(start_color="1A2744", end_color="1A2744", fill_type="solid")
    HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF", size=9)
    NORMAL_FONT = Font(name="Arial", size=9)
    MISSING_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    thin = Side(style="thin", color="D9D9D9")
    BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def _write_sheet(sheet_name, data, highlight_col=None, rupiah_cols=None):
        ws = wb.create_sheet(sheet_name[:31])
        if data is None or data.empty:
            ws.cell(row=1, column=1, value="Data belum tersedia.")
            return
        cols = list(data.columns)
        for c, h in enumerate(cols, start=1):
            cell = ws.cell(row=1, column=c, value=h)
            cell.fill = HEADER_FILL; cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center", vertical="center")
        highlight_idx = (cols.index(highlight_col) if (highlight_col and highlight_col in cols) else None)
        for r_i, row in enumerate(data.itertuples(index=False), start=2):
            is_missing = pd.isna(row[highlight_idx]) if highlight_idx is not None else False
            for c_i, val in enumerate(row, start=1):
                cell = ws.cell(row=r_i, column=c_i, value=(None if pd.isna(val) else val))
                cell.font = NORMAL_FONT
                cell.border = BORDER
                if rupiah_cols and cols[c_i - 1] in rupiah_cols:
                    cell.number_format = "#,##0"
                if is_missing:
                    cell.fill = MISSING_FILL
        for c_i, col in enumerate(cols, start=1):
            sample = data[col].astype(str).head(200)
            maxlen = max([len(str(col))] + [len(str(v)) for v in sample])
            ws.column_dimensions[get_column_letter(c_i)].width = min(max(maxlen + 2, 8), 38)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

    # --- Sheet Data BKMS: Semua Data saja (tidak dipisah per site) ---
    # Ditambah kolom "blok" (MINING / PLANTATION - ALAT BERAT / PLANTATION - TRANSPORTASI), aturannya SAMA dgn
    # pembagian blok di PPT & Perhitungan Detail: semua site Mining = MINING (termasuk unit TR di Tanjung),
    # site Plantation dipisah per kategori AB/TR. Disisipkan tepat setelah kolom "lokasi".
    semua_data = data_df.copy() if data_df is not None else pd.DataFrame()
    if not semua_data.empty and "lokasi" in semua_data.columns:
        _MINING = {"TANJUNG", "BUHUT", "BUHUT LHL", "AMPAH"}
        _PLANT = {"SUNGAI DANAU", "KUMAI"}
        def _blok(r):
            lok = str(r.get("lokasi", "")).strip().upper()
            kat = str(r.get("kategori", "")).strip().upper()
            if lok in _MINING:
                return "MINING"
            if lok in _PLANT:
                if kat == "AB":
                    return "PLANTATION - ALAT BERAT"
                if kat == "TR":
                    return "PLANTATION - TRANSPORTASI"
            return None
        _blok_vals = semua_data.apply(_blok, axis=1)
        if "blok" in semua_data.columns:
            semua_data = semua_data.drop(columns=["blok"])
        semua_data.insert(list(semua_data.columns).index("lokasi") + 1, "blok", _blok_vals)
    _write_sheet("Semua Data", semua_data, highlight_col="jenis_unit")

    # --- Sheet Sasaran Mutu ---
    _write_sheet("Sasaran Mutu", sasaran_mutu_df)

    # --- Sheet MTTR ---
    _write_sheet("MTTR", mttr_df)

    # --- Sheet Biaya Maintenance: detail transaksi Pemeliharaan (sumber chart Rutin vs Non-Rutin) ---
    # Ditambah kolom kelompok_unit (lookup nama_unit -> data BKMS), sama spt yg dipakai slide PPT.
    maint_out = pd.DataFrame()
    if maint_df is not None and not maint_df.empty:
        maint_out = maint_df.copy()
        if data_df is not None and not data_df.empty and {"nama_unit", "kelompok_unit"}.issubset(data_df.columns):
            _lk_cols = [c for c in ["kategori", "jenis_unit", "id_unit", "kelompok_unit"] if c in data_df.columns]
            _lk = lookup_atribut_unit(maint_out, data_df, _lk_cols)
            for _c in _lk_cols:
                if _c == "kelompok_unit" or _c not in maint_out.columns:
                    maint_out[_c] = _lk[_c]
                else:
                    maint_out[_c] = maint_out[_c].where(maint_out[_c].notna(), _lk[_c])
        if "id_unit" in maint_out.columns:
            maint_out["id_unit"] = maint_out["id_unit"].apply(
                lambda v: str(int(float(v))) if pd.notna(v) and str(v).replace(".", "", 1).isdigit() else v)
        maint_out = maint_out.rename(columns={"kelompok": "divisi"})
        if "bulan_no" in maint_out.columns:
            maint_out = maint_out.sort_values(["bulan_no", "lokasi", "tanggal"], kind="stable")
        _urutan = ["tanggal", "bulan", "lokasi", "divisi", "id_unit", "nama_unit", "kategori", "kelompok_unit",
                   "jenis_unit", "jenis_pemeliharaan", "kategori_sparepart", "tipe_biaya", "biaya", "keterangan"]
        maint_out = maint_out[[c for c in _urutan if c in maint_out.columns]
                              + [c for c in maint_out.columns if c not in _urutan and c != "bulan_no"]]
    _write_sheet("Biaya Maintenance", maint_out, highlight_col="kelompok_unit" if "kelompok_unit" in maint_out.columns else None,
                 rupiah_cols={"biaya"})

    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def load_from_upload_sparepart(uploaded_file) -> pd.DataFrame:
    """Parse an uploaded spare-part usage detail file (e.g. 'Rincian_Pemakaian.xls').
    Note: in the source export, the long description text is actually stored in the
    'ACCOUNT_DESC' column (the 'KETERANGAN' column only holds the unit code)."""
    raw = pd.read_excel(uploaded_file, sheet_name=0, header=0)
    pattern = re.compile(
        r'^PEMELIHARAAN\s+(RUTIN|NON RUTIN)\s+(.*?)\s+(SPAREPART|ALOKASI WORKSHOP|SERVICE LUAR|LAIN-LAIN)\s+(PLANTATION|MINING)\s+(.*?)\s+-\s+(.*)$'
    )
    month_id_map = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                     7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    raw["TGL"] = pd.to_datetime(raw["TGL"], errors="coerce")
    raw = raw.dropna(subset=["TGL", "ACCOUNT_DESC", "TOTAL"])

    rows = []
    for _, r in raw.iterrows():
        desc = str(r["ACCOUNT_DESC"]).strip()
        m = pattern.match(desc)
        if not m:
            continue
        jenis, kategori_sparepart, tipe_biaya, kelompok, lokasi, unit = m.groups()
        dt = r["TGL"]
        rows.append(dict(
            tanggal=dt.date().isoformat(), bulan=month_id_map.get(dt.month, ''), bulan_no=dt.month,
            lokasi=lokasi.strip(), kelompok=kelompok.strip(),
            jenis_pemeliharaan=jenis.strip(), kategori_sparepart=kategori_sparepart.strip(),
            nama_unit=unit.strip(), kode_barang=str(r["KODE BRG"]),
            part_number=str(r["PART NUMBER"]) if pd.notna(r["PART NUMBER"]) else '',
            nama_barang=str(r["NAMA BARANG"]), qty=float(r["QTY"]), satuan=str(r["SAT"]),
            biaya=float(r["TOTAL"]),
            group_desc=str(r["GROUP_DESC"]), class_desc=str(r["CLASS_DESC"]), subclass_desc=str(r["SUBCLASS_DESC"]),
        ))
    return pd.DataFrame(rows)

def _guess_site_from_filename(filename: str) -> str:
    """Tebak nama site dari nama file upload Workshop (mis. 'Workshop_Sungai_Danau__PH_Gabungan_.xlsx' -> 'SUNGAI DANAU')."""
    name_up = filename.upper().replace("_", " ")
    if "BUHUT" in name_up and "LHL" in name_up:
        return "BUHUT LHL"
    if "SUNGAI" in name_up and "DANAU" in name_up:
        return "SUNGAI DANAU"
    if "BUHUT" in name_up:
        return "BUHUT"
    if "TANJUNG" in name_up:
        return "TANJUNG"
    if "KUMAI" in name_up:
        return "KUMAI"
    if "AMPAH" in name_up:
        return "AMPAH"
    return ""

def load_workshop_mttr_files(uploaded_files, unit_lookup_df=None) -> pd.DataFrame:
    """Parse file(s) 'Workshop_[Site]__Gabungan_.xlsx' (jurnal harian bengkel per site, 1 sheet per bulan).
    Menghasilkan data per KEJADIAN perbaikan (1 baris = 1 kejadian), dipakai utk hitung MTTR
    (Mean Time To Repair) = Total Jam / Jumlah Kejadian, difilter site & bulan saat render slide.
    Baris valid = Kegiatan berisi 'WS-PERBAIKAN UNIT' atau 'WS-PERBAIKAN DAN MAINTENANCE UNIT',
    dgn kolom Jumlah (jam) berupa angka. Kode unit diekstrak dari awal kolom Remark (mis. '322-012'),
    dicocokkan ke kode_unit pada data utama (unit_lookup_df) utk dapat id_unit/nama_unit/jenis_unit."""
    import openpyxl as _oxl
    import re as _re
    REPAIR_KEGIATAN = {"WS-PERBAIKAN UNIT", "WS-PERBAIKAN DAN MAINTENANCE UNIT"}
    MONTH_MAP_ID = {"Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "May": "May", "Jun": "Jun",
                     "Jul": "Jul", "Aug": "Aug", "Sep": "Sep", "Oct": "Oct", "Nov": "Nov", "Dec": "Dec"}
    # Fallback deteksi bulan dari NAMA FILE (dipakai kalau nama sheet TIDAK diawali nama bulan, mis. sheet
    # bernama "Running Account Daily Journal" spt pd file export terbaru -- bulannya ada di nama file, bukan sheet).
    # Dicek berdasarkan kata bhs Indonesia (Juli, Agustus, dst) MAUPUN singkatan bhs Inggris (Jul, Aug, dst).
    MONTH_FILENAME_MAP = [
        ("JANUARI", "Jan"), ("FEBRUARI", "Feb"), ("MARET", "Mar"), ("APRIL", "Apr"), ("MEI", "May"),
        ("JUNI", "Jun"), ("JULI", "Jul"), ("AGUSTUS", "Aug"), ("AGT", "Aug"), ("SEPTEMBER", "Sep"),
        ("OKTOBER", "Oct"), ("NOVEMBER", "Nov"), ("DESEMBER", "Dec"),
        ("JAN", "Jan"), ("FEB", "Feb"), ("MAR", "Mar"), ("APR", "Apr"), ("JUN", "Jun"), ("JUL", "Jul"),
        ("AUG", "Aug"), ("SEP", "Sep"), ("OCT", "Oct"), ("NOV", "Nov"), ("DEC", "Dec"),
    ]

    def _guess_bulan_from_filename(filename: str):
        name_up = filename.upper()
        # Batasi pencocokan HANYA pd kata yg benar2 berdiri sendiri (diapit non-huruf: _, spasi, angka, awal/akhir
        # teks) -- spy tdk salah tangkap substring kebetulan spt "JUN" yg ada di dalam "TANJUNG".
        for kata, bulan_kode in MONTH_FILENAME_MAP:
            if _re.search(r'(?<![A-Z])' + kata + r'(?![A-Z])', name_up):
                return bulan_kode
        return None

    KODE_PATTERN = _re.compile(r'^(\d{2,3}-\d{2,3})')

    kode_lookup = None
    if unit_lookup_df is not None and not unit_lookup_df.empty and "kode_unit" in unit_lookup_df.columns:
        kode_lookup = (unit_lookup_df.dropna(subset=["kode_unit"]).drop_duplicates("kode_unit")
                        .set_index("kode_unit")[["id_unit", "nama_unit", "jenis_unit", "kategori"]])

    rows = []
    for uf in uploaded_files:
        site = _guess_site_from_filename(uf.name)
        if not site:
            continue
        bulan_fallback = _guess_bulan_from_filename(uf.name)  # dipakai kalau nama sheet tdk mengandung nama bulan
        uf.seek(0)  # reset cursor -- Streamlit menjalankan ulang skrip tiap ada interaksi (mis. klik tombol),
                    # dan file yg sudah pernah dibaca sebelumnya cursor-nya bisa tertinggal di akhir file
        wb = _oxl.load_workbook(uf, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            bulan = MONTH_MAP_ID.get(sheet_name.strip()[:3].title()) or bulan_fallback
            if not bulan:
                continue
            ws = wb[sheet_name]
            for row in ws.iter_rows(values_only=True):
                tgl = row[0] if len(row) > 0 else None
                kegiatan = row[1] if len(row) > 1 else None
                account = row[2] if len(row) > 2 else None
                remark = row[5] if len(row) > 5 else None
                jumlah = row[10] if len(row) > 10 else None
                if kegiatan in REPAIR_KEGIATAN and isinstance(jumlah, (int, float)) and remark:
                    m = KODE_PATTERN.match(str(remark).strip())
                    kode_unit = m.group(1) if m else None
                    id_unit, nama_unit, jenis_unit, kategori = None, None, None, None
                    if kode_unit is not None and kode_lookup is not None and kode_unit in kode_lookup.index:
                        lu = kode_lookup.loc[kode_unit]
                        id_unit, nama_unit, jenis_unit, kategori = lu["id_unit"], lu["nama_unit"], lu["jenis_unit"], lu["kategori"]
                    rows.append(dict(
                        lokasi=site, bulan=bulan,
                        tanggal=tgl.date().isoformat() if hasattr(tgl, "date") else None,
                        account=str(account) if account is not None else None,
                        kode_unit=kode_unit, id_unit=id_unit, nama_unit=nama_unit, jenis_unit=jenis_unit, kategori=kategori,
                        kegiatan=kegiatan, remark=str(remark).strip(), jumlah_jam=float(jumlah),
                    ))
        wb.close()
    return pd.DataFrame(rows)

with st.sidebar:
    MINING_SITES = ["TANJUNG", "BUHUT", "BUHUT LHL", "AMPAH"]
    PLANTATION_SITES = ["SUNGAI DANAU", "KUMAI"]
    DIVISI_MAP = {"Mining": MINING_SITES, "Plantation": PLANTATION_SITES}

    # ================= AKSES ADMIN =================
    # Hanya ADMIN (pemilik) yg bisa upload data & simpan ke GitHub. Orang lain yg membuka link share
    # cuma bisa memakai filter & melihat/unduh laporan. Password diambil dari Secrets `ADMIN_PASSWORD`.
    # Status login disimpan di session_state -> berlaku per browser/sesi, TIDAK ikut ke orang lain.
    import hmac as _hmac
    try:
        _admin_pw_secret = st.secrets.get("ADMIN_PASSWORD")
    except Exception:
        _admin_pw_secret = None
    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False

    if _admin_pw_secret:
        if st.session_state["is_admin"]:
            _c_adm1, _c_adm2 = st.columns([3, 2])
            _c_adm1.markdown("🔓 **Mode Admin aktif**")
            if _c_adm2.button("Logout", use_container_width=True):
                st.session_state["is_admin"] = False
                st.rerun()
        else:
            with st.expander("🔒 Login Admin (khusus upload data)"):
                _pw_input = st.text_input("Password Admin", type="password", key="_admin_pw_input")
                if st.button("Masuk", use_container_width=True):
                    if _pw_input and _hmac.compare_digest(str(_pw_input), str(_admin_pw_secret)):
                        st.session_state["is_admin"] = True
                        st.rerun()
                    else:
                        st.error("Password salah.")
        IS_ADMIN = st.session_state["is_admin"]
    else:
        # Secrets ADMIN_PASSWORD belum diisi -> perilaku lama (semua orang bisa upload), dgn peringatan.
        IS_ADMIN = True
        st.warning("⚠️ `ADMIN_PASSWORD` belum diisi di Secrets — saat ini SIAPA PUN yg punya link bisa upload data. "
                   "Isi Secrets tersebut supaya upload hanya bisa dilakukan admin.")

    def _admin_uploader(*args, **kwargs):
        """Pengganti st.file_uploader: hanya tampil utk admin. Non-admin -> dianggap tidak ada upload."""
        if not IS_ADMIN:
            return [] if kwargs.get("accept_multiple_files") else None
        return st.file_uploader(*args, **kwargs)

    if IS_ADMIN:
        st.markdown("### 📁 Sumber Data")
    df_raw = load_data(DATA_PATH, _file_mtime(DATA_PATH))
    maint_raw = load_maintenance_data(MAINT_DATA_PATH, _file_mtime(MAINT_DATA_PATH))
    sparepart_raw = load_sparepart_data(SPAREPART_DATA_PATH, _file_mtime(SPAREPART_DATA_PATH))
    mttr_raw = load_mttr_data(MTTR_DATA_PATH, _file_mtime(MTTR_DATA_PATH))

    # --- Upload Data Realisasi: MENGGABUNG (update) ke data yg sudah ada (id_unit + bulan) ---
    # supaya Budget yg sudah ada (sampai Des) tetap utuh, cuma kolom Realisasi yg diperbarui.
    # accept_multiple_files=True -- spy bisa upload BEBERAPA file site sekaligus (mis. AB_Kumai_Jul,
    # TR_Tanjung_Jul, dst) dalam satu kali pilih, diproses satu-per-satu scr berurutan.
    _realisasi_diupload = False
    _maint_diupload = False
    _sparepart_diupload = False
    _mttr_diupload = False

    uploaded_realisasi_list = _admin_uploader("Upload Data Realisasi (format sama dgn template Budget)",
                                                 type=["xls", "xlsx"], accept_multiple_files=True)
    if uploaded_realisasi_list:
        total_upd, total_unmatch = 0, 0
        gagal = []
        for uf_real in uploaded_realisasi_list:
            try:
                df_raw, n_upd, n_unmatch, new_rows_detail = load_from_upload_realisasi(uf_real, df_raw)
                total_upd += n_upd
                total_unmatch += n_unmatch
                _realisasi_diupload = True
            except Exception as e:
                gagal.append(f"{uf_real.name}: {e}")
        if total_upd or total_unmatch:
            st.success(f"Realisasi ter-update untuk {total_upd:,} baris dari {len(uploaded_realisasi_list) - len(gagal)} file "
                       f"(id_unit + bulan cocok dgn data existing).")
        if gagal:
            st.error("Gagal membaca sebagian file Realisasi:\n" + "\n".join(f"- {g}" for g in gagal))

    def _gabung_per_site_bulan(base_df, new_df):
        """Gabungkan data upload ke data lama per (lokasi, bulan): kombinasi site+bulan yg ADA di file upload
        diganti dgn versi baru, sisanya (bulan/site lain) TETAP dipertahankan. Sebelumnya upload langsung
        MENIMPA seluruh data lama -> data Jan-Jul hilang begitu file Agustus diupload."""
        if new_df is None or new_df.empty:
            return base_df
        if base_df is None or base_df.empty or not {"lokasi", "bulan"}.issubset(base_df.columns):
            return new_df.reset_index(drop=True)
        kunci_baru = set(zip(new_df["lokasi"], new_df["bulan"]))
        sisa = base_df[~pd.Series(list(zip(base_df["lokasi"], base_df["bulan"])), index=base_df.index).isin(kunci_baru)]
        hasil = pd.concat([sisa, new_df], ignore_index=True, sort=False)
        if "tanggal" in hasil.columns:
            hasil = hasil.sort_values(["tanggal", "lokasi"], kind="stable").reset_index(drop=True)
        return hasil

    def _ringkas_bulan(df_):
        if df_ is None or df_.empty or "bulan" not in df_.columns:
            return "-"
        return ", ".join([m for m in MONTH_ORDER if m in set(df_["bulan"].dropna())])

    uploaded_maint_list = _admin_uploader("Upload Data Maintenance (Pemeliharaan)", type=["xls", "xlsx"],
                                           accept_multiple_files=True)
    if uploaded_maint_list:
        _gagal_m = []
        _baru_m = []
        for uf_m in uploaded_maint_list:
            try:
                _baru_m.append(load_from_upload_maintenance(uf_m))
            except Exception as e:
                _gagal_m.append(f"{uf_m.name}: {e}")
        _baru_m = [d for d in _baru_m if not d.empty]
        if _baru_m:
            _new_m = pd.concat(_baru_m, ignore_index=True)
            maint_raw = _gabung_per_site_bulan(maint_raw, _new_m)
            _maint_diupload = True
            st.success(f"Maintenance: {len(_new_m):,} baris dari file upload digabung (bulan di file: {_ringkas_bulan(_new_m)}). "
                       f"Total data sekarang {len(maint_raw):,} baris, bulan tersedia: {_ringkas_bulan(maint_raw)}.")
        if _gagal_m:
            st.error("Gagal membaca sebagian file maintenance:\n" + "\n".join(f"- {g}" for g in _gagal_m))

    uploaded_sparepart_list = _admin_uploader("Upload Data Pemakaian Sparepart", type=["xls", "xlsx"],
                                               accept_multiple_files=True)
    if uploaded_sparepart_list:
        _gagal_s = []
        _baru_s = []
        for uf_s in uploaded_sparepart_list:
            try:
                _baru_s.append(load_from_upload_sparepart(uf_s))
            except Exception as e:
                _gagal_s.append(f"{uf_s.name}: {e}")
        _baru_s = [d for d in _baru_s if not d.empty]
        if _baru_s:
            _new_s = pd.concat(_baru_s, ignore_index=True)
            sparepart_raw = _gabung_per_site_bulan(sparepart_raw, _new_s)
            _sparepart_diupload = True
            st.success(f"Sparepart: {len(_new_s):,} baris dari file upload digabung (bulan di file: {_ringkas_bulan(_new_s)}). "
                       f"Total data sekarang {len(sparepart_raw):,} baris, bulan tersedia: {_ringkas_bulan(sparepart_raw)}.")
        if _gagal_s:
            st.error("Gagal membaca sebagian file sparepart:\n" + "\n".join(f"- {g}" for g in _gagal_s))

    uploaded_workshop = _admin_uploader(
        "Upload Data MTTR",
        type=["xls", "xlsx"], accept_multiple_files=True)
    if uploaded_workshop:
        try:
            mttr_raw_new = load_workshop_mttr_files(uploaded_workshop, df_raw)
            if not mttr_raw_new.empty:
                # --- GABUNG (bukan timpa total!) dgn data MTTR yg sudah ada -- utk kombinasi (lokasi, bulan)
                # yg SAMA dgn upload baru, baris lama dibuang dulu (spy tdk dobel kalau ini revisi), lalu
                # baris baru ditambahkan. Kombinasi (lokasi, bulan) LAIN yg tdk ada di upload ini TETAP UTUH. ---
                _kombinasi_baru = set(zip(mttr_raw_new["lokasi"], mttr_raw_new["bulan"]))
                if not mttr_raw.empty:
                    _mask_lama_yg_ditimpa = mttr_raw.apply(lambda r: (r["lokasi"], r["bulan"]) in _kombinasi_baru, axis=1)
                    mttr_raw = pd.concat([mttr_raw[~_mask_lama_yg_ditimpa], mttr_raw_new], ignore_index=True)
                else:
                    mttr_raw = mttr_raw_new
                st.success(f"Berhasil memuat data MTTR dari {len(uploaded_workshop)} file workshop "
                           f"({mttr_raw_new['lokasi'].nunique()} site, bulan: {', '.join(sorted(mttr_raw_new['bulan'].unique()))}) "
                           f"-- digabung dgn data bulan lain yg sudah ada sebelumnya.")
                _mttr_diupload = True
            else:
                st.warning("File workshop terbaca, tapi tidak ada baris perbaikan yang valid ditemukan.")
        except Exception as e:
            st.error(f"Gagal membaca file workshop: {e}")


    # --- Saring otomatis: baris dgn Realisasi DAN Budget SAMA-SAMA kosong (semua kolom = 0) dianggap
    # unit yg tidak berlaku (mis. belum ada rencana sama sekali) -- dikecualikan dari SELURUH downstream
    # (dashboard, download, PPT). AMPAH dikecualikan dari aturan ini krn site tsb memang belum beroperasi. ---
    if not df_raw.empty:
        _realisasi_cols_chk = [c for c in ["pendapatan_realisasi", "prestasi_realisasi", "upah_realisasi",
                                            "qty_bbm_realisasi", "harga_bbm_realisasi", "biaya_bbm_realisasi",
                                            "maintenance_realisasi", "penyusutan_realisasi", "lainnya_realisasi",
                                            "biaya_tidak_langsung_realisasi"] if c in df_raw.columns]
        _budget_cols_chk = [c for c in ["pendapatan_budget", "prestasi_budget", "upah_budget",
                                         "qty_bbm_budget", "harga_bbm_budget", "biaya_bbm_budget",
                                         "maintenance_budget", "penyusutan_budget", "lainnya_budget",
                                         "biaya_tidak_langsung_budget"] if c in df_raw.columns]
        if _realisasi_cols_chk and _budget_cols_chk:
            _realisasi_zero = (df_raw[_realisasi_cols_chk].fillna(0) == 0).all(axis=1)
            _budget_zero = (df_raw[_budget_cols_chk].fillna(0) == 0).all(axis=1)
            _is_empty_unit = _realisasi_zero & _budget_zero & (df_raw["lokasi"] != "AMPAH")
            _n_filtered = int(_is_empty_unit.sum())
            if _n_filtered > 0:
                df_raw = df_raw[~_is_empty_unit].copy()
                st.caption(f"ℹ️ {_n_filtered} baris disaring otomatis (Realisasi & Budget sama-sama kosong).")

    # --- Tombol simpan PERMANEN: SATU tombol yg otomatis menyesuaikan isinya sesuai data APA SAJA yg
    # benar2 diupload sesi ini (pakai flag _xxx_diupload, BUKAN sekadar "tidak kosong" -- krn df_raw/
    # maint_raw/sparepart_raw/mttr_raw SELALU terisi dari file CSV dasar sejak awal meski tdk diupload apa2).
    # Kalau secrets GitHub (GITHUB_TOKEN, GITHUB_REPO) sdh dikonfigurasi -> commit LANGSUNG ke GitHub via API
    # (user tdk perlu download+upload manual). Kalau BELUM dikonfigurasi -> fallback ke tombol download biasa
    # (spy fitur lama tetap jalan utk user yg blm setup token). ---
    _jumlah_tipe_diupload = sum([_realisasi_diupload, _maint_diupload, _sparepart_diupload, _mttr_diupload])
    if IS_ADMIN and _jumlah_tipe_diupload > 0:
        st.markdown("---")
        st.markdown("**💾 Simpan Perubahan Secara Permanen**")

        _files_to_save = {}
        if _realisasi_diupload:
            _files_to_save["data_bkms.csv"] = df_raw.to_csv(index=False)
        if _maint_diupload:
            _files_to_save["data_maintenance.csv"] = maint_raw.to_csv(index=False)
        if _sparepart_diupload:
            _files_to_save["data_sparepart.csv"] = sparepart_raw.to_csv(index=False)
        if _mttr_diupload:
            _files_to_save["data_mttr.csv"] = mttr_raw.to_csv(index=False)

        _gh_token = st.secrets.get("GITHUB_TOKEN")
        _gh_repo = st.secrets.get("GITHUB_REPO")
        _gh_branch = st.secrets.get("GITHUB_BRANCH", "main")

        if _gh_token and _gh_repo:
            # --- Mode OTOMATIS: commit langsung ke GitHub via Contents API ---
            def _github_update_file(path: str, content_str: str, token: str, repo: str, branch: str, message: str):
                import requests, base64
                url = f"https://api.github.com/repos/{repo}/contents/{path}"
                headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
                # Ambil SHA file saat ini dulu (wajib utk update file yg sdh ada di GitHub)
                r_get = requests.get(url, headers=headers, params={"ref": branch}, timeout=30)
                sha = r_get.json().get("sha") if r_get.status_code == 200 else None
                content_b64 = base64.b64encode(content_str.encode("utf-8")).decode("utf-8")
                payload = {"message": message, "content": content_b64, "branch": branch}
                if sha:
                    payload["sha"] = sha
                r_put = requests.put(url, headers=headers, json=payload, timeout=30)
                return r_put.status_code in (200, 201), r_put.json()

            if st.button("🚀 Simpan ke GitHub Otomatis", use_container_width=True, type="primary"):
                _berhasil, _gagal = [], []
                with st.spinner(f"Menyimpan {len(_files_to_save)} file ke GitHub..."):
                    for _fname, _content in _files_to_save.items():
                        _ok, _resp = _github_update_file(
                            _fname, _content, _gh_token, _gh_repo, _gh_branch,
                            message=f"Update {_fname} via dashboard upload",
                        )
                        if _ok:
                            _berhasil.append(_fname)
                        else:
                            _gagal.append(f"{_fname}: {_resp.get('message', 'unknown error')}")
                if _berhasil:
                    st.success(f"✅ Berhasil disimpan ke GitHub: {', '.join(_berhasil)}. "
                               f"Reboot aplikasi supaya perubahan terpakai.")
                if _gagal:
                    st.error("Gagal menyimpan sebagian file:\n" + "\n".join(f"- {g}" for g in _gagal))
        else:
            # --- Mode MANUAL (fallback): secrets blm dikonfigurasi -> download spt biasa ---
            st.caption("💡 Mau tombol ini otomatis commit ke GitHub tanpa download manual? Tambahkan "
                       "`GITHUB_TOKEN` & `GITHUB_REPO` di Settings → Secrets aplikasi Anda.")
            if len(_files_to_save) == 1:
                _nama_file, _isi_str = next(iter(_files_to_save.items()))
                st.download_button(
                    f"⬇️ Simpan Perubahan Secara Permanen ({_nama_file})",
                    _isi_str.encode("utf-8"), file_name=_nama_file, mime="text/csv",
                    use_container_width=True,
                )
            else:
                import io as _io_zip
                import zipfile as _zipfile
                _zip_buf = _io_zip.BytesIO()
                with _zipfile.ZipFile(_zip_buf, "w", _zipfile.ZIP_DEFLATED) as _zf:
                    for _fname, _content in _files_to_save.items():
                        _zf.writestr(_fname, _content)
                st.caption(f"File yg akan disimpan: {', '.join(_files_to_save.keys())}")
                st.download_button(
                    "⬇️ Simpan Perubahan Secara Permanen (ZIP)",
                    _zip_buf.getvalue(), file_name="update_data_bkms.zip", mime="application/zip",
                    use_container_width=True,
                )

    # Lengkapi kolom 'kategori' (AB/TR), 'jenis_unit', & 'id_unit' di data maintenance & sparepart (dicocokkan
    # lewat KODE UNIT ke data utama, lihat lookup_atribut_unit). Hanya di MEMORI -- TIDAK lagi menulis ulang file
    # CSV di server: dulu penulisan ulang ini bisa MENIMPA file CSV yg lebih baru dgn isi cache yg sudah usang.
    # Kolom yg SUDAH terisi dipertahankan; hanya yg kosong yg diisi.
    if not df_raw.empty and "nama_unit" in df_raw.columns and "kategori" in df_raw.columns:
        _unit_lookup_cols = [c for c in ["kategori", "jenis_unit", "id_unit"] if c in df_raw.columns]

        def _lengkapi_atribut_unit(df_):
            if df_.empty or "nama_unit" not in df_.columns:
                return df_
            if not any(c not in df_.columns or df_[c].isna().any() for c in _unit_lookup_cols):
                return df_
            df_ = df_.copy()
            _lk = lookup_atribut_unit(df_, df_raw, _unit_lookup_cols)
            for _col in _unit_lookup_cols:
                df_[_col] = df_[_col].where(df_[_col].notna(), _lk[_col]) if _col in df_.columns else _lk[_col]
            return df_

        maint_raw = _lengkapi_atribut_unit(maint_raw)
        sparepart_raw = _lengkapi_atribut_unit(sparepart_raw)

    # --- Info (khusus admin): bulan yg TERSEDIA di tiap data yg sedang dimuat aplikasi ---
    if IS_ADMIN:
        def _bln(df_):
            if df_ is None or df_.empty or "bulan" not in df_.columns:
                return "kosong"
            _b = [m for m in MONTH_ORDER if m in set(df_["bulan"].dropna())]
            return f"{', '.join(_b)} ({len(df_):,} baris)"
        with st.expander("\U0001F4CB Cek data yang sedang dimuat"):
            st.caption(f"**Maintenance:** {_bln(maint_raw)}")
            st.caption(f"**Sparepart:** {_bln(sparepart_raw)}")
            st.caption(f"**MTTR:** {_bln(mttr_raw)}")

    sasaran_mutu_raw = load_sasaran_mutu_data(SASARAN_MUTU_PATH, _file_mtime(SASARAN_MUTU_PATH))

    st.markdown("---")
    st.markdown("### 🏭 Divisi")
    sel_divisi = st.multiselect("Divisi (Mining / Plantation)", list(DIVISI_MAP.keys()), default=list(DIVISI_MAP.keys()))
    sites_allowed_by_divisi = [s for d in sel_divisi for s in DIVISI_MAP.get(d, [])]

    st.markdown("---")
    st.markdown("### 🔎 Filter")

    all_sites_raw = sorted(df_raw["lokasi"].dropna().unique().tolist())
    site_opts = [s for s in all_sites_raw if s in sites_allowed_by_divisi] if sel_divisi else []
    sel_site = st.multiselect("Site / Lokasi", site_opts, default=site_opts)


    month_opts = [m for m in MONTH_ORDER if m in df_raw["bulan"].unique()]
    sel_month = st.multiselect("Bulan", month_opts, default=month_opts)

    kat_opts = sorted(df_raw["kategori"].dropna().unique().tolist())
    kat_labels = [KATEGORI_LABEL.get(k, k) for k in kat_opts]
    sel_kat_labels = st.multiselect("Kategori Unit", kat_labels, default=kat_labels)
    sel_kat = [k for k in kat_opts if KATEGORI_LABEL.get(k, k) in sel_kat_labels]

    kriteria_scope_df = df_raw[df_raw["lokasi"].isin(sel_site) & df_raw["kategori"].isin(sel_kat)]
    kriteria_opts_raw = sorted(kriteria_scope_df["kriteria_unit"].dropna().unique().tolist()) if "kriteria_unit" in df_raw.columns else []
    has_null_kriteria = ("kriteria_unit" in df_raw.columns) and kriteria_scope_df["kriteria_unit"].isna().any()
    kriteria_opts = kriteria_opts_raw + (["Tidak Diketahui"] if has_null_kriteria else [])
    if kriteria_opts:
        sel_kriteria = st.multiselect("Kriteria Unit (Tarif)", kriteria_opts, default=kriteria_opts)
    else:
        sel_kriteria = []

    unit_opts_df = df_raw[
        df_raw["lokasi"].isin(sel_site) & df_raw["kategori"].isin(sel_kat)
    ][["nama_unit"]].dropna().drop_duplicates().copy()
    unit_opts_df["unit_label"] = unit_opts_df["nama_unit"].apply(_unit_label)
    unit_opts = sorted(unit_opts_df["unit_label"].unique().tolist())
    sel_id_unit = st.multiselect(
        "ID Unit (opsional, kosongkan = semua unit) — ketik ID Unit atau nama unit",
        unit_opts, default=[],
    )

# ---------------------------------------------------------------
# APPLY FILTERS (data utama)
# ---------------------------------------------------------------
df = df_raw[
    df_raw["lokasi"].isin(sel_site) &
    df_raw["bulan"].isin(sel_month) &
    df_raw["kategori"].isin(sel_kat)
].copy()

if "kriteria_unit" in df.columns and kriteria_opts:
    sel_kriteria_actual = [k for k in sel_kriteria if k != "Tidak Diketahui"]
    include_null = "Tidak Diketahui" in sel_kriteria
    mask = df["kriteria_unit"].isin(sel_kriteria_actual)
    if include_null:
        mask = mask | df["kriteria_unit"].isna()
    df = df[mask]

if sel_id_unit:
    df["unit_label"] = df["nama_unit"].apply(_unit_label)
    df = df[df["unit_label"].isin(sel_id_unit)]

maint_df_site_bulan = pd.DataFrame()
if not maint_raw.empty:
    maint_df_site_bulan = maint_raw[
        maint_raw["lokasi"].isin(sel_site) &
        maint_raw["bulan"].isin(sel_month)
    ].copy()
    if sel_id_unit:
        maint_df_site_bulan["unit_label"] = maint_df_site_bulan["nama_unit"].apply(_unit_label)
        maint_df_site_bulan = maint_df_site_bulan[maint_df_site_bulan["unit_label"].isin(sel_id_unit)]

sparepart_df_site_bulan = pd.DataFrame()
if not sparepart_raw.empty:
    sparepart_df_site_bulan = sparepart_raw[
        sparepart_raw["lokasi"].isin(sel_site) &
        sparepart_raw["bulan"].isin(sel_month)
    ].copy()
    if sel_id_unit:
        sparepart_df_site_bulan["unit_label"] = sparepart_df_site_bulan["nama_unit"].apply(_unit_label)
        sparepart_df_site_bulan = sparepart_df_site_bulan[sparepart_df_site_bulan["unit_label"].isin(sel_id_unit)]

sasaran_mutu_df = pd.DataFrame()
if not sasaran_mutu_raw.empty:
    sasaran_mutu_df = sasaran_mutu_raw[
        sasaran_mutu_raw["lokasi"].isin(sel_site) &
        sasaran_mutu_raw["bulan"].isin(sel_month) &
        sasaran_mutu_raw["kategori"].isin(sel_kat)
    ].copy()
    if sel_id_unit:
        sasaran_mutu_df["unit_label"] = sasaran_mutu_df["nama_unit"].apply(_unit_label)
        sasaran_mutu_df = sasaran_mutu_df[sasaran_mutu_df["unit_label"].isin(sel_id_unit)]

if sel_id_unit:
    st.caption(f"🔗 Dashboard sedang difilter untuk ID Unit: {', '.join(sel_id_unit)}")


def fmt_rp(x):
    if abs(x) >= 1e9:
        return f"Rp {x/1e9:,.2f} M"
    if abs(x) >= 1e6:
        return f"Rp {x/1e6:,.1f} Jt"
    if abs(x) >= 1e3:
        return f"Rp {x/1e3:,.1f} Rb"
    return f"Rp {x:,.0f}"

def achievement(real, budget):
    if budget == 0 or pd.isna(real) or pd.isna(budget):
        return None
    return real / budget * 100

def _safe_chart_val(v, ndigits=1):
    """Pengaman universal utk nilai yg dikirim ke chart PPTX (native chart XLSX-embedded) -- xlsxwriter akan
    ERROR keras (TypeError) kalau ada NaN/Inf yg lolos, jadi SEMUA nilai numerik yg dikirim ke add_series()
    HARUS lewat fungsi ini dulu. Aman dipanggil dgn v=None, NaN, Inf, string, atau angka biasa."""
    if v is None or pd.isna(v):
        return 0
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return 0
    if fv in (float("inf"), float("-inf")):
        return 0
    return round(fv, ndigits)

def capaian_per_target_group(df, realisasi_col, target_col):
    """Metodologi perhitungan Capaian utk Utilisasi/Availability/Downtime (BUKAN average langsung semua baris) --
    krn 1 blok (mis. Plantation Transportasi) bisa punya BEBERAPA target berbeda (mis. 3 target Utilisasi: 35/95/100)
    tergantung jenis unit, & average langsung akan bias ke target dgn jumlah unit TERBANYAK. Metodologi yg benar:
      1. Kelompokkan baris berdasarkan nilai TARGET yg unik (bukan per unit/per baris)
      2. Rata-ratakan Realisasi DI DALAM tiap kelompok target tsb
      3. Hitung Capaian tiap kelompok = (avg Realisasi kelompok) / (target kelompok) x 100%
      4. Hasil akhir (Realisasi, Target, Capaian) yg ditampilkan = rata-rata SEDERHANA dari nilai per-kelompok
         (setiap kelompok target dapat bobot yg SAMA, terlepas dari jumlah unit di dalamnya)
    Return: (avg_realisasi_display, avg_target_display, avg_capaian) -- ketiganya None kalau data kosong."""
    if df is None or df.empty or target_col not in df.columns or realisasi_col not in df.columns:
        return None, None, None
    valid = df.dropna(subset=[target_col])
    if valid.empty:
        return None, None, None
    grouped = valid.groupby(target_col)[realisasi_col].mean()  # avg Realisasi per kelompok target unik
    if grouped.empty:
        return None, None, None
    targets_unik = grouped.index.to_series()
    capaian_per_grup = grouped / targets_unik.values * 100
    avg_realisasi_display = grouped.mean()       # rata2 dari rata2-tiap-kelompok (bukan rata2 semua baris)
    avg_target_display = targets_unik.mean()     # rata2 dari NILAI TARGET UNIK (bukan rata2 semua baris)
    avg_capaian = capaian_per_grup.mean()        # rata2 dari Capaian tiap kelompok (bukan realisasi/target akhir)
    return avg_realisasi_display, avg_target_display, avg_capaian

def tandai_kriteria_sasaran_mutu(sm, data):
    """Tambahkan kolom kriteria_unit (Floating Tarif / Tarif Tetap) ke data Sasaran Mutu, diambil dari data BKMS
    per (lokasi, id_unit). Data Sasaran Mutu sendiri TIDAK punya kolom kriteria; sebelumnya penyaringan Tarif Tetap
    cuma lewat jenis_unit=='Tarif Tetap' yg hanya menangkap sebagian kecil unit (mis. bus S.Danau jenis_unit-nya
    'Rental Bus' padahal kriterianya Tarif Tetap -> ikut terhitung)."""
    if sm is None or sm.empty or data is None or data.empty or not {"lokasi", "id_unit", "kriteria_unit"}.issubset(data.columns):
        return sm
    if "id_unit" not in sm.columns:
        return sm
    _k = (data.dropna(subset=["kriteria_unit"])
          .assign(_id=lambda d: d["id_unit"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip())
          .drop_duplicates(["lokasi", "_id"]).set_index(["lokasi", "_id"])["kriteria_unit"].to_dict())
    out = sm.copy()
    _ids = out["id_unit"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    out["kriteria_unit"] = [_k.get((l, i)) for l, i in zip(out["lokasi"], _ids)]
    return out


def capaian_per_kelompok_unit(df, efektif_col, ideal_col, target_pct_col, kelompok_col="kelompok_unit", jenis_unit_col="jenis_unit", unit_sewa_col="unit_sewa", lokasi_col="lokasi"):
    """Metodologi Capaian Utilisasi/Availability BERBASIS SITE + KELOMPOK UNIT & FORMULA MENTAH (bukan target-value
    spt capaian_per_target_group, dan bukan pakai kolom persentase yg sudah jadi). Langkah:
      1. KECUALIKAN unit berkriteria 'Tarif Tetap' & unit_sewa=True -- pendapatannya tdk terpengaruh Utilisasi/
         Availability, jadi tdk relevan dihitung.
      2. Kelompokkan sisa baris berdasarkan KOMBINASI SITE + KELOMPOK UNIT (mis. 'KUMAI-Dump Truck' & 'S.DANAU-
         Dump Truck' dihitung sbg 2 kelompok TERPISAH, tdk digabung jadi 1 'Dump Truck' lintas site).
      3. Utk tiap kombinasi Site+Kelompok: Realisasi dihitung dari FORMULA mentah = Sum(Efektif/Tersedia) / Sum
         (Ideal) x 100 (BUKAN mengambil rata-rata kolom persentase yg sudah dihitung sebelumnya).
      4. Target tiap kombinasi = rata-rata target persentase (mis. utilisasi_target) DI DALAM kombinasi itu.
      5. Capaian tiap kombinasi = Realisasi / Target x 100.
      6. Hasil akhir (Realisasi, Target, Capaian) = rata-rata SEDERHANA dari nilai per-kombinasi Site+Kelompok
         (bobot sama per kombinasi, PERSIS SAMA dgn baris2 yg tampil di chart/tabel breakdown per Site & Kelompok
         Unit -- jadi kartu KPI ini adalah rata-rata dari baris2 breakdown tsb).
    Return: (avg_realisasi_display, avg_target_display, avg_capaian) -- None kalau data kosong/kolom tdk ada."""
    required = [efektif_col, ideal_col, target_pct_col, kelompok_col, lokasi_col]
    if df is None or df.empty or any(c not in df.columns for c in required):
        return None, None, None
    valid = df.copy()
    if "kriteria_unit" in valid.columns:
        # Kriteria unit dari data BKMS (lihat tandai_kriteria_sasaran_mutu) -> HANYA Floating Tarif.
        valid = valid[valid["kriteria_unit"] == "Floating Tarif"]
    if jenis_unit_col in valid.columns:
        valid = valid[valid[jenis_unit_col] != "Tarif Tetap"]
    if unit_sewa_col in valid.columns:
        valid = valid[valid[unit_sewa_col] != True]
    valid = valid.dropna(subset=[kelompok_col])
    if valid.empty:
        return None, None, None

    def _grp(g):
        sum_efektif = g[efektif_col].sum()
        sum_ideal = g[ideal_col].sum()
        realisasi_formula = (sum_efektif / sum_ideal * 100) if sum_ideal else None
        target_avg = g[target_pct_col].mean()
        return pd.Series({"realisasi": realisasi_formula, "target": target_avg})

    grouped = valid.groupby([lokasi_col, kelompok_col]).apply(_grp)
    grouped = grouped.dropna(subset=["realisasi", "target"])
    if grouped.empty:
        return None, None, None
    grouped["capaian"] = grouped["realisasi"] / grouped["target"] * 100

    avg_realisasi_display = grouped["realisasi"].mean()
    avg_target_display = grouped["target"].mean()
    avg_capaian = grouped["capaian"].mean()
    return avg_realisasi_display, avg_target_display, avg_capaian

# =====================================================================================================
# DETAIL PERHITUNGAN PPT (model baru): setiap slide PPT dibawa ke Excel, SEMUA angka = RUMUS yg tertaut
# ke sheet data mentah di workbook yg sama (Data BKMS, Data Sasaran Mutu, Data Pemeliharaan, Data MTTR).
# Per blok (TR / AB / MN) ada 4 slide; tiap slide = 1 sheet tampilan + 1 sheet "Perhitungan".
# Daftar baris (Site — Kelompok Unit) & urutannya ditentukan saat file dibuat (sama dgn PPT); angkanya rumus.
# =====================================================================================================
import io as _io_dx
import pandas as _pd_dx
from openpyxl import Workbook as _WB_dx
from openpyxl.utils import get_column_letter as _CL
from openpyxl.styles import Font as _Font, PatternFill as _Fill, Alignment as _Al, Border as _Bd, Side as _Sd
from openpyxl.formatting.rule import FormulaRule as _FRule
from openpyxl.chart import BarChart as _Bar, DoughnutChart as _Dn, Reference as _Ref
from openpyxl.chart.label import DataLabelList as _DLL
from openpyxl.chart.series import DataPoint as _DP

_DX_MINING = ["TANJUNG", "BUHUT", "BUHUT LHL", "AMPAH"]
_DX_SITE_ABBR = {"SUNGAI DANAU": "S.DANAU", "BUHUT LHL": "B.LHL"}
_DX_KEL_ABBR = {
    "TANGKI SERIES 300": "TANGKI 300", "TANGKI SERIES 500": "TANGKI 500",
    "TRUCK ARM ROLL 4x4": "ARM ROLL 4x4", "TRUCK ARM ROLL": "ARM ROLL",
    "TRUCK - TUS": "TUS", "TRUCK - BAK": "BAK",
    "DUMP TRUCK 4x4": "DT 4x4", "DUMP TRUCK HOWO": "DT HOWO", "DUMP TRUCK": "DT",
    "EXCAVATOR MEDIUM": "EXC MEDIUM", "EXCAVATOR MINI": "EXC MINI",
    "BULLDOZER MEDIUM": "BULLDOZER M", "BULLDOZER MINI": "BULLDOZER m",
    "BACKHOE LOADER": "BACKHOE", "FARM TRACKTOR": "TRACTOR", "WHEEL LOADER": "WHL LOADER",
    "TRUCK - BAK - PICK UP": "PICK UP", "PICK UP DOUBLE CABIN": "PU D.CABIN",
}
_DX_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
_DX_BLOK_TR, _DX_BLOK_AB, _DX_BLOK_MN = "PLANTATION - TRANSPORTASI", "PLANTATION - ALAT BERAT", "MINING"

_FONT = "Arial"
_NAVY = "1E2761"; _GOLD = "D98E1F"; _RED = "D64541"; _GREEN = "2E8B57"; _TEAL = "17A2B8"
_MUTED = "6B7280"; _DARK = "1F2937"; _PURPLE = "8E6BC9"; _BLUE = "2E6DB4"
_RED_BG = "FCE4E1"; _GREEN_BG = "DEF2E4"; _GOLD_BG = "FBEED8"; _GREY_BG = "F3F4F6"
_thin = _Sd(style="thin", color="D1D5DB")
_BORDER = _Bd(left=_thin, right=_thin, top=_thin, bottom=_thin)
_CENTER = _Al(horizontal="center", vertical="center", wrap_text=True)
_LEFT = _Al(horizontal="left", vertical="center", wrap_text=True)
_RIGHT = _Al(horizontal="right", vertical="center", indent=1)  # indent spy angka tdk menempel garis sel
_PALETTE = ["0D9488", "1E5AA8", "D98E1F", "17A2B8", "7B5EA7", "E06C4F", "5BA84C", "2C3E7A", "C94F8A", "8C9A2B",
            "467A9E", "B56A2E", "3FB49C", "9E9E3A", "6D4C9F", "A04545"]


def _f(size=10, bold=False, color=_DARK, italic=False):
    return _Font(name=_FONT, size=size, bold=bold, color=color, italic=italic)


def _fill(h):
    return _Fill("solid", start_color=h, end_color=h)


def _blok_py(lok, kat):
    if lok in _DX_MINING:
        return _DX_BLOK_MN
    return _DX_BLOK_AB if kat == "AB" else (_DX_BLOK_TR if kat == "TR" else None)


def _blok_formula(lok, kat):
    return (f'=IF(OR({lok}="TANJUNG",{lok}="BUHUT",{lok}="BUHUT LHL",{lok}="AMPAH"),"{_DX_BLOK_MN}",'
            f'IF({kat}="AB","{_DX_BLOK_AB}",IF({kat}="TR","{_DX_BLOK_TR}","")))')


def _rp(x):
    """Format Rupiah spt PPT (Rp .. M / Jt / Rb). FIXED (bukan TEXT) spy aman di Excel berbahasa Indonesia."""
    return (f'IF(ABS({x})>=1E9,"Rp "&FIXED({x}/1E9,2)&" M",IF(ABS({x})>=1E6,"Rp "&FIXED({x}/1E6,1)&" Jt",'
            f'IF(ABS({x})>=1E3,"Rp "&FIXED({x}/1E3,1)&" Rb","Rp "&FIXED({x},0))))')


def _pct(x, d=1):
    # tanpa pemisah ribuan (TRUE) -> "1017%" spt di PPT, bukan "1,017%"
    return f'FIXED({x}*100,{d},TRUE)&"%"'


def _site(l):
    return _DX_SITE_ABBR.get(l, l)


def _kel(k):
    return _DX_KEL_ABBR.get(k, k)


class _DataSheet:
    """Sheet data mentah: kolom bantu (rumus, header emas) + kolom asli (header navy)."""

    def __init__(self, wb, name, df, helpers):
        self.ws = wb.create_sheet(name)
        self.name = name
        self.df = df.reset_index(drop=True)
        self.cols = [h for h, _ in helpers] + list(self.df.columns)
        self.C = {n: _CL(i + 1) for i, n in enumerate(self.cols)}
        self.n = len(self.df) + 1
        ws = self.ws
        for i, h in enumerate(self.cols, start=1):
            c = ws.cell(1, i, h)
            c.font = _f(9, True, "FFFFFF"); c.fill = _fill(_GOLD if i <= len(helpers) else _NAVY); c.alignment = _CENTER
        num = set(self.df.select_dtypes("number").columns)
        off = len(helpers)
        for r, row in enumerate(self.df.itertuples(index=False), start=2):
            for j, name in enumerate(self.df.columns):
                v = row[j]
                if v is None or (not isinstance(v, str) and _pd_dx.isna(v)):
                    continue
                if isinstance(v, (bool,)) or str(type(v)).endswith("bool_'>"):
                    v = bool(v)
                elif name in num:
                    v = float(v)
                ws.cell(r, off + 1 + j, v)
            for k, (h, fn) in enumerate(helpers):
                ws.cell(r, k + 1, fn(self.C, r))
        ws.freeze_panes = ws.cell(2, off + 1)
        for i in range(1, len(self.cols) + 1):
            ws.column_dimensions[_CL(i)].width = 14
        ws.column_dimensions["A"].width = 27
        if "nama_unit" in self.C:
            ws.column_dimensions[self.C["nama_unit"]].width = 34

    def R(self, col):
        return f"'{self.name}'!${self.C[col]}$2:${self.C[col]}${self.n}"


class _Sheet:
    """Helper sheet tampilan / perhitungan."""

    def __init__(self, wb, name, grid=True):
        self.ws = wb.create_sheet(name)
        self.name = name
        self.P = f"'{name}'!"
        self.ws.sheet_view.showGridLines = False

    def put(self, ref, v, fmt=None, bold=False, color=_DARK, align=_RIGHT, size=9, border=True, fillc=None, italic=False):
        c = self.ws[ref]
        c.value = v
        c.font = _f(size, bold, color, italic)
        c.alignment = align
        if border:
            c.border = _BORDER
        if fmt:
            c.number_format = fmt
        if fillc:
            c.fill = _fill(fillc)
        return c

    def merge_put(self, rng, v, **kw):
        self.ws.merge_cells(rng)
        return self.put(rng.split(":")[0], v, **kw)

    def section(self, row, text, c1="B", c2="T", color=_NAVY):
        self.ws.merge_cells(f"{c1}{row}:{c2}{row}")
        c = self.ws[f"{c1}{row}"]
        c.value = text
        c.font = _f(11, True, "FFFFFF"); c.fill = _fill(color)
        c.alignment = _Al(horizontal="left", vertical="center", indent=1)
        self.ws.row_dimensions[row].height = 22

    def header(self, row, col_start, labels, height=30):
        for i, t in enumerate(labels):
            c = self.ws.cell(row, col_start + i, t)
            c.font = _f(9, True, "FFFFFF"); c.fill = _fill("4B5563"); c.alignment = _CENTER; c.border = _BORDER
        self.ws.row_dimensions[row].height = height

    def title(self, text, sub, blok, last_month, period_txt, note):
        ws = self.ws
        ws.merge_cells("B1:T1")
        ws["B1"] = text
        ws["B1"].font = _f(16, True, "FFFFFF"); ws["B1"].fill = _fill(_NAVY)
        ws["B1"].alignment = _Al(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[1].height = 34
        ws.merge_cells("B2:T2")
        ws["B2"] = sub
        ws["B2"].font = _f(10, False, "FFFFFF"); ws["B2"].fill = _fill(_NAVY)
        ws["B2"].alignment = _Al(horizontal="right", vertical="center", indent=1)
        # Baris info: label rata kanan (boleh meluber ke sel kosong di kirinya), nilai digabung 2 sel.
        # C3 (Blok) & G3 (Bulan terakhir) TETAP di posisinya -- dipakai sbg parameter oleh semua rumus.
        ws.merge_cells("C3:E3"); ws.merge_cells("G3:H3"); ws.merge_cells("K3:L3")
        for ref, v in (("B3", "Blok:"), ("F3", "s/d Bulan:"), ("J3", "Periode:")):
            ws[ref] = v
            ws[ref].font = _f(9.5, True, _MUTED); ws[ref].alignment = _Al(horizontal="right", vertical="center")
        for ref, v in (("C3", blok), ("G3", last_month), ("K3", period_txt)):
            ws[ref] = v
            ws[ref].font = _f(9.5, True, _NAVY)
            ws[ref].alignment = _Al(horizontal="left", vertical="center", indent=0, shrink_to_fit=(ref == "C3"))
        ws.merge_cells("N3:T3")
        ws["N3"] = note
        ws["N3"].font = _f(8, False, _MUTED, True)
        ws["N3"].alignment = _Al(horizontal="right", vertical="center", shrink_to_fit=True)
        ws.row_dimensions[3].height = 20
        ws.freeze_panes = "A4"

    def card(self, col, top, label, val_f, val_fmt, sub_f, pill_f, good_cond, accent, width_cols=3, sub2_f=None):
        """Kartu KPI: baris top = garis warna, +1 label, +2..+3 angka besar, +4 target/rincian, (+5 rincian 2), +last status."""
        ws = self.ws
        c0 = ws[col + "1"].column
        c3 = _CL(c0 + width_cols - 1)
        rng = lambda r: f"{col}{r}:{c3}{r}"
        ws.merge_cells(rng(top)); ws[f"{col}{top}"].fill = _fill(accent)
        ws.row_dimensions[top].height = 5
        ws.merge_cells(rng(top + 1)); ws[f"{col}{top+1}"] = label
        ws[f"{col}{top+1}"].font = _f(11, True, _MUTED); ws[f"{col}{top+1}"].alignment = _CENTER
        ws.merge_cells(f"{col}{top+2}:{c3}{top+3}"); ws[f"{col}{top+2}"] = val_f
        ws[f"{col}{top+2}"].font = _f(24, True, _DARK); ws[f"{col}{top+2}"].alignment = _CENTER
        ws[f"{col}{top+2}"].number_format = val_fmt
        ws.merge_cells(rng(top + 4)); ws[f"{col}{top+4}"] = sub_f
        ws[f"{col}{top+4}"].font = _f(10, False, _MUTED); ws[f"{col}{top+4}"].alignment = _CENTER
        last = top + 5
        if sub2_f is not None:
            ws.merge_cells(rng(top + 5)); ws[f"{col}{top+5}"] = sub2_f
            ws[f"{col}{top+5}"].font = _f(10, False, _MUTED); ws[f"{col}{top+5}"].alignment = _CENTER
            last = top + 6
        ws.merge_cells(rng(last)); ws[f"{col}{last}"] = pill_f
        ws[f"{col}{last}"].font = _f(10.5, True, _DARK); ws[f"{col}{last}"].alignment = _CENTER
        for rr in range(top + 1, last + 1):
            for cc in range(c0, c0 + width_cols):
                ws.cell(rr, cc).border = _Bd(left=_thin if cc == c0 else None, right=_thin if cc == c0 + width_cols - 1 else None,
                                             bottom=_thin if rr == last else None)
        if good_cond:
            ws.conditional_formatting.add(rng(last), _FRule(formula=[f"AND({good_cond})"], fill=_fill(_GREEN_BG), font=_Font(name=_FONT, bold=True, color=_GREEN)))
            ws.conditional_formatting.add(rng(last), _FRule(formula=[f"NOT(AND({good_cond}))"], fill=_fill(_RED_BG), font=_Font(name=_FONT, bold=True, color=_RED)))
        for rr, h in ((top + 1, 22), (top + 2, 22), (top + 3, 22), (top + 4, 18), (last, 22)):
            ws.row_dimensions[rr].height = h
        return last

    def note_box(self, rng, formula, color=_RED, bg=_RED_BG):
        ws = self.ws
        ws.merge_cells(rng)
        a, b = rng.split(":")
        c = ws[a]
        c.value = formula
        c.font = _f(11, True, color); c.fill = _fill(bg)
        c.alignment = _Al(horizontal="left", vertical="center", wrap_text=True, indent=1)
        r1, r2 = int("".join(ch for ch in a if ch.isdigit())), int("".join(ch for ch in b if ch.isdigit()))
        c1 = ws[a].column; c2 = ws[b].column
        med = _Sd(style="medium", color=color)
        for rr in range(r1, r2 + 1):
            ws.row_dimensions[rr].height = 20
            for cc in range(c1, c2 + 1):
                ws.cell(rr, cc).border = _Bd(top=med if rr == r1 else None, bottom=med if rr == r2 else None,
                                             left=med if cc == c1 else None, right=med if cc == c2 else None)

    def widths(self, spec):
        for k, v in spec.items():
            self.ws.column_dimensions[k].width = v


def _bar_chart(kind="col", grouping="clustered", overlap=None, gap=60, height=9, width=30, legend="t"):
    # Legenda default di ATAS chart: kalau di bawah, di Excel legenda bisa menumpuk dgn nama kelompok di sumbu
    # bawah yg turun jadi 2 baris (mis. "S.DANAU — TANGKI SERIES 300").
    ch = _Bar(); ch.type = kind; ch.grouping = grouping; ch.gapWidth = gap
    if overlap is not None:
        ch.overlap = overlap
    ch.height = height; ch.width = width
    ch.y_axis.delete = False; ch.x_axis.delete = False
    if legend:
        ch.legend.position = legend
        ch.legend.overlay = False  # legenda punya ruang sendiri, tdk menumpuk di atas area gambar
    else:
        ch.legend = None
    return ch


def _labels(ch, fmt, pos="outEnd", size=9):
    ch.dataLabels = _DLL(); ch.dataLabels.showVal = True; ch.dataLabels.numFmt = fmt
    ch.dataLabels.showSerName = False; ch.dataLabels.showCatName = False
    ch.dataLabels.showLegendKey = False; ch.dataLabels.showPercent = False
    if pos:
        ch.dataLabels.position = pos
    try:  # ukuran huruf label (dikecilkan kalau batangnya banyak spy tdk bertumpuk)
        from openpyxl.chart.text import RichText as _RT
        from openpyxl.drawing.text import Paragraph as _Pg, ParagraphProperties as _PP, CharacterProperties as _CP
        ch.dataLabels.txPr = _RT(p=[_Pg(pPr=_PP(defRPr=_CP(sz=int(size * 100), b=True)), endParaRPr=_CP())])
    except Exception:
        pass


def _fix_label_numfmt(xlsx_bytes):
    """openpyxl menulis <c:numFmt formatCode=".."/> di label chart TANPA sourceLinked="0", shg Excel/LibreOffice tetap
    memakai format sel sumber (mis. 1 desimal). Tambahkan sourceLinked="0" spy format label ("0%", "Rp .. Jt") dipakai."""
    import zipfile as _zf, re as _re
    src = _zf.ZipFile(_io_dx.BytesIO(xlsx_bytes))
    out = _io_dx.BytesIO()
    with _zf.ZipFile(out, "w", _zf.ZIP_DEFLATED) as dst:
        for it in src.infolist():
            data = src.read(it.filename)
            if it.filename.startswith("xl/charts/chart") and it.filename.endswith(".xml"):
                t = data.decode("utf-8")
                t = _re.sub(r'<((?:c:)?)numFmt formatCode="([^"]*)"\s*/>', r'<\1numFmt formatCode="\2" sourceLinked="0"/>', t)
                data = t.encode("utf-8")
            dst.writestr(it, data)
    return out.getvalue()


def _place(ws, chart, rng):
    """Tempatkan chart PAS mengisi rentang sel (mis. "B13:P33") -- lebar/tinggi chart ikut kolom & baris, jadi
    selalu sejajar dgn judul panel & tabel di sheet (tidak melenceng/menutupi judul)."""
    from openpyxl.drawing.spreadsheet_drawing import TwoCellAnchor, AnchorMarker
    from openpyxl.utils.cell import range_boundaries
    c1, r1, c2, r2 = range_boundaries(rng)
    chart.anchor = TwoCellAnchor(_from=AnchorMarker(col=c1 - 1, row=r1 - 1), to=AnchorMarker(col=c2, row=r2))
    ws.add_chart(chart)


def _color_series(ch, colors):
    for s_, c in zip(ch.series, colors):
        s_.graphicalProperties.solidFill = c
        s_.graphicalProperties.line.solidFill = c
        # Excel default: batang bernilai NEGATIF warnanya dibalik (jadi putih/kosong) -> matikan
        s_.invertIfNegative = False


def build_detail_ppt_excel(df_raw, sm_raw, maint_raw, mttr_raw, sites, months, kats, lookup_fn, lookup_base=None):
    """Bangun workbook Detail Perhitungan PPT (bytes). Input SAMA dgn build_pptx (data yg sudah difilter).
    lookup_fn = lookup_atribut_unit (pencocokan kode unit); lookup_base = data acuan pencocokan (default df_raw)."""
    lookup_base = df_raw if lookup_base is None else lookup_base
    months = [m for m in _DX_MONTHS if m in set(months)]
    last_month = months[-1] if months else "-"
    li = _DX_MONTHS.index(last_month) if last_month in _DX_MONTHS else 0
    rom = ["I", "II", "III"][li // 4]
    cawu = f"Cawu {rom}" if li % 4 == 3 else f"{last_month} (Cawu {rom})"
    cawu_inline = f"Cawu {rom}" if li % 4 == 3 else f"{last_month}, Cawu {rom}"
    period_txt = f"{months[0]} – {months[-1]}" if months else "-"

    # ---------------- data (filter sama dgn PPT)
    db = df_raw[df_raw["lokasi"].isin(sites) & df_raw["bulan"].isin(months) & df_raw["kategori"].isin(kats)].copy()
    db["id_unit"] = db["id_unit"].astype(str).str.replace(r"\.0$", "", regex=True)
    db["_blok"] = [_blok_py(l, k) for l, k in zip(db["lokasi"], db["kategori"])]
    db["_katp"] = ["AB" if l in _DX_MINING else k for l, k in zip(db["lokasi"], db["kategori"])]
    sm = sm_raw[sm_raw["lokasi"].isin(sites) & sm_raw["bulan"].isin(months)].copy() if sm_raw is not None else _pd_dx.DataFrame()
    if not sm.empty:
        sm.loc[sm["lokasi"].isin(_DX_MINING), "kategori"] = "AB"
        sm = sm[sm["kategori"].isin(set(db["_katp"]))]
        sm["id_unit"] = sm["id_unit"].astype(str).str.replace(r"\.0$", "", regex=True)
    mt = maint_raw[maint_raw["lokasi"].isin(sites) & maint_raw["bulan"].isin(months)].copy() if maint_raw is not None else _pd_dx.DataFrame()
    if not mt.empty:
        _lk = lookup_fn(mt, lookup_base[lookup_base["bulan"].isin(months)], ["kategori", "kelompok_unit"])
        mt["kategori"] = mt["kategori"].where(mt["kategori"].notna(), _lk["kategori"]) if "kategori" in mt.columns else _lk["kategori"]
        mt["kelompok_unit"] = _lk["kelompok_unit"]
        mt.loc[mt["lokasi"].isin(_DX_MINING), "kategori"] = "AB"
        mt = mt[[c for c in ["tanggal", "bulan", "lokasi", "kategori", "kelompok_unit", "nama_unit", "jenis_pemeliharaan",
                             "kategori_sparepart", "tipe_biaya", "biaya", "keterangan"] if c in mt.columns]]
    mr = mttr_raw[mttr_raw["lokasi"].isin(sites) & mttr_raw["bulan"].isin(months)].copy() if mttr_raw is not None else _pd_dx.DataFrame()
    if not mr.empty:
        mr.loc[mr["lokasi"].isin(_DX_MINING), "kategori"] = "AB"

    # Data kosong (mis. belum ada data Pemeliharaan utk bulan terpilih) tetap dibuatkan kolom lengkap,
    # spy rumus yg merujuk ke kolomnya tetap valid (hasilnya 0 / "-").
    def _ensure_cols(d_, cols_):
        d_ = d_.copy() if d_ is not None else _pd_dx.DataFrame()
        for c_ in cols_:
            if c_ not in d_.columns:
                d_[c_] = _pd_dx.Series(dtype="object")
        return d_
    sm = _ensure_cols(sm, ["id_unit", "lokasi", "bulan", "nama_unit", "kode_unit", "kelompok_unit", "kategori", "jenis_unit",
                           "unit_sewa", "availability_target", "utilisasi_target", "downtime_target", "efektif_hm_km_realisasi",
                           "breakdown_hm_km_realisasi", "tersedia_hm_km_realisasi", "hm_km_ideal_target"])
    mt = _ensure_cols(mt, ["tanggal", "bulan", "lokasi", "kategori", "kelompok_unit", "nama_unit", "jenis_pemeliharaan",
                           "kategori_sparepart", "tipe_biaya", "biaya", "keterangan"])
    mr = _ensure_cols(mr, ["lokasi", "bulan", "tanggal", "nama_unit", "kategori", "jumlah_jam"])

    wb = _WB_dx()
    wb.remove(wb.active)
    blocks = [b for b in (_DX_BLOK_TR, _DX_BLOK_AB, _DX_BLOK_MN) if b in set(db["_blok"])]
    PREFIX = {_DX_BLOK_TR: "TR", _DX_BLOK_AB: "AB", _DX_BLOK_MN: "MN"}
    SUBLBL = {_DX_BLOK_TR: "PLANTATION · TRANSPORTASI", _DX_BLOK_AB: "PLANTATION · ALAT BERAT", _DX_BLOK_MN: "MINING"}
    # placeholder urutan sheet: tampilan & perhitungan dibuat per blok di bawah, data di akhir
    D = {}

    def _mk_data():
        D["db"] = _DataSheet(wb, "Data BKMS", db.drop(columns=["_blok", "_katp"]), [
            ("Blok", lambda C, r: _blok_formula(f"{C['lokasi']}{r}", f"{C['kategori']}{r}")),
            ("Kategori PPT", lambda C, r: f'=IF(A{r}="{_DX_BLOK_MN}","AB",{C["kategori"]}{r})'),
            ("Kunci Unit", lambda C, r: f'={C["lokasi"]}{r}&"|"&{C["id_unit"]}{r}'),
            ("Unit Aktif Floating", lambda C, r: (f'=IF(AND({C["kriteria_unit"]}{r}="Floating Tarif",{C["nama_unit"]}{r}<>"",'
                                                  f'OR(N({C["prestasi_realisasi"]}{r})>0,N({C["pendapatan_realisasi"]}{r})>0,N({C["total_biaya_realisasi"]}{r})>0)),1,0)')),
            ("Hitung Unit", lambda C, r: (f'=IF(AND(D{r}=1,COUNTIFS(${C["lokasi"]}$2:{C["lokasi"]}{r},{C["lokasi"]}{r},'
                                          f'${C["nama_unit"]}$2:{C["nama_unit"]}{r},{C["nama_unit"]}{r},${C["bulan"]}$2:{C["bulan"]}{r},{C["bulan"]}{r},'
                                          f'$D$2:D{r},1)=1),1,0)')),
            # --- BBM (sama dgn PPT): baris "tdk valid" (qty>0 tapi biaya=0) dikecualikan dari total BBM
            ("BBM Valid", lambda C, r: (f'=IF(OR(AND(N({C["qty_bbm_realisasi"]}{r})>0,N({C["biaya_bbm_realisasi"]}{r})=0),'
                                        f'AND(N({C["qty_bbm_budget"]}{r})>0,N({C["biaya_bbm_budget"]}{r})=0)),0,1)')),
            # --- konsumsi BBM per kelompok: realisasi/budget yg datanya tdk lengkap (qty, biaya, prestasi) dinolkan
            ("Qty BBM R (konsumsi)", lambda C, r: (f'=IF(AND(N({C["qty_bbm_realisasi"]}{r})>0,N({C["biaya_bbm_realisasi"]}{r})>0,'
                                                   f'N({C["prestasi_realisasi"]}{r})>0),N({C["qty_bbm_realisasi"]}{r}),0)')),
            ("Prestasi R (konsumsi)", lambda C, r: (f'=IF(AND(N({C["qty_bbm_realisasi"]}{r})>0,N({C["biaya_bbm_realisasi"]}{r})>0,'
                                                    f'N({C["prestasi_realisasi"]}{r})>0),N({C["prestasi_realisasi"]}{r}),0)')),
            ("Qty BBM B (konsumsi)", lambda C, r: (f'=IF(AND(N({C["qty_bbm_budget"]}{r})>0,N({C["biaya_bbm_budget"]}{r})>0,'
                                                   f'N({C["prestasi_budget"]}{r})>0),N({C["qty_bbm_budget"]}{r}),0)')),
            ("Prestasi B (konsumsi)", lambda C, r: (f'=IF(AND(N({C["qty_bbm_budget"]}{r})>0,N({C["biaya_bbm_budget"]}{r})>0,'
                                                    f'N({C["prestasi_budget"]}{r})>0),N({C["prestasi_budget"]}{r}),0)')),
        ])
        dbs = D["db"]
        D["sm"] = _DataSheet(wb, "Data Sasaran Mutu", sm, [
            ("Blok", lambda C, r: _blok_formula(f"{C['lokasi']}{r}", f"{C['kategori']}{r}")),
            ("Kriteria Unit", lambda C, r: (f"=IFERROR(INDEX({dbs.R('kriteria_unit')},MATCH({C['lokasi']}{r}&\"|\"&{C['id_unit']}{r},"
                                            f"{dbs.R('Kunci Unit')},0)),\"\")")),
            # target downtime UNIK per blok+site (kartu per-site di slide Downtime memakai rata2 target unik)
            ("Target DT Unik", lambda C, r: (f'=IF({C["downtime_target"]}{r}="",0,IF(COUNTIFS($A$2:A{r},A{r},${C["lokasi"]}$2:{C["lokasi"]}{r},'
                                             f'{C["lokasi"]}{r},${C["downtime_target"]}$2:{C["downtime_target"]}{r},{C["downtime_target"]}{r})=1,1,0))')),
        ])
        D["mt"] = _DataSheet(wb, "Data Pemeliharaan", mt, [
            ("Blok", lambda C, r: _blok_formula(f"{C['lokasi']}{r}", f"{C['kategori']}{r}")),
        ])
        D["mr"] = _DataSheet(wb, "Data MTTR", mr, [
            ("Blok", lambda C, r: _blok_formula(f"{C['lokasi']}{r}", f"{C['kategori']}{r}")),
        ])

    # sheet data dibuat dulu (butuh nama range), lalu dipindah ke paling belakang
    _mk_data()
    DB, SM, MT, MR = D["db"], D["sm"], D["mt"], D["mr"]
    note_all = "Semua angka = rumus. Rincian: sheet '… Perhitungan'; data mentah: sheet 'Data …' (kolom emas = kolom bantu/rumus)."

    for blok in blocks:
        px = PREFIX[blok]
        bd = db[db["_blok"] == blok]
        BL = None  # sel Blok (di sheet slide 01)

        # =========================== SLIDE 01 — INFORMASI KINERJA ===========================
        v1 = _Sheet(wb, f"{px}-01 Informasi Kinerja"); c1 = _Sheet(wb, f"{px}-01 Perhitungan")
        v1.title(f"KPI DASHBOARD — Informasi Kinerja s/d {cawu}", f"Informasi Kinerja · 01 · {SUBLBL[blok]}", blok, last_month, period_txt, note_all)
        v1.widths({"A": 2, "B": 17, "C": 13, "D": 13, "E": 3, "F": 17, "G": 13, "H": 13, "I": 3, "J": 17, "K": 13, "L": 13,
                   "M": 3, "N": 17, "O": 13, "P": 13, "Q": 3, "R": 27, "S": 8, "T": 8})
        c1.widths({"A": 2, "B": 30, "C": 16, "D": 22, **{k: 14 for k in "EFGHIJKLMNOP"}})
        BL = f"'{v1.name}'!$C$3"; LM = f"'{v1.name}'!$G$3"
        P1 = c1.P
        c1.section(2, f"{px}-01 PERHITUNGAN — sumber semua angka di sheet '{v1.name}'", "B", "P")
        # (A) total
        r = 4
        c1.put(f"B{r}", "A. Total blok (Prestasi khusus Floating Tarif)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c1.header(r + 1, 2, ["Komponen", "Realisasi", "Budget"])
        fl = f'{DB.R("kriteria_unit")},"Floating Tarif"'
        rowsA = [
            ("Prestasi (Floating Tarif)", f"=SUMIFS({DB.R('prestasi_realisasi')},{DB.R('Blok')},{BL},{fl})", f"=SUMIFS({DB.R('prestasi_budget')},{DB.R('Blok')},{BL},{fl})", "#,##0"),
            ("Biaya Langsung (semua unit)", f"=SUMIFS({DB.R('biaya_langsung_realisasi')},{DB.R('Blok')},{BL})", f"=SUMIFS({DB.R('biaya_langsung_budget')},{DB.R('Blok')},{BL})", "#,##0"),
            ("Biaya Tdk Langsung (semua unit)", f"=SUMIFS({DB.R('biaya_tidak_langsung_realisasi')},{DB.R('Blok')},{BL})", f"=SUMIFS({DB.R('biaya_tidak_langsung_budget')},{DB.R('Blok')},{BL})", "#,##0"),
            ("Biaya Langsung / Prestasi", f'=IFERROR(C{r+3}/C{r+2},"")', f'=IFERROR(D{r+3}/D{r+2},"")', "#,##0.0"),
            ("Biaya Tdk Langsung / Prestasi", f'=IFERROR(C{r+4}/C{r+2},"")', f'=IFERROR(D{r+4}/D{r+2},"")', "#,##0.0"),
        ]
        for i, (nm, fr, fb, fm) in enumerate(rowsA):
            c1.put(f"B{r+2+i}", nm, bold=True, align=_LEFT); c1.put(f"C{r+2+i}", fr, fm); c1.put(f"D{r+2+i}", fb, fm)
        PR, PB = f"{P1}$C${r+2}", f"{P1}$D${r+2}"
        BLR, BLB = f"{P1}$C${r+5}", f"{P1}$D${r+5}"
        BTR, BTB = f"{P1}$C${r+6}", f"{P1}$D${r+6}"
        # (B) per kelompok (Floating)
        k_map = bd.dropna(subset=["kriteria_unit"]).drop_duplicates(["lokasi", "id_unit"]).set_index(["lokasi", "id_unit"])["kriteria_unit"].to_dict()
        smb = sm[[_blok_py(l, k) == blok for l, k in zip(sm["lokasi"], sm["kategori"])]].copy() if not sm.empty else sm
        if not smb.empty:
            smb["_krit"] = [k_map.get((l, i)) for l, i in zip(smb["lokasi"], smb["id_unit"])]
            smk = smb[(smb["_krit"] == "Floating Tarif") & (smb["jenis_unit"] != "Tarif Tetap") & (smb["unit_sewa"] != True)].dropna(subset=["kelompok_unit"])
            au_keys = smk[["lokasi", "kelompok_unit"]].drop_duplicates().sort_values(["kelompok_unit", "lokasi"]).values.tolist()
        else:
            au_keys = []
        rB = r + 9
        c1.put(f"B{rB}", "B. Capaian per Site & Kelompok Unit (khusus Floating Tarif, exclude unit sewa)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c1.header(rB + 1, 2, ["Label (chart)", "Site", "Kelompok Unit", "Prestasi Realisasi", "Prestasi Budget", "% Capaian Prestasi",
                              "Efektif (HM/KM)", "Tersedia (HM/KM)", "Ideal (HM/KM)", "Utilisasi Realisasi", "Utilisasi Target",
                              "% Capaian Utilisasi", "Availability Realisasi", "Availability Target", "% Capaian Availability"])
        bf = rB + 2
        for i, (lok, kel) in enumerate(au_keys):
            rr = bf + i
            c1.put(f"B{rr}", f"{_site(lok)} — {kel}", bold=True, align=_LEFT); c1.put(f"C{rr}", lok, align=_LEFT); c1.put(f"D{rr}", kel, align=_LEFT)
            cd_ = f'{DB.R("Blok")},{BL},{DB.R("lokasi")},$C{rr},{DB.R("kelompok_unit")},$D{rr},{DB.R("kriteria_unit")},"<>Tarif Tetap"'
            c1.put(f"E{rr}", f"=SUMIFS({DB.R('prestasi_realisasi')},{cd_})", "#,##0")
            c1.put(f"F{rr}", f"=SUMIFS({DB.R('prestasi_budget')},{cd_})", "#,##0")
            c1.put(f"G{rr}", f'=IF(F{rr}=0,"",E{rr}/F{rr})', "0%", bold=True)  # 0 desimal: sama dgn label chart PPT
            cs = (f'{SM.R("Blok")},{BL},{SM.R("lokasi")},$C{rr},{SM.R("kelompok_unit")},$D{rr},'
                  f'{SM.R("Kriteria Unit")},"Floating Tarif",{SM.R("jenis_unit")},"<>Tarif Tetap",{SM.R("unit_sewa")},"<>TRUE"')
            c1.put(f"H{rr}", f"=SUMIFS({SM.R('efektif_hm_km_realisasi')},{cs})", "#,##0")
            c1.put(f"I{rr}", f"=SUMIFS({SM.R('tersedia_hm_km_realisasi')},{cs})", "#,##0")
            c1.put(f"J{rr}", f"=SUMIFS({SM.R('hm_km_ideal_target')},{cs})", "#,##0")
            c1.put(f"K{rr}", f'=IF(J{rr}=0,"",H{rr}/J{rr})', "0.0%")
            c1.put(f"L{rr}", f'=IF(K{rr}="","",IFERROR(AVERAGEIFS({SM.R("utilisasi_target")},{cs})/100,""))', "0.0%")
            c1.put(f"M{rr}", f'=IF(OR(K{rr}="",L{rr}="",L{rr}=0),"",K{rr}/L{rr})', "0%", bold=True)
            c1.put(f"N{rr}", f'=IF(J{rr}=0,"",I{rr}/J{rr})', "0.0%")
            c1.put(f"O{rr}", f'=IF(N{rr}="","",IFERROR(AVERAGEIFS({SM.R("availability_target")},{cs})/100,""))', "0.0%")
            c1.put(f"P{rr}", f'=IF(OR(N{rr}="",O{rr}="",O{rr}=0),"",N{rr}/O{rr})', "0%", bold=True)
        bl_ = bf + max(len(au_keys), 1) - 1
        ravg = bl_ + 1
        c1.put(f"B{ravg}", "RATA-RATA (= kartu KPI)", bold=True, align=_LEFT, fillc="EEF2FF")
        for col in "KLMNOP":
            c1.put(f"{col}{ravg}", f'=IFERROR(AVERAGE({col}{bf}:{col}{bl_}),"")', "0.0%", bold=True, color=_NAVY, fillc="EEF2FF")
        # (C) populasi
        pop = bd[(bd["bulan"] == last_month) & (bd["kriteria_unit"] == "Floating Tarif")]
        pop = pop[(pop["prestasi_realisasi"].fillna(0) > 0) | (pop["pendapatan_realisasi"].fillna(0) > 0) | (pop["total_biaya_realisasi"].fillna(0) > 0)]
        pop_n = pop.dropna(subset=["kelompok_unit"]).groupby(["lokasi", "kelompok_unit"])["nama_unit"].nunique()
        pop_keys = [k for k in au_keys if pop_n.get(tuple(k), 0) > 0]
        rC = ravg + 3
        c1.put(f"B{rC}", "C. Populasi Unit (Floating Tarif, bulan terakhir, unit yg ada realisasinya)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c1.header(rC + 1, 2, ["Label (chart)", "Site", "Kelompok Unit", "Jumlah Unit", "Porsi"])
        cf = rC + 2
        cl_ = cf + max(len(pop_keys), 1) - 1
        for i, (lok, kel) in enumerate(pop_keys):
            rr = cf + i
            c1.put(f"B{rr}", f"{_site(lok)} — {kel}", bold=True, align=_LEFT); c1.put(f"C{rr}", lok, align=_LEFT); c1.put(f"D{rr}", kel, align=_LEFT)
            c1.put(f"E{rr}", f"=COUNTIFS({DB.R('Blok')},{BL},{DB.R('lokasi')},$C{rr},{DB.R('kelompok_unit')},$D{rr},{DB.R('bulan')},{LM},{DB.R('Hitung Unit')},1)", "0", bold=True)
            c1.put(f"F{rr}", f"=IFERROR(E{rr}/SUM($E${cf}:$E${cl_}),0)", "0%")
        rpt = cl_ + 1
        c1.put(f"B{rpt}", "TOTAL", bold=True, align=_LEFT)
        c1.put(f"E{rpt}", f"=SUM(E{cf}:E{cl_})", "0", bold=True, color=_NAVY)
        # (D) gap pendapatan
        g_ = bd.groupby(["lokasi", "kelompok_unit"])[["pendapatan_realisasi", "pendapatan_budget"]].sum()
        gap_keys = [list(k) for k, v in g_.iterrows() if v["pendapatan_realisasi"] > 0 or v["pendapatan_budget"] > 0]
        rD = rpt + 3
        c1.put(f"B{rD}", "D. Gap Pendapatan per Site & Kelompok Unit (semua kriteria) — dasar kotak analisa", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c1.header(rD + 1, 2, ["Label", "Site", "Kelompok Unit", "Pendapatan Realisasi", "Pendapatan Budget", "Gap (R - B)",
                              "Prestasi Realisasi", "Prestasi Budget", "% Capaian Prestasi"])
        df_ = rD + 2
        for i, (lok, kel) in enumerate(gap_keys):
            rr = df_ + i
            c1.put(f"B{rr}", f"{_site(lok)} — {kel}", bold=True, align=_LEFT); c1.put(f"C{rr}", lok, align=_LEFT); c1.put(f"D{rr}", kel, align=_LEFT)
            cr_ = f'{DB.R("Blok")},{BL},{DB.R("lokasi")},$C{rr},{DB.R("kelompok_unit")},$D{rr}'
            c1.put(f"E{rr}", f"=SUMIFS({DB.R('pendapatan_realisasi')},{cr_})", "#,##0")
            c1.put(f"F{rr}", f"=SUMIFS({DB.R('pendapatan_budget')},{cr_})", "#,##0")
            c1.put(f"G{rr}", f"=E{rr}-F{rr}", "#,##0;[Red]-#,##0", bold=True)
            c1.put(f"H{rr}", f"=SUMIFS({DB.R('prestasi_realisasi')},{cr_})", "#,##0")
            c1.put(f"I{rr}", f"=SUMIFS({DB.R('prestasi_budget')},{cr_})", "#,##0")
            c1.put(f"J{rr}", f'=IF(I{rr}=0,"",H{rr}/I{rr})', "0.0%")
        dl_ = df_ + max(len(gap_keys), 1) - 1
        rmin = dl_ + 1
        c1.put(f"B{rmin}", "Gap paling minus", bold=True, align=_LEFT)
        c1.put(f"G{rmin}", f"=MIN(G{df_}:G{dl_})", "#,##0;[Red]-#,##0", bold=True, color=_RED)
        c1.put(f"H{rmin}", f"=MATCH(G{rmin},G{df_}:G{dl_},0)", "0")
        c1.put(f"I{rmin}", "← posisi baris", border=False, size=8, color=_MUTED, italic=True, align=_LEFT)
        pick = lambda col: f"INDEX({P1}${col}${df_}:${col}${dl_},{P1}$H${rmin})"
        # kartu
        rp_fmt = '[>=1000000]"Rp "#,##0.0,," Jt";[>=1000]"Rp "#,##0.0," Rb";"Rp "#,##0'
        v1.card("B", 5, "Capaian Prestasi", f'=IFERROR({PR}/{PB},"")', "0.0%", '="Target: 100.0%"',
                f'=IF(B7="","Data tidak tersedia",IF(B7>=1,"✓ "&{_pct("B7")}&" — Tercapai","✗ "&{_pct("B7")}&" — Belum Tercapai"))', "$B$7>=1", _GREEN)
        v1.card("F", 5, "Capaian Utilisasi", f"={P1}K{ravg}", "0.0%", f'=IF({P1}L{ravg}="","Target: -","Target: "&{_pct(f"{P1}L{ravg}")})',
                f'=IF({P1}M{ravg}="","Data tidak tersedia",IF({P1}M{ravg}>=1,"✓ ","✗ ")&{_pct(f"{P1}M{ravg}")}&" dari Target")', f"{P1}$M${ravg}>=1", _GOLD)
        v1.card("J", 5, "Capaian Availability", f"={P1}N{ravg}", "0.0%", f'=IF({P1}O{ravg}="","Target: -","Target: "&{_pct(f"{P1}O{ravg}")})',
                f'=IF({P1}P{ravg}="","Data tidak tersedia",IF({P1}P{ravg}>=1,"✓ ","✗ ")&{_pct(f"{P1}P{ravg}")}&" dari Target")', f"{P1}$P${ravg}>=1", _TEAL)
        v1.card("N", 5, "Biaya Langsung / Prestasi", f"={BLR}", rp_fmt, f'=IF({BLB}="","Budget: -","Budget: "&{_rp(BLB)})',
                f'=IF(OR({BLB}="",{BLR}=""),"Target = 0",IF({BLR}/{BLB}<=1,"✓ "&{_pct(f"{BLR}/{BLB}")}&" — Under Budget","✗ "&{_pct(f"{BLR}/{BLB}")}&" — Over Budget"))', f"{BLR}/{BLB}<=1", _GREEN)
        v1.card("R", 5, "Biaya T.Langsung / Prestasi", f"={BTR}", rp_fmt, f'=IF({BTB}="","Budget: -","Budget: "&{_rp(BTB)})',
                f'=IF(OR({BTB}="",{BTR}=""),"Target = 0",IF({BTR}/{BTB}<=1,"✓ "&{_pct(f"{BTR}/{BTB}")}&" — Under Budget","✗ "&{_pct(f"{BTR}/{BTB}")}&" — Over Budget"))', f"{BTR}/{BTB}<=1", _PURPLE)
        v1.section(12, "Capaian Prestasi, Utilisasi & Availability — per Site & Kelompok Unit", "B", "P")
        v1.section(12, "Populasi Unit", "R", "T")
        if au_keys:
            ch = _bar_chart(overlap=-10, height=10.8, width=34.5)
            for col_idx in (7, 13, 16):
                ch.add_data(_Ref(c1.ws, min_col=col_idx, min_row=rB + 1, max_row=bl_), titles_from_data=True)
            ch.set_categories(_Ref(c1.ws, min_col=2, min_row=bf, max_row=bl_))
            _color_series(ch, (_BLUE, _GOLD, _TEAL)); _labels(ch, "0%", size=(9 if len(au_keys) <= 9 else 7)); ch.y_axis.numFmt = "0%"
            _place(v1.ws, ch, f"B13:P{max(33, 26 + len(pop_keys) - 1)}")  # tinggi chart ikut turun sampai tepat di atas kotak analisa (tdk ada ruang kosong)
        if pop_keys:
            dn = _Dn(); dn.holeSize = 58; dn.firstSliceAng = 0
            dn.add_data(_Ref(c1.ws, min_col=5, min_row=cf - 1, max_row=cl_), titles_from_data=True)
            dn.set_categories(_Ref(c1.ws, min_col=2, min_row=cf, max_row=cl_))
            for i in range(len(pop_keys)):
                pt = _DP(idx=i); pt.graphicalProperties.solidFill = _PALETTE[i % len(_PALETTE)]
                pt.graphicalProperties.line.solidFill = "FFFFFF"
                dn.series[0].dPt.append(pt)
            dn.legend = None
            _place(v1.ws, dn, "R13:T24")
            v1.ws.merge_cells("R25:T25")
            v1.put("R25", f"={P1}E{rpt}", '0" unit"', bold=True, size=16, border=False, align=_CENTER)
            for i in range(len(pop_keys)):
                rr = 26 + i
                v1.put(f"Q{rr}", "●", border=False, align=_CENTER, size=11, color=_PALETTE[i % len(_PALETTE)])
                v1.put(f"R{rr}", f"={P1}B{cf+i}", border=False, align=_LEFT, size=8.5)
                v1.put(f"S{rr}", f"={P1}E{cf+i}", border=False, bold=True, size=8.5)
                v1.put(f"T{rr}", f"={P1}F{cf+i}", "0%", border=False, size=8.5, color=_MUTED)
        an_row = max(35, 26 + len(pop_keys) + 1)
        if gap_keys:
            lab_w, gap_w, pr_w, pb_w, cap_w = pick("B"), pick("G"), pick("E"), pick("F"), pick("J")
            v1.note_box(f"B{an_row}:P{an_row+2}", (
                f'=IF({P1}$G${rmin}>=0,"Tidak ada unit dengan gap pendapatan minus — seluruh unit mencapai/melebihi target pendapatan.",'
                f'{lab_w}&" adalah unit dengan GAP PENDAPATAN MINUS PALING TINGGI ("&{_rp(gap_w)}&") — Realisasi "&{_rp(pr_w)}'
                f'&" vs Budget "&{_rp(pb_w)}&", dengan Capaian Prestasi "&IF({cap_w}="","tidak tersedia",{_pct(cap_w)})&". "'
                f'&IF({cap_w}="","Data capaian prestasi unit ini belum tersedia untuk analisis lebih lanjut.",'
                f'IF({cap_w}<1,"Rendahnya capaian prestasi unit ini menjadi salah satu penyebab utama kekurangan pendapatan.",'
                f'"Meski capaian prestasi sudah tercapai, gap pendapatan tetap terjadi — kemungkinan disebabkan faktor lain (tarif/rate, harga jual, atau komposisi pekerjaan).")))'))

        # =========================== SLIDE 04 (dihitung dulu: tabel downtime dipakai slide 02) ===========================
        v4 = _Sheet(wb, f"{px}-04 Analisis Downtime"); c4 = _Sheet(wb, f"{px}-04 Perhitungan")
        P4 = c4.P
        c4.widths({"A": 2, "B": 30, "C": 16, "D": 22, **{k: 14 for k in "EFGHIJKLMNOP"}})
        c4.section(2, f"{px}-04 PERHITUNGAN — sumber semua angka di sheet '{v4.name}'", "B", "P")
        # (A) downtime per kelompok utk KARTU (exclude jenis_unit Tarif Tetap & unit sewa; semua kriteria)
        if not smb.empty:
            smd = smb[(smb["jenis_unit"] != "Tarif Tetap") & (smb["unit_sewa"] != True)].dropna(subset=["kelompok_unit"])
            dtk_keys = smd[["lokasi", "kelompok_unit"]].drop_duplicates().sort_values(["kelompok_unit", "lokasi"]).values.tolist()
            sma = smb.dropna(subset=["kelompok_unit"])
        else:
            dtk_keys = []; sma = smb
        rA4 = 4
        c4.put(f"B{rA4}", "A. Downtime per Site & Kelompok (dasar kartu Capaian Downtime; exclude jenis unit Tarif Tetap & unit sewa)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c4.header(rA4 + 1, 2, ["Label", "Site", "Kelompok Unit", "Breakdown (HM/KM)", "Ideal (HM/KM)", "Downtime Realisasi", "Downtime Target", "% Capaian Downtime"])
        af = rA4 + 2
        for i, (lok, kel) in enumerate(dtk_keys):
            rr = af + i
            c4.put(f"B{rr}", f"{_site(lok)} — {_kel(kel)}", bold=True, align=_LEFT); c4.put(f"C{rr}", lok, align=_LEFT); c4.put(f"D{rr}", kel, align=_LEFT)
            cs = f'{SM.R("Blok")},{BL},{SM.R("lokasi")},$C{rr},{SM.R("kelompok_unit")},$D{rr},{SM.R("jenis_unit")},"<>Tarif Tetap",{SM.R("unit_sewa")},"<>TRUE"'
            c4.put(f"E{rr}", f"=SUMIFS({SM.R('breakdown_hm_km_realisasi')},{cs})", "#,##0")
            c4.put(f"F{rr}", f"=SUMIFS({SM.R('hm_km_ideal_target')},{cs})", "#,##0")
            c4.put(f"G{rr}", f'=IF(F{rr}=0,"",E{rr}/F{rr})', "0.0%")
            c4.put(f"H{rr}", f'=IF(G{rr}="","",IFERROR(AVERAGEIFS({SM.R("downtime_target")},{cs})/100,""))', "0.0%")
            c4.put(f"I{rr}", f'=IF(OR(G{rr}="",H{rr}="",H{rr}=0),"",G{rr}/H{rr})', "0.0%", bold=True)
        al_ = af + max(len(dtk_keys), 1) - 1
        ra4 = al_ + 1
        c4.put(f"B{ra4}", "RATA-RATA (= kartu Capaian Downtime)", bold=True, align=_LEFT, fillc="EEF2FF")
        for col in "GHI":
            c4.put(f"{col}{ra4}", f'=IFERROR(AVERAGE({col}{af}:{col}{al_}),"")', "0.0%", bold=True, color=_NAVY, fillc="EEF2FF")
        CAPDT = f"{P4}$I${ra4}"
        # (B) downtime per site (rincian kartu): realisasi = rata2 per kelompok (semua unit), target = rata2 target UNIK
        site_keys = []
        if not sma.empty and sma["lokasi"].nunique() > 1:
            res = []
            for lok, g in sma.groupby("lokasi"):
                tu = g["downtime_target"].dropna().unique()
                if len(tu) == 0:
                    continue
                reals = [gk["breakdown_hm_km_realisasi"].fillna(0).sum() / gk["hm_km_ideal_target"].sum() * 100
                         for _, gk in g.groupby("kelompok_unit") if gk["hm_km_ideal_target"].sum()]
                if reals:
                    res.append((lok, sum(reals) / len(reals)))
            site_keys = [l for l, _ in sorted(res, key=lambda x: x[1], reverse=True)]
        rB4 = ra4 + 3
        c4.put(f"B{rB4}", "B. Downtime per Site (rincian di kartu; semua unit)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        dts_keys = sma[["lokasi", "kelompok_unit"]].drop_duplicates().sort_values(["lokasi", "kelompok_unit"]).values.tolist() if not sma.empty else []
        # B1: per site+kelompok (semua unit)
        c4.header(rB4 + 1, 2, ["Site", "Kelompok Unit", "Breakdown (HM/KM)", "Ideal (HM/KM)", "Downtime Realisasi"])
        b4f = rB4 + 2
        for i, (lok, kel) in enumerate(dts_keys):
            rr = b4f + i
            c4.put(f"B{rr}", lok, align=_LEFT); c4.put(f"C{rr}", kel, align=_LEFT)
            cs = f'{SM.R("Blok")},{BL},{SM.R("lokasi")},$B{rr},{SM.R("kelompok_unit")},$C{rr}'
            c4.put(f"D{rr}", f"=SUMIFS({SM.R('breakdown_hm_km_realisasi')},{cs})", "#,##0")
            c4.put(f"E{rr}", f"=SUMIFS({SM.R('hm_km_ideal_target')},{cs})", "#,##0")
            c4.put(f"F{rr}", f'=IF(E{rr}=0,"",D{rr}/E{rr})', "0.0%")
        b4l = b4f + max(len(dts_keys), 1) - 1
        # B2: ringkasan per site
        rB4s = b4l + 2
        c4.header(rB4s, 2, ["Site", "Realisasi (rata2 kelompok)", "Target (rata2 target unik)", "% Capaian Downtime", "Teks kartu"])
        s4f = rB4s + 1
        for i, lok in enumerate(site_keys):
            rr = s4f + i
            c4.put(f"B{rr}", lok, align=_LEFT)
            c4.put(f"C{rr}", f'=IFERROR(AVERAGEIFS($F${b4f}:$F${b4l},$B${b4f}:$B${b4l},B{rr}),"")', "0.0%")
            c4.put(f"D{rr}", (f'=IFERROR(SUMIFS({SM.R("downtime_target")},{SM.R("Blok")},{BL},{SM.R("lokasi")},B{rr},{SM.R("Target DT Unik")},1)/'
                              f'COUNTIFS({SM.R("Blok")},{BL},{SM.R("lokasi")},B{rr},{SM.R("Target DT Unik")},1)/100,"")'), "0.0%")
            c4.put(f"E{rr}", f'=IF(OR(C{rr}="",D{rr}="",D{rr}=0),"",C{rr}/D{rr})', "0.0%", bold=True)
            c4.put(f"F{rr}", f'=IF(E{rr}="","","{_site(lok)} "&FIXED(E{rr}*100,0,TRUE)&"%")', align=_LEFT)
        s4l = s4f + len(site_keys) - 1
        dt_site_txt = (f'=_xlfn.TEXTJOIN("  ·  ",TRUE,{P4}F{s4f}:F{s4l})' if site_keys else '=""')
        # (C) chart downtime per kelompok (SEMUA unit), urutan capaian tertinggi (sama dgn PPT)
        dtc = []
        if not sma.empty:
            for (lok, kel), g in sma.groupby(["lokasi", "kelompok_unit"]):
                si = g["hm_km_ideal_target"].sum()
                t = g["downtime_target"].mean()
                if si and t and not _pd_dx.isna(t):
                    dtc.append((lok, kel, g["breakdown_hm_km_realisasi"].fillna(0).sum() / si * 100 / t * 100))
        dtc.sort(key=lambda x: x[2], reverse=True)
        rC4 = (s4l if site_keys else rB4s) + 3
        c4.put(f"B{rC4}", "C. % Capaian Downtime per Site & Kelompok Unit (chart; semua unit)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c4.header(rC4 + 1, 2, ["Label (chart)", "Site", "Kelompok Unit", "Breakdown (HM/KM)", "Ideal (HM/KM)", "Downtime Realisasi",
                               "Downtime Target", "% Capaian Downtime", "Melebihi target", "Dalam target"])
        c4f = rC4 + 2
        for i, (lok, kel, _) in enumerate(dtc):
            rr = c4f + i
            c4.put(f"B{rr}", f"{_site(lok)} — {_kel(kel)}", bold=True, align=_LEFT); c4.put(f"C{rr}", lok, align=_LEFT); c4.put(f"D{rr}", kel, align=_LEFT)
            cs = f'{SM.R("Blok")},{BL},{SM.R("lokasi")},$C{rr},{SM.R("kelompok_unit")},$D{rr}'
            c4.put(f"E{rr}", f"=SUMIFS({SM.R('breakdown_hm_km_realisasi')},{cs})", "#,##0")
            c4.put(f"F{rr}", f"=SUMIFS({SM.R('hm_km_ideal_target')},{cs})", "#,##0")
            c4.put(f"G{rr}", f'=IF(F{rr}=0,"",E{rr}/F{rr})', "0.0%")
            c4.put(f"H{rr}", f'=IFERROR(AVERAGEIFS({SM.R("downtime_target")},{cs})/100,"")', "0.0%")
            c4.put(f"I{rr}", f'=IF(OR(G{rr}="",H{rr}="",H{rr}=0),"",G{rr}/H{rr})', "0.0%", bold=True)
            c4.put(f"J{rr}", f'=IF(N(I{rr})>1,I{rr},0)', "0%;;;")
            c4.put(f"K{rr}", f'=IF(N(I{rr})>1,0,N(I{rr}))', "0%;;;")
        c4l = c4f + max(len(dtc), 1) - 1
        rs4 = c4l + 1
        c4.put(f"B{rs4}", "Jumlah unit / melebihi target / posisi terburuk", bold=True, align=_LEFT)
        c4.put(f"C{rs4}", f"=COUNT(I{c4f}:I{c4l})", "0", bold=True)
        c4.put(f"D{rs4}", f'=COUNTIF(I{c4f}:I{c4l},">1")', "0", bold=True, color=_RED)
        c4.put(f"E{rs4}", f"=IFERROR(MATCH(MAX(I{c4f}:I{c4l}),I{c4f}:I{c4l},0),0)", "0")
        # (D) MTTR
        rD4 = rs4 + 3
        c4.put(f"B{rD4}", "D. MTTR (Mean Time To Repair) — dari Data MTTR", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c4.header(rD4 + 1, 2, ["Site", "Total Jam Perbaikan", "Jumlah Kejadian", "MTTR (jam)", "Teks kartu"])
        mrb = mr[[_blok_py(l, k) == blok for l, k in zip(mr["lokasi"], mr["kategori"])]] if not mr.empty else mr
        mttr_sites = []
        if not mrb.empty and mrb["lokasi"].nunique() > 1:
            mttr_sites = mrb.groupby("lokasi")["jumlah_jam"].sum().sort_values(ascending=False).index.tolist()
        d4f = rD4 + 2
        rr = d4f
        c4.put(f"B{rr}", "TOTAL BLOK", bold=True, align=_LEFT)
        c4.put(f"C{rr}", f"=SUMIFS({MR.R('jumlah_jam')},{MR.R('Blok')},{BL})", "#,##0.0")
        c4.put(f"D{rr}", f"=COUNTIFS({MR.R('Blok')},{BL})", "#,##0")
        c4.put(f"E{rr}", f'=IF(D{rr}=0,"",C{rr}/D{rr})', "0.0", bold=True)
        MTTR_T, MTTR_N = f"{P4}$E${d4f}", f"{P4}$D${d4f}"
        for i, lok in enumerate(mttr_sites):
            rr = d4f + 1 + i
            c4.put(f"B{rr}", lok, align=_LEFT)
            c4.put(f"C{rr}", f"=SUMIFS({MR.R('jumlah_jam')},{MR.R('Blok')},{BL},{MR.R('lokasi')},B{rr})", "#,##0.0")
            c4.put(f"D{rr}", f"=COUNTIFS({MR.R('Blok')},{BL},{MR.R('lokasi')},B{rr})", "#,##0")
            c4.put(f"E{rr}", f'=IF(D{rr}=0,"",C{rr}/D{rr})', "0.0")
            c4.put(f"F{rr}", f'=IF(E{rr}="","","{_site(lok)} "&FIXED(E{rr},1)&"j")', align=_LEFT)
        mttr_site_txt = (f'=_xlfn.TEXTJOIN("  ·  ",TRUE,{P4}F{d4f+1}:F{d4f+len(mttr_sites)})' if mttr_sites else '=""')
        # (E) Rutin vs Non-Rutin (kartu) & (F) kategori sparepart
        mtb = mt[[_blok_py(l, k) == blok for l, k in zip(mt["lokasi"], mt["kategori"])]] if not mt.empty else mt
        rE4 = d4f + len(mttr_sites) + 3
        c4.put(f"B{rE4}", "E. Maintenance Rutin vs Non-Rutin (porsi biaya, dari Data Pemeliharaan)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c4.header(rE4 + 1, 2, ["Site", "Biaya Rutin", "Biaya Non-Rutin", "Total Biaya", "% Rutin", "% Non-Rutin", "Teks Rutin", "Teks Non-Rutin"])
        rut_sites = []
        if not mtb.empty and mtb["lokasi"].nunique() > 1:
            st_ = mtb.groupby("lokasi")["biaya"].sum().sort_values(ascending=False)
            rut_sites = [l for l, v in st_.items() if v > 0]
        e4f = rE4 + 2
        c4.put(f"B{e4f}", "TOTAL BLOK", bold=True, align=_LEFT)
        for i, lok in enumerate([None] + rut_sites):
            rr = e4f + i
            if lok:
                c4.put(f"B{rr}", lok, align=_LEFT)
            crit = f'{MT.R("Blok")},{BL}' + (f',{MT.R("lokasi")},B{rr}' if lok else "")
            c4.put(f"C{rr}", f'=SUMIFS({MT.R("biaya")},{crit},{MT.R("jenis_pemeliharaan")},"RUTIN")', "#,##0")
            c4.put(f"D{rr}", f'=SUMIFS({MT.R("biaya")},{crit},{MT.R("jenis_pemeliharaan")},"NON RUTIN")', "#,##0")
            c4.put(f"E{rr}", f'=SUMIFS({MT.R("biaya")},{crit})', "#,##0")
            c4.put(f"F{rr}", f'=IF(E{rr}=0,"",' + (f"C{rr}/E{rr})" if not lok else f"C{rr}/E{rr})"), "0.0%", bold=True)
            c4.put(f"G{rr}", f'=IF(E{rr}=0,"",' + (f"D{rr}/E{rr})" if not lok else f"1-F{rr})"), "0.0%", bold=True)
            if lok:
                c4.put(f"H{rr}", f'=IF(F{rr}="","","{_site(lok)} "&FIXED(F{rr}*100,0,TRUE)&"%")', align=_LEFT)
                c4.put(f"I{rr}", f'=IF(G{rr}="","","{_site(lok)} "&FIXED(G{rr}*100,0,TRUE)&"%")', align=_LEFT)
        RUT, NRUT = f"{P4}$F${e4f}", f"{P4}$G${e4f}"
        e4l = e4f + len(rut_sites)
        rut_txt = (f'="Rutin: "&_xlfn.TEXTJOIN("  ·  ",TRUE,{P4}H{e4f+1}:H{e4l})' if rut_sites else '=""')
        nrut_txt = (f'="Non-Rutin: "&_xlfn.TEXTJOIN("  ·  ",TRUE,{P4}I{e4f+1}:I{e4l})' if rut_sites else None)
        rF4 = e4l + 3
        c4.put(f"B{rF4}", "F. Kategori Sparepart — 10 nilai tertinggi (biaya pemeliharaan per sistem)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        kat_top, kat_sites = [], []
        if not mtb.empty:
            ka = mtb.groupby("kategori_sparepart")["biaya"].sum().sort_values(ascending=False).head(10)
            kat_top = list(ka.index)
            kat_sites = mtb[mtb["kategori_sparepart"].isin(kat_top)].groupby("lokasi")["biaya"].sum().sort_values(ascending=False).index.tolist()
        c4.header(rF4 + 1, 2, ["No", "Kategori"] + kat_sites + ["Total"])
        f4f = rF4 + 2
        for i, kat in enumerate(kat_top):
            rr = f4f + i
            c4.put(f"B{rr}", i + 1, "0", align=_CENTER); c4.put(f"C{rr}", kat, bold=True, align=_LEFT)
            for j, lok in enumerate(kat_sites):
                col = _CL(4 + j)
                c4.put(f"{col}{rr}", f'=SUMIFS({MT.R("biaya")},{MT.R("Blok")},{BL},{MT.R("kategori_sparepart")},$C{rr},{MT.R("lokasi")},"{lok}")', "#,##0")
            colT = _CL(4 + len(kat_sites))
            c4.put(f"{colT}{rr}", f'=SUMIFS({MT.R("biaya")},{MT.R("Blok")},{BL},{MT.R("kategori_sparepart")},$C{rr})', "#,##0", bold=True, color=_GOLD)
        # ---- tampilan slide 04
        v4.title(f"KEY INSIGHTS — Downtime Analysis & Varian s/d {cawu}", f"Analisis Downtime · 04 · {SUBLBL[blok]}", blok, last_month, period_txt, note_all)
        v4.widths({"A": 2, **{_CL(i): 11 for i in range(2, 21)}})
        v4.ws["C3"] = f"='{v1.name}'!C3"
        v4.ws["G3"] = f"='{v1.name}'!G3"
        v4.card("B", 5, "Capaian Downtime (Realisasi s/d " + cawu_inline + ")", f"={CAPDT}", "0.0%", dt_site_txt,
                f'=IF({CAPDT}="","Data tidak tersedia",IF({CAPDT}>1,"✗ Melebihi Target","✓ Dalam Target"))', f"{CAPDT}<=1", _RED, width_cols=6, sub2_f="")
        v4.card("H", 5, "MTTR (Mean Time To Repair)", f"={MTTR_T}", '0.0" jam"', mttr_site_txt,
                f'=IF({MTTR_T}="","Data Workshop belum tersedia","Dari "&SUBSTITUTE(FIXED({MTTR_N},0),",",".")&" kejadian perbaikan")', "TRUE", _TEAL, width_cols=6, sub2_f="")
        v4.card("N", 5, "Rutin vs Non-Rutin (porsi biaya maintenance)",
                f'=IF({RUT}="","-",FIXED({RUT}*100,0,TRUE)&"% / "&FIXED({NRUT}*100,0,TRUE)&"%")', "@", rut_txt,
                f'=IF({RUT}="","Data tidak tersedia",IF({RUT}>=0.5,"✓ Rutin Lebih Dominan","✗ Non-Rutin Lebih Dominan"))', f"N({RUT})>=0.5", _GREEN,
                width_cols=7, sub2_f=nrut_txt)
        v4.section(14, "% Downtime — per Site & Kelompok Unit", "B", "L")
        v4.section(14, "Kategori Sparepart — Nilai Tertinggi per Site", "N", "T", color=_NAVY)
        if dtc:
            # 2 seri (merah = melebihi target, hijau = dalam target) ditumpuk di posisi sama (overlap 100) -> label
            # angka bisa ditaruh di ATAS batang (outEnd); nilai 0 dari seri lawannya disembunyikan ("0%;;;").
            ch = _bar_chart(grouping="clustered", overlap=100, gap=50)
            for col_idx in (10, 11):
                ch.add_data(_Ref(c4.ws, min_col=col_idx, min_row=rC4 + 1, max_row=c4l), titles_from_data=True)
            ch.set_categories(_Ref(c4.ws, min_col=2, min_row=c4f, max_row=c4l))
            _color_series(ch, (_RED, _GREEN)); _labels(ch, "0%;;;", size=(9.5 if len(dtc) <= 12 else 8)); ch.y_axis.numFmt = "0%"
            _place(v4.ws, ch, "B15:L33")
        # tabel sparepart di tampilan
        hdr = ["No", "Kategori"] + [_site(l) for l in kat_sites] + ["Total"]
        cols_sp = ["N", "O"] + [_CL(16 + j) for j in range(len(kat_sites))] + [_CL(16 + len(kat_sites))]
        # Lebar kolom: tabel mengisi PENUH panel N..T (kolom nilai dibagi rata, sisa kolom kosong dipersempit)
        n_val_sp = len(kat_sites) + 1
        v4.ws.column_dimensions["N"].width = 5
        v4.ws.column_dimensions["O"].width = 27
        for j in range(5):
            v4.ws.column_dimensions[_CL(16 + j)].width = (60 / n_val_sp) if j < n_val_sp else 1
        for j, (col, h) in enumerate(zip(cols_sp, hdr)):
            v4.put(f"{col}15", h, bold=True, color="FFFFFF", fillc="4B5563", align=_CENTER, size=10)
        for i, kat in enumerate(kat_top):
            rr = 16 + i
            v4.ws.row_dimensions[rr].height = 22
            v4.put(f"N{rr}", i + 1, "0", bold=True, color="FFFFFF", fillc=_GOLD, align=_CENTER, size=10)
            v4.put(f"O{rr}", f"={P4}C{f4f+i}", bold=True, align=_LEFT, size=10)
            for j in range(len(kat_sites)):
                src = f"{P4}{_CL(4+j)}{f4f+i}"
                v4.put(f"{cols_sp[2+j]}{rr}", f'=IF({src}=0,"-",{_rp(src)})', align=_RIGHT, size=10)
            srcT = f"{P4}{_CL(4+len(kat_sites))}{f4f+i}"
            v4.put(f"{cols_sp[-1]}{rr}", f"={_rp(srcT)}", bold=True, color=_GOLD, align=_RIGHT, size=10.5)
        if dtc:
            npos = f"{P4}$E${rs4}"
            v4.note_box("B35:L37", (
                f'=IF({P4}$D${rs4}>0,{P4}$D${rs4}&" dari "&{P4}$C${rs4}&" unit ("&FIXED({P4}$D${rs4}/{P4}$C${rs4}*100,0,TRUE)&"%) melebihi target downtime. Unit paling kritis: "'
                f'&INDEX({P4}$B${c4f}:$B${c4l},{npos})&" dengan Capaian Downtime "&FIXED(INDEX({P4}$I${c4f}:$I${c4l},{npos})*100,0,TRUE)&"% (downtime realisasinya "'
                f'&FIXED(INDEX({P4}$I${c4f}:$I${c4l},{npos})*100-100,0,TRUE)&"% di atas batas yang diizinkan) — prioritaskan preventive maintenance pada unit-unit ini.",'
                f'"Seluruh "&{P4}$C${rs4}&" unit berada dalam target downtime yang diizinkan. Pertahankan jadwal preventive maintenance saat ini.")'))

        # =========================== SLIDE 02 — BIAYA OPERASIONAL ===========================
        v2 = _Sheet(wb, f"{px}-02 Biaya Operasional"); c2 = _Sheet(wb, f"{px}-02 Perhitungan")
        P2 = c2.P
        c2.widths({"A": 2, "B": 30, "C": 16, "D": 22, **{k: 14 for k in "EFGHIJKLMNOPQ"}})
        c2.section(2, f"{px}-02 PERHITUNGAN — sumber semua angka di sheet '{v2.name}'", "B", "P")
        rA2 = 4
        c2.put(f"B{rA2}", "A. Ringkasan Biaya (BBM hanya baris yg valid; Cap. Fisik: Prestasi Floating / Qty BBM / Capaian Downtime)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c2.header(rA2 + 1, 2, ["Metrik", "Budget", "Aktual", "Capaian", "Cap. Fisik", "Fisik: lebih tinggi lebih baik?"])
        bbm_ok = f'{DB.R("BBM Valid")},1'
        rows2 = [
            ("Total Biaya", f"=SUMIFS({DB.R('total_biaya_budget')},{DB.R('Blok')},{BL})", f"=SUMIFS({DB.R('total_biaya_realisasi')},{DB.R('Blok')},{BL})",
             f"={PR}/{PB}", True, bd["total_biaya_realisasi"].sum()),
            ("Upah Operator", f"=SUMIFS({DB.R('upah_budget')},{DB.R('Blok')},{BL})", f"=SUMIFS({DB.R('upah_realisasi')},{DB.R('Blok')},{BL})", None, None,
             bd["upah_realisasi"].sum()),
            ("Biaya BBM", f"=SUMIFS({DB.R('biaya_bbm_budget')},{DB.R('Blok')},{BL},{bbm_ok})", f"=SUMIFS({DB.R('biaya_bbm_realisasi')},{DB.R('Blok')},{BL},{bbm_ok})",
             f"=IFERROR(SUMIFS({DB.R('qty_bbm_realisasi')},{DB.R('Blok')},{BL},{bbm_ok})/SUMIFS({DB.R('qty_bbm_budget')},{DB.R('Blok')},{BL},{bbm_ok}),\"\")", False,
             None),
            ("Biaya Maintenance", f"=SUMIFS({DB.R('maintenance_budget')},{DB.R('Blok')},{BL})", f"=SUMIFS({DB.R('maintenance_realisasi')},{DB.R('Blok')},{BL})",
             f"={CAPDT}", False, bd["maintenance_realisasi"].sum()),
            ("Biaya Lainnya", f"=SUMIFS({DB.R('lainnya_budget')},{DB.R('Blok')},{BL})", f"=SUMIFS({DB.R('lainnya_realisasi')},{DB.R('Blok')},{BL})", None, None,
             bd["lainnya_realisasi"].sum()),
        ]
        _bad = ((bd["qty_bbm_realisasi"] > 0) & (bd["biaya_bbm_realisasi"].fillna(0) == 0)) | ((bd["qty_bbm_budget"] > 0) & (bd["biaya_bbm_budget"].fillna(0) == 0))
        rows2[2] = rows2[2][:5] + (bd.loc[~_bad, "biaya_bbm_realisasi"].sum(),)
        order2 = [rows2[0]] + sorted(rows2[1:], key=lambda x: -x[5])
        a2f = rA2 + 2
        for i, (nm, fb, fr, ff, hib, _) in enumerate(order2):
            rr = a2f + i
            c2.put(f"B{rr}", nm, bold=True, align=_LEFT)
            c2.put(f"C{rr}", fb, "#,##0"); c2.put(f"D{rr}", fr, "#,##0")
            c2.put(f"E{rr}", f'=IF(C{rr}=0,"",D{rr}/C{rr})', "0.0%", bold=True)
            c2.put(f"F{rr}", ff if ff else "", "0.0%"); c2.put(f"G{rr}", ("YA" if hib else "TIDAK") if hib is not None else "", align=_CENTER)
        # BTL per site
        rB2 = a2f + 7
        c2.put(f"B{rB2}", "B. Biaya Tidak Langsung per Site (Kategori)", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c2.header(rB2 + 1, 2, ["Site (Kategori)", "Site", "Kategori", "Budget", "Aktual", "% Target", "% BTL", "Over budget?"])
        btl = bd.groupby(["lokasi", "_katp"])[["biaya_tidak_langsung_realisasi", "biaya_tidak_langsung_budget"]].sum()
        btl = btl[(btl["biaya_tidak_langsung_realisasi"] > 0) | (btl["biaya_tidak_langsung_budget"] > 0)].sort_values("biaya_tidak_langsung_realisasi", ascending=False)
        b2f = rB2 + 2
        btl_keys = list(btl.index)
        b2l = b2f + max(len(btl_keys), 1) - 1
        for i, (lok, kat) in enumerate(btl_keys):
            rr = b2f + i
            c2.put(f"B{rr}", f"{_site(lok)} ({kat})", bold=True, align=_LEFT); c2.put(f"C{rr}", lok, align=_LEFT); c2.put(f"D{rr}", kat, align=_CENTER)
            cr_ = f'{DB.R("Blok")},{BL},{DB.R("lokasi")},$C{rr},{DB.R("Kategori PPT")},$D{rr}'
            c2.put(f"E{rr}", f"=SUMIFS({DB.R('biaya_tidak_langsung_budget')},{cr_})", "#,##0")
            c2.put(f"F{rr}", f"=SUMIFS({DB.R('biaya_tidak_langsung_realisasi')},{cr_})", "#,##0")
            c2.put(f"G{rr}", f'=IF(E{rr}=0,"",F{rr}/E{rr})', "0%", bold=True)
            c2.put(f"H{rr}", f"=IFERROR(F{rr}/SUM($F${b2f}:$F${b2l}),0)", "0.0%")
            c2.put(f"I{rr}", f'=IF(AND(G{rr}<>"",N(G{rr})>1),B{rr},"")', align=_LEFT)
        # BBM per kelompok
        rC2 = b2l + 3
        c2.put(f"B{rC2}", "C. Analisa Penyebab Kenaikan Biaya BBM per Site & Kelompok Unit", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        hdrC = ["Label (chart)", "Site", "Kelompok Unit", "Kategori", "Qty BBM R", "Qty BBM B", "Prestasi R", "Prestasi B",
                "Cap. Prestasi", "Cap. Konsumsi", "Harga BBM R (Rp/Ltr)", "Harga BBM B (Rp/Ltr)", "Capaian Harga BBM",
                "Gap Biaya BBM (Rp)", "Penyebab dominan"]
        c2.header(rC2 + 1, 2, hdrC)
        d3 = bd.copy()
        vr = (d3["qty_bbm_realisasi"].fillna(0) > 0) & (d3["biaya_bbm_realisasi"].fillna(0) > 0) & (d3["prestasi_realisasi"].fillna(0) > 0)
        vb = (d3["qty_bbm_budget"].fillna(0) > 0) & (d3["biaya_bbm_budget"].fillna(0) > 0) & (d3["prestasi_budget"].fillna(0) > 0)
        d3["_qr"] = d3["qty_bbm_realisasi"].where(vr, 0); d3["_pr"] = d3["prestasi_realisasi"].where(vr, 0)
        d3["_qb"] = d3["qty_bbm_budget"].where(vb, 0); d3["_pb"] = d3["prestasi_budget"].where(vb, 0)
        su3 = d3.groupby(["lokasi", "_katp", "kelompok_unit"])[["_qr", "_qb", "_pr", "_pb"]].sum().reset_index()
        su3 = su3[(su3["_qr"] > 0) | (su3["_qb"] > 0)]

        def _capk(r):
            if r["_katp"] == "AB":
                rr_ = (r["_qr"] / r["_pr"]) if r["_pr"] else None
                rb_ = (r["_qb"] / r["_pb"]) if r["_pb"] else None
                return None if (rr_ is None or not rb_) else rr_ / rb_
            rr_ = (r["_pr"] / r["_qr"]) if r["_qr"] else None
            rb_ = (r["_pb"] / r["_qb"]) if r["_qb"] else None
            return None if (not rr_ or rb_ is None) else rb_ / rr_
        su3 = su3[[(_capk(r) is not None) for _, r in su3.iterrows()]].sort_values(["kelompok_unit", "lokasi"]).head(12)
        bbm_keys = su3[["lokasi", "_katp", "kelompok_unit"]].values.tolist()
        c2f = rC2 + 2
        c2l = c2f + max(len(bbm_keys), 1) - 1
        for i, (lok, kat, kel) in enumerate(bbm_keys):
            rr = c2f + i
            c2.put(f"B{rr}", f"{_site(lok)} — {kel}", bold=True, align=_LEFT); c2.put(f"C{rr}", lok, align=_LEFT)
            c2.put(f"D{rr}", kel, align=_LEFT); c2.put(f"E{rr}", kat, align=_CENTER)
            ck = f'{DB.R("Blok")},{BL},{DB.R("lokasi")},$C{rr},{DB.R("Kategori PPT")},$E{rr},{DB.R("kelompok_unit")},$D{rr}'
            c2.put(f"F{rr}", f"=SUMIFS({DB.R('Qty BBM R (konsumsi)')},{ck})", "#,##0")
            c2.put(f"G{rr}", f"=SUMIFS({DB.R('Qty BBM B (konsumsi)')},{ck})", "#,##0")
            c2.put(f"H{rr}", f"=SUMIFS({DB.R('Prestasi R (konsumsi)')},{ck})", "#,##0")
            c2.put(f"I{rr}", f"=SUMIFS({DB.R('Prestasi B (konsumsi)')},{ck})", "#,##0")
            c2.put(f"J{rr}", f'=IF(I{rr}=0,"",H{rr}/I{rr})', "0%", bold=True)
            c2.put(f"K{rr}", (f'=IF($E{rr}="AB",IFERROR((F{rr}/H{rr})/(G{rr}/I{rr}),""),IFERROR((I{rr}/G{rr})/(H{rr}/F{rr}),""))'), "0%", bold=True)
            ch_ = f'{DB.R("Blok")},{BL},{DB.R("lokasi")},$C{rr},{DB.R("kelompok_unit")},$D{rr},{DB.R("BBM Valid")},1'
            c2.put(f"L{rr}", f"=IFERROR(SUMIFS({DB.R('biaya_bbm_realisasi')},{ch_})/SUMIFS({DB.R('qty_bbm_realisasi')},{ch_}),\"\")", "#,##0")
            c2.put(f"M{rr}", f"=IFERROR(SUMIFS({DB.R('biaya_bbm_budget')},{ch_})/SUMIFS({DB.R('qty_bbm_budget')},{ch_}),\"\")", "#,##0")
            c2.put(f"N{rr}", f'=IF(OR(L{rr}="",M{rr}="",M{rr}=0),"",L{rr}/M{rr})', "0%", bold=True)
            cg = f'{DB.R("Blok")},{BL},{DB.R("lokasi")},$C{rr},{DB.R("kelompok_unit")},$D{rr}'
            c2.put(f"O{rr}", f"=SUMIFS({DB.R('biaya_bbm_realisasi')},{cg})-SUMIFS({DB.R('biaya_bbm_budget')},{cg})", "#,##0;[Red]-#,##0")
            dp = f'IF(J{rr}="",-1,ABS(J{rr}-1))'; dk = f"ABS(K{rr}-1)"; dh = f'IF(N{rr}="",-1,ABS(N{rr}-1))'
            c2.put(f"P{rr}", (f'=IF(AND({dp}>={dk},{dp}>={dh}),"Volume Operasi (Prestasi) "&IF(J{rr}>1,"Naik","Turun"),'
                              f'IF({dk}>={dh},"Konsumsi BBM "&IF(K{rr}>1,"Naik","Turun"),"Harga BBM "&IF(N{rr}>1,"Naik","Turun")))'), align=_LEFT)
        rmx = c2l + 1
        c2.put(f"B{rmx}", "Dampak Rupiah terbesar (posisi baris)", bold=True, align=_LEFT)
        c2.put(f"O{rmx}", f"=MAX(O{c2f}:O{c2l})", "#,##0;[Red]-#,##0", bold=True)
        c2.put(f"P{rmx}", f"=IFERROR(MATCH(O{rmx},O{c2f}:O{c2l},0),0)", "0", bold=True)
        # ---- tampilan slide 02
        v2.title(f"BIAYA OPERASIONAL — Budget vs Aktual s/d {cawu}", f"Biaya Operasional · 02 · {SUBLBL[blok]}", blok, last_month, period_txt, note_all)
        v2.widths({"A": 2, **{_CL(i): 11 for i in range(2, 21)}})
        v2.ws["C3"] = f"='{v1.name}'!C3"; v2.ws["G3"] = f"='{v1.name}'!G3"
        v2.ws.merge_cells("B5:J5")
        v2.put("B5", f"Ringkasan Biaya PT. BKMS (s/d {cawu_inline})", bold=True, size=13, border=False, align=_LEFT)
        for j, (rng, h) in enumerate((("B6:C6", "Metrik"), ("D6:E6", "Budget"), ("F6:G6", "Aktual"), ("H6:H6", "Capaian"), ("I6:J6", "Cap. Fisik"))):
            v2.merge_put(rng, h, bold=True, color="FFFFFF", fillc=_NAVY, align=_CENTER, size=10)
        v2.ws.row_dimensions[6].height = 22
        capd = lambda x: f'IF({x}="","-",IF({x}>9.99,">999%",{_pct(x)}))'
        for i in range(5):
            rr = 7 + i; src = a2f + i
            v2.ws.row_dimensions[rr].height = 22
            v2.merge_put(f"B{rr}:C{rr}", f"={P2}B{src}", align=_LEFT, size=10, bold=True)
            v2.merge_put(f"D{rr}:E{rr}", f"={_rp(f'{P2}C{src}')}", align=_RIGHT, size=10)
            v2.merge_put(f"F{rr}:G{rr}", f"={_rp(f'{P2}D{src}')}", align=_RIGHT, size=10)
            v2.put(f"H{rr}", f"={capd(f'{P2}E{src}')}", bold=True, align=_CENTER, size=10)
            fx = f"{P2}F{src}"; hi = f"{P2}G{src}"
            v2.merge_put(f"I{rr}:J{rr}", (f'=IF({fx}="","-",IF({fx}>9.99,">999%",{_pct(fx)}))'), bold=True, align=_CENTER, size=10)
            ex = f"{P2}$E${src}"; fxa = f"{P2}$F${src}"; hia = f"{P2}$G${src}"
            v2.ws.conditional_formatting.add(f"H{rr}", _FRule(formula=[f'AND({ex}<>"",N({ex})<=1)'], fill=_fill(_GREEN_BG), font=_Font(name=_FONT, bold=True, color=_GREEN)))
            v2.ws.conditional_formatting.add(f"H{rr}", _FRule(formula=[f'AND({ex}<>"",N({ex})>1)'], fill=_fill(_RED), font=_Font(name=_FONT, bold=True, color="FFFFFF")))
            good_f = f'AND({fxa}<>"",IF({hia}="YA",N({fxa})>=1,N({fxa})<=1))'
            bad_f = f'AND({fxa}<>"",NOT(IF({hia}="YA",N({fxa})>=1,N({fxa})<=1)))'
            v2.ws.conditional_formatting.add(f"I{rr}:J{rr}", _FRule(formula=[good_f], fill=_fill(_GREEN_BG), font=_Font(name=_FONT, bold=True, color=_GREEN)))
            v2.ws.conditional_formatting.add(f"I{rr}:J{rr}", _FRule(formula=[bad_f], fill=_fill(_RED), font=_Font(name=_FONT, bold=True, color="FFFFFF")))
        overj = f"_xlfn.TEXTJOIN(\" & \",TRUE,{P2}I{b2f}:I{b2l})"
        v2.ws.merge_cells("L5:T5")
        v2.put("L5", f'=IF({overj}="","✅ BTL — UNDER BUDGET secara keseluruhan","⚠️ BTL — UNDER BUDGET, kecuali "&{overj})', bold=True, size=11, align=_CENTER)
        v2.ws.conditional_formatting.add("L5:T5", _FRule(formula=[f'LEFT($L$5,1)="✅"'], fill=_fill(_GREEN_BG), font=_Font(name=_FONT, bold=True, color=_GREEN)))
        v2.ws.conditional_formatting.add("L5:T5", _FRule(formula=[f'LEFT($L$5,1)<>"✅"'], fill=_fill(_RED_BG), font=_Font(name=_FONT, bold=True, color=_RED)))
        for rng, h in (("L6:N6", "Site (Kategori)"), ("O6:P6", "Budget"), ("Q6:R6", "Aktual"), ("S6:S6", "% Target"), ("T6:T6", "% BTL")):
            v2.merge_put(rng, h, bold=True, color="FFFFFF", fillc=_NAVY, align=_CENTER, size=10)
        for i in range(len(btl_keys)):
            rr = 7 + i; src = b2f + i
            v2.merge_put(f"L{rr}:N{rr}", f"={P2}B{src}", align=_LEFT, size=10, bold=True)
            v2.merge_put(f"O{rr}:P{rr}", f"={_rp(f'{P2}E{src}')}", align=_RIGHT, size=10)
            v2.merge_put(f"Q{rr}:R{rr}", f"={_rp(f'{P2}F{src}')}", align=_RIGHT, size=10)
            g_ = f"{P2}G{src}"
            v2.put(f"S{rr}", f'=IF({g_}="","-",FIXED({g_}*100,0,TRUE)&"%")', bold=True, align=_CENTER, size=10)
            v2.put(f"T{rr}", f"=FIXED({P2}H{src}*100,1)&\"%\"", align=_CENTER, size=10)
            ga = f"{P2}$G${src}"
            v2.ws.conditional_formatting.add(f"S{rr}", _FRule(formula=[f'AND({ga}<>"",N({ga})<=1)'], font=_Font(name=_FONT, bold=True, color=_GREEN)))
            v2.ws.conditional_formatting.add(f"S{rr}", _FRule(formula=[f'AND({ga}<>"",N({ga})>1)'], font=_Font(name=_FONT, bold=True, color=_RED)))
        top_c = max(13, 8 + len(btl_keys))
        v2.section(top_c, "Analisa Penyebab Kenaikan Biaya BBM — per Site & Kelompok Unit")
        if bbm_keys:
            ch = _bar_chart(overlap=-8, legend="t")
            for col_idx in (10, 11, 14):
                ch.add_data(_Ref(c2.ws, min_col=col_idx, min_row=rC2 + 1, max_row=c2l), titles_from_data=True)
            ch.set_categories(_Ref(c2.ws, min_col=2, min_row=c2f, max_row=c2l))
            _color_series(ch, ("7B5CC9", "D98A2E", "3FA86B")); _labels(ch, "0%", size=(9 if len(bbm_keys) <= 9 else 7.5)); ch.y_axis.numFmt = "0%"
            _place(v2.ws, ch, f"B{top_c+1}:T{top_c+18}")
            pk = lambda col: f"INDEX({P2}${col}${c2f}:${col}${c2l},{P2}$P${rmx})"
            nb = top_c + 20
            v2.note_box(f"B{nb}:T{nb+2}", (
                f'={pk("B")}&" adalah unit dengan dampak Rupiah biaya BBM terbesar ("&{_rp("ABS(" + pk("O") + ")")}&" "&IF({pk("O")}>0,"over budget","hemat")'
                f'&") — penyebab dominannya: "&{pk("P")}&" (Cap. Prestasi "&IF({pk("J")}="","data tidak tersedia",FIXED({pk("J")}*100,0,TRUE)&"%")'
                f'&", Cap. Konsumsi "&FIXED({pk("K")}*100,0,TRUE)&"%, Cap. Harga BBM "&IF({pk("N")}="","data tidak tersedia",FIXED({pk("N")}*100,0,TRUE)&"%")&")."'),
                color="7A5C0D", bg=_GOLD_BG)

        # =========================== SLIDE 03 — ANALISIS BIAYA MAINTENANCE ===========================
        v3 = _Sheet(wb, f"{px}-03 Analisis Biaya"); c3 = _Sheet(wb, f"{px}-03 Perhitungan")
        P3 = c3.P
        c3.widths({"A": 2, "B": 28, "C": 16, "D": 22, **{k: 14 for k in "EFGHIJKLMNOPQRS"}})
        c3.section(2, f"{px}-03 PERHITUNGAN — sumber semua angka di sheet '{v3.name}'", "B", "P")
        ms = bd.groupby(["lokasi", "kelompok_unit"])[["maintenance_realisasi", "maintenance_budget"]].sum()
        mkeys = {k for k, v in ms.iterrows() if v["maintenance_realisasi"] > 0 or v["maintenance_budget"] > 0}
        rkeys = set()
        if not mtb.empty:
            mk_ = mtb.dropna(subset=["kelompok_unit"])
            if not mk_.empty:
                tt = mk_[mk_["jenis_pemeliharaan"].isin(["RUTIN", "NON RUTIN"])].groupby(["lokasi", "kelompok_unit"])["biaya"].sum()
                rkeys = {k for k, v in tt.items() if v > 0}
        rows3 = sorted(mkeys | rkeys, key=lambda k: (k[1], k[0]))
        c3.put("B4", "A. Gap Biaya Maintenance, Rutin/Non-Rutin & Capaian Downtime per Site & Kelompok Unit", border=False, bold=True, color=_NAVY, size=10, align=_LEFT)
        c3.header(5, 2, ["Label", "Site", "Kelompok Unit", "Maint. Realisasi", "Maint. Budget", "% Capaian", "Gap (R - B)",
                         "Over budget (Rp)", "Di bawah budget (Rp)", "Biaya Rutin", "Biaya Non-Rutin", "% Rutin", "% Non-Rutin",
                         "Breakdown (HM/KM)", "Ideal (HM/KM)", "Cap. Downtime", "Rutin", "Non-Rutin"])
        a3f = 6
        a3l = a3f + max(len(rows3), 1) - 1
        for i, (lok, kel) in enumerate(rows3):
            rr = a3f + i
            c3.put(f"B{rr}", f"{_site(lok)} — {_kel(kel)}", bold=True, align=_LEFT); c3.put(f"C{rr}", lok, align=_LEFT); c3.put(f"D{rr}", kel, align=_LEFT)
            cb = f'{DB.R("Blok")},{BL},{DB.R("lokasi")},$C{rr},{DB.R("kelompok_unit")},$D{rr}'
            has_m = (lok, kel) in mkeys
            c3.put(f"E{rr}", f"=SUMIFS({DB.R('maintenance_realisasi')},{cb})" if has_m else "", "#,##0")
            c3.put(f"F{rr}", f"=SUMIFS({DB.R('maintenance_budget')},{cb})" if has_m else "", "#,##0")
            c3.put(f"G{rr}", f'=IF(OR(E{rr}="",N(F{rr})=0),"",E{rr}/F{rr})', "0%", bold=True)
            c3.put(f"H{rr}", f'=IF(E{rr}="","",E{rr}-F{rr})', "#,##0;[Red]-#,##0", bold=True)
            c3.put(f"I{rr}", f"=IF(N(H{rr})>0,H{rr},0)", '"+Rp "#,##0.0,," Jt";"−Rp "#,##0.0,," Jt";;')
            c3.put(f"J{rr}", f"=IF(N(H{rr})<0,H{rr},0)", '"+Rp "#,##0.0,," Jt";"−Rp "#,##0.0,," Jt";;')
            cm = f'{MT.R("Blok")},{BL},{MT.R("lokasi")},$C{rr},{MT.R("kelompok_unit")},$D{rr}'
            c3.put(f"K{rr}", f'=SUMIFS({MT.R("biaya")},{cm},{MT.R("jenis_pemeliharaan")},"RUTIN")', "#,##0")
            c3.put(f"L{rr}", f'=SUMIFS({MT.R("biaya")},{cm},{MT.R("jenis_pemeliharaan")},"NON RUTIN")', "#,##0")
            c3.put(f"M{rr}", f'=IF(K{rr}+L{rr}=0,"",K{rr}/(K{rr}+L{rr}))', "0%", bold=True)
            c3.put(f"N{rr}", f'=IF(M{rr}="","",1-M{rr})', "0%", bold=True)
            cs = f'{SM.R("Blok")},{BL},{SM.R("lokasi")},$C{rr},{SM.R("kelompok_unit")},$D{rr}'
            c3.put(f"O{rr}", f"=SUMIFS({SM.R('breakdown_hm_km_realisasi')},{cs})", "#,##0")
            c3.put(f"P{rr}", f"=SUMIFS({SM.R('hm_km_ideal_target')},{cs})", "#,##0")
            c3.put(f"Q{rr}", (f'=IF(OR(M{rr}="",P{rr}=0),"",IFERROR((O{rr}/P{rr})/(AVERAGEIFS({SM.R("downtime_target")},{cs})/100),""))'), "0%", bold=True)
            c3.put(f"R{rr}", f"=N(M{rr})", "0%;;;"); c3.put(f"S{rr}", f"=N(N{rr})", "0%;;;")
        rt3 = a3l + 1
        c3.put(f"B{rt3}", "TOTAL", bold=True, align=_LEFT, fillc="EEF2FF")
        for col in "EFKL":
            c3.put(f"{col}{rt3}", f"=SUM({col}{a3f}:{col}{a3l})", "#,##0", bold=True, fillc="EEF2FF")
        c3.put(f"G{rt3}", f'=IF(F{rt3}=0,"",E{rt3}/F{rt3})', "0%", bold=True, fillc="EEF2FF")
        c3.put(f"H{rt3}", f"=E{rt3}-F{rt3}", "#,##0;[Red]-#,##0", bold=True, fillc="EEF2FF")
        c3.put(f"M{rt3}", f'=IF(K{rt3}+L{rt3}=0,"",K{rt3}/(K{rt3}+L{rt3}))', "0%", bold=True, fillc="EEF2FF")
        c3.put(f"N{rt3}", f'=IF(M{rt3}="","",1-M{rt3})', "0%", bold=True, fillc="EEF2FF")
        rs3 = rt3 + 2
        c3.put(f"B{rs3}", "Ringkasan analisa", bold=True, color=_NAVY, border=False, align=_LEFT)
        c3.header(rs3 + 1, 2, ["Jumlah kelompok", "Over budget", "Tanpa budget (over)", "Posisi over terbesar"])
        rs = rs3 + 2
        c3.put(f"B{rs}", f"=ROWS(B{a3f}:B{a3l})", "0", align=_CENTER)
        c3.put(f"C{rs}", f'=COUNTIF(H{a3f}:H{a3l},">0")', "0", align=_CENTER, bold=True, color=_RED)
        c3.put(f"D{rs}", f'=COUNTIFS(H{a3f}:H{a3l},">0",F{a3f}:F{a3l},0)', "0", align=_CENTER)
        c3.put(f"E{rs}", f"=IFERROR(MATCH(MAX(H{a3f}:H{a3l}),H{a3f}:H{a3l},0),0)", "0", align=_CENTER)
        # ---- tampilan slide 03
        v3.title(f"ANALISIS: Biaya Maintenance & Rutin/Non-Rutin — s/d {cawu}", f"Analisis Biaya · 03 · {SUBLBL[blok]}", blok, last_month, period_txt, note_all)
        v3.widths({"A": 2, **{_CL(i): 11 for i in range(2, 21)}})
        v3.ws["C3"] = f"='{v1.name}'!C3"; v3.ws["G3"] = f"='{v1.name}'!G3"
        v3.section(5, "Gap Biaya Maintenance — per Site & Kelompok Unit", "B", "J")
        v3.section(5, "Rutin vs Non-Rutin — per Site & Kelompok Unit", "L", "T")
        if rows3:
            hh = max(8, 0.55 * len(rows3) + 2)
            # clustered + overlap 100 (bukan stacked) spy label nilai bisa di UJUNG batang (outEnd)
            ch = _bar_chart(kind="bar", grouping="clustered", overlap=100, gap=40, legend="t")
            for col_idx in (9, 10):
                ch.add_data(_Ref(c3.ws, min_col=col_idx, min_row=5, max_row=a3l), titles_from_data=True)
            ch.set_categories(_Ref(c3.ws, min_col=2, min_row=a3f, max_row=a3l))
            _color_series(ch, (_RED, _TEAL))
            _labels(ch, '"+Rp "#,##0.0,," Jt";"−Rp "#,##0.0,," Jt";;', size=(8.5 if len(rows3) <= 14 else 7.5))
            ch.x_axis.scaling.orientation = "maxMin"; ch.y_axis.numFmt = '#,##0,," Jt"'
            ch.x_axis.tickLblPos = "low"  # nama kelompok di tepi kiri (tdk menabrak batang negatif)
            ch.y_axis.crosses = "max"  # urutan kategori dibalik -> sumbu nilai pindah ke BAWAH (tdk menabrak legenda di atas)
            # Batas sumbu diberi ruang kiri-kanan (dari data saat file dibuat) spy label "+Rp .. Jt"/"−Rp .. Jt" di
            # ujung batang tdk menabrak nama kelompok atau terpotong di tepi chart.
            try:
                import math as _m
                _gv = [float(ms.loc[k, "maintenance_realisasi"] - ms.loc[k, "maintenance_budget"]) for k in rows3 if k in ms.index]
                if _gv:
                    _hi, _lo = max(max(_gv), 0.0), min(min(_gv), 0.0)
                    _span = (_hi - _lo) or 1.0
                    _top = _hi + 0.30 * _span
                    _bot = _lo - (0.30 * _span if _lo < 0 else 0.02 * _span)
                    # kelipatan "enak dibaca" (1/2/5 x 10^n) dgn target sktr 6 garis sumbu
                    _raw = (_top - _bot) / 6
                    _p = 10 ** _m.floor(_m.log10(_raw))
                    _step = next(m_ * _p for m_ in (1, 2, 5, 10) if m_ * _p >= _raw)
                    ch.y_axis.scaling.max = _m.ceil(_top / _step) * _step
                    ch.y_axis.scaling.min = _m.floor(_bot / _step) * _step
                    ch.y_axis.majorUnit = _step
            except Exception:
                pass
            ch_bottom = 6 + len(rows3) + 3
            for rr_ in range(6, ch_bottom + 1):
                v3.ws.row_dimensions[rr_].height = 21
            _place(v3.ws, ch, f"B6:J{ch_bottom}")
            ch2 = _bar_chart(kind="bar", grouping="percentStacked", overlap=100, gap=40, legend="t")
            for col_idx in (18, 19):
                ch2.add_data(_Ref(c3.ws, min_col=col_idx, min_row=5, max_row=a3l), titles_from_data=True)
            ch2.set_categories(_Ref(c3.ws, min_col=2, min_row=a3f, max_row=a3l))
            _color_series(ch2, (_TEAL, _GOLD)); _labels(ch2, "0%;;;", pos=None, size=8.5)
            ch2.x_axis.scaling.orientation = "maxMin"; ch2.y_axis.numFmt = "0%"
            ch2.y_axis.crosses = "max"
            _place(v3.ws, ch2, f"L6:T{ch_bottom}")
            # tabel ringkas di bawah chart (angka yg sama dgn PPT) -- selebar halaman (B..T)
            t0 = ch_bottom + 2
            v3.section(t0 - 1, "Rincian per Site & Kelompok Unit", "B", "T")
            for rng, h in (("B{0}:E{0}", "Site — Kelompok"), ("F{0}:H{0}", "Capaian Biaya"), ("I{0}:L{0}", "Gap (Realisasi − Budget)"),
                           ("M{0}:N{0}", "% Rutin"), ("O{0}:P{0}", "% Non-Rutin"), ("Q{0}:T{0}", "Cap. Downtime")):
                v3.merge_put(rng.format(t0), h, bold=True, color="FFFFFF", fillc="4B5563", align=_CENTER, size=10)
            v3.ws.row_dimensions[t0].height = 22
            for i in range(len(rows3) + 1):
                rr = t0 + 1 + i; src = a3f + i if i < len(rows3) else rt3
                v3.ws.row_dimensions[rr].height = 20
                v3.merge_put(f"B{rr}:E{rr}", f"={P3}B{src}", bold=True, align=_LEFT, size=10)
                g_ = f"{P3}G{src}"; h_ = f"{P3}H{src}"
                v3.merge_put(f"F{rr}:H{rr}", f'=IF({g_}="","N/A",FIXED({g_}*100,0,TRUE)&"%")', bold=True, align=_CENTER, size=10)
                v3.ws.conditional_formatting.add(f"F{rr}:H{rr}", _FRule(formula=[f'AND({g_}<>"",N({g_})>1)'], fill=_fill(_RED_BG), font=_Font(name=_FONT, bold=True, color=_RED)))
                v3.ws.conditional_formatting.add(f"F{rr}:H{rr}", _FRule(formula=[f'AND({g_}<>"",N({g_})<=1)'], fill=_fill(_GREEN_BG), font=_Font(name=_FONT, bold=True, color=_GREEN)))
                if i < len(rows3):
                    v3.merge_put(f"I{rr}:L{rr}", f'=IF({h_}="","tidak ada data",IF({h_}>0,"+","−")&{_rp("ABS(" + h_ + ")")})', align=_RIGHT, size=10)
                else:
                    v3.merge_put(f"I{rr}:L{rr}", f'="Gap total: "&IF({h_}>0,"+","−")&{_rp("ABS(" + h_ + ")")}&IF({h_}>0," (over budget)"," (di bawah budget)")', bold=True, align=_RIGHT, size=10)
                m_ = f"{P3}M{src}"; n_ = f"{P3}N{src}"
                v3.merge_put(f"M{rr}:N{rr}", f'=IF({m_}="","—",FIXED({m_}*100,0,TRUE)&"%")', align=_CENTER, size=10, color=_TEAL, bold=True)
                v3.merge_put(f"O{rr}:P{rr}", f'=IF({n_}="","—",FIXED({n_}*100,0,TRUE)&"%")', align=_CENTER, size=10, color=_GOLD, bold=True)
                if i < len(rows3):
                    q_ = f"{P3}Q{src}"
                    v3.merge_put(f"Q{rr}:T{rr}", f'=IF({q_}="","—",FIXED({q_}*100,0,TRUE)&"%")', bold=True, align=_CENTER, size=10)
                    v3.ws.conditional_formatting.add(f"Q{rr}:T{rr}", _FRule(formula=[f'AND({q_}<>"",N({q_})>1)'], fill=_fill(_RED_BG), font=_Font(name=_FONT, bold=True, color=_RED)))
                    v3.ws.conditional_formatting.add(f"Q{rr}:T{rr}", _FRule(formula=[f'AND({q_}<>"",N({q_})<=1)'], fill=_fill(_GREEN_BG), font=_Font(name=_FONT, bold=True, color=_GREEN)))
            nb = t0 + len(rows3) + 3
            pos = f"{P3}$E${rs}"
            pk = lambda col: f"INDEX({P3}${col}${a3f}:${col}${a3l},{pos})"
            # ---- STRIP SOROTAN (sama dgn PPT): 4 kolom -> jumlah over budget | over terbesar | porsi Non-Rutin | Cap. Downtime
            ws3 = v3.ws
            nO, nK, nTB = f"{P3}$C${rs}", f"{P3}$B${rs}", f"{P3}$D${rs}"
            ada = f"{nO}>0"  # ada kelompok over budget?
            sk = lambda col: f'IFERROR({pk(col)},"")'
            BROWN = "7A5C0D"
            for rr_ in range(nb, nb + 3):
                for cc in range(2, 21):
                    ws3.cell(rr_, cc).fill = _fill(_GOLD_BG)
            ws3.row_dimensions[nb].height = 18; ws3.row_dimensions[nb + 1].height = 32; ws3.row_dimensions[nb + 2].height = 18
            ws3.merge_cells(f"B{nb}:B{nb+2}")
            ws3[f"B{nb}"] = "💡"; ws3[f"B{nb}"].font = _f(20, False, _GOLD); ws3[f"B{nb}"].alignment = _CENTER

            def _cell(rng, val, size, color, bold=False, align=_LEFT, italic=False):
                ws3.merge_cells(rng) if ":" in rng and rng.split(":")[0] != rng.split(":")[1] else None
                c = ws3[rng.split(":")[0]]
                c.value = val; c.font = _f(size, bold, color, italic); c.alignment = align
                return c
            L = _Al(horizontal="left", vertical="center", indent=1)
            # 1) Kelompok unit over budget
            _cell(f"C{nb}:E{nb}", "Kelompok unit over budget", 9, BROWN, align=L)
            _cell(f"C{nb+1}:E{nb+1}", f'={nO}&" dari "&{nK}&" kelompok"', 16, _RED, True, L)
            _cell(f"C{nb+2}:E{nb+2}", f'=IF({nTB}>0,"termasuk "&{nTB}&" kelompok tanpa budget","per site & kelompok unit")', 8.5, _MUTED, False, L, True)
            # 2) Over budget terbesar
            _cell(f"F{nb}:J{nb}", "Over budget terbesar", 9, BROWN, align=L)
            _cell(f"F{nb+1}:J{nb+1}", f'=IF({ada},{sk("B")},"— (tidak ada)")', 16, _NAVY, True, L)
            _cell(f"F{nb+2}:J{nb+2}", (f'=IF({ada},"+"&{_rp(sk("H"))}&"  ·  "&IF({sk("G")}="","tanpa budget","Capaian "&FIXED({sk("G")}*100,0,TRUE)&"%"),'
                                        f'"seluruh kelompok dalam/di bawah budget")'), 9.5, _RED, True, L)
            # 3) Porsi Non-Rutin (+ bar mini: biru = Rutin, emas = Non-Rutin)
            _cell(f"K{nb}:O{nb}", "Porsi pemeliharaan Non-Rutin", 9, BROWN, align=L)
            nr_, r_ = sk("N"), sk("M")
            _cell(f"K{nb+1}", f'=IF(OR(NOT({ada}),{nr_}=""),"—",FIXED({nr_}*100,0,TRUE)&"%")', 18, _GOLD, True, L)
            _cell(f"L{nb+1}:M{nb+1}", f'=IF(OR(NOT({ada}),{r_}=""),"",REPT("█",ROUND({r_}*12,0)))', 12, _TEAL, False, _Al(horizontal="right", vertical="center"))
            _cell(f"N{nb+1}:O{nb+1}", f'=IF(OR(NOT({ada}),{nr_}=""),"",REPT("█",12-ROUND({r_}*12,0)))', 12, _GOLD, False, _Al(horizontal="left", vertical="center"))
            _cell(f"K{nb+2}:O{nb+2}", f'=IF(OR(NOT({ada}),{r_}=""),"tanpa transaksi pemeliharaan","Rutin "&FIXED({r_}*100,0,TRUE)&"%  ·  Non-Rutin "&FIXED({nr_}*100,0,TRUE)&"%")', 8.5, _MUTED, False, L)
            # 4) Capaian Downtime (+ status)
            dq = sk("Q")
            _cell(f"P{nb}:T{nb}", "Capaian Downtime", 9, BROWN, align=L)
            cdt = _cell(f"P{nb+1}:Q{nb+1}", f'=IF(OR(NOT({ada}),{dq}=""),"—",FIXED({dq}*100,0,TRUE)&"%")', 18, _GREEN, True, L)
            ws3.conditional_formatting.add(f"P{nb+1}:Q{nb+1}", _FRule(formula=[f'AND({ada},{dq}<>"",N({dq})>1)'], font=_Font(name=_FONT, size=18, bold=True, color=_RED)))
            _cell(f"R{nb+1}:S{nb+1}", f'=IF(OR(NOT({ada}),{dq}=""),"",IF({dq}>1,"Melebihi target","Dalam target"))', 9, _GREEN, True, _CENTER)
            ws3.conditional_formatting.add(f"R{nb+1}:S{nb+1}", _FRule(formula=[f'AND({ada},{dq}<>"",N({dq})<=1)'], fill=_fill(_GREEN_BG), font=_Font(name=_FONT, bold=True, color=_GREEN)))
            ws3.conditional_formatting.add(f"R{nb+1}:S{nb+1}", _FRule(formula=[f'AND({ada},{dq}<>"",N({dq})>1)'], fill=_fill(_RED_BG), font=_Font(name=_FONT, bold=True, color=_RED)))
            _cell(f"P{nb+2}:T{nb+2}", "≤ 100% = sesuai target downtime", 8.5, _MUTED, False, L)
            # bingkai emas + garis pemisah antar kolom sorotan
            med = _Sd(style="medium", color=_GOLD); sep = _Sd(style="thin", color="E3C98F")
            for rr_ in range(nb, nb + 3):
                for cc in range(2, 21):
                    ws3.cell(rr_, cc).border = _Bd(top=med if rr_ == nb else None, bottom=med if rr_ == nb + 2 else None,
                                                   left=med if cc == 2 else (sep if cc in (6, 11, 16) else None),
                                                   right=med if cc == 20 else None)

    # urutan sheet: per blok (01..04 tampilan+perhitungan), data di belakang
    order = []
    for blok in blocks:
        px = PREFIX[blok]
        for n in ("01 Informasi Kinerja", "01 Perhitungan", "02 Biaya Operasional", "02 Perhitungan",
                  "03 Analisis Biaya", "03 Perhitungan", "04 Analisis Downtime", "04 Perhitungan"):
            order.append(f"{px}-{n}")
    order += ["Data BKMS", "Data Sasaran Mutu", "Data Pemeliharaan", "Data MTTR"]
    wb._sheets = [wb[n] for n in order]
    for ws_ in wb.worksheets:
        ws_.sheet_properties.tabColor = (_NAVY if ws_.title.startswith("Data") else
                                        (_GOLD if ws_.title.endswith("Perhitungan") else "2E8B57"))
    # Excel menghitung ulang semua rumus saat file dibuka (file ini tdk menyimpan hasil hitungan)
    from openpyxl.workbook.properties import CalcProperties as _CalcP
    wb.calculation = _CalcP(fullCalcOnLoad=True)
    buf = _io_dx.BytesIO()
    wb.save(buf)
    try:
        return _fix_label_numfmt(buf.getvalue())
    except Exception:
        return buf.getvalue()


# ---------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------
# Ikon daun putih utk slide pembukaan (dari Slide_Pembukaan.pptx), disimpan inline spy tdk perlu file tambahan.
_COVER_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAQAAAAEACAYAAABccqhmAAAACXBIWXMAAAsTAAALEwEAmpwYAAAQhUlEQVR4nO3de/BfRXnH8RUN"
    "t0BJwiUIESugIFCxsVApiCiXiJWqVKwjDOAgAS13KgnD0AFRsChqKk6LIhFJqxhFIKKlyB2Gi8rFACUCFYoCYgiYCIFAeHee8tCJ"
    "Ib/L9/f9nvPs2f28ZvJvfmd3z57vObvPPk9KIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiIiLSB2AKcBJwEXAtcAHwSWB8P/+v"
    "iGQMeDVwCvACq/Y48KHo6xSRAQNeBcxlZMuBjw/674tIIOA4Ru9ZYKvI6xWRAQG29kndi8sG9fdFJPbV/0rGZpuo6xaRAQAOYuy+"
    "NIhrEJEAwCTgt308AJ7U1qBIRwHfpH+HRLdDRHoE7Mtg3N7r3xaRQMCmwEIGZ8fI9ojIKAGr9bHqP5TZo/37IhIImMHgLQHWjmyX"
    "iIwA2HOYOP9+fXikvy8iQYA3DPi7f2U/iGqbiAwDWBeYT7MslHjCcNchIi0DXgNcSjs+1nb7RGT4OP9zac9/DnUtItIy4EzaZQuM"
    "k9tup4isBPgUMT6x8rWISIuAI4EXgx4A8zTYImUF+vTiGWAt3QAi7U/+U8jDNA2+SLvZfM8mH1/W4Iu0M/nXAS4hLws0+CLtFPC4"
    "jTxtqRtApLnJv4sX6sjVkRp8kWbO888ElpE3bQeKDHjybwT8mG5YZA8r3QEig5n8e/eZwTfCdhp8kf4m/kTgnMDIvn4cpsEXGfvk"
    "3y/zhb6RfEuDL9L7xN8WuJzu+28Nvkhv6brPAZ6nHFN0A4gMP/EnAJ8FnqY8ShYqMswv/heAxZRLBURFVpr42wDnAc9Rvqs0+lI9"
    "YE1f1b+io1t6Y7Ww+sGXqo/pvtMTcy6mXptEj4VIKywbDrCPr+Y/Gj3zMrG3bj8pecLbr/zJwH94Siz5YydEj5PIoMJy7RjuYcA/"
    "AzdWspDXrzm6/eouTjHR/00GNs/w3/bA24DdvIDmAcA/2BYW8G3gOuDXfU+Dev0i+j6UZurNTQX2BY7zX8SLgeuBe/zkWlOVaKVb"
    "LHfBOE3CjgI2BP4GOBW4CLi/sq0s6Z9ShHUF8FrgYGA2cO8ABl9kz+j7WoZPM2WLW2cAt+vXXRowXRMwz2OnVkzigSZGXGQFZ0Tf"
    "7/LSpN8EOMnOaq84OiIN+44mYOxW3F6+Sl/SWXPpjlv0AGh/4q8OHGj7sNGjL9V7XA+AdsNTjwUeqf62k5ysq4dAsxN/nK22KmpN"
    "MrWVHgDNfeP/HfBg9AiLDGNnPQAGP/mneqy6SO7erwfAYBNJfg1YHj2qIqN0iB4Ag5n87wMeHm2vi2Riph4A/U38DYC50aMoMkaf"
    "1wNg7JN/d63uS8fN1gOg94m/BvBFHdCRAszTA6C3yT8FuDl61EQG5EY9AEY/+XdVVlkpzM/1ABjd5D9Kh3akQHfpATByIYlZ0aMk"
    "0pBf6gEw9OQfD1zSVM+LZOAhPQCGjuq7KXp0RBr2mB4Ar5z8k4Bbm+55kQw8qQfAK7Pv3h09KiIteUYPgD/OtW8FNERqsVwPgJcm"
    "/3rAz6JHQ6Rlz1f/APCSWorukxrV/Qng+/yXRo+CSJCnUs2Ar0b1vEgGfpdqBcyI7n2RYI+kijP4KHWX1O7BVBtgC2BRdM+LZOC+"
    "VGGBjtuie10kE3ekmgDnRfe4SEauTbUA9o3ubZHMXJJqAGwKLIzubZHMnJ8qKdN1ZXRPi2ToK6l0XpxTRF7p06mC473a8hNZteNT"
    "yYCLhmi4iMBBqfBoPxEZ2p6pRMA44N5hGi4isG0qEXCsRldkRBNToUk9tfAnMrylqUTAGSM0XETg/lQaYCPgDxpdkRHdkErjZbtF"
    "ZGQXpAJ//Z8ZRcNFBE5JJQFO1aiKjNr+qRTAmlbnbPRtF6neX6ZSAIdVP5wivZmUSmGpjXpsvEjNFqVSAG+P7k2RjrkllUJ5/kR6"
    "dm4qqKinAn9EenNUKgFwcI8Nl/ws8bMb9u8J4IEV/t3jVZtf/nefVbSNvuACvDOVAPhRdE/K/09iO359HXAhMMvjMo4HDgX2A6YB"
    "O9kRVOB19vY2xjGf6P/n/6jvx+RFYEIq5NTfsrH1gfTgSeDnwHf9oNWRwIeAXYAtgbUDy7rP00hWWg4MOKT3tssQfgdcA3wDOAn4"
    "CLAjsH7KGLA6cL1GtScXpxJYQ3prtwBPAz/1iX4csAewceow4E16E6zsDIA/+Rf31u7q/B74CfAZr4pkr+urpQIB34vu7A6ZlroO"
    "eHd0L2bGSp3Pt/1d/zTartTJvir6HOzpPiliAfBM6mZbYTcCpwG724JYqpj3gYxsfiqBf8fWxvbFz/Ette4/xQcIeG/04HTEv6Su"
    "s22nShZ9HvNXepvwG0T3e86AY6IHqyO6XwgE2I1y2Xf86X7AqZpv+H5ZnfvogeuIN6au833qkr7lrXLx0cDm0X3bRVoQHrXfWKXs"
    "1HXAD+j+SqwF3RyuV/u+74WNFRI8auenEvhiWBfd6sE3U6L7sATAWy23ffSgdkj3cwB6/LcdZugKO712sgXhRPddCYDJwF72awa8"
    "ED24HWJzZnLqOuCvyN+zwL/7t2n3v7l6BKwFbAHs7NtzH/GcjTN8gfNsy0kPXOKfQnbM97aVjgE/usIR4aeiB7QAd6QSZB7xdbdv"
    "R2V9gGYA39x2CnB/L8B6FjAHuNrP7muy5unMVAKPa8/Jc8C37M0kFcC2HoHX+9vLdOCfgO970lVlXuquPVIJ/NcmB0950ospHU+n"
    "totPdGvLDZrkxeZzWD2VwG/SSHcBH7fv3NQhwKaexMMSelymrbOqzEmlAB4O6sTLffU5+0U9YJwn87Dgom9rslfvb1MpgKUtb53M"
    "y72Ekq+628Ppc56TTwVS5WV2L4xPJfAYgDYn/g4p34W6t/m22hUtPxSlW8pI/2V8dbrpEN3vWDKNlBlgE1+smwssbLgfpBwHp1IA"
    "UxvsqB8Cb0kZAbYGZgI3dyz6UfKwtKi8EcCuDXSSTa53pUx4zvxTPDpOpB8XppIMOO2TRe19IGUA2B74fOAOh5Rpn1SSAaV9etyr"
    "yrw6uC2b+eu9xRWIDJrd5+NSSewXu8/EG7Miv4k88u5Qz15jC44iTZmVSgN8cIydcWXkyr5v2X1dYbbSor9IpfFgl148ZOGvQdc6"
    "3k8uWhIQkTbdmUrUQy4ASxTxxYgIKGAr4Cs6FiuBDk8l8tXykdwZEbrrp+qseq6y1EikxcUWibGsuSPEPM9sc+XTdhI8Z/8tLQ6w"
    "yHDOTqUa5izANW3m3PPDN0d0ODmplGvbVDJgyUqhjjPa2tP3isTTPb+6SG6uTqUDFnhjb29raw9YA/h74NfBAyxSx7n/oQBXeUDP"
    "Gi0l1jhQr/rSAQuqKCUHbNTC33gV8GFNfOmQQ5ueF1XwVFqWVUekS1Wk14yeO53mh3MsvbfO3UvXnBA9f7q+tfgFz+8v0jWWnn69"
    "6HnUSf6dr5V96bJPR8+jzvG6dT+OHjmRART8mBg9nzrDFko83Zay6EoJToyeU50B7AT8V/SIiQww40+Zh34aiNu3ghk6pSclOSZ6"
    "bmUPeAdwX/RIiQyYJY/Vvv8Iv/oWLqy8e1KiA1r9Je0SYBtPCiJSopu6UKA2hB/ceTp6hEQaYlGqO0bPs+wAGwCXNtXrIpmYHT3X"
    "sgPspgQdUoElViA2er5lw4/sfsoLfoiU7oToOZfbAR7LwCtSgzuLK/PVZ8lsK+wpUoMXiqzyMxZW5UfltaQyZ0XPuywARyuwRyrz"
    "ILBOqpmf4JsTPRIiAXv+01LNfH/fSmmL1OarqWZeZPNX0aMgEsCOra+dagXs4OedRWrzfNXhvsAeXuFUpEYnpsoP8yyLHgGRINe1"
    "VecyO8BRyskvFfstsGmqkcf0i9RqObBnqpGX9xap2cxUI0/RLVKzeVVm+AFOj+55kWD3AxNSbYB/jO55kWC/B7ZLtbF85tE9LxJs"
    "mcW7pNoAR0T3vEgGDk+1AT6qfX4Rzki1sWONivAT4UJgtVQTS2fkGU1FanYFsEaqCbClhziK1Oz66o73ApOABdE9L5JBRt+JqSaW"
    "whj4SXTPiwT7JTA51Qb41+ieFwl2b5Wn+4DjydtT0RcgxZtf6y//7l7IIFezgNcr3Zg06DZLZptqA2yW8cR6fsXoK+DdmT+opJt+"
    "BqyfKs3db43P9dDFXqu45hOjL0yKciXwJ6lGwDfI06PA9sNUF54bfYFShDnA6qnien05egh40yjeXG6IvlDptFnVhfe+DHgd8AT5"
    "eQB4wyjbsL5v2Yj0wtaQPplqZemLPcQxN3f0ugUDbKGQZelxK/l9qWaZZvW5c6xbMLZWACyMboBkbwGwTaqZl+5almE9tY37bNdb"
    "M/2kkTxcCqyXamb1yj3GOSf2Df/aAbVvKrAoukGSXanuz1W72Lci4ALycl+/v/yraONOegiIe6Taoh0rA95LXizXwBsbauu2wMPR"
    "DZRQlw/6x6WzLKEB8KvMIvz+vOE227kBbRHWZylwdJUFO4YCnEVeA/SOltq9IXBrdIOl1Z2k7dq4tzoDeEtGq/62ILN/y+23iMHz"
    "oxsujVrmC3115e0bia18AjdldPN9NrAv7LVQpwjLc2P1e/vD3PRHko8fWQRicH+8B3gyuiNkIJ726tSh91S2gE18sS0HvwDWTflk"
    "O9a6QHe96Cf4pkTfS1kDziUPFqK7RcoI8Bovb65Pgm75KbBz9P2TPWBrz6STw+LMu1Km7NoUL9AJvwGmK5pvlICLycMnUjdqIJyn"
    "2odZsrfHmcD46PukM4C3Z3IzX5Q6xGITgHuiO03+zxP+iVb34Z2xyCRLjoXhTkod4zEDpwLPRXdgpewg18nV5ufrF/D+6BH0hbXd"
    "UofZGQXPOZjDm1QN7vct63Wix77TgFuiRxI4LZWVO+Hq6A4tmGWjPtB2ZaLHuvPsVzd6ND3qsLjBBPbxdGXSv8W+RT01elyLAswL"
    "vjv/AGyeCuWpyC2S8Krgfu4i+5S6BjhIK/oNAN6cwffqsakS/mlgawTLg/s8d5Z96rTcAsGKA3w9eKBvrTEm2yrIejy6LWLJS+72"
    "k3m7RI9PFeyVys/YR0b7rbKCT2WnLnf3GPXIsYiw1D+LZjSV4UmGAXyg1iO+GWdfskXDc4DHgsemCct99d6q6uyXyyGvagFfC07q"
    "uVZ0H+TKDx3ZeYMvAXdlsE4zFo/5ArPVktgbmBjdr5LP3v8HV7wWGZ5NHuCv7a0JuBZ4hrxe5W2r87u+cGd1IzfTmGYuMNnnNdFt"
    "7zpgnGWzsQepH3qZ7bEUixo6WDPfs+V+EzgdOAKYBvypTtp1FLCEmO9ABXI0O65reQHXqR5/cABwjC+22b8TfbX95X+fAY4DPubr"
    "QrsCf+Y7FWs2ea0SyM9Kt+38yDaLiANuDjjso+0ekRwA/9byA2BOdJtFxAEfbXHy2zaWCi+I5MKyprSYwGJudHtFZCW+rdPGt79+"
    "/UVy44Uwn234AXBudDtFZAgevdUUC0xRIQaRzE+k/bCByW/1BfaIbp+IjACYANw+4Ii/6SP9XRHJhGVWBb4/oNxtOuwj0tH8dcd6"
    "gYWxsEy4b45uh4j0/0lgR08fGeU2nx1RfU8/f1NE8nwj2MGrrtiR08u8gtD3gC/7CbINo69TRERERERERERERERERERERERERERE"
    "RERERERERCQV5X8BgfPbmxKuxd8AAAAASUVORK5CYII="
)

LOGO_PATH = Path(__file__).parent / "logo.png"

def get_logo_base64() -> str:
    if LOGO_PATH.exists():
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

logo_b64 = get_logo_base64()
logo_html = f'<img class="header-logo" src="data:image/png;base64,{logo_b64}">' if logo_b64 else ""

st.markdown(f"""
<div class="header-banner">
    {logo_html}
    <h1>📊 Dashboard Operational Review</h1>
    <p>PT BUANA KARYA MANDIRI SEJAHTERA (BKMS) &nbsp;•&nbsp; Target vs Realisasi</p>
</div>
""", unsafe_allow_html=True)

if df.empty:
    st.warning("Tidak ada data untuk kombinasi filter yang dipilih. Silakan ubah filter di sidebar.")
    st.stop()

st.caption(f"Site: {', '.join(sel_site) if len(sel_site)<=4 else f'{len(sel_site)} site'} • Bulan: {', '.join(sel_month)}")

# ---------------------------------------------------------------
# HITUNG METRIK UTAMA (dipakai di beberapa bagian + PPTX)
# ---------------------------------------------------------------
tot_pendapatan_r = df["pendapatan_realisasi"].sum()
tot_pendapatan_b = df["pendapatan_budget"].sum()
tot_prestasi_r = df["prestasi_realisasi"].sum()
tot_prestasi_b = df["prestasi_budget"].sum()
tot_biaya_r = df["total_biaya_realisasi"].sum()
tot_biaya_b = df["total_biaya_budget"].sum()
tot_biaya_langsung_r = df["biaya_langsung_realisasi"].sum()
tot_biaya_langsung_b = df["biaya_langsung_budget"].sum()
tot_biaya_tdklangsung_r = df["biaya_tidak_langsung_realisasi"].sum()
tot_biaya_tdklangsung_b = df["biaya_tidak_langsung_budget"].sum()

ach_pendapatan = achievement(tot_pendapatan_r, tot_pendapatan_b)
ach_prestasi = achievement(tot_prestasi_r, tot_prestasi_b)
ach_biaya = achievement(tot_biaya_r, tot_biaya_b)
ach_biaya_langsung = achievement(tot_biaya_langsung_r, tot_biaya_langsung_b)
ach_biaya_tdklangsung = achievement(tot_biaya_tdklangsung_r, tot_biaya_tdklangsung_b)

if "bulan_no" in df.columns and not df.empty:
    _bulan_terakhir_no_global = df["bulan_no"].max()
    df_bulan_terakhir_global = df[df["bulan_no"] == _bulan_terakhir_no_global]
else:
    df_bulan_terakhir_global = df

target_populasi = df_bulan_terakhir_global.loc[df_bulan_terakhir_global["pendapatan_budget"] > 0, "nama_unit"].nunique()
realisasi_populasi = df_bulan_terakhir_global.loc[df_bulan_terakhir_global["pendapatan_realisasi"] > 0, "nama_unit"].nunique()
pct_populasi = (realisasi_populasi / target_populasi * 100) if target_populasi else None

# ---------------------------------------------------------------
# POWERPOINT EXPORT — didesain mengikuti gaya "Tinjauan Manajemen" (RTM):
# background terang, header bar navy, kartu KPI ikon+pill status, tabel
# dengan indikator warna, dan kotak analisis.
# ---------------------------------------------------------------
def build_pptx(data, maint_data, sparepart_data, site_list, month_list, kat_list, sasaran_mutu_data=None, mttr_data=None) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION, XL_MARKER_STYLE
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.dml import MSO_LINE_DASH_STYLE
    import io as _io

    # Khusus site Mining (TANJUNG, BUHUT, BUHUT LHL, AMPAH): gabungkan kategori TR ke AB (dianggap AB dulu utk
    # sementara) -- tidak dipisah AB/TR di seluruh chart PPTX utk site2 ini.
    MINING_SITES_MERGE = ["TANJUNG", "BUHUT", "BUHUT LHL", "AMPAH"]
    data = data.copy()
    data.loc[data["lokasi"].isin(MINING_SITES_MERGE), "kategori"] = "AB"
    if mttr_data is None:
        mttr_data = pd.DataFrame()
    # Aturan penggabungan yg SAMA wajib diterapkan jg ke data Pemeliharaan, Sparepart & MTTR -- kalau tidak, transaksi
    # unit TR di site Mining (mis. truk tangki TANJUNG 261-018/262-002) masih berkategori "TR" & TERBUANG saat
    # difilter kategori blok Mining (yg isinya cuma "AB"), shg chart Rutin/Non-Rutin menampilkan "tidak ada transaksi".
    def _gabung_kategori_mining(df_):
        if df_ is None or df_.empty or "lokasi" not in df_.columns or "kategori" not in df_.columns:
            return df_
        df_ = df_.copy()
        df_.loc[df_["lokasi"].isin(MINING_SITES_MERGE), "kategori"] = "AB"
        return df_
    maint_data = _gabung_kategori_mining(maint_data)
    sparepart_data = _gabung_kategori_mining(sparepart_data)
    mttr_data = _gabung_kategori_mining(mttr_data)
    if sasaran_mutu_data is not None and not sasaran_mutu_data.empty:
        sasaran_mutu_data = sasaran_mutu_data.copy()
        sasaran_mutu_data.loc[sasaran_mutu_data["lokasi"].isin(MINING_SITES_MERGE), "kategori"] = "AB"
        sasaran_mutu_data.loc[sasaran_mutu_data["lokasi"].isin(MINING_SITES_MERGE), "Jenis_Sarmut"] = "Sarmut Kelompok Alat Berat"
        # Baris kosong (NaN) pada downtime_pct dianggap 0% (tidak pernah downtime), bukan diabaikan dari rata-rata --
        # supaya unit yg sebagian besar datanya belum terisi tidak jadi timpang krn cuma 1-2 baris yg kebetulan terisi
        if "downtime_pct" in sasaran_mutu_data.columns:
            sasaran_mutu_data["downtime_pct"] = sasaran_mutu_data["downtime_pct"].fillna(0)

    # Singkatan nama site dipakai konsisten di semua chart yg padat kategori
    SITE_ABBR = {"SUNGAI DANAU": "S.DANAU", "BUHUT LHL": "B.LHL", "TANJUNG": "TANJUNG",
                 "BUHUT": "BUHUT", "KUMAI": "KUMAI", "AMPAH": "AMPAH"}

    # Korelasi Jenis Unit -> Jenis Sarmut (mis. Arm Roll -> Dump Truck)
    JENIS_UNIT_TO_SARMUT = {
        "DT": "Dump Truck", "DT FM 260 JD": "Dump Truck", "DT Hino": "Dump Truck",
        "DT Howo": "Dump Truck", "Arm Roll": "Dump Truck", "Trailler": "Dump Truck",
        "Isuzu Elf": "Dump Truck",
        "Crawler": "Crawler",
        "Excavator": "Excavator", "Excavator All in": "Excavator", "Excavator Braaker 20 Ton": "Excavator",
        "Excavator Breaker 30 Ton": "Excavator", "Excavator Bucket": "Excavator",
        "Excavator Long arm": "Excavator", "Excavator Mini": "Excavator", "Excavator ZX-130": "Excavator",
        "FT": "FT",
        "Bulldozer": "Unit Support", "Compactor": "Unit Support", "Grader": "Unit Support",
        "TLB": "Unit Support", "Backhoe Loader": "Unit Support", "Wheel Loader": "Unit Support",
        "Pompa Air": "Unit Support", "Fuel Tank": "Unit Support",
        "Truk Tangki": "Tangki CPO", "Tangki Air": "Tangki CPO",
    }

    def map_jenis_sarmut(jenis_unit):
        return JENIS_UNIT_TO_SARMUT.get(jenis_unit, "Alat Berat")

    # Deteksi divisi (Mining/Plantation) berdasarkan site yang difilter
    MINING_SITES_PPTX = {"TANJUNG", "BUHUT", "BUHUT LHL", "AMPAH"}
    PLANTATION_SITES_PPTX = {"SUNGAI DANAU", "KUMAI"}
    site_set = set(site_list) if site_list else set()
    if site_set and site_set.issubset(MINING_SITES_PPTX):
        divisi_label = " · MINING"
    elif site_set and site_set.issubset(PLANTATION_SITES_PPTX):
        divisi_label = " · PLANTATION"
    else:
        divisi_label = ""

    # --- Palet warna (mengikuti gaya laporan RTM: terang, header navy) ---
    NAVY = RGBColor(0x1B, 0x25, 0x4B)
    NAVY_DARK = RGBColor(0x12, 0x18, 0x35)
    BG_LIGHT = RGBColor(0xF2, 0xF4, 0xF9)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    TEAL = RGBColor(0x17, 0xA9, 0xC7)
    GREEN = RGBColor(0x21, 0xA1, 0x66)
    GREEN_BG = RGBColor(0xDF, 0xF5, 0xE9)
    RED = RGBColor(0xE0, 0x4A, 0x3D)
    RED_BG = RGBColor(0xFC, 0xE4, 0xE1)
    GOLD = RGBColor(0xC9, 0x8A, 0x1E)
    GOLD_BG = RGBColor(0xFB, 0xEE, 0xD8)
    TEXT_DARK = RGBColor(0x21, 0x29, 0x37)
    TEXT_MUTED = RGBColor(0x71, 0x78, 0x86)
    BORDER = RGBColor(0xE1, 0xE4, 0xEC)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def add_bg(slide, color):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid(); bg.fill.fore_color.rgb = color
        bg.line.fill.background(); bg.shadow.inherit = False
        slide.shapes._spTree.remove(bg._element)
        slide.shapes._spTree.insert(2, bg._element)
        return bg

    def add_content_slide(title, subtitle_right=""):
        s = prs.slides.add_slide(blank)
        add_bg(s, BG_LIGHT)
        header = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.95))
        header.fill.solid(); header.fill.fore_color.rgb = NAVY
        header.line.fill.background(); header.shadow.inherit = False
        tb = s.shapes.add_textbox(Inches(0.5), Inches(0.18), Inches(9), Inches(0.6))
        p = tb.text_frame.paragraphs[0]
        r = p.add_run(); r.text = title
        r.font.size = Pt(20); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Calibri"
        if subtitle_right:
            # Kotak dilebarkan ke kiri (mulai 8.4 in; judul terpanjang di kiri selesai sktr 7.9 in) spy subjudul
            # panjang spt "Analisis Downtime · 04 · PLANTATION · TRANSPORTASI" tetap 1 baris (tdk ter-wrap).
            tb2 = s.shapes.add_textbox(Inches(8.4), Inches(0.28), Inches(4.5), Inches(0.4))
            tb2.text_frame.word_wrap = True
            p2 = tb2.text_frame.paragraphs[0]
            p2.alignment = PP_ALIGN.RIGHT
            r2 = p2.add_run(); r2.text = subtitle_right
            r2.font.size = Pt(11); r2.font.color.rgb = RGBColor(0xC9, 0xCF, 0xE0); r2.font.name = "Calibri"
        return s

    def add_textbox(slide, left, top, width, height, text, size=14, bold=False,
                     color=TEXT_DARK, align=PP_ALIGN.LEFT, italic=False):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        r = p.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic
        r.font.color.rgb = color; r.font.name = "Calibri"
        return tb

    def pill_colors(is_good):
        return (GREEN_BG, GREEN) if is_good else (RED_BG, RED)

    def add_soft_shadow(shape, blur=90000, dist=22000, alpha=22000):
        """Tambahkan efek bayangan lembut (drop shadow) custom via manipulasi XML,
        karena python-pptx tidak menyediakan API tingkat tinggi untuk ini."""
        from pptx.oxml.ns import qn as _qn_shadow
        spPr = shape._element.spPr
        existing = spPr.find(_qn_shadow('a:effectLst'))
        if existing is not None:
            spPr.remove(existing)
        effectLst = spPr.makeelement(_qn_shadow('a:effectLst'), {})
        outerShdw = spPr.makeelement(_qn_shadow('a:outerShdw'), {
            'blurRad': str(blur), 'dist': str(dist), 'dir': '5400000', 'rotWithShape': '0'
        })
        srgbClr = spPr.makeelement(_qn_shadow('a:srgbClr'), {'val': '1A2744'})
        alpha_el = spPr.makeelement(_qn_shadow('a:alpha'), {'val': str(alpha)})
        srgbClr.append(alpha_el)
        outerShdw.append(srgbClr)
        effectLst.append(outerShdw)
        spPr.append(effectLst)

    def add_kpi_card(slide, left, top, width, height, icon_txt, icon_color, accent_color,
                      label, value, sub_text, pill_text, pill_good):
        # accent strip (top border)
        strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.07))
        strip.fill.solid(); strip.fill.fore_color.rgb = accent_color
        strip.line.fill.background(); strip.shadow.inherit = False
        # card body
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top + 0.07), Inches(width), Inches(height - 0.07))
        card.adjustments[0] = 0.045
        card.fill.solid(); card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = BORDER; card.line.width = Pt(0.75)
        card.shadow.inherit = False
        add_soft_shadow(card)
        # icon circle (ukuran diperbesar sedikit agar lebih menonjol; sedikit lebih kecil kalau kartu sempit)
        narrow_pre = width < 2.6
        icon_size = 0.56 if narrow_pre else 0.68
        icon_left = left + 0.2 if narrow_pre else left + 0.25
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(icon_left), Inches(top + 0.25), Inches(icon_size), Inches(icon_size))
        circ.fill.solid(); circ.fill.fore_color.rgb = icon_color
        circ.line.fill.background(); circ.shadow.inherit = False
        ic_tf = circ.text_frame; ic_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ic_tf.margin_left = 0; ic_tf.margin_right = 0; ic_tf.margin_top = 0; ic_tf.margin_bottom = 0
        icp = ic_tf.paragraphs[0]; icp.alignment = PP_ALIGN.CENTER
        icr = icp.add_run(); icr.text = icon_txt
        icr.font.size = Pt(19 if narrow_pre else 24); icr.font.bold = True; icr.font.color.rgb = WHITE; icr.font.name = EMOJI_FONT
        # Skala ukuran font & posisi menyesuaikan lebar kartu (supaya tetap muat kalau kartu dibuat sempit, mis. 5 kartu sejajar)
        narrow = narrow_pre
        label_size = 11 if narrow else 11.5  # kartu sempit (slide KPI) diperbesar dari 9.5 pt spy jelas saat presentasi
        has_sub = bool(sub_text)
        # Kalau tidak ada sub-teks, angka utama dibuat lebih besar & diposisikan di tengah ruang kosong yg tersisa
        value_size = (25 if narrow else 23) if has_sub else (28 if narrow else 30)
        sub_size = 10.5 if narrow else 10
        pill_size = 10.5 if narrow else 10.5
        label_h = 0.55 if narrow else 0.4
        # label
        # Kartu sempit: kotak label digeser sedikit ke kiri (masih di kanan ikon) & diperlebar, supaya label
        # 2 kata spt "Capaian Availability" muat 1 baris (tidak ter-wrap). Label panjang (mis. "Biaya Langsung /
        # Prestasi") tetap boleh 2 baris spt sebelumnya.
        label_x_off = 0.88 if narrow else 1.0
        label_w_cut = 0.95 if narrow else 1.15
        _lbl_tb = add_textbox(slide, left + label_x_off, top + 0.24, width - label_w_cut, label_h, label, size=label_size, bold=True, color=TEXT_MUTED)
        if narrow:
            # tanpa margin kiri/kanan spy label 2 kata (mis. "Capaian Availability") tetap 1 baris di font lebih besar
            _lbl_tb.text_frame.margin_left = 0; _lbl_tb.text_frame.margin_right = 0
        # value (posisi proporsional thd tinggi kartu, agar tidak tumpang tindih di kartu pendek)
        if has_sub:
            value_top = top + (0.72 if narrow else 0.66)
            add_textbox(slide, left, value_top, width, 0.55, value, size=value_size, bold=True, color=TEXT_DARK, align=PP_ALIGN.CENTER)
            # sub text (target/budget)
            add_textbox(slide, left, value_top + (0.47 if narrow else 0.42), width, 0.3, sub_text, size=sub_size, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
        else:
            # Tidak ada sub-teks: angka ditengahkan vertikal (MIDDLE anchor) di ruang antara label & pill,
            # supaya tidak ada celah kosong besar seperti kalau pakai box TOP-anchored biasa.
            label_bottom_ref = top + 0.6
            pill_top_ref = top + height - 0.5
            val_box = slide.shapes.add_textbox(Inches(left + 0.25), Inches(label_bottom_ref), Inches(width - 0.5), Inches(pill_top_ref - label_bottom_ref))
            val_tf = val_box.text_frame; val_tf.word_wrap = True; val_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            val_p = val_tf.paragraphs[0]; val_p.alignment = PP_ALIGN.CENTER
            val_r = val_p.add_run(); val_r.text = value
            val_r.font.size = Pt(value_size); val_r.font.bold = True; val_r.font.color.rgb = TEXT_DARK; val_r.font.name = "Calibri"
        # pill (selalu menempel ke bawah kartu)
        pbg, ptxt = pill_colors(pill_good)
        # Kartu sempit: pill dilebarkan (sisi 0.15 in) spy teks font besar spt "✓ 99.8% — Under Budget" muat 1 baris
        _pill_pad = 0.15 if narrow else 0.25
        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left + _pill_pad), Inches(top + height - 0.5), Inches(width - 2 * _pill_pad), Inches(0.36))
        pill.adjustments[0] = 0.5
        pill.fill.solid(); pill.fill.fore_color.rgb = pbg
        pill.line.fill.background(); pill.shadow.inherit = False
        ptf = pill.text_frame; ptf.vertical_anchor = MSO_ANCHOR.MIDDLE
        if narrow:
            ptf.margin_left = Inches(0.04); ptf.margin_right = Inches(0.04)
        pp = ptf.paragraphs[0]; pp.alignment = PP_ALIGN.CENTER
        pr = pp.add_run(); pr.text = pill_text
        pr.font.size = Pt(pill_size); pr.font.bold = True; pr.font.color.rgb = ptxt

    def add_kpi_card_wide(slide, left, top, width, height, icon_txt, icon_color, accent_color,
                          label, sublabel, value, detail, pill_text, pill_good, value_color=None):
        """Kartu KPI LEBAR (slide Analisis Downtime) dgn tata letak rapi & font besar utk presentasi:
        [ikon] Label (besar) / sublabel (kecil)  ->  angka utama besar di tengah  ->  rincian per site  ->  pill status."""
        strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.07))
        strip.fill.solid(); strip.fill.fore_color.rgb = accent_color
        strip.line.fill.background(); strip.shadow.inherit = False
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top + 0.07), Inches(width), Inches(height - 0.07))
        card.adjustments[0] = 0.045
        card.fill.solid(); card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = BORDER; card.line.width = Pt(0.75)
        card.shadow.inherit = False
        add_soft_shadow(card)

        def _t(x, y, w, h, text, size, color, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.MIDDLE):
            tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
            tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
            tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
            p = tf.paragraphs[0]; p.alignment = align
            r = p.add_run(); r.text = text
            r.font.size = Pt(size); r.font.bold = bold; r.font.color.rgb = color; r.font.name = "Calibri"
            return tb

        # Baris 1: ikon + label + sublabel
        ic = 0.52
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left + 0.22), Inches(top + 0.14), Inches(ic), Inches(ic))
        circ.fill.solid(); circ.fill.fore_color.rgb = icon_color
        circ.line.fill.background(); circ.shadow.inherit = False
        ctf = circ.text_frame; ctf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ctf.margin_left = 0; ctf.margin_right = 0; ctf.margin_top = 0; ctf.margin_bottom = 0
        cp_ = ctf.paragraphs[0]; cp_.alignment = PP_ALIGN.CENTER
        cr_ = cp_.add_run(); cr_.text = icon_txt
        cr_.font.size = Pt(20); cr_.font.bold = True; cr_.font.color.rgb = WHITE; cr_.font.name = EMOJI_FONT
        lx = left + 0.22 + ic + 0.15
        lw = width - (lx - left) - 0.2
        _t(lx, top + 0.11, lw, 0.3, label, 13, TEXT_DARK, bold=True, anchor=MSO_ANCHOR.BOTTOM)
        if sublabel:
            _t(lx, top + 0.41, lw, 0.2, sublabel, 10, TEXT_MUTED, anchor=MSO_ANCHOR.TOP)

        # Baris 2: angka utama
        # detail boleh 1 baris (str) atau 2 baris (list, mis. Rutin & Non-Rutin per site)
        det_lines = [d for d in (detail if isinstance(detail, (list, tuple)) else [detail]) if d]
        two_lines = len(det_lines) >= 2
        # angka utama dinaikkan (jarak lebih lega ke baris rincian per site di bawahnya)
        _t(left + 0.2, top + (0.58 if two_lines else 0.61), width - 0.4, 0.42, value, 26 if two_lines else 28,
           value_color or TEXT_DARK, bold=True, align=PP_ALIGN.CENTER)
        # Baris 3: rincian per site (font mengecil otomatis kalau teksnya panjang, mis. 4 site Mining)
        if det_lines:
            _longest = max(len(d) for d in det_lines)
            _det_size = max(8.5, min(10.5 if two_lines else 11, (width - 0.4) * 72 / (_longest * 0.5)))
            _y0 = top + (1.06 if two_lines else 1.14)
            _lh = 0.175 if two_lines else 0.22
            for _i, _d in enumerate(det_lines[:2]):
                _t(left + 0.2, _y0 + _i * _lh, width - 0.4, _lh, _d, _det_size, TEXT_MUTED, align=PP_ALIGN.CENTER)

        # Baris 4: pill status
        pbg, ptxt = pill_colors(pill_good)
        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left + 0.35), Inches(top + height - 0.43), Inches(width - 0.7), Inches(0.33))
        pill.adjustments[0] = 0.5
        pill.fill.solid(); pill.fill.fore_color.rgb = pbg
        pill.line.fill.background(); pill.shadow.inherit = False
        ptf = pill.text_frame; ptf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ptf.margin_top = 0; ptf.margin_bottom = 0
        pp = ptf.paragraphs[0]; pp.alignment = PP_ALIGN.CENTER
        pr = pp.add_run(); pr.text = pill_text
        pr.font.size = Pt(11); pr.font.bold = True; pr.font.color.rgb = ptxt; pr.font.name = "Calibri"

    def add_card_panel(slide, left, top, width, height, accent_color=None):
        card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.fill.solid(); card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = BORDER; card.line.width = Pt(0.75)
        card.shadow.inherit = False
        add_soft_shadow(card, blur=70000, dist=18000, alpha=18000)
        if accent_color:
            strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.06))
            strip.fill.solid(); strip.fill.fore_color.rgb = accent_color
            strip.line.fill.background(); strip.shadow.inherit = False
        return card

    def add_note_callout(slide, left, top, width, height, icon, text, text_color=RED, size=11):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]
        r_icon = p.add_run(); r_icon.text = f"{icon} "
        r_icon.font.size = Pt(size); r_icon.font.bold = True; r_icon.font.color.rgb = text_color; r_icon.font.name = EMOJI_FONT
        r = p.add_run(); r.text = text
        r.font.size = Pt(size); r.font.bold = True; r.font.italic = True
        r.font.color.rgb = text_color; r.font.name = "Calibri"
        return tb

    def add_finding_box(slide, left, top, width, height, icon, text, bg_color, border_color, text_color):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        box.adjustments[0] = min(0.12, 0.35 / height)
        box.fill.solid(); box.fill.fore_color.rgb = bg_color
        box.line.color.rgb = border_color; box.line.width = Pt(1.25)
        box.shadow.inherit = False
        # Ikon dalam lingkaran (badge) di kiri, konsisten dgn elemen lain, supaya lebih menonjol
        icon_d = min(0.42, height - 0.16)
        icon_y = top + height / 2 - icon_d / 2
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left + 0.14), Inches(icon_y), Inches(icon_d), Inches(icon_d))
        circ.fill.solid(); circ.fill.fore_color.rgb = border_color
        circ.line.fill.background(); circ.shadow.inherit = False
        ictf = circ.text_frame; ictf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ictf.margin_left = 0; ictf.margin_right = 0
        icp = ictf.paragraphs[0]; icp.alignment = PP_ALIGN.CENTER
        icr = icp.add_run(); icr.text = icon
        icr.font.size = Pt(max(10, icon_d * 22)); icr.font.color.rgb = WHITE; icr.font.name = EMOJI_FONT
        text_left = left + 0.14 + icon_d + 0.14
        tf = slide.shapes.add_textbox(Inches(text_left), Inches(top), Inches(width - (text_left - left) - 0.15), Inches(height)).text_frame
        tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = text
        r.font.size = Pt(10.5); r.font.bold = True; r.font.color.rgb = text_color; r.font.name = "Calibri"
        return box


    def add_status_banner(slide, left, top, width, height, icon, text, bg_color, border_color, text_color):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        box.adjustments[0] = 0.15
        box.fill.solid(); box.fill.fore_color.rgb = bg_color
        box.line.color.rgb = border_color; box.line.width = Pt(1)
        box.shadow.inherit = False
        strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(0.07), Inches(height))
        strip.fill.solid(); strip.fill.fore_color.rgb = border_color
        strip.line.fill.background(); strip.shadow.inherit = False
        tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.2)
        p = tf.paragraphs[0]
        r_icon = p.add_run(); r_icon.text = f"{icon}  "
        r_icon.font.size = Pt(12.5); r_icon.font.bold = True; r_icon.font.color.rgb = text_color; r_icon.font.name = EMOJI_FONT
        r = p.add_run(); r.text = text
        r.font.size = Pt(12.5); r.font.bold = True; r.font.color.rgb = text_color; r.font.name = "Calibri"
        return box

    def add_table(slide, left, top, width, height, headers, rows, status_col=None, col_widths=None,
                  fill_badge=False, font_size=11.5, header_size=12, status_row=None):
        n_rows = len(rows) + 1
        n_cols = len(headers)
        gframe = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top), Inches(width), Inches(height))
        table = gframe.table
        if col_widths:
            total = sum(col_widths)
            for i, w in enumerate(col_widths):
                table.columns[i].width = Inches(width * w / total)
        status_cols = [status_col] if isinstance(status_col, int) else (status_col or [])
        status_rows = [status_row] if isinstance(status_row, int) else (status_row or [])
        for j, h in enumerate(headers):
            cell = table.cell(0, j)
            cell.text = h
            cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
            p = cell.text_frame.paragraphs[0]
            p.runs[0].font.bold = True; p.runs[0].font.size = Pt(header_size); p.runs[0].font.color.rgb = WHITE
            p.runs[0].font.name = "Calibri"
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        for i, row in enumerate(rows, start=1):
            for j, val in enumerate(row):
                cell = table.cell(i, j)
                text = str(val)
                is_status = (j in status_cols) or (i in status_rows and j > 0)
                alt_bg = WHITE if i % 2 == 1 else RGBColor(0xF5, 0xF7, 0xFB)
                is_na = text.startswith("N/A") or text == "-"
                is_good = text.startswith("✓")
                display_text = text.lstrip("✓✗").strip()
                if is_status and fill_badge:
                    if is_na:
                        cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0x9C, 0xA3, 0xAF)
                        txt_color = WHITE
                    elif is_good:
                        cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg
                        txt_color = GREEN
                    else:
                        cell.fill.solid(); cell.fill.fore_color.rgb = RED
                        txt_color = WHITE
                elif is_status:
                    cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg
                    txt_color = RGBColor(0x9C, 0xA3, 0xAF) if is_na else (GREEN if is_good else RED)
                else:
                    cell.fill.solid(); cell.fill.fore_color.rgb = alt_bg
                    txt_color = TEXT_DARK
                cell.text_frame.paragraphs[0].text = ""
                p = cell.text_frame.paragraphs[0]
                r = p.add_run(); r.text = display_text
                r.font.size = Pt(font_size)
                r.font.color.rgb = txt_color
                r.font.bold = is_status
                r.font.name = "Calibri"
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.margin_left = Inches(0.08); cell.margin_right = Inches(0.08)
        return table

    def add_insight_box(slide, left, top, width, height, title, bullets, border_color=TEAL, title_color=None):
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        box.adjustments[0] = 0.03
        box.fill.solid(); box.fill.fore_color.rgb = WHITE
        box.line.color.rgb = border_color; box.line.width = Pt(1.25)
        box.shadow.inherit = False
        left_strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(0.07), Inches(height))
        left_strip.fill.solid(); left_strip.fill.fore_color.rgb = border_color
        left_strip.line.fill.background(); left_strip.shadow.inherit = False
        tb = slide.shapes.add_textbox(Inches(left + 0.3), Inches(top + 0.15), Inches(width - 0.55), Inches(height - 0.3))
        tf = tb.text_frame; tf.word_wrap = True
        p0 = tf.paragraphs[0]
        r0 = p0.add_run(); r0.text = title
        r0.font.size = Pt(13); r0.font.bold = True; r0.font.color.rgb = (title_color or border_color)
        p0.space_after = Pt(8)
        for b in bullets:
            p = tf.add_paragraph()
            r = p.add_run(); r.text = f"•  {b}"
            r.font.size = Pt(11); r.font.color.rgb = TEXT_DARK
            p.space_after = Pt(6)

    def style_chart_light(chart, legend=True, legend_pos=None):
        chart.has_title = False
        chart.has_legend = legend
        if legend:
            chart.legend.position = legend_pos or XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
            chart.legend.font.color.rgb = TEXT_DARK
            chart.legend.font.size = Pt(10.5)
            chart.legend.font.bold = True
            chart.legend.font.name = "Calibri"
        cat_ax = chart.category_axis
        cat_ax.tick_labels.font.color.rgb = TEXT_DARK
        cat_ax.tick_labels.font.size = Pt(10)
        cat_ax.tick_labels.font.bold = True
        cat_ax.tick_labels.font.name = "Calibri"
        cat_ax.format.line.color.rgb = BORDER
        val_ax = chart.value_axis
        val_ax.tick_labels.font.color.rgb = TEXT_DARK
        val_ax.tick_labels.font.size = Pt(9.5)
        val_ax.tick_labels.font.name = "Calibri"
        val_ax.tick_labels.number_format = '#,##0'
        val_ax.tick_labels.number_format_is_linked = False
        val_ax.format.line.color.rgb = BORDER
        val_ax.has_major_gridlines = True
        val_ax.major_gridlines.format.line.color.rgb = BORDER

    def add_panel_header(slide, left, top, width, text, height=0.42):
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        bar.fill.solid(); bar.fill.fore_color.rgb = NAVY
        bar.line.fill.background(); bar.shadow.inherit = False
        # Aksen tipis di bawah header supaya ada pemisah visual halus dgn konten panel
        accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top + height - 0.035), Inches(width), Inches(0.035))
        accent.fill.solid(); accent.fill.fore_color.rgb = GOLD
        accent.line.fill.background(); accent.shadow.inherit = False
        tf = bar.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.15); tf.margin_right = Inches(0.1)
        p = tf.paragraphs[0]
        # Pisahkan ikon (kata pertama) dari teks, ikon dirender sedikit lebih besar supaya lebih menonjol
        parts = text.split(" ", 1)
        if len(parts) == 2 and len(parts[0]) <= 2:
            r_icon = p.add_run(); r_icon.text = parts[0] + "  "
            r_icon.font.size = Pt(15); r_icon.font.bold = True; r_icon.font.color.rgb = WHITE; r_icon.font.name = EMOJI_FONT
            r_txt = p.add_run(); r_txt.text = parts[1]
            r_txt.font.size = Pt(12.5); r_txt.font.bold = True; r_txt.font.color.rgb = WHITE; r_txt.font.name = "Calibri"
        else:
            r = p.add_run(); r.text = text
            r.font.size = Pt(12.5); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Calibri"
        return bar

    def ach_txt_pct(real, budget):
        if budget == 0 or pd.isna(real) or pd.isna(budget):
            return None
        return real / budget * 100

    import datetime as _dt

    period = sorted(month_list, key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99)[-1] if month_list else "-"

    # Label periode per CAWU (caturwulan): Cawu I = Jan-Apr, Cawu II = May-Aug, Cawu III = Sep-Dec.
    # Kalau bulan terakhir = akhir cawu (Apr/Aug/Dec) -> "Cawu II"; kalau di tengah cawu -> "Jun (Cawu II)".
    _CAWU_ROMAWI = ["I", "II", "III"]
    if period in MONTH_ORDER:
        _idx_p = MONTH_ORDER.index(period)
        _cawu_no = _idx_p // 4
        period_cawu = (f"Cawu {_CAWU_ROMAWI[_cawu_no]}" if _idx_p % 4 == 3
                       else f"{period} (Cawu {_CAWU_ROMAWI[_cawu_no]})")
        # Versi tanpa kurung, utk teks yg SUDAH di dalam kurung (mis. "Ringkasan Biaya ... (s/d Jun, Cawu II)")
        period_cawu_inline = (f"Cawu {_CAWU_ROMAWI[_cawu_no]}" if _idx_p % 4 == 3
                              else f"{period}, Cawu {_CAWU_ROMAWI[_cawu_no]}")
    else:
        period_cawu = period
        period_cawu_inline = period
    site_txt = ", ".join(site_list) if len(site_list) <= 6 else f"{len(site_list)} site"
    kat_txt = ", ".join([KATEGORI_LABEL.get(k, k) for k in kat_list])
    _bulan_id = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]
    _now = _dt.datetime.now()
    tgl_laporan = f"{_bulan_id[_now.month-1]} {_now.year}"

    def render_6_slides(data, sasaran_mutu_data, snum1, snum2, snum3, snum4, kat_suffix):
        # Site scope KHUSUS blok ini (bukan site_list global) -- penting saat kedua Divisi dipilih sekaligus,
        # supaya data Maintenance/MTTR/Sparepart tdk "bocor" dari site di blok LAIN (mis. Tanjung ikut kefilter
        # ke blok Plantation gara2 site_list global masih berisi Tanjung juga).
        block_site_list = sorted(data["lokasi"].dropna().unique().tolist())
        r_ = data["pendapatan_realisasi"].sum(); b_ = data["pendapatan_budget"].sum()
        # Prestasi (dipakai utk Capaian Prestasi & rasio Biaya Langsung/Tdk Langsung per Prestasi) HANYA dihitung
        # dari unit berkriteria "Floating Tarif" -- unit "Tarif Tetap" tidak dipengaruhi Prestasi sama sekali
        # (pendapatannya tetap flat, tdk berbasis KM/HM), jadi ikut sertakan akan mendistorsi rasio ini.
        data_floating = data[data["kriteria_unit"] == "Floating Tarif"] if "kriteria_unit" in data.columns else data
        pr_ = data_floating["prestasi_realisasi"].sum(); pb_ = data_floating["prestasi_budget"].sum()
        bl_r_raw = data["biaya_langsung_realisasi"].sum(); bl_b_raw = data["biaya_langsung_budget"].sum()
        btl_r_raw = data["biaya_tidak_langsung_realisasi"].sum(); btl_b_raw = data["biaya_tidak_langsung_budget"].sum()
        bl_r = (bl_r_raw / pr_) if pr_ else None
        bl_b = (bl_b_raw / pb_) if pb_ else None
        btl_r = (btl_r_raw / pr_) if pr_ else None
        btl_b = (btl_b_raw / pb_) if pb_ else None
        ach_r = ach_txt_pct(r_, b_); ach_p = ach_txt_pct(pr_, pb_)
        ach_bl = ach_txt_pct(bl_r, bl_b) if (bl_r is not None and bl_b) else None
        ach_btl = ach_txt_pct(btl_r, btl_b) if (btl_r is not None and btl_b) else None

        if sasaran_mutu_data is None:
            sasaran_mutu_data = pd.DataFrame()

        def klasifikasi_satuan_lokal(row):
            lok, kat = row["lokasi"], row["kategori"]
            if lok == "BUHUT LHL":
                return "Ton"
            if lok in ("SUNGAI DANAU", "KUMAI"):
                if kat == "AB":
                    return "HM"
                if kat == "TR":
                    return "KM"
                return "HM"
            return "HM"

        data["satuan_lokal"] = data.apply(klasifikasi_satuan_lokal, axis=1)

        # Slide KPI (kartu Utilisasi/Availability + chart per Site & Kelompok) KHUSUS unit FLOATING TARIF.
        # Kriteria diambil dari data BKMS (Sasaran Mutu tdk punya kolom kriteria). Slide Downtime TIDAK memakai ini
        # (Downtime tetap semua unit, sesuai metodologi).
        sm_floating_kpi = tandai_kriteria_sasaran_mutu(sasaran_mutu_data, data)
        avg_avail_r, avg_avail_t, ach_avail = capaian_per_kelompok_unit(sm_floating_kpi, "tersedia_hm_km_realisasi", "hm_km_ideal_target", "availability_target")
        avg_util_r, avg_util_t, ach_util = capaian_per_kelompok_unit(sm_floating_kpi, "efektif_hm_km_realisasi", "hm_km_ideal_target", "utilisasi_target")
        prestasi_r_kpi = data_floating["prestasi_realisasi"].sum() if "prestasi_realisasi" in data_floating.columns else None
        prestasi_b_kpi = data_floating["prestasi_budget"].sum() if "prestasi_budget" in data_floating.columns else None
        ach_prestasi_kpi = ach_txt_pct(prestasi_r_kpi, prestasi_b_kpi) if (prestasi_r_kpi is not None and prestasi_b_kpi) else None

        # ================= SLIDE 1: KPI DASHBOARD — PERFORMANCE KESELURUHAN =================
        s = add_content_slide(f"KPI DASHBOARD — Informasi Kinerja s/d {period_cawu}", f"Informasi Kinerja · {snum1}{divisi_label}{kat_suffix}")

        # --- Siapkan data chart: % Capaian Utilisasi & % Capaian Prestasi per Site & KELOMPOK UNIT ---
        # (bukan lagi per Jenis Unit -- supaya unit sejenis dari BEBERAPA SITE bisa dibandingkan berdampingan,
        # mis. "KUMAI -- Dump Truck" bersebelahan dgn "S.DANAU -- Dump Truck". Metodologi Capaian Utilisasi &
        # Availability SAMA PERSIS dgn kartu KPI (formula mentah Efektif/Tersedia / Ideal, exclude Tarif Tetap
        # & unit_sewa), tapi dipecah per Site+Kelompok Unit (bukan digabung semua site jadi 1 angka).
        au_rows = []

        data_k = data.copy()

        if sm_floating_kpi is not None and not sm_floating_kpi.empty and "kelompok_unit" in sm_floating_kpi.columns:
            sm_kpi = sm_floating_kpi.copy()
            if "kriteria_unit" in sm_kpi.columns:
                sm_kpi = sm_kpi[sm_kpi["kriteria_unit"] == "Floating Tarif"]
            sm_kpi = sm_kpi[(sm_kpi["jenis_unit"] != "Tarif Tetap")]
            if "unit_sewa" in sm_kpi.columns:
                sm_kpi = sm_kpi[sm_kpi["unit_sewa"] != True]
            sm_kpi = sm_kpi.dropna(subset=["kelompok_unit"])
            if "efektif_hm_km_realisasi" in sm_kpi.columns:
                sm_kpi["efektif_hm_km_realisasi"] = sm_kpi["efektif_hm_km_realisasi"].fillna(0)
            if "breakdown_hm_km_realisasi" in sm_kpi.columns:
                sm_kpi["breakdown_hm_km_realisasi"] = sm_kpi["breakdown_hm_km_realisasi"].fillna(0)

            def _au_grp(g):
                sum_ideal = g["hm_km_ideal_target"].sum() if "hm_km_ideal_target" in g.columns else None
                util_r_formula = (g["efektif_hm_km_realisasi"].sum() / sum_ideal * 100) if (sum_ideal and "efektif_hm_km_realisasi" in g.columns) else None
                avail_r_formula = (g["tersedia_hm_km_realisasi"].sum() / sum_ideal * 100) if (sum_ideal and "tersedia_hm_km_realisasi" in g.columns) else None
                return pd.Series({
                    "util_r": util_r_formula, "util_t": g["utilisasi_target"].mean(),
                    "avail_r": avail_r_formula, "avail_t": g["availability_target"].mean(),
                })

            au_tbl = sm_kpi.groupby(["lokasi", "kategori", "kelompok_unit"]).apply(_au_grp).reset_index()
            au_tbl["site_short"] = au_tbl["lokasi"].map(SITE_ABBR).fillna(au_tbl["lokasi"])
            # Urutkan berdasarkan KELOMPOK UNIT dulu, baru SITE -- spy site yg sama kelompoknya berdampingan
            au_tbl = au_tbl.sort_values(["kelompok_unit", "lokasi"])

            prestasi_unit = data_k[(data_k["kriteria_unit"] != "Tarif Tetap")].groupby(["lokasi", "kategori", "kelompok_unit"], as_index=False).agg(
                prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum")) if "kelompok_unit" in data_k.columns else pd.DataFrame()
            def _safe_cap(r, col_r="prestasi_r", col_b="prestasi_b"):
                real_v = r[col_r]; budget_v = r[col_b]
                if pd.isna(real_v) or pd.isna(budget_v) or budget_v == 0:
                    return None
                result = real_v / budget_v * 100
                return result if pd.notna(result) and not (result == float("inf") or result == float("-inf")) else None
            if not prestasi_unit.empty:
                prestasi_unit["cap"] = prestasi_unit.apply(_safe_cap, axis=1)
                prestasi_lookup_unit = {(r["lokasi"], r["kategori"], r["kelompok_unit"]): r["cap"] for _, r in prestasi_unit.iterrows()}
            else:
                prestasi_lookup_unit = {}

            for _, r in au_tbl.iterrows():
                util_cap = _safe_cap(r, "util_r", "util_t")
                avail_cap = _safe_cap(r, "avail_r", "avail_t")
                # TANPA fallback ke angka level site: dulu kalau kelompok ini tdk punya angka prestasi sendiri,
                # yg dipakai adalah capaian SELURUH unit site tsb (termasuk Tarif Tetap) -> menyesatkan.
                prestasi_cap = prestasi_lookup_unit.get((r["lokasi"], r["kategori"], r["kelompok_unit"]))
                au_rows.append({"label": f"{r['site_short']} — {r['kelompok_unit']}", "util_cap": util_cap, "avail_cap": avail_cap,
                                 "prestasi_cap": prestasi_cap, "kriteria_unit": "Floating Tarif", "kelompok_unit": r["kelompok_unit"]})

        au_rows_floating = au_rows  # sudah dikecualikan Tarif Tetap & unit_sewa sejak awal (lihat filter di atas)
        # Urutan SUDAH per Kelompok Unit dari au_tbl.sort_values di atas -- TIDAK diurutkan ulang berdasarkan Gap
        # Pendapatan lagi (beda dgn versi lama), supaya site2 dgn kelompok unit yg sama tetap berdampingan.

        # --- Kartu ringkasan mini (ringkasan cepat keseluruhan, lengkap dgn Budget & Capaian) ---
        mini_w, mini_h, mini_gap, mini_y = 2.32, 1.95, 0.19, 1.05
        add_kpi_card(s, 0.4, mini_y, mini_w, mini_h, "📈", RGBColor(0x2E, 0x6D, 0xB4), GREEN if (ach_prestasi_kpi is not None and ach_prestasi_kpi >= 100) else RED,
                     "Capaian Prestasi", (f"{ach_prestasi_kpi:.1f}%" if ach_prestasi_kpi is not None else "-"),
                     "Target: 100.0%" if prestasi_r_kpi is not None else "Data tidak tersedia",
                     (f"✓ {ach_prestasi_kpi:.1f}% — Tercapai" if ach_prestasi_kpi is not None and ach_prestasi_kpi >= 100 else (f"✗ {ach_prestasi_kpi:.1f}% — Belum Tercapai" if ach_prestasi_kpi is not None else "Data tidak tersedia")),
                     ach_prestasi_kpi is not None and ach_prestasi_kpi >= 100)
        add_kpi_card(s, 0.4 + (mini_w + mini_gap), mini_y, mini_w, mini_h, "🎯", GOLD, GOLD if (ach_util is not None and ach_util < 100) else GREEN,
                     "Capaian Utilisasi", (f"{avg_util_r:.1f}%" if avg_util_r is not None else "-"),
                     f"Target: {avg_util_t:.1f}%" if avg_util_t is not None else "Target: -",
                     (f"✓ {ach_util:.1f}% dari Target" if ach_util is not None and ach_util >= 100 else (f"✗ {ach_util:.1f}% dari Target" if ach_util is not None else "Data tidak tersedia")),
                     ach_util is not None and ach_util >= 100)
        add_kpi_card(s, 0.4 + 2 * (mini_w + mini_gap), mini_y, mini_w, mini_h, "⚙", TEAL, TEAL if (ach_avail is not None and ach_avail < 100) else GREEN,
                     "Capaian Availability", (f"{avg_avail_r:.1f}%" if avg_avail_r is not None else "-"),
                     f"Target: {avg_avail_t:.1f}%" if avg_avail_t is not None else "Target: -",
                     (f"✓ {ach_avail:.1f}% dari Target" if ach_avail is not None and ach_avail >= 100 else (f"✗ {ach_avail:.1f}% dari Target" if ach_avail is not None else "Data tidak tersedia")),
                     ach_avail is not None and ach_avail >= 100)
        add_kpi_card(s, 0.4 + 3 * (mini_w + mini_gap), mini_y, mini_w, mini_h, "💰", GREEN, GREEN if (ach_bl is not None and ach_bl <= 100) else RED,
                     "Biaya Langsung / Prestasi", (fmt_rp(bl_r) if bl_r is not None else "-"),
                     f"Budget: {fmt_rp(bl_b)}" if bl_b is not None else "Budget: -",
                     (f"✓ {ach_bl:.1f}% — Under Budget" if ach_bl is not None and ach_bl <= 100 else (f"✗ {ach_bl:.1f}% — Over Budget" if ach_bl is not None else "Target = 0")),
                     ach_bl is not None and ach_bl <= 100)
        add_kpi_card(s, 0.4 + 4 * (mini_w + mini_gap), mini_y, mini_w, mini_h, "🧾", RGBColor(0x8E, 0x6B, 0xC9), GREEN if (ach_btl is not None and ach_btl <= 100) else RED,
                     "Biaya T.Langsung / Prestasi", (fmt_rp(btl_r) if btl_r is not None else "-"),
                     f"Budget: {fmt_rp(btl_b)}" if btl_b is not None else "Budget: -",
                     (f"✓ {ach_btl:.1f}% — Under Budget" if ach_btl is not None and ach_btl <= 100 else (f"✗ {ach_btl:.1f}% — Over Budget" if ach_btl is not None else "Target = 0")),
                     ach_btl is not None and ach_btl <= 100)

        def _draw_util_chart(slide, rows, top, height, title):
            # --- Dipisah jadi 2 PANEL TERPISAH (masing2 card & header sendiri): panel kiri utk chart Capaian
            # Prestasi/Utilisasi/Availability, panel kanan (terpisah) khusus utk pie chart Populasi Unit --
            # panel kanan DIPERLEBAR (lebih besar dr panel kiri secara proporsi) & TINGGINYA diperpanjang
            # sampai ke panel_bottom (turun sampai sejajar bawah kotak analisa), krn kotak analisa "Gap
            # Pendapatan" di bawah sekarang dipersempit hanya selebar panel kiri saja.
            bar_panel_w = 9.3  # diperlebar lagi (dari 8.1) -- kembali ke bullet chart yg tdk butuh area persegi lebar spt pie, jd chart Capaian Prestasi bisa lbh lega
            gap_panel = 0.25
            pie_panel_x = 0.45 + bar_panel_w + gap_panel
            pie_panel_w = 12.35 - bar_panel_w - gap_panel
            pie_panel_h = panel_bottom - top  # turun sampai ke batas bawah slide (sejajar bawah kotak analisa)

            add_card_panel(slide, 0.45, top, bar_panel_w, height)
            add_panel_header(slide, 0.45, top, bar_panel_w, title, height=0.34)
            chart_top_x = top + 0.4
            chart_h_x = height - 0.45
            bar_w_x = bar_panel_w
            if rows:
                n_x = len(rows)
                # Label satuan Utilisasi menyesuaikan kategori: Transportasi -> Hari, Alat Berat -> HM.
                # Kalau datanya campuran (AB & TR sekaligus, tidak dipisah), label dikosongkan (netral).
                kat_set_util = set(data["kategori"].dropna().unique())
                if kat_set_util == {"TR"}:
                    util_label_x = "% Capaian Utilisasi (Hari)"
                elif kat_set_util == {"AB"}:
                    util_label_x = "% Capaian Utilisasi (HM)"
                else:
                    util_label_x = "% Capaian Utilisasi"
                cd_x = CategoryChartData()
                cd_x.categories = [r["label"] for r in rows]
                cd_x.add_series("% Capaian Prestasi", tuple(_safe_chart_val(r["prestasi_cap"]) for r in rows))
                cd_x.add_series(util_label_x, tuple(_safe_chart_val(r["util_cap"]) for r in rows))
                cd_x.add_series("% Capaian Availability", tuple(_safe_chart_val(r["avail_cap"]) for r in rows))
                gframe_x = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(chart_top_x), Inches(bar_w_x - 0.15), Inches(chart_h_x), cd_x)
                chart_x = gframe_x.chart
                PRESTASI_COLOR = RGBColor(0x2E, 0x6D, 0xB4)  # disamakan dgn warna ikon kartu KPI "Capaian Prestasi"
                chart_x.series[0].format.fill.solid(); chart_x.series[0].format.fill.fore_color.rgb = PRESTASI_COLOR
                chart_x.series[1].format.fill.solid(); chart_x.series[1].format.fill.fore_color.rgb = GOLD
                chart_x.series[2].format.fill.solid(); chart_x.series[2].format.fill.fore_color.rgb = TEAL
                chart_x.has_title = False
                plot_x = chart_x.plots[0]
                plot_x.gap_width = 60
                plot_x.has_data_labels = True
                dls_x = plot_x.data_labels
                dls_x.number_format = '0"%"'; dls_x.number_format_is_linked = False
                label_font_x = 7.5 if n_x <= 8 else (6.5 if n_x <= 16 else 5.5)
                dls_x.font.size = Pt(label_font_x); dls_x.font.bold = True; dls_x.font.color.rgb = TEXT_DARK; dls_x.font.name = "Calibri"
                dls_x.position = XL_LABEL_POSITION.OUTSIDE_END
                # Label angka Prestasi ditampilkan utk SEMUA nilai (termasuk yg >=100%), diwarnai merah kalau <100%
                for i_pt_x, pt_x in enumerate(chart_x.series[0].points):
                    prestasi_val_x = rows[i_pt_x]["prestasi_cap"]
                    dl_x = pt_x.data_label
                    dl_x.has_text_frame = True
                    if prestasi_val_x is not None and not pd.isna(prestasi_val_x):
                        dl_x.text_frame.text = f"{prestasi_val_x:.0f}%"
                        r0_x = dl_x.text_frame.paragraphs[0].runs[0]
                        r0_x.font.size = Pt(label_font_x); r0_x.font.bold = True; r0_x.font.name = "Calibri"
                        r0_x.font.color.rgb = RED if prestasi_val_x < 100 else TEXT_DARK
                    else:
                        # Tidak ada angka prestasi sendiri (mis. budget prestasi = 0) -> "N/A", bukan "nan%"/"0%"
                        dl_x.text_frame.text = "N/A"
                        r0_x = dl_x.text_frame.paragraphs[0].runs[0]
                        r0_x.font.size = Pt(label_font_x); r0_x.font.bold = True; r0_x.font.name = "Calibri"; r0_x.font.color.rgb = TEXT_MUTED
                style_chart_light(chart_x, legend=True, legend_pos=XL_LEGEND_POSITION.BOTTOM)
                cat_font_x = 8.5 if n_x <= 8 else (7 if n_x <= 14 else (6 if n_x <= 22 else 5.3))
                chart_x.category_axis.tick_labels.font.size = Pt(cat_font_x)
                chart_x.value_axis.tick_labels.font.size = Pt(cat_font_x)
                chart_x.value_axis.tick_labels.number_format = '0"%"'
                chart_x.value_axis.tick_labels.number_format_is_linked = False
            else:
                add_textbox(slide, 0.6, chart_top_x + 0.1, 12.0, 0.4, "Tidak ada data untuk kategori ini.", size=10, italic=True, color=TEXT_MUTED)

            # --- Pie chart: Populasi Unit per Site & Kelompok Unit (bulan terakhir yg dipilih, unit yg ADA
            # realisasinya saja) -- diperbesar, tanpa judul, label nama+angka LANGSUNG di slice (BEST_FIT:
            # otomatis di DALAM slice kalau muat, otomatis pindah ke LUAR slice + garis penunjuk kalau tdk muat).
            pie_x_left = pie_panel_x + 0.12
            pie_w_x = pie_panel_w - 0.24
            last_month_pop = None
            for _m in reversed(MONTH_ORDER):
                if _m in month_list:
                    last_month_pop = _m
                    break
            pop_rows = []
            if last_month_pop and "kelompok_unit" in data.columns:
                data_pop = data[data["bulan"] == last_month_pop].copy()
                # Hanya unit berkriteria "Floating Tarif" yg dihitung (Tarif Tetap dikecualikan) -- konsisten
                # dgn metodologi metrik lain (Utilisasi/Availability/Downtime) di dashboard ini yg jg
                # mengecualikan Tarif Tetap.
                if "kriteria_unit" in data_pop.columns:
                    data_pop = data_pop[data_pop["kriteria_unit"] == "Floating Tarif"]
                has_real_pop = (data_pop["prestasi_realisasi"].fillna(0) > 0) | (data_pop["pendapatan_realisasi"].fillna(0) > 0) | (data_pop["total_biaya_realisasi"].fillna(0) > 0)
                data_pop = data_pop[has_real_pop].dropna(subset=["kelompok_unit"])
                if not data_pop.empty:
                    pop_agg = data_pop.groupby(["lokasi", "kelompok_unit"])["nama_unit"].nunique().reset_index(name="n_unit")
                    pop_agg["site_short_pop"] = pop_agg["lokasi"].map(SITE_ABBR).fillna(pop_agg["lokasi"])
                    pop_agg["label_pop"] = pop_agg["site_short_pop"] + " \u2014 " + pop_agg["kelompok_unit"]
                    # Filter: HANYA kombinasi Site+Kelompok Unit yg JUGA ada di chart "Capaian Prestasi,
                    # Utilisasi & Availability" (au_rows_floating) -- spy daftar kategori antara kedua chart
                    # di Slide 1 ini KONSISTEN/SAMA PERSIS, tdk ada kategori yg muncul di satu chart tp tdk
                    # di chart lainnya.
                    _label_set_au = {r["label"] for r in au_rows_floating}
                    pop_agg = pop_agg[pop_agg["label_pop"].isin(_label_set_au)]
                    pop_agg = pop_agg.sort_values("n_unit", ascending=False)
                    pop_rows = list(zip(pop_agg["label_pop"], pop_agg["n_unit"]))
            # --- Panel TERPISAH khusus Pie Chart Populasi Unit (card & header sendiri, bukan menyatu dgn
            # panel chart Capaian Prestasi/Utilisasi/Availability di kiri) -- tingginya DIPERPANJANG turun
            # sampai panel_bottom (bkn cuma setinggi `height` bar chart), krn kotak analisa di bawah kiri
            # sudah dipersempit shg tdk lagi menghalangi ruang di kanan bawah ini. ---
            add_card_panel(slide, pie_panel_x, top, pie_panel_w, pie_panel_h)
            # Header: ikon + judul + total unit DIGABUNG jadi SATU teks & di-CENTER sbg satu kesatuan --
            # (bukan lagi ikon/judul rata-kiri terpisah dari badge angka di kanan yg bikin jaraknya
            # timpang/tdk simetris spt sebelumnya).
            _total_pop_header = sum(n for _, n in pop_rows) if pop_rows else 0
            _header_bar_pop = add_panel_header(slide, pie_panel_x, top, pie_panel_w, "\U0001F4CA Populasi Unit", height=0.34)  # total unit cukup ditampilkan di tengah donut
            _header_bar_pop.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
            if pop_rows:
                # === DONUT CHART (variasi visual; sebelumnya bullet/bar horizontal spt chart lain di slide ini) ===
                # Donut di atas dgn TOTAL unit di tengah lubang, legenda di bawah: warna \u2022 Site \u2014 Kelompok \u2022
                # jumlah unit \u2022 porsi %. Urutan mengikuti chart di kiri (searah jarum jam dari atas).
                # Urutan SAMA dgn chart Capaian Prestasi/Utilisasi/Availability di kiri (per Kelompok Unit, lalu Site)
                _urut_au = {r["label"]: i for i, r in enumerate(au_rows_floating)}
                pop_rows_final = sorted(pop_rows, key=lambda x: _urut_au.get(x[0], len(_urut_au)))
                total_unit_pop = sum(n for _, n in pop_rows_final)
                n_pop = len(pop_rows_final)
                DONUT_PALETTE = [RGBColor(0x0D, 0x94, 0x88), RGBColor(0x1E, 0x5A, 0xA8), RGBColor(0xD9, 0x8E, 0x1F),
                                 RGBColor(0x17, 0xA2, 0xB8), RGBColor(0x7B, 0x5E, 0xA7), RGBColor(0xE0, 0x6C, 0x4F),
                                 RGBColor(0x5B, 0xA8, 0x4C), RGBColor(0x2C, 0x3E, 0x7A), RGBColor(0xC9, 0x4F, 0x8A),
                                 RGBColor(0x8C, 0x9A, 0x2B), RGBColor(0x46, 0x7A, 0x9E), RGBColor(0xB5, 0x6A, 0x2E),
                                 RGBColor(0x3F, 0xB4, 0x9C), RGBColor(0x9E, 0x9E, 0x3A), RGBColor(0x6D, 0x4C, 0x9F),
                                 RGBColor(0xA0, 0x45, 0x45)]
                pop_colors = [DONUT_PALETTE[i % len(DONUT_PALETTE)] for i in range(n_pop)]

                area_top_pop = chart_top_x
                area_h_pop = pie_panel_h - (chart_top_x - top) - 0.1
                # Donut dibuat SEBESAR MUNGKIN: sisa tinggi panel setelah dikurangi ruang legenda (tinggi baris legenda
                # ideal 0.22 in utk <=9 kelompok, 0.17 in kalau lebih banyak), dibatasi lebar panel.
                _leg_row_ideal = 0.185 if n_pop <= 9 else 0.148
                donut_d = max(1.3, min(pie_w_x + 0.05, area_h_pop - n_pop * _leg_row_ideal - 0.08))
                donut_x = pie_panel_x + (pie_panel_w - donut_d) / 2
                donut_y = area_top_pop - 0.04

                cd_pop = CategoryChartData()
                cd_pop.categories = [lbl for lbl, _ in pop_rows_final]
                cd_pop.add_series("Populasi", tuple(int(v) for _, v in pop_rows_final))
                gf_pop = slide.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(donut_x), Inches(donut_y),
                                                Inches(donut_d), Inches(donut_d), cd_pop)
                ch_pop = gf_pop.chart
                ch_pop.has_legend = False
                ch_pop.has_title = False
                pl_pop = ch_pop.plots[0]
                pl_pop.has_data_labels = False
                pl_pop.vary_by_categories = True
                for i_p, pt_p in enumerate(ch_pop.series[0].points):
                    pt_p.format.fill.solid(); pt_p.format.fill.fore_color.rgb = pop_colors[i_p]
                    pt_p.format.line.color.rgb = WHITE; pt_p.format.line.width = Pt(1.25)
                # Lubang donut lebih besar (default ~50%) spy angka total di tengah lega; mulai dari arah jam 12
                for el in ch_pop._chartSpace.iter():
                    tag = el.tag.split("}")[-1]
                    if tag == "holeSize":
                        el.set("val", "58")
                    elif tag == "firstSliceAng":
                        el.set("val", "0")
                # Area gambar donut dibuat MENGISI PENUH kotak chart (manual layout). Tanpa ini PowerPoint/LibreOffice
                # otomatis memberi margin kosong sktr 0.13 in di tiap sisi -> donut tampak kecil & jauh dari legenda.
                try:
                    from lxml import etree as _et_pop
                    _C = "http://schemas.openxmlformats.org/drawingml/2006/chart"
                    _pa = ch_pop._chartSpace.find(f"{{{_C}}}chart/{{{_C}}}plotArea")
                    if _pa is not None:
                        for _old_l in _pa.findall(f"{{{_C}}}layout"):
                            _pa.remove(_old_l)
                        _lay = _et_pop.SubElement(_pa, f"{{{_C}}}layout")
                        _pa.remove(_lay); _pa.insert(0, _lay)
                        _ml = _et_pop.SubElement(_lay, f"{{{_C}}}manualLayout")
                        for _tag, _val in (("layoutTarget", "inner"), ("xMode", "edge"), ("yMode", "edge"),
                                           ("x", "0.01"), ("y", "0.01"), ("w", "0.98"), ("h", "0.98")):
                            _et_pop.SubElement(_ml, f"{{{_C}}}{_tag}").set("val", _val)
                except Exception:
                    pass  # kalau gagal, donut tetap tampil dgn margin bawaan

                # Angka total di tengah lubang donut
                _c_w = donut_d * 0.6
                _tb_c = slide.shapes.add_textbox(Inches(donut_x + (donut_d - _c_w) / 2), Inches(donut_y + donut_d / 2 - 0.3),
                                                 Inches(_c_w), Inches(0.6))
                _tf_c = _tb_c.text_frame; _tf_c.word_wrap = True; _tf_c.vertical_anchor = MSO_ANCHOR.MIDDLE
                _tf_c.margin_left = 0; _tf_c.margin_right = 0; _tf_c.margin_top = 0; _tf_c.margin_bottom = 0
                _p_c = _tf_c.paragraphs[0]; _p_c.alignment = PP_ALIGN.CENTER
                _r_c = _p_c.add_run(); _r_c.text = str(total_unit_pop)
                _c_size = max(13, min(22, donut_d * 12))  # angka tengah ikut besar-kecilnya donut
                _r_c.font.size = Pt(_c_size); _r_c.font.bold = True; _r_c.font.color.rgb = TEXT_DARK; _r_c.font.name = "Calibri"
                _p_c2 = _tf_c.add_paragraph(); _p_c2.alignment = PP_ALIGN.CENTER
                _r_c2 = _p_c2.add_run(); _r_c2.text = "unit"
                _r_c2.font.size = Pt(8.5 if donut_d >= 1.6 else 7); _r_c2.font.color.rgb = TEXT_MUTED; _r_c2.font.name = "Calibri"

                # Legenda di bawah donut
                leg_top_pop = donut_y + donut_d + 0.06
                leg_h_pop = (top + pie_panel_h - 0.1) - leg_top_pop
                leg_row_h = min(0.26, leg_h_pop / max(n_pop, 1))
                leg_font = 7.5 if leg_row_h >= 0.2 else (7 if leg_row_h >= 0.175 else (6.5 if leg_row_h >= 0.145 else 5.5))
                dot_d = min(0.11, leg_row_h * 0.6)
                pct_w_pop = 0.38; cnt_w_pop = 0.28
                lbl_x_pop = pie_x_left + dot_d + 0.07
                lbl_w_pop = pie_w_x - (dot_d + 0.07) - cnt_w_pop - pct_w_pop
                for i_p, (lbl_p, val_p) in enumerate(pop_rows_final):
                    y_p = leg_top_pop + i_p * leg_row_h
                    _dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(pie_x_left), Inches(y_p + (leg_row_h - dot_d) / 2), Inches(dot_d), Inches(dot_d))
                    _dot.fill.solid(); _dot.fill.fore_color.rgb = pop_colors[i_p]
                    _dot.line.fill.background(); _dot.shadow.inherit = False
                    for _el in _dot._element.iter():
                        if _el.tag.endswith("}effectRef"):
                            _el.set("idx", "0")
                    for _x, _w, _txt, _al, _bold, _col in (
                            (lbl_x_pop, lbl_w_pop, lbl_p, PP_ALIGN.LEFT, False, TEXT_DARK),
                            (lbl_x_pop + lbl_w_pop, cnt_w_pop, str(val_p), PP_ALIGN.RIGHT, True, TEXT_DARK),
                            (lbl_x_pop + lbl_w_pop + cnt_w_pop, pct_w_pop, f"{val_p / total_unit_pop * 100:.0f}%", PP_ALIGN.RIGHT, False, TEXT_MUTED)):
                        _tb = slide.shapes.add_textbox(Inches(_x), Inches(y_p), Inches(_w), Inches(leg_row_h))
                        _tf = _tb.text_frame; _tf.word_wrap = True; _tf.vertical_anchor = MSO_ANCHOR.MIDDLE
                        _tf.margin_left = 0; _tf.margin_right = 0; _tf.margin_top = 0; _tf.margin_bottom = 0
                        _pp = _tf.paragraphs[0]; _pp.alignment = _al
                        _rr = _pp.add_run(); _rr.text = _txt
                        _rr.font.size = Pt(leg_font); _rr.font.bold = _bold; _rr.font.color.rgb = _col; _rr.font.name = "Calibri"
            else:
                add_textbox(slide, pie_x_left, chart_top_x + 0.3, pie_w_x, 0.4, "Data populasi tidak tersedia.", size=8, italic=True, color=TEXT_MUTED, align=PP_ALIGN.CENTER)



        # --- Chart Floating Tarif saja (Tarif Tetap dihilangkan krn tidak ada tracking Utilisasi/Availability yg berarti) ---
        panel_top = mini_y + mini_h + 0.15
        panel_bottom = 7.3
        total_h = panel_bottom - panel_top
        h_floating = total_h * 0.8
        h_finding = total_h - h_floating - 0.15

        _draw_util_chart(s, au_rows_floating, panel_top, h_floating, "🟢 Capaian Prestasi, Utilisasi & Availability — per Site & Kelompok Unit")

        # --- Analisa: unit dgn gap pendapatan (realisasi - budget) paling minus, dikaitkan dgn capaian utilisasinya ---
        # (Kotak ini SEKARANG per KELOMPOK UNIT -- konsisten dgn chart di atas yg jg per Site & Kelompok Unit.)
        note_top_au = panel_top + h_floating + 0.1
        note_h_au = panel_bottom - note_top_au
        gap_unit = data_k.groupby(["lokasi", "kategori", "kelompok_unit"], as_index=False).agg(
            pend_r=("pendapatan_realisasi", "sum"), pend_b=("pendapatan_budget", "sum"),
            prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum")) if "kelompok_unit" in data_k.columns else pd.DataFrame(columns=["lokasi","kategori","kelompok_unit","pend_r","pend_b","prestasi_r","prestasi_b"])
        gap_unit = gap_unit[(gap_unit["pend_r"] > 0) | (gap_unit["pend_b"] > 0)].copy()
        gap_unit["gap"] = gap_unit["pend_r"] - gap_unit["pend_b"]
        gap_unit["site_short"] = gap_unit["lokasi"].map(SITE_ABBR).fillna(gap_unit["lokasi"])
        gap_unit["label"] = gap_unit["site_short"] + " — " + gap_unit["kelompok_unit"]
        def _safe_cap_gap(r):
            real_v = r["prestasi_r"]; budget_v = r["prestasi_b"]
            if pd.isna(real_v) or pd.isna(budget_v) or budget_v == 0:
                return None
            result = real_v / budget_v * 100
            return result if pd.notna(result) and not (result == float("inf") or result == float("-inf")) else None
        gap_unit["prestasi_cap"] = gap_unit.apply(_safe_cap_gap, axis=1)
        gap_unit_neg = gap_unit[gap_unit["gap"] < 0].sort_values("gap")
        # Cari unit dgn gap pendapatan paling minus secara keseluruhan (tanpa filter prioritas prestasi)
        target_row = gap_unit_neg.iloc[0] if not gap_unit_neg.empty else None
        if target_row is not None:
            wg = target_row
            wg_prestasi = wg["prestasi_cap"]
            prestasi_txt = f"{wg_prestasi:.1f}%" if wg_prestasi is not None else "tidak tersedia"
            if wg_prestasi is not None and wg_prestasi < 100:
                penyebab_txt = "Rendahnya capaian prestasi unit ini menjadi salah satu penyebab utama kekurangan pendapatan."
            elif wg_prestasi is not None:
                penyebab_txt = "Meski capaian prestasi sudah tercapai, gap pendapatan tetap terjadi — kemungkinan disebabkan faktor lain (tarif/rate, harga jual, atau komposisi pekerjaan)."
            else:
                penyebab_txt = "Data capaian prestasi unit ini belum tersedia untuk analisis lebih lanjut."
            add_finding_box(s, 0.6, note_top_au, 9.15, note_h_au, "⚠",
                             f"{wg['label']} adalah unit dengan GAP PENDAPATAN MINUS PALING TINGGI ({fmt_rp(wg['gap'])}) — "
                             f"Realisasi {fmt_rp(wg['pend_r'])} vs Budget {fmt_rp(wg['pend_b'])}, dengan Capaian Prestasi {prestasi_txt}. "
                             f"{penyebab_txt}",
                             RED_BG, RED, RED)
        else:
            add_finding_box(s, 0.6, note_top_au, 9.15, note_h_au, "✅",
                             "Tidak ada unit dengan gap pendapatan minus — seluruh unit mencapai/melebihi target pendapatan.",
                             GREEN_BG, GREEN, GREEN)

        # ================= SLIDE 2: BIAYA OPERASIONAL — Ringkasan Biaya vs Fisik =================
        s = add_content_slide(f"BIAYA OPERASIONAL — Budget vs Aktual s/d {period_cawu}", f"Biaya Operasional \u00b7 {snum2}{divisi_label}{kat_suffix}")

        # --- Filter khusus BBM: baris dgn qty_bbm ada TAPI biaya_bbm ATAU prestasi tidak ada -> jangan dihitung ---
        def _bbm_valid_mask(df_):
            # Qty BBM Realisasi HANYA dikecualikan kalau Biaya BBM Realisasi-nya kosong (Qty>0 tapi Biaya=0 = data
            # tidak masuk akal, kemungkinan salah input). Pendapatan/Prestasi kosong TIDAK membuat baris dikecualikan
            # -- unit tetap bisa mengisi BBM meski blm ada pendapatan tercatat di bulan itu.
            bad_r = (df_["qty_bbm_realisasi"] > 0) & (df_["biaya_bbm_realisasi"].fillna(0) == 0)
            bad_b = (df_["qty_bbm_budget"] > 0) & (df_["biaya_bbm_budget"].fillna(0) == 0)
            return ~(bad_r | bad_b)

        data_bbm_ok = data[_bbm_valid_mask(data)]

        tot_biaya_r3 = data["total_biaya_realisasi"].sum()
        tot_biaya_b3 = data["total_biaya_budget"].sum()
        cap_biaya3 = (tot_biaya_r3 / tot_biaya_b3 * 100) if tot_biaya_b3 else None
        prestasi_r3 = data_floating["prestasi_realisasi"].sum()
        prestasi_b3 = data_floating["prestasi_budget"].sum()
        cap_fisik_biaya3 = (prestasi_r3 / prestasi_b3 * 100) if prestasi_b3 else None

        upah_r3 = data["upah_realisasi"].sum()
        upah_b3 = data["upah_budget"].sum()
        cap_upah3 = (upah_r3 / upah_b3 * 100) if upah_b3 else None

        bbm_biaya_r3 = data_bbm_ok["biaya_bbm_realisasi"].sum()
        bbm_biaya_b3 = data_bbm_ok["biaya_bbm_budget"].sum()
        bbm_qty_r3 = data_bbm_ok["qty_bbm_realisasi"].sum()
        bbm_qty_b3 = data_bbm_ok["qty_bbm_budget"].sum()
        # Capaian Biaya BBM = Total Biaya BBM Realisasi dibanding Total Budget Biaya BBM (bukan lagi Rp/Ltr)
        cap_bbm3 = (bbm_biaya_r3 / bbm_biaya_b3 * 100) if bbm_biaya_b3 else None
        # Rp/Ltr tetap dihitung, dipakai sbg info pendukung (bukan basis Capaian lagi)
        harga_bbm_r3 = (bbm_biaya_r3 / bbm_qty_r3) if bbm_qty_r3 else None
        harga_bbm_b3 = (bbm_biaya_b3 / bbm_qty_b3) if bbm_qty_b3 else None
        bbm_prestasi_r3 = data_bbm_ok["prestasi_realisasi"].sum()
        bbm_prestasi_b3 = data_bbm_ok["prestasi_budget"].sum()

        # Capaian Fisik BBM tergantung kategori: Transportasi pakai KM/Ltr (makin tinggi makin baik),
        # Alat Berat pakai Ltr/HM (makin rendah makin baik). Kalau data campuran, tentukan dari kategori dominan.
        kategori_set_bbm3 = set(data_bbm_ok["kategori"].dropna().unique())
        if kategori_set_bbm3 == {"AB"} or (len(kategori_set_bbm3) > 1 and "ALAT BERAT" in kat_suffix):
            is_ab_bbm3 = True
        elif kategori_set_bbm3 == {"TR"} or (len(kategori_set_bbm3) > 1 and "TRANSPORTASI" in kat_suffix):
            is_ab_bbm3 = False
        elif len(kategori_set_bbm3) > 1:
            # Campuran & tidak ada penanda kategori jelas -> pakai kategori dgn kontribusi biaya BBM terbesar
            kat_biaya = data_bbm_ok.groupby("kategori")["biaya_bbm_realisasi"].sum()
            is_ab_bbm3 = (not kat_biaya.empty) and (kat_biaya.idxmax() == "AB")
        else:
            is_ab_bbm3 = False

        if is_ab_bbm3:
            # Alat Berat: Liter/HM — makin rendah makin baik
            rate_r3 = (bbm_qty_r3 / bbm_prestasi_r3) if bbm_prestasi_r3 else None
            rate_b3 = (bbm_qty_b3 / bbm_prestasi_b3) if bbm_prestasi_b3 else None
            cap_fisik_bbm3 = (rate_r3 / rate_b3 * 100) if (rate_r3 is not None and rate_b3) else None
            fisik_bbm_higher_better3 = False
        else:
            # Transportasi: KM/Ltr — makin tinggi makin baik
            rate_r3 = (bbm_prestasi_r3 / bbm_qty_r3) if bbm_qty_r3 else None
            rate_b3 = (bbm_prestasi_b3 / bbm_qty_b3) if bbm_qty_b3 else None
            cap_fisik_bbm3 = (rate_r3 / rate_b3 * 100) if (rate_r3 is not None and rate_b3) else None
            fisik_bbm_higher_better3 = True

        maint_r3 = data["maintenance_realisasi"].sum()
        maint_b3 = data["maintenance_budget"].sum()
        cap_maint3 = (maint_r3 / maint_b3 * 100) if maint_b3 else None

        lain_r3 = data["lainnya_realisasi"].sum()
        lain_b3 = data["lainnya_budget"].sum()
        cap_lain3 = (lain_r3 / lain_b3 * 100) if lain_b3 else None

        def _cap_disp3(v):
            if v is None or pd.isna(v):
                return "-"
            ok = "\u2713" if v <= 100 else "\u2717"
            vv = ">999%" if v > 999 else f"{v:.1f}%"
            return f"{ok} {vv}"

        def _fisik_disp3(v, higher_is_better):
            if v is None or pd.isna(v):
                return "-"
            good = (v >= 100) if higher_is_better else (v <= 100)
            ok = "\u2713" if good else "\u2717"
            vv = ">999%" if v > 999 else f"{v:.1f}%"
            return f"{ok} {vv}"

        # Cap. Fisik utk Biaya Maintenance = Capaian Downtime (Realisasi vs Target Downtime, dari Sasaran Mutu)
        cap_fisik_maint3 = None
        if not sasaran_mutu_data.empty:
            _sm_dt3 = sasaran_mutu_data.copy()
            if "breakdown_hm_km_realisasi" in _sm_dt3.columns:
                _sm_dt3["breakdown_hm_km_realisasi"] = _sm_dt3["breakdown_hm_km_realisasi"].fillna(0)
            _, _, cap_fisik_maint3 = capaian_per_kelompok_unit(_sm_dt3, "breakdown_hm_km_realisasi", "hm_km_ideal_target", "downtime_target")

        # Cap. Fisik utk Biaya BBM = % Capaian Qty BBM (Realisasi Qty vs Budget Qty, murni volume)
        cap_fisik_bbm_qty3 = (bbm_qty_r3 / bbm_qty_b3 * 100) if bbm_qty_b3 else None

        total_row3 = ["Total Biaya", fmt_rp(tot_biaya_b3), fmt_rp(tot_biaya_r3), _cap_disp3(cap_biaya3), _fisik_disp3(cap_fisik_biaya3, True)]
        other_rows3 = [
            (upah_r3, ["Upah Operator", fmt_rp(upah_b3), fmt_rp(upah_r3), _cap_disp3(cap_upah3), "-"]),
            (bbm_biaya_r3, ["Biaya BBM",
                            fmt_rp(bbm_biaya_b3),
                            fmt_rp(bbm_biaya_r3),
                            _cap_disp3(cap_bbm3), _fisik_disp3(cap_fisik_bbm_qty3, False)]),
            (maint_r3, ["Biaya Maintenance", fmt_rp(maint_b3), fmt_rp(maint_r3), _cap_disp3(cap_maint3), _fisik_disp3(cap_fisik_maint3, False)]),
            (lain_r3, ["Biaya Lainnya", fmt_rp(lain_b3), fmt_rp(lain_r3), _cap_disp3(cap_lain3), "-"]),
        ]
        # Urutkan 4 baris selain Total Biaya berdasarkan nilai Aktual (Realisasi) paling tinggi dulu; Total Biaya tetap di atas
        other_rows3_sorted = sorted(other_rows3, key=lambda x: (x[0] is None, -(x[0] if x[0] is not None else 0)))
        ringkasan3_rows = [total_row3] + [r[1] for r in other_rows3_sorted]

        add_textbox(s, 0.4, 0.98, 5.9, 0.3, f"Ringkasan Biaya PT. BKMS (s/d {period_cawu_inline})", size=14, bold=True, color=TEXT_DARK)

        tbl3_top = 1.28
        tbl3_h = 2.15
        add_table(s, 0.4, tbl3_top, 5.9, tbl3_h,
                  ["Metrik", "Budget", "Aktual", "Capaian", "Cap. Fisik"], ringkasan3_rows,
                  status_col=[3, 4], col_widths=[1.7, 1.15, 1.15, 0.95, 0.95], font_size=10, header_size=10,
                  fill_badge=True)

        # --- Catatan otomatis: metrik biaya mana yang paling over budget (DIHAPUS sesuai permintaan) ---
        note_top3 = tbl3_top + tbl3_h + 0.1
        note_h3 = 0.65
        left_col_bottom3 = tbl3_top + tbl3_h

        # ================= PANEL KANAN ATAS: BTL per Site & Kategori =================
        btl_sk3 = data.groupby(["lokasi", "kategori"], as_index=False).agg(
            btl_r=("biaya_tidak_langsung_realisasi", "sum"), btl_b=("biaya_tidak_langsung_budget", "sum"))
        btl_sk3 = btl_sk3[(btl_sk3["btl_r"] > 0) | (btl_sk3["btl_b"] > 0)].copy()
        total_btl_r3 = btl_sk3["btl_r"].sum()
        btl_sk3["site_short"] = btl_sk3["lokasi"].map(SITE_ABBR).fillna(btl_sk3["lokasi"])
        btl_sk3["label"] = btl_sk3["site_short"] + " (" + btl_sk3["kategori"] + ")"
        btl_sk3 = btl_sk3.sort_values("btl_r", ascending=False)

        over_btl_sites3 = []
        btl3_rows = []
        for _, r in btl_sk3.iterrows():
            pct_target = (r["btl_r"] / r["btl_b"] * 100) if r["btl_b"] else None
            pct_share = (r["btl_r"] / total_btl_r3 * 100) if total_btl_r3 else 0
            pct_disp = (f"\u2713 {pct_target:.0f}%" if pct_target is not None and pct_target <= 100
                        else (f"\u2717 {pct_target:.0f}%" if pct_target is not None else "-"))
            btl3_rows.append([r["label"], fmt_rp(r["btl_b"]), fmt_rp(r["btl_r"]), pct_disp, f"{pct_share:.1f}%"])
            if pct_target is not None and pct_target > 100:
                over_btl_sites3.append(r["label"])

        btl_panel_top3 = 0.98
        n_btl3 = max(len(btl3_rows), 1)
        row_h_btl3_min = 0.32 if n_btl3 <= 6 else (0.26 if n_btl3 <= 10 else 0.22)
        tbl_h_btl3_min = row_h_btl3_min * (n_btl3 + 1)
        btl_content_h3 = 0.15 + 0.45 + 0.1 + tbl_h_btl3_min + 0.15
        # Regangkan tinggi card BTL supaya sejajar dgn panel kiri (Ringkasan Biaya), tidak menyisakan
        # celah kosong sebelum panel Maintenance di bawahnya. Konten (banner+tabel) tetap di posisi natural.
        btl_panel_h3 = max(btl_content_h3, left_col_bottom3 - btl_panel_top3)
        add_card_panel(s, 6.85, btl_panel_top3, 6.05, btl_panel_h3)
        if not over_btl_sites3:
            add_status_banner(s, 7.1, btl_panel_top3 + 0.15, 5.55, 0.45, "\u2705", "BTL \u2014 UNDER BUDGET secara keseluruhan", GREEN_BG, GREEN, GREEN)
        else:
            over_txt3 = " & ".join(over_btl_sites3[:3]) + (", dll" if len(over_btl_sites3) > 3 else "")
            add_status_banner(s, 7.1, btl_panel_top3 + 0.15, 5.55, 0.45, "\u26a0\ufe0f", f"BTL \u2014 UNDER BUDGET, kecuali {over_txt3}", RED_BG, RED, RED)
        font_btl3 = 9.5 if n_btl3 <= 6 else (8.5 if n_btl3 <= 10 else 7.5)
        # Tinggi baris tabel mengisi penuh sisa ruang card (bukan cuma ukuran minimum), supaya tidak ada celah kosong
        tbl_h_btl3_avail = btl_panel_h3 - 0.15 - 0.45 - 0.1 - 0.15
        row_h_btl3 = min(0.55, max(row_h_btl3_min, tbl_h_btl3_avail / (n_btl3 + 1)))
        tbl_h_btl3 = row_h_btl3 * (n_btl3 + 1)
        add_table(s, 7.1, btl_panel_top3 + 0.7, 5.55, tbl_h_btl3, ["Site (Kategori)", "Budget", "Aktual", "% Target", "% BTL"], btl3_rows,
                  status_col=3, col_widths=[1.55, 1.15, 1.15, 0.85, 0.85], font_size=font_btl3, header_size=font_btl3)
        right_col_bottom3 = btl_panel_top3 + btl_panel_h3

        # ================= PANEL BAWAH (LEBAR PENUH): % Capaian Konsumsi BBM per Site & Jenis Unit =================
        # Transportasi: KM/Ltr (Realisasi dibagi Budget). Alat Berat: Ltr/HM (Realisasi dibagi Budget).
        # Filter (per baris, realisasi & budget dicek terpisah): qty/biaya/prestasi harus lengkap ketiganya,
        # kalau ada yg tidak lengkap maka qty & prestasi baris tsb tidak ikut dihitung.
        data_bbm_ok3 = data.copy()

        valid_r3 = (data_bbm_ok3["qty_bbm_realisasi"].fillna(0) > 0) & \
                   (data_bbm_ok3["biaya_bbm_realisasi"].fillna(0) > 0) & \
                   (data_bbm_ok3["prestasi_realisasi"].fillna(0) > 0)
        partial_r3 = (~valid_r3) & ((data_bbm_ok3["qty_bbm_realisasi"].fillna(0) > 0) | (data_bbm_ok3["prestasi_realisasi"].fillna(0) > 0))
        data_bbm_ok3.loc[partial_r3, ["qty_bbm_realisasi", "prestasi_realisasi"]] = 0

        valid_b3 = (data_bbm_ok3["qty_bbm_budget"].fillna(0) > 0) & \
                   (data_bbm_ok3["biaya_bbm_budget"].fillna(0) > 0) & \
                   (data_bbm_ok3["prestasi_budget"].fillna(0) > 0)
        partial_b3 = (~valid_b3) & ((data_bbm_ok3["qty_bbm_budget"].fillna(0) > 0) | (data_bbm_ok3["prestasi_budget"].fillna(0) > 0))
        data_bbm_ok3.loc[partial_b3, ["qty_bbm_budget", "prestasi_budget"]] = 0

        maint_su3 = data_bbm_ok3.groupby(["lokasi", "kategori", "kelompok_unit"], as_index=False).agg(
            qty_r=("qty_bbm_realisasi", "sum"), qty_b=("qty_bbm_budget", "sum"),
            prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum")) if "kelompok_unit" in data_bbm_ok3.columns else pd.DataFrame(columns=["lokasi","kategori","kelompok_unit","qty_r","qty_b","prestasi_r","prestasi_b"])
        maint_su3 = maint_su3[(maint_su3["qty_r"] > 0) | (maint_su3["qty_b"] > 0)].copy()
        maint_su3["site_short"] = maint_su3["lokasi"].map(SITE_ABBR).fillna(maint_su3["lokasi"])
        maint_su3["label"] = maint_su3["site_short"] + " \u2014 " + maint_su3["kelompok_unit"]

        # Biaya BBM (Rp) per site & Kelompok Unit -> dipakai utk urutan (Rupiah over tertinggi ditampilkan pertama)
        biaya_bbm_su3 = data.groupby(["lokasi", "kelompok_unit"], as_index=False).agg(
            biaya_r=("biaya_bbm_realisasi", "sum"), biaya_b=("biaya_bbm_budget", "sum")) if "kelompok_unit" in data.columns else pd.DataFrame(columns=["lokasi","kelompok_unit","biaya_r","biaya_b"])
        biaya_bbm_su3["gap_rp"] = biaya_bbm_su3["biaya_r"] - biaya_bbm_su3["biaya_b"]
        gap_rp_lookup3 = {(r["lokasi"], r["kelompok_unit"]): r["gap_rp"] for _, r in biaya_bbm_su3.iterrows()}
        maint_su3["gap"] = maint_su3.apply(lambda r: gap_rp_lookup3.get((r["lokasi"], r["kelompok_unit"]), 0), axis=1)

        # Harga BBM aktual (Rp/Ltr) per site & Kelompok Unit -> ditampilkan di label chart (bukan lagi gap Rupiah)
        harga_bbm_su3 = data_bbm_ok.groupby(["lokasi", "kelompok_unit"], as_index=False).agg(
            biaya_r=("biaya_bbm_realisasi", "sum"), qty_r=("qty_bbm_realisasi", "sum")) if "kelompok_unit" in data_bbm_ok.columns else pd.DataFrame(columns=["lokasi","kelompok_unit","biaya_r","qty_r"])
        harga_bbm_su3["harga_r"] = harga_bbm_su3.apply(lambda r: (r["biaya_r"] / r["qty_r"]) if r["qty_r"] else None, axis=1)
        harga_bbm_lookup3 = {(r["lokasi"], r["kelompok_unit"]): r["harga_r"] for _, r in harga_bbm_su3.iterrows()}
        maint_su3["harga_r"] = maint_su3.apply(lambda r: harga_bbm_lookup3.get((r["lokasi"], r["kelompok_unit"])), axis=1)

        def _bbm_cap3(row):
            if row["kategori"] == "AB":
                # Alat Berat: konsumsi Ltr/HM -- makin besar realisasi (makin boros) -> makin besar % (>100=boros, konsisten)
                rate_r = (row["qty_r"] / row["prestasi_r"]) if row["prestasi_r"] else None
                rate_b = (row["qty_b"] / row["prestasi_b"]) if row["prestasi_b"] else None
                if rate_r is None or not rate_b:
                    return None
                return rate_r / rate_b * 100
            else:
                # Transportasi: konsumsi KM/Ltr -- rumus DIBALIK (target/realisasi, bukan realisasi/target) spy
                # makin IRIT (KM/Ltr realisasi lbh tinggi dr target) justru menghasilkan persentase LEBIH KECIL
                # (<100%), konsisten dgn konvensi "di bawah 100% = bagus/hemat" yg dipakai metrik biaya lainnya
                # di dashboard ini -- supaya tdk terbaca seolah "over" padahal sebenarnya lebih hemat.
                rate_r = (row["prestasi_r"] / row["qty_r"]) if row["qty_r"] else None
                rate_b = (row["prestasi_b"] / row["qty_b"]) if row["qty_b"] else None
                if not rate_r or rate_b is None:
                    return None
                return rate_b / rate_r * 100

        maint_su3["cap"] = maint_su3.apply(_bbm_cap3, axis=1)
        maint_su3 = maint_su3.dropna(subset=["cap"])

        # --- Hitung Cap. Prestasi & Cap. Harga BBM, utk dekomposisi 3 faktor penyebab kenaikan biaya BBM ---
        maint_su3["cap_prestasi"] = maint_su3.apply(
            lambda r: (r["prestasi_r"] / r["prestasi_b"] * 100) if r["prestasi_b"] else None, axis=1)
        harga_bbm_full3 = data_bbm_ok.groupby(["lokasi", "kelompok_unit"], as_index=False).agg(
            biaya_r=("biaya_bbm_realisasi", "sum"), biaya_b=("biaya_bbm_budget", "sum"),
            qty_r=("qty_bbm_realisasi", "sum"), qty_b=("qty_bbm_budget", "sum")) if "kelompok_unit" in data_bbm_ok.columns else pd.DataFrame(columns=["lokasi","kelompok_unit","biaya_r","biaya_b","qty_r","qty_b"])
        harga_bbm_full3["harga_r"] = harga_bbm_full3.apply(lambda r: (r["biaya_r"] / r["qty_r"]) if r["qty_r"] else None, axis=1)
        harga_bbm_full3["harga_b"] = harga_bbm_full3.apply(lambda r: (r["biaya_b"] / r["qty_b"]) if r["qty_b"] else None, axis=1)
        harga_full_lookup3 = {(r["lokasi"], r["kelompok_unit"]): (r["harga_r"], r["harga_b"]) for _, r in harga_bbm_full3.iterrows()}
        maint_su3["harga_r"] = maint_su3.apply(lambda r: harga_full_lookup3.get((r["lokasi"], r["kelompok_unit"]), (None, None))[0], axis=1)
        maint_su3["harga_b"] = maint_su3.apply(lambda r: harga_full_lookup3.get((r["lokasi"], r["kelompok_unit"]), (None, None))[1], axis=1)
        maint_su3["cap_harga"] = maint_su3.apply(
            lambda r: (r["harga_r"] / r["harga_b"] * 100) if (r["harga_r"] is not None and r["harga_b"]) else None, axis=1)

        def _penyebab_dominan3(row):
            devs = []
            if row["cap_prestasi"] is not None:
                devs.append(("Volume Operasi (Prestasi)", row["cap_prestasi"], abs(row["cap_prestasi"] - 100)))
            devs.append(("Konsumsi BBM", row["cap"], abs(row["cap"] - 100)))
            if row["cap_harga"] is not None:
                devs.append(("Harga BBM", row["cap_harga"], abs(row["cap_harga"] - 100)))
            if not devs:
                return "-"
            nama, cap_val, _ = max(devs, key=lambda x: x[2])
            # Rumus "cap" utk Konsumsi BBM (fungsi _bbm_cap3) SUDAH disesuaikan per kategori (TR dibalik jadi
            # target/realisasi, AB tetap realisasi/target) shg >100% SELALU berarti "memperberat/menaikkan
            # biaya" utk KETIGA metrik (Prestasi, Konsumsi, Harga) -- tdk perlu lagi pengecualian arah khusus
            # kategori di sini spt sebelumnya.
            arah = "Naik" if cap_val > 100 else "Turun"
            return f"{nama} {arah}"

        maint_su3["penyebab"] = maint_su3.apply(_penyebab_dominan3, axis=1)
        # Diurutkan berdasarkan KELOMPOK UNIT dulu, baru SITE -- spy site dgn kelompok unit yg sama berdampingan
        # (beda dgn versi lama yg diurutkan by Capaian tertinggi/gap Rupiah)
        maint_su3 = maint_su3.sort_values(["kelompok_unit", "lokasi"])
        n_maint3 = max(len(maint_su3), 1)

        maint_panel_top3 = max(left_col_bottom3, right_col_bottom3) + 0.15
        maint_panel_h3 = 7.3 - maint_panel_top3
        add_card_panel(s, 0.4, maint_panel_top3, 12.5, maint_panel_h3)
        add_panel_header(s, 0.4, maint_panel_top3, 12.5,
                          "\U0001F50D Analisa Penyebab Kenaikan Biaya BBM \u2014 per Site & Kelompok Unit", height=0.36)
        chart_top_m3b = maint_panel_top3 + 0.42
        avail_h_m3b = maint_panel_h3 - 0.42 - 0.15
        if not maint_su3.empty:
            unit_label3 = "KM/Ltr" if set(maint_su3["kategori"].unique()) == {"TR"} else ("Ltr/HM" if set(maint_su3["kategori"].unique()) == {"AB"} else "Rate")
            # Tampilkan SEMUA kombinasi Site+Kelompok Unit (bukan top-N lagi) -- spy perbandingan antar site tetap
            # utuh & tidak ada kelompok yg "terpotong" di salah satu site tapi tidak di site lain.
            top_n3 = 12
            chart_src3 = maint_su3.head(top_n3) if len(maint_su3) > top_n3 else maint_su3

            note_h3b = 0.85
            chart_h_m3b = avail_h_m3b - note_h3b - 0.12

            cd_m3b = CategoryChartData()
            cd_m3b.categories = list(chart_src3["label"])
            cd_m3b.add_series("Cap. Prestasi", tuple(_safe_chart_val(v, 0) for v in chart_src3["cap_prestasi"]))
            cd_m3b.add_series(f"Cap. Konsumsi ({unit_label3})", tuple(_safe_chart_val(v, 0) for v in chart_src3["cap"]))
            cd_m3b.add_series("Capaian Harga BBM (Rp/Ltr)", tuple(_safe_chart_val(v, 0) for v in chart_src3["cap_harga"]))
            gframe_m3b = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(chart_top_m3b), Inches(12.1), Inches(chart_h_m3b), cd_m3b)
            chart_m3b = gframe_m3b.chart
            SERIES_COLORS3 = [RGBColor(0x7B, 0x5C, 0xC9), RGBColor(0xD9, 0x8A, 0x2E), RGBColor(0x3F, 0xA8, 0x6B)]  # Prestasi=ungu terang, Konsumsi=oranye keemasan, Harga=hijau segar
            for si, col in enumerate(SERIES_COLORS3):
                chart_m3b.series[si].format.fill.solid(); chart_m3b.series[si].format.fill.fore_color.rgb = col
            chart_m3b.has_title = False
            plot_m3b = chart_m3b.plots[0]
            plot_m3b.gap_width = 60
            plot_m3b.overlap = -8
            plot_m3b.has_data_labels = True
            dls_m3b = plot_m3b.data_labels
            dls_m3b.number_format = '0"%"'; dls_m3b.number_format_is_linked = False
            # Angka capaian diperbesar utk presentasi (sebelumnya 7.5 pt), menyesuaikan jumlah kelompok (3 batang/kelompok)
            _n_cat3_lbl = len(chart_src3)
            _lbl_font3b = 11 if _n_cat3_lbl <= 6 else (10 if _n_cat3_lbl <= 9 else 9)
            dls_m3b.font.size = Pt(_lbl_font3b); dls_m3b.font.bold = True; dls_m3b.font.color.rgb = TEXT_DARK; dls_m3b.font.name = "Calibri"
            dls_m3b.position = XL_LABEL_POSITION.OUTSIDE_END
            style_chart_light(chart_m3b, legend=True, legend_pos=XL_LEGEND_POSITION.TOP)
            n_cat3b = len(chart_src3)
            cat_font_m3b = 8.5 if n_cat3b <= 6 else 7.5
            chart_m3b.category_axis.tick_labels.font.size = Pt(cat_font_m3b)
            chart_m3b.value_axis.tick_labels.font.size = Pt(cat_font_m3b)
            chart_m3b.value_axis.has_major_gridlines = True

            # --- Insight otomatis: unit #1 (dampak Rupiah OVER BUDGET terbesar) & penyebab dominannya ---
            top1_3 = chart_src3.sort_values("gap", ascending=False).iloc[0]
            gap_sign3 = "over budget" if top1_3["gap"] > 0 else "hemat"
            cap_prestasi_txt3 = f"{top1_3['cap_prestasi']:.0f}%" if top1_3["cap_prestasi"] is not None else "data tidak tersedia"
            cap_harga_txt3 = f"{top1_3['cap_harga']:.0f}%" if top1_3["cap_harga"] is not None else "data tidak tersedia"
            note_top3b = chart_top_m3b + chart_h_m3b + 0.12
            add_finding_box(s, 0.55, note_top3b, 12.2, note_h3b, "\U0001F4A1",
                             f"{top1_3['label']} adalah unit dengan dampak Rupiah biaya BBM terbesar ({fmt_rp(abs(top1_3['gap']))} {gap_sign3}) \u2014 "
                             f"penyebab dominannya: {top1_3['penyebab']} (Cap. Prestasi {cap_prestasi_txt3}, "
                             f"Cap. Konsumsi {top1_3['cap']:.0f}%, Cap. Harga BBM {cap_harga_txt3}).",
                             GOLD_BG, GOLD, RGBColor(0x7A, 0x5C, 0x0D))
        else:
            add_textbox(s, 0.55, chart_top_m3b + 0.1, 12.0, 0.5, "Data Konsumsi BBM belum tersedia.", size=10, italic=True, color=TEXT_MUTED)


        # ================= SLIDE 3: ANALISIS Biaya Maintenance & Maintenance Rutin/Non-Rutin =================
        s = add_content_slide(f"ANALISIS: Biaya Maintenance & Rutin/Non-Rutin \u2014 s/d {period_cawu}", f"Analisis Biaya \u00b7 {snum3}{divisi_label}{kat_suffix}")

        panel_top4 = 1.0
        panel_bottom4 = 7.3
        panel_h4 = panel_bottom4 - panel_top4

        # ================= PANEL KIRI: % Capaian Biaya Maintenance per Site & Kelompok Unit =================
        maint_su4 = data.groupby(["lokasi", "kelompok_unit"], as_index=False).agg(
            maint_r=("maintenance_realisasi", "sum"), maint_b=("maintenance_budget", "sum")) if "kelompok_unit" in data.columns else pd.DataFrame(columns=["lokasi","kelompok_unit","maint_r","maint_b"])
        # Filter diperluas: unit dgn REALISASI maintenance (biaya sungguhan keluar) TETAP ditampilkan meski
        # budget-nya 0 -- sebelumnya filter cuma "maint_b > 0" bikin unit yg ada pengeluaran nyata tp tanpa
        # alokasi budget (mis. S.DANAU -- Pick Up Double Cabin) HILANG dari chart ini, padahal muncul di
        # chart "Rutin vs Non-Rutin" sebelahnya (yg berbasis catatan transaksi, bkn budget) -- inkonsisten.
        maint_su4 = maint_su4[(maint_su4["maint_b"] > 0) | (maint_su4["maint_r"] > 0)].copy()
        maint_su4["site_short"] = maint_su4["lokasi"].map(SITE_ABBR).fillna(maint_su4["lokasi"])
        KELOMPOK_ABBR = {
            "TANGKI SERIES 300": "TANGKI 300", "TANGKI SERIES 500": "TANGKI 500",
            "TRUCK ARM ROLL 4x4": "ARM ROLL 4x4", "TRUCK ARM ROLL": "ARM ROLL",
            "TRUCK - TUS": "TUS", "TRUCK - BAK": "BAK",
            "DUMP TRUCK 4x4": "DT 4x4", "DUMP TRUCK HOWO": "DT HOWO", "DUMP TRUCK": "DT",
            "EXCAVATOR MEDIUM": "EXC MEDIUM", "EXCAVATOR MINI": "EXC MINI",
            "BULLDOZER MEDIUM": "BULLDOZER M", "BULLDOZER MINI": "BULLDOZER m",
            "BACKHOE LOADER": "BACKHOE", "FARM TRACKTOR": "TRACTOR", "WHEEL LOADER": "WHL LOADER",
            "TRUCK - BAK - PICK UP": "PICK UP", "PICK UP DOUBLE CABIN": "PU D.CABIN",
        }
        maint_su4["kelompok_short"] = maint_su4["kelompok_unit"].map(KELOMPOK_ABBR).fillna(maint_su4["kelompok_unit"])
        maint_su4["label"] = maint_su4["site_short"] + " \u2014 " + maint_su4["kelompok_short"]
        # "cap" (persentase capaian) tdk terdefinisi kalau budget=0 (pembagian dgn nol) -- diberi None,
        # bukan crash/infinity; unit spt ini tetap tampil di chart (via gap_rp), cuma teks %-nya "N/A".
        maint_su4["cap"] = maint_su4.apply(lambda r: (r["maint_r"] / r["maint_b"] * 100) if r["maint_b"] else None, axis=1)
        maint_su4["gap_rp"] = maint_su4["maint_r"] - maint_su4["maint_b"]
        # Diurutkan berdasarkan KELOMPOK UNIT dulu, baru SITE -- spy site dgn kelompok unit yg sama berdampingan
        maint_su4 = maint_su4.sort_values(["kelompok_unit", "lokasi"])
        maint_su4_full = maint_su4.copy()  # simpan versi LENGKAP (semua unit) utk analisa insight di bawah
        n_maint4_total = len(maint_su4)
        n_maint4 = max(len(maint_su4), 1)

        chart_top_r4 = panel_top4 + 0.45
        note_h4 = 0.95
        chart_h_r4 = panel_h4 - 0.45 - note_h4 - 0.25
        chart_top_m4 = chart_top_r4
        chart_h_m4 = chart_h_r4

        # ---- Data Rutin vs Non-Rutin (dihitung DULUAN, spy daftar baris kedua panel bisa disatukan) ----
        rutin_pivot4 = pd.DataFrame()
        if maint_data is not None and not maint_data.empty and "jenis_pemeliharaan" in maint_data.columns:
            m4 = maint_data.copy()
            if "lokasi" in m4.columns and block_site_list:
                m4 = m4[m4["lokasi"].isin(block_site_list)]
            if "bulan" in m4.columns and month_list:
                m4 = m4[m4["bulan"].isin(month_list)]
            kat_scope4 = set(data["kategori"].dropna().unique())
            if "kategori" in m4.columns:
                m4 = m4[m4["kategori"].isin(kat_scope4)]
            elif "nama_unit" in m4.columns:
                valid_units4 = set(data["nama_unit"].astype(str).str.strip().str.upper().unique())
                m4 = m4[m4["nama_unit"].astype(str).str.strip().str.upper().isin(valid_units4)]
            # Lookup KELOMPOK UNIT via KODE UNIT (maint_data tdk punya kolom kelompok_unit langsung) --
            # lihat lookup_atribut_unit(): nama unit di Pemeliharaan sering beda penulisan dgn data BKMS.
            m4["kelompok_unit"] = lookup_atribut_unit(m4, data, ["kelompok_unit"])["kelompok_unit"] if "kelompok_unit" in data.columns else None
            m4 = m4.dropna(subset=["kelompok_unit"])
            if not m4.empty:
                rutin_su4 = m4.groupby(["lokasi", "kelompok_unit", "jenis_pemeliharaan"], as_index=False).agg(biaya=("biaya", "sum"))
                rutin_pivot4 = rutin_su4.pivot_table(index=["lokasi", "kelompok_unit"], columns="jenis_pemeliharaan", values="biaya", fill_value=0).reset_index()
                if "RUTIN" not in rutin_pivot4.columns:
                    rutin_pivot4["RUTIN"] = 0
                if "NON RUTIN" not in rutin_pivot4.columns:
                    rutin_pivot4["NON RUTIN"] = 0
                rutin_pivot4["total"] = rutin_pivot4["RUTIN"] + rutin_pivot4["NON RUTIN"]
                rutin_pivot4 = rutin_pivot4[rutin_pivot4["total"] > 0].copy()
                rutin_pivot4["pct_rutin"] = rutin_pivot4["RUTIN"] / rutin_pivot4["total"] * 100
                rutin_pivot4["pct_nonrutin"] = rutin_pivot4["NON RUTIN"] / rutin_pivot4["total"] * 100
                rutin_pivot4["site_short"] = rutin_pivot4["lokasi"].map(SITE_ABBR).fillna(rutin_pivot4["lokasi"])
                rutin_pivot4["label"] = rutin_pivot4["site_short"] + " \u2014 " + rutin_pivot4["kelompok_unit"].map(KELOMPOK_ABBR).fillna(rutin_pivot4["kelompok_unit"])
                # Diurutkan berdasarkan KELOMPOK UNIT dulu, baru SITE -- spy site dgn kelompok unit yg sama berdampingan
                rutin_pivot4 = rutin_pivot4.sort_values(["kelompok_unit", "lokasi"])

                # --- % Capaian Downtime per (lokasi, kelompok_unit), dari Sasaran Mutu (formula mentah) ---
                # TIDAK mengecualikan Tarif Tetap maupun unit sewa lagi -- ditampilkan APA ADANYA sesuai data
                # riil yg ada di Sasaran Mutu (baik unit Floating Tarif maupun Tarif Tetap ikut dihitung).
                if not sasaran_mutu_data.empty and "kelompok_unit" in sasaran_mutu_data.columns:
                    _sm_dt4b = sasaran_mutu_data.copy()
                    if "breakdown_hm_km_realisasi" in _sm_dt4b.columns:
                        _sm_dt4b["breakdown_hm_km_realisasi"] = _sm_dt4b["breakdown_hm_km_realisasi"].fillna(0)
                    def _dt4b_grp(g):
                        sum_ideal = g["hm_km_ideal_target"].sum() if "hm_km_ideal_target" in g.columns else None
                        dt_r_formula = (g["breakdown_hm_km_realisasi"].sum() / sum_ideal * 100) if (sum_ideal and "breakdown_hm_km_realisasi" in g.columns) else None
                        return pd.Series({"dt_r": dt_r_formula, "dt_t": g["downtime_target"].mean()})
                    dt_su4b = _sm_dt4b.dropna(subset=["kelompok_unit"]).groupby(["lokasi", "kelompok_unit"]).apply(_dt4b_grp).reset_index()
                    dt_su4b["cap_dt"] = dt_su4b.apply(lambda r: (r["dt_r"] / r["dt_t"] * 100) if r["dt_t"] else None, axis=1)
                    dt_lookup4b = {(r["lokasi"], r["kelompok_unit"]): r["cap_dt"] for _, r in dt_su4b.iterrows()}
                    rutin_pivot4["cap_downtime"] = rutin_pivot4.apply(lambda r: dt_lookup4b.get((r["lokasi"], r["kelompok_unit"])), axis=1)
                else:
                    rutin_pivot4["cap_downtime"] = None


        # ================= DAFTAR BARIS BERSAMA (kiri & kanan IDENTIK: jumlah, urutan, label) =================
        # Sebelumnya panel kiri (dari data Budget/Realisasi) & panel kanan (dari transaksi Pemeliharaan) punya
        # daftar Site+Kelompok Unit sendiri2 -> jumlah & urutan baris berbeda, sulit dibandingkan. Sekarang
        # dipakai GABUNGAN (union) keduanya, urutan sama (kelompok unit dulu, baru site), & tiap baris digambar
        # pada posisi Y yg SAMA di kedua panel. Baris yg datanya tidak ada di salah satu sisi tetap tampil
        # dgn keterangan, bukan dihilangkan.
        _keys_l4 = maint_su4[["lokasi", "kelompok_unit"]] if not maint_su4.empty else pd.DataFrame(columns=["lokasi", "kelompok_unit"])
        _keys_r4 = rutin_pivot4[["lokasi", "kelompok_unit"]] if not rutin_pivot4.empty else pd.DataFrame(columns=["lokasi", "kelompok_unit"])
        rows4 = pd.concat([_keys_l4, _keys_r4]).drop_duplicates().copy()
        if not rows4.empty:
            rows4 = rows4.merge(maint_su4[["lokasi", "kelompok_unit", "maint_r", "maint_b", "cap", "gap_rp"]] if not maint_su4.empty
                                else pd.DataFrame(columns=["lokasi", "kelompok_unit", "maint_r", "maint_b", "cap", "gap_rp"]),
                                on=["lokasi", "kelompok_unit"], how="left")
            _rcols4 = ["lokasi", "kelompok_unit", "pct_rutin", "pct_nonrutin", "cap_downtime"]
            rows4 = rows4.merge(rutin_pivot4[_rcols4] if not rutin_pivot4.empty else pd.DataFrame(columns=_rcols4),
                                on=["lokasi", "kelompok_unit"], how="left")
            rows4["label"] = (rows4["lokasi"].map(SITE_ABBR).fillna(rows4["lokasi"]) + " \u2014 "
                              + rows4["kelompok_unit"].map(KELOMPOK_ABBR).fillna(rows4["kelompok_unit"]))
            rows4 = rows4.sort_values(["kelompok_unit", "lokasi"]).reset_index(drop=True)
        n_rows4 = len(rows4)

        # --- Geometri baris bersama ---
        legend_h4 = 0.3
        rows_top4 = chart_top_r4 + legend_h4 + 0.08
        rows_h4 = chart_h_r4 - legend_h4 - 0.1
        row_gap4 = 0.02 if n_rows4 > 16 else 0.04
        total_gap4 = 0.08  # jarak ekstra sebelum baris TOTAL
        _slots4 = n_rows4 + 1  # +1 utk baris TOTAL di bawah
        row_h4 = max(0.13, min(0.42, (rows_h4 - total_gap4 - max(_slots4 - 1, 0) * row_gap4) / max(_slots4, 1)))
        # Font DIPERBESAR spy jelas saat presentasi (sebelumnya 7-8 pt utk 13-18 baris)
        lbl_font4 = 10.5 if n_rows4 <= 8 else (10 if n_rows4 <= 12 else (9.5 if n_rows4 <= 16 else (8.5 if n_rows4 <= 20 else (7.5 if n_rows4 <= 24 else 6.5))))
        val_font4 = lbl_font4

        def _row_y4(i):
            return rows_top4 + i * (row_h4 + row_gap4) + (total_gap4 if i >= n_rows4 else 0)

        def _txt4(x, y, w, h, text, size, color, bold=True, align=PP_ALIGN.LEFT, italic=False):
            tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
            tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
            p = tf.paragraphs[0]; p.alignment = align
            r = p.add_run(); r.text = text
            r.font.size = Pt(size); r.font.bold = bold; r.font.italic = italic; r.font.color.rgb = color; r.font.name = "Calibri"
            return tb

        def _no_shadow4(shp):
            """Hilangkan bayangan secara tuntas. shadow.inherit=False saja cukup utk PowerPoint, tapi LibreOffice
            (dipakai utk konversi PDF) tetap mengambil bayangan dari style tema (effectRef) -> diset ke idx 0."""
            shp.shadow.inherit = False
            for el in shp._element.iter():
                if el.tag.endswith("}effectRef"):
                    el.set("idx", "0")
            return shp

        def _rect4(x, y, w, h, color):
            shp = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(max(w, 0.005)), Inches(max(h, 0.005)))
            shp.fill.solid(); shp.fill.fore_color.rgb = color
            shp.line.fill.background()
            return _no_shadow4(shp)

        SEP4 = RGBColor(0xEE, 0xF0, 0xF4)
        SEP_TOTAL4 = RGBColor(0xC9, 0xCE, 0xD8)

        def _separators4(x, w):
            """Garis tipis pemisah antar baris (bukan pita belang -- pita berbayang tebal saat dirender) +
            garis tebal di atas baris TOTAL."""
            for i in range(1, n_rows4):
                _rect4(x, _row_y4(i) - row_gap4 / 2 - 0.004, w, 0.008, SEP4)
            _rect4(x, _row_y4(n_rows4) - total_gap4 / 2 - row_gap4 / 2 - 0.008, w, 0.016, SEP_TOTAL4)

        def _badge4(x, y, w, h, text, bg, fg, size):
            b = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
            b.adjustments[0] = 0.5
            b.fill.solid(); b.fill.fore_color.rgb = bg
            b.line.fill.background(); _no_shadow4(b)
            tf = b.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE; tf.word_wrap = False
            tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
            p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
            r = p.add_run(); r.text = text
            r.font.size = Pt(size); r.font.bold = True; r.font.name = "Calibri"; r.font.color.rgb = fg
            return b

        RED_SOFT4 = RGBColor(0xFC, 0xE4, 0xE1)
        GREEN_SOFT4 = RGBColor(0xDE, 0xF2, 0xE4)
        GREY_SOFT4 = RGBColor(0xF1, 0xF2, 0xF5)

        def _rp_kolom4(v):
            return "\u2014" if (v is None or pd.isna(v) or v == 0) else fmt_rp(v)

        # ================= PANEL KIRI: Gap Biaya Maintenance (bar HORIZONTAL, sejajar baris panel kanan) =================
        add_card_panel(s, 0.4, panel_top4, 7.5, panel_h4)
        add_panel_header(s, 0.4, panel_top4, 7.5, "\U0001F527 Gap Biaya Maintenance \u2014 per Site & Kelompok Unit", height=0.4)
        if n_rows4 and rows4["gap_rp"].notna().any():
            # Tata letak TABEL + BAR: Label | Budget | Realisasi | Capaian | Gap (bar divergen).
            # Kolom angka mengisi ruang kosong di kiri sumbu & memberi konteks nilai absolut di balik tiap gap.
            lbl_x4, lbl_w4 = 0.5, 1.55
            # Kolom Budget & Realisasi TIDAK ditampilkan (permintaan user) -> Label | Capaian | Gap (bar lebih lebar)
            cap_x4, cap_w4 = lbl_x4 + lbl_w4 + 0.15, 0.62
            plot_l4 = cap_x4 + cap_w4 + 0.15
            plot_r4 = 0.4 + 7.5 - 0.12
            _separators4(lbl_x4, plot_r4 - lbl_x4)

            gaps4 = rows4["gap_rp"].fillna(0)
            pos_max4 = max(gaps4.max(), 0)
            neg_max4 = max(-gaps4.min(), 0)
            room_txt4 = 1.0 if val_font4 >= 9.5 else (0.88 if val_font4 >= 8 else 0.75)  # ruang label nilai gap di ujung bar
            room_pos4 = room_txt4 if pos_max4 > 0 else 0.05
            room_neg4 = room_txt4 if neg_max4 > 0 else 0.05
            span4 = (pos_max4 + neg_max4) or 1
            k4 = (plot_r4 - plot_l4 - room_pos4 - room_neg4) / span4
            zero_x4 = plot_l4 + room_neg4 + neg_max4 * k4

            # Header kolom (sejajar legend panel kanan)
            leg_y4 = chart_top_r4
            hdr_font4 = 9
            _txt4(cap_x4, leg_y4, cap_w4, legend_h4, "Capaian", hdr_font4, TEXT_MUTED, align=PP_ALIGN.CENTER)
            _rect4(plot_l4 + 0.05, leg_y4 + 0.09, 0.12, 0.12, RED)
            _txt4(plot_l4 + 0.22, leg_y4, 0.9, legend_h4, "Over Budget", hdr_font4, TEXT_MUTED)
            _rect4(plot_l4 + 1.15, leg_y4 + 0.09, 0.12, 0.12, TEAL)
            _txt4(plot_l4 + 1.32, leg_y4, 1.2, legend_h4, "Di Bawah Budget", hdr_font4, TEXT_MUTED)
            _rect4(lbl_x4, leg_y4 + legend_h4 + 0.02, plot_r4 - lbl_x4, 0.012, SEP_TOTAL4)

            # Garis nol (hanya sepanjang baris unit, tdk menembus baris TOTAL)
            _rect4(zero_x4 - 0.006, rows_top4 - 0.03, 0.012, _row_y4(n_rows4 - 1) + row_h4 - rows_top4 + 0.06, RGBColor(0xB8, 0xBE, 0xC8))

            badge_h4 = min(0.26, row_h4 * 0.82)

            def _cap_badge4(y, cap_v):
                if cap_v is None or pd.isna(cap_v):
                    _badge4(cap_x4, y + row_h4 / 2 - badge_h4 / 2, cap_w4, badge_h4, "N/A", GREY_SOFT4, TEXT_MUTED, min(9.5, val_font4))
                else:
                    over = cap_v > 100
                    _badge4(cap_x4, y + row_h4 / 2 - badge_h4 / 2, cap_w4, badge_h4, f"{cap_v:.0f}%",
                            RED_SOFT4 if over else GREEN_SOFT4, RED if over else GREEN, min(10, val_font4))

            for i, r in rows4.iterrows():
                y = _row_y4(i)
                _txt4(lbl_x4, y, lbl_w4, row_h4, r["label"], lbl_font4, TEXT_DARK, align=PP_ALIGN.RIGHT)
                g = r["gap_rp"]
                if pd.isna(g):
                    _txt4(cap_x4, y, plot_r4 - cap_x4, row_h4, "tidak ada data budget/realisasi maintenance", max(lbl_font4 - 1, 5), TEXT_MUTED, bold=False, italic=True, align=PP_ALIGN.CENTER)
                    continue
                _cap_badge4(y, r["cap"])
                bh = row_h4 * 0.66
                by = y + (row_h4 - bh) / 2
                bw = max(abs(g) * k4, 0.02)
                is_over = g > 0
                bx = zero_x4 if is_over else zero_x4 - bw
                _rect4(bx, by, bw, bh, RED if is_over else TEAL)
                sign_txt4 = "+" if is_over else "\u2212"
                txt = f"{sign_txt4}{fmt_rp(abs(g))}"
                if is_over:
                    _txt4(bx + bw + 0.05, y, room_pos4, row_h4, txt, val_font4, RED, align=PP_ALIGN.LEFT)
                else:
                    _txt4(bx - room_neg4 - 0.05, y, room_neg4, row_h4, txt, val_font4, TEAL, align=PP_ALIGN.RIGHT)

            # --- Baris TOTAL ---
            yt = _row_y4(n_rows4)
            tot_b4 = rows4["maint_b"].fillna(0).sum()
            tot_r4 = rows4["maint_r"].fillna(0).sum()
            tot_cap4 = (tot_r4 / tot_b4 * 100) if tot_b4 else None
            tot_gap4 = tot_r4 - tot_b4
            tot_font4 = min(val_font4 + 0.5, 11)
            _txt4(lbl_x4, yt, lbl_w4, row_h4, "TOTAL", tot_font4, NAVY, align=PP_ALIGN.RIGHT)
            _cap_badge4(yt, tot_cap4)
            _tot_over4 = tot_gap4 > 0
            _txt4(plot_l4, yt, plot_r4 - plot_l4, row_h4,
                  f"Gap total: {'+' if _tot_over4 else chr(0x2212)}{fmt_rp(abs(tot_gap4))} ({'over budget' if _tot_over4 else 'di bawah budget'})",
                  tot_font4, RED if _tot_over4 else TEAL, align=PP_ALIGN.CENTER)
        else:
            add_textbox(s, 0.55, chart_top_r4 + 0.1, 5.6, 0.5, "Data Biaya Maintenance belum tersedia.", size=10, italic=True, color=TEXT_MUTED)

        # ================= PANEL KANAN: Rutin vs Non-Rutin (baris SAMA PERSIS dgn panel kiri) =================
        add_card_panel(s, 8.3, panel_top4, 4.6, panel_h4)
        add_panel_header(s, 8.3, panel_top4, 4.6, "\U0001F527 Rutin vs Non-Rutin \u2014 per Site & Kelompok Unit", height=0.4)
        if n_rows4 and not rutin_pivot4.empty:
            label_x4 = 8.3 + 0.12
            label_w4 = 1.5
            bar_x4 = label_x4 + label_w4 + 0.08
            bar_max_w4 = 1.75
            dt_x4 = bar_x4 + bar_max_w4 + 0.12
            dt_w4 = (8.3 + 4.6 - 0.12) - dt_x4

            leg_y4 = chart_top_m4
            _rect4(bar_x4, leg_y4 + 0.08, 0.14, 0.14, TEAL)
            _txt4(bar_x4 + 0.2, leg_y4, 0.6, legend_h4, "Rutin", 9, TEXT_MUTED)
            _rect4(bar_x4 + 0.8, leg_y4 + 0.08, 0.14, 0.14, GOLD)
            _txt4(bar_x4 + 1.0, leg_y4, 0.8, legend_h4, "Non Rutin", 9, TEXT_MUTED)
            _txt4(dt_x4, leg_y4, dt_w4, legend_h4, "Cap. Downtime", 8.5, TEXT_MUTED, align=PP_ALIGN.CENTER)
            _rect4(label_x4, leg_y4 + legend_h4 + 0.02, (8.3 + 4.6 - 0.12) - label_x4, 0.012, SEP_TOTAL4)
            _separators4(label_x4, (8.3 + 4.6 - 0.12) - label_x4)

            for i, r in rows4.iterrows():
                y = _row_y4(i)
                _txt4(label_x4, y, label_w4, row_h4, r["label"], lbl_font4, TEXT_DARK, align=PP_ALIGN.RIGHT)
                bh = row_h4 * 0.72
                by = y + (row_h4 - bh) / 2
                if pd.isna(r["pct_rutin"]):
                    _txt4(bar_x4, y, bar_max_w4, row_h4, "tidak ada transaksi pemeliharaan", max(lbl_font4 - 1, 5), TEXT_MUTED, bold=False, italic=True, align=PP_ALIGN.CENTER)
                else:
                    w_r = bar_max_w4 * r["pct_rutin"] / 100
                    w_n = bar_max_w4 * r["pct_nonrutin"] / 100
                    if w_r > 0:
                        _rect4(bar_x4, by, w_r, bh, TEAL)
                    if w_n > 0:
                        _rect4(bar_x4 + w_r, by, w_n, bh, GOLD)
                    if w_r > 0.32:
                        _txt4(bar_x4, by, w_r, bh, f"{r['pct_rutin']:.0f}%", val_font4, WHITE, align=PP_ALIGN.CENTER)
                    if w_n > 0.32:
                        _txt4(bar_x4 + w_r, by, w_n, bh, f"{r['pct_nonrutin']:.0f}%", val_font4, WHITE, align=PP_ALIGN.CENTER)
                cap_dt_val = r["cap_downtime"]
                has_dt4 = cap_dt_val is not None and not pd.isna(cap_dt_val)
                badge_h4 = min(0.26, row_h4 * 0.82)
                badge4 = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(dt_x4 + 0.05), Inches(y + row_h4 / 2 - badge_h4 / 2), Inches(dt_w4 - 0.1), Inches(badge_h4))
                badge4.adjustments[0] = 0.5
                badge4.fill.solid()
                badge4.fill.fore_color.rgb = ((RGBColor(0xFC, 0xE4, 0xE1) if cap_dt_val > 100 else RGBColor(0xDE, 0xF2, 0xE4)) if has_dt4 else RGBColor(0xF1, 0xF2, 0xF5))
                badge4.line.fill.background(); _no_shadow4(badge4)
                btf4 = badge4.text_frame; btf4.vertical_anchor = MSO_ANCHOR.MIDDLE
                btf4.margin_left = 0; btf4.margin_right = 0; btf4.margin_top = 0; btf4.margin_bottom = 0
                bp4 = btf4.paragraphs[0]; bp4.alignment = PP_ALIGN.CENTER
                br4 = bp4.add_run(); br4.text = f"{cap_dt_val:.0f}%" if has_dt4 else "\u2014"
                br4.font.size = Pt(min(10, val_font4)); br4.font.bold = True; br4.font.name = "Calibri"
                br4.font.color.rgb = ((RED if cap_dt_val > 100 else GREEN) if has_dt4 else TEXT_MUTED)

            # --- Baris TOTAL: porsi Rutin/Non-Rutin keseluruhan (dari total Rupiah, bukan rata-rata %) ---
            yt = _row_y4(n_rows4)
            _tot_r = rutin_pivot4["RUTIN"].sum()
            _tot_n = rutin_pivot4["NON RUTIN"].sum()
            _tot_all = _tot_r + _tot_n
            tot_font4 = min(val_font4 + 0.5, 11)
            _txt4(label_x4, yt, label_w4, row_h4, "TOTAL", tot_font4, NAVY, align=PP_ALIGN.RIGHT)
            if _tot_all:
                _pr, _pn = _tot_r / _tot_all * 100, _tot_n / _tot_all * 100
                bh = row_h4 * 0.72
                by = yt + (row_h4 - bh) / 2
                w_r, w_n = bar_max_w4 * _pr / 100, bar_max_w4 * _pn / 100
                if w_r > 0:
                    _rect4(bar_x4, by, w_r, bh, TEAL)
                if w_n > 0:
                    _rect4(bar_x4 + w_r, by, w_n, bh, GOLD)
                if w_r > 0.32:
                    _txt4(bar_x4, by, w_r, bh, f"{_pr:.0f}%", tot_font4, WHITE, align=PP_ALIGN.CENTER)
                if w_n > 0.32:
                    _txt4(bar_x4 + w_r, by, w_n, bh, f"{_pn:.0f}%", tot_font4, WHITE, align=PP_ALIGN.CENTER)
        else:
            add_textbox(s, 8.45, chart_top_m4 + 0.1, 4.3, 0.8,
                        "Data Maintenance (jenis_pemeliharaan) belum tersedia. Silakan upload data Pemeliharaan terlebih dahulu.",
                        size=10, italic=True, color=TEXT_MUTED)

        # ================= INSIGHT: ringkasan over budget + unit over terbesar (Non-Rutin & Downtime-nya) =================
        # Format: "Dari N kelompok unit per site, terdapat X kelompok yang OVER BUDGET ... Over budget terbesar pada
        # <Site — Kelompok> (+Rp.., Capaian ..%) dgn porsi pemeliharaan Non-Rutin ..% dan Capaian Downtime ..%."
        # Dihitung dari baris yg SAMA dgn kedua chart di atas (rows4), jadi angkanya pasti cocok dgn yg tampil.
        insight_top4 = panel_top4 + panel_h4 - note_h4
        _rows_gap4 = rows4[rows4["gap_rp"].notna()] if n_rows4 else pd.DataFrame()
        if not _rows_gap4.empty:
            n_kel4 = n_rows4
            over4 = _rows_gap4[_rows_gap4["gap_rp"] > 0]
            if not over4.empty:
                n_tanpa_budget4 = int(over4["cap"].isna().sum())
                ket_tb4 = f" (termasuk {n_tanpa_budget4} kelompok tanpa budget)" if n_tanpa_budget4 else ""
                w4 = over4.sort_values("gap_rp", ascending=False).iloc[0]
                cap_txt4 = f"Capaian {w4['cap']:.0f}%" if pd.notna(w4["cap"]) else "tanpa budget"
                nr_txt4 = (f"porsi pemeliharaan Non-Rutin {w4['pct_nonrutin']:.0f}%" if pd.notna(w4.get("pct_nonrutin"))
                           else "tanpa transaksi pemeliharaan tercatat")
                _dt4 = w4.get("cap_downtime")
                dt_txt4 = f"Capaian Downtime {_dt4:.0f}%" if (_dt4 is not None and pd.notna(_dt4)) else "Capaian Downtime belum tersedia"
                # --- Tampilan "strip sorotan" (lebih enak dipresentasikan dibanding 1 paragraf panjang) ---
                # [ikon] | 10 dari 13 kelompok OVER BUDGET | Over terbesar: S.DANAU — DT (+Rp.., Capaian ..%) |
                #          Porsi Non-Rutin ..% (+ mini bar) | Capaian Downtime ..% (+ status). Isi = format kalimat yg disetujui.
                bx4, by4, bw4, bh4 = 0.55, insight_top4, 12.0, note_h4 - 0.1
                strip4 = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(bx4), Inches(by4), Inches(bw4), Inches(bh4))
                strip4.adjustments[0] = min(0.12, 0.35 / bh4)
                strip4.fill.solid(); strip4.fill.fore_color.rgb = GOLD_BG
                strip4.line.color.rgb = GOLD; strip4.line.width = Pt(1.25)
                _no_shadow4(strip4)
                ic_d4 = min(0.46, bh4 - 0.2)
                ic4 = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(bx4 + 0.16), Inches(by4 + bh4 / 2 - ic_d4 / 2), Inches(ic_d4), Inches(ic_d4))
                ic4.fill.solid(); ic4.fill.fore_color.rgb = GOLD; ic4.line.fill.background(); _no_shadow4(ic4)
                _ictf4 = ic4.text_frame; _ictf4.vertical_anchor = MSO_ANCHOR.MIDDLE
                _ictf4.margin_left = 0; _ictf4.margin_right = 0; _ictf4.margin_top = 0; _ictf4.margin_bottom = 0
                _icp4 = _ictf4.paragraphs[0]; _icp4.alignment = PP_ALIGN.CENTER
                _icr4 = _icp4.add_run(); _icr4.text = "\U0001F4A1"; _icr4.font.size = Pt(14); _icr4.font.name = EMOJI_FONT

                BROWN4 = RGBColor(0x7A, 0x5C, 0x0D)
                DIV4 = RGBColor(0xE6, 0xCF, 0x9E)
                lab_y4, lab_h4 = by4 + 0.07, 0.2
                big_y4, big_h4 = by4 + 0.25, 0.36
                sub_y4, sub_h4 = by4 + bh4 - 0.25, 0.2
                seg_x4 = bx4 + 0.16 + ic_d4 + 0.2
                seg_w4 = [2.35, 3.0, 2.65, 2.3]  # total + jarak antar kolom muat di dalam kotak (lebar 12 in)

                def _div4(x):
                    _rect4(x - 0.12, by4 + 0.14, 0.012, bh4 - 0.28, DIV4)

                # 1) Jumlah kelompok over budget
                x1 = seg_x4
                _txt4(x1, lab_y4, seg_w4[0], lab_h4, "Kelompok unit over budget", 8.5, BROWN4, bold=False)
                _tb_big = s.shapes.add_textbox(Inches(x1), Inches(big_y4), Inches(seg_w4[0]), Inches(big_h4))
                _tfb = _tb_big.text_frame; _tfb.word_wrap = True; _tfb.vertical_anchor = MSO_ANCHOR.MIDDLE
                _tfb.margin_left = 0; _tfb.margin_right = 0; _tfb.margin_top = 0; _tfb.margin_bottom = 0
                _pb = _tfb.paragraphs[0]
                _rb1 = _pb.add_run(); _rb1.text = f"{len(over4)}"
                _rb1.font.size = Pt(22); _rb1.font.bold = True; _rb1.font.color.rgb = RED; _rb1.font.name = "Calibri"
                _rb2 = _pb.add_run(); _rb2.text = f" dari {n_kel4} kelompok"
                _rb2.font.size = Pt(12); _rb2.font.bold = True; _rb2.font.color.rgb = TEXT_DARK; _rb2.font.name = "Calibri"
                _txt4(x1, sub_y4, seg_w4[0], sub_h4,
                      (f"termasuk {n_tanpa_budget4} kelompok tanpa budget" if n_tanpa_budget4 else "per site & kelompok unit"),
                      8, TEXT_MUTED, bold=False, italic=True)

                # 2) Over budget terbesar
                x2 = x1 + seg_w4[0] + 0.24
                _div4(x2)
                _txt4(x2, lab_y4, seg_w4[1], lab_h4, "Over budget terbesar", 8.5, BROWN4, bold=False)
                _txt4(x2, big_y4, seg_w4[1], big_h4, str(w4["label"]), 16, NAVY)
                _txt4(x2, sub_y4, seg_w4[1], sub_h4, f"+{fmt_rp(w4['gap_rp'])}  \u00b7  {cap_txt4}", 9.5, RED)

                # 3) Porsi Non-Rutin unit tsb (+ mini bar Rutin/Non-Rutin)
                x3 = x2 + seg_w4[1] + 0.24
                _div4(x3)
                _txt4(x3, lab_y4, seg_w4[2], lab_h4, "Porsi pemeliharaan Non-Rutin", 8.5, BROWN4, bold=False)
                _nr4 = w4.get("pct_nonrutin")
                if pd.notna(_nr4):
                    _txt4(x3, big_y4, 0.8, big_h4, f"{_nr4:.0f}%", 20, GOLD)
                    mb_x4, mb_w4, mb_h4 = x3 + 0.85, seg_w4[2] - 0.95, 0.13
                    mb_y4 = big_y4 + big_h4 / 2 - mb_h4 / 2
                    _w_r4 = mb_w4 * (100 - _nr4) / 100
                    if _w_r4 > 0:
                        _rect4(mb_x4, mb_y4, _w_r4, mb_h4, TEAL)
                    _rect4(mb_x4 + _w_r4, mb_y4, mb_w4 - _w_r4, mb_h4, GOLD)
                    _txt4(x3, sub_y4, seg_w4[2], sub_h4, f"Rutin {100 - _nr4:.0f}%  \u00b7  Non-Rutin {_nr4:.0f}%", 8, TEXT_MUTED, bold=False)
                else:
                    _txt4(x3, big_y4, seg_w4[2], big_h4, "\u2014", 20, TEXT_MUTED)
                    _txt4(x3, sub_y4, seg_w4[2], sub_h4, "tanpa transaksi pemeliharaan", 8, TEXT_MUTED, bold=False, italic=True)

                # 4) Capaian Downtime unit tsb
                x4 = x3 + seg_w4[2] + 0.24
                _div4(x4)
                _txt4(x4, lab_y4, seg_w4[3], lab_h4, "Capaian Downtime", 8.5, BROWN4, bold=False)
                if _dt4 is not None and pd.notna(_dt4):
                    _dt_over4 = _dt4 > 100
                    _txt4(x4, big_y4, 0.82, big_h4, f"{_dt4:.0f}%", 20, RED if _dt_over4 else GREEN)
                    _badge4(x4 + 0.86, big_y4 + big_h4 / 2 - 0.11, min(1.2, seg_w4[3] - 0.9), 0.22,
                            "Melebihi target" if _dt_over4 else "Dalam target",
                            RED_SOFT4 if _dt_over4 else GREEN_SOFT4, RED if _dt_over4 else GREEN, 8)
                    _txt4(x4, sub_y4, seg_w4[3], sub_h4, "\u2264 100% = sesuai target downtime", 8, TEXT_MUTED, bold=False)
                else:
                    _txt4(x4, big_y4, seg_w4[3], big_h4, "\u2014", 20, TEXT_MUTED)
                    _txt4(x4, sub_y4, seg_w4[3], sub_h4, "data downtime belum tersedia", 8, TEXT_MUTED, bold=False, italic=True)
            else:
                add_finding_box(s, 0.55, insight_top4, 12.0, note_h4 - 0.1, "\u2705",
                                 f"Dari {n_kel4} kelompok unit per site, tidak ada yang over budget pada biaya maintenance \u2014 "
                                 f"seluruhnya berada dalam/di bawah budget.",
                                 GREEN_BG, GREEN, GREEN)
        else:
            add_finding_box(s, 0.55, insight_top4, 12.0, note_h4 - 0.1, "\u2139\ufe0f",
                             "Data Biaya Maintenance belum tersedia untuk analisis.",
                             GOLD_BG, GOLD, RGBColor(0x7A, 0x5C, 0x0D))

        # ================= SLIDE 4: KEY INSIGHTS \u2014 DOWNTIME ANALYSIS & VARIAN =================
        s = add_content_slide(f"KEY INSIGHTS \u2014 Downtime Analysis & Varian s/d {period_cawu}", f"Analisis Downtime \u00b7 {snum4}{divisi_label}{kat_suffix}")

        _sm_dt5 = sasaran_mutu_data.copy()
        if not _sm_dt5.empty and "breakdown_hm_km_realisasi" in _sm_dt5.columns:
            _sm_dt5["breakdown_hm_km_realisasi"] = _sm_dt5["breakdown_hm_km_realisasi"].fillna(0)
        dt_avg_r5, dt_avg_t5, cap_dt5 = capaian_per_kelompok_unit(_sm_dt5, "breakdown_hm_km_realisasi", "hm_km_ideal_target", "downtime_target")
        varian_dt5 = (dt_avg_r5 - dt_avg_t5) if (dt_avg_r5 is not None and dt_avg_t5 is not None) else None
        good_dt5 = varian_dt5 is not None and varian_dt5 <= 0
        avail_target5 = (100 - dt_avg_t5) if dt_avg_t5 is not None else None
        avail_aktual5 = (100 - dt_avg_r5) if dt_avg_r5 is not None else None

        # --- Hitung MTTR (Mean Time To Repair) dari data Workshop (per kejadian), difilter site, bulan, & kategori (AB/TR) yg sedang aktif ---
        mttr_val5 = None
        mttr_n5 = 0
        mttr_per_site5 = []
        if mttr_data is not None and not mttr_data.empty:
            m5mttr = mttr_data.copy()
            if block_site_list:
                m5mttr = m5mttr[m5mttr["lokasi"].isin(block_site_list)]
            if month_list:
                m5mttr = m5mttr[m5mttr["bulan"].isin(month_list)]
            kat_scope5mttr = set(data["kategori"].dropna().unique())
            if "kategori" in m5mttr.columns and kat_scope5mttr:
                m5mttr = m5mttr[m5mttr["kategori"].isin(kat_scope5mttr)]
            if not m5mttr.empty:
                total_jam5 = m5mttr["jumlah_jam"].sum()
                mttr_n5 = len(m5mttr)
                mttr_val5 = (total_jam5 / mttr_n5) if mttr_n5 else None
                # --- Breakdown MTTR per site ---
                if m5mttr["lokasi"].nunique() > 1:
                    site_mttr_agg5 = m5mttr.groupby("lokasi").agg(total_jam=("jumlah_jam", "sum"), n=("jumlah_jam", "size"))
                    site_mttr_agg5 = site_mttr_agg5.sort_values("total_jam", ascending=False)
                    for site5m, row5m in site_mttr_agg5.iterrows():
                        if row5m["n"] <= 0:
                            continue
                        mttr_site5 = row5m["total_jam"] / row5m["n"]
                        site_short5m = SITE_ABBR.get(site5m, site5m)
                        mttr_per_site5.append(f"{site_short5m} {mttr_site5:.1f}j")

        # --- Breakdown % Capaian Downtime per site ---
        # Metodologi yg BENAR: (1) Target site = average dari NILAI TARGET UNIK dlm site itu (bukan average per
        # unit/baris -- mis. KUMAI cuma py 2 target unik: 0.5 & 2.5, itu saja yg diaverage). (2) Realisasi site =
        # average dari Capaian PER KELOMPOK UNIT dulu (Realisasi kelompok = Sum Breakdown kelompok / Sum Ideal
        # kelompok), BUKAN average langsung semua baris/unit individual.
        cap_dt_per_site5 = []
        if not sasaran_mutu_data.empty and sasaran_mutu_data["lokasi"].nunique() > 1:
            _sm_dtsite5 = sasaran_mutu_data.copy()
            if "breakdown_hm_km_realisasi" in _sm_dtsite5.columns:
                _sm_dtsite5["breakdown_hm_km_realisasi"] = _sm_dtsite5["breakdown_hm_km_realisasi"].fillna(0)
            _sm_dtsite5 = _sm_dtsite5.dropna(subset=["kelompok_unit"]) if "kelompok_unit" in _sm_dtsite5.columns else _sm_dtsite5.iloc[0:0]
            site_dt_result5 = []
            if not _sm_dtsite5.empty:
                for site5d, g_site5d in _sm_dtsite5.groupby("lokasi"):
                    # Target site = average dari nilai target UNIK di site ini (bukan per unit/baris)
                    target_unik5d = g_site5d["downtime_target"].dropna().unique()
                    if len(target_unik5d) == 0:
                        continue
                    target_site5d = target_unik5d.mean()
                    # Realisasi site = average dari Capaian PER KELOMPOK UNIT (Sum Breakdown/Sum Ideal per kelompok)
                    kelompok_real5d = []
                    for kel5d, g_kel5d in g_site5d.groupby("kelompok_unit"):
                        sum_ideal_kel5d = g_kel5d["hm_km_ideal_target"].sum()
                        if sum_ideal_kel5d:
                            kelompok_real5d.append(g_kel5d["breakdown_hm_km_realisasi"].sum() / sum_ideal_kel5d * 100)
                    if not kelompok_real5d:
                        continue
                    realisasi_site5d = sum(kelompok_real5d) / len(kelompok_real5d)
                    site_dt_result5.append((site5d, realisasi_site5d, target_site5d))
            site_dt_result5.sort(key=lambda x: x[1], reverse=True)
            for site5d, dt_r5d, dt_t5d in site_dt_result5:
                if not dt_t5d:
                    continue
                cap_dt_site5 = dt_r5d / dt_t5d * 100
                site_short5d = SITE_ABBR.get(site5d, site5d)
                cap_dt_per_site5.append(f"{site_short5d} {cap_dt_site5:.0f}%")

        # --- Hitung per Site & Jenis Unit lebih awal, dipakai baik di kartu KPI maupun chart di bawah ---
        # Realisasi Downtime dihitung dari FORMULA data mentah (Sum Breakdown / Sum Ideal), BUKAN average kolom
        # persentase yg sudah jadi -- konsisten dgn metodologi kartu KPI "% Capaian Realisasi Downtime" di atas.
        # TIDAK mengecualikan Tarif Tetap maupun unit sewa lagi -- ditampilkan sesuai data riil Sasaran Mutu.
        dt_su5 = pd.DataFrame()
        if not sasaran_mutu_data.empty:
            _sm_dt5b = sasaran_mutu_data.dropna(subset=["kelompok_unit"]).copy() if "kelompok_unit" in sasaran_mutu_data.columns else pd.DataFrame()
            if "breakdown_hm_km_realisasi" in _sm_dt5b.columns:
                _sm_dt5b["breakdown_hm_km_realisasi"] = _sm_dt5b["breakdown_hm_km_realisasi"].fillna(0)
            def _dt5_grp(g):
                sum_ideal = g["hm_km_ideal_target"].sum() if "hm_km_ideal_target" in g.columns else None
                dt_r_formula = (g["breakdown_hm_km_realisasi"].sum() / sum_ideal * 100) if (sum_ideal and "breakdown_hm_km_realisasi" in g.columns) else None
                return pd.Series({"dt_r": dt_r_formula, "dt_t": g["downtime_target"].mean()})
            dt_su5 = _sm_dt5b.groupby(["lokasi", "kategori", "kelompok_unit"]).apply(_dt5_grp).reset_index() if "kelompok_unit" in _sm_dt5b.columns else pd.DataFrame()
            dt_su5["site_short"] = dt_su5["lokasi"].map(SITE_ABBR).fillna(dt_su5["lokasi"])
            # Nama kelompok DISINGKAT (sama dgn slide Analisis Biaya: DT, EXC MEDIUM, BULLDOZER M, TANGKI 300, dst)
            dt_su5["label"] = dt_su5["site_short"] + " \u2014 " + dt_su5["kelompok_unit"].map(KELOMPOK_ABBR).fillna(dt_su5["kelompok_unit"])
            dt_su5["cap"] = dt_su5.apply(lambda r: (r["dt_r"] / r["dt_t"] * 100) if r["dt_t"] else None, axis=1)
            dt_su5 = dt_su5.dropna(subset=["cap"])
            dt_su5 = dt_su5.sort_values("cap", ascending=False)
        n_dt5 = max(len(dt_su5), 1)
        n_over5 = int((dt_su5["cap"] > 100).sum()) if not dt_su5.empty else 0

        # ================= BARIS ATAS: 3 KARTU KPI =================
        card_top5 = 0.98
        card_h5 = 1.85
        card_gap5 = 0.25
        card_w5 = (12.5 - 2 * card_gap5) / 3

        # Status downtime konsisten dgn angka yg ditampilkan: dalam target kalau Capaian <= 100%
        # (sebelumnya warna pill pakai selisih rata2, bisa merah padahal teksnya "DALAM TARGET").
        dt_ok5 = cap_dt5 is not None and cap_dt5 <= 100
        add_kpi_card_wide(s, 0.4, card_top5, card_w5, card_h5, "\u23f8", GREEN if dt_ok5 else RED, GREEN if dt_ok5 else RED,
                          "Capaian Downtime", "Realisasi s/d " + period_cawu_inline,
                          (f"{cap_dt5:.1f}%" if cap_dt5 is not None else "-"),
                          ("  \u00b7  ".join(cap_dt_per_site5) if cap_dt_per_site5 else ""),
                          ("\u2717 Melebihi Target" if (cap_dt5 is not None and cap_dt5 > 100)
                           else ("\u2713 Dalam Target" if cap_dt5 is not None else "Data tidak tersedia")),
                          dt_ok5)

        add_kpi_card_wide(s, 0.4 + card_w5 + card_gap5, card_top5, card_w5, card_h5, "\u26a1", TEAL, TEAL,
                          "MTTR", "Mean Time To Repair (rata-rata waktu perbaikan)",
                          (f"{mttr_val5:.1f} jam" if mttr_val5 is not None else "-"),
                          ("  \u00b7  ".join(mttr_per_site5) if mttr_per_site5 else ""),
                          (f"Dari {mttr_n5:,} kejadian perbaikan".replace(",", ".") if mttr_val5 is not None else "Data Workshop belum tersedia"),
                          True)

        # --- Hitung % Maintenance Rutin vs Non-Rutin (dari total biaya maintenance), utk Kartu KPI 3 ---
        pct_rutin5 = None
        pct_nonrutin5 = None
        rutin_per_site5 = []
        site_rutin_vals5 = []  # list of (site_short, pct_rutin) utk baris "Rutin"
        site_nonrutin_vals5 = []  # list of (site_short, pct_nonrutin) utk baris "Non Rutin"
        if maint_data is not None and not maint_data.empty and "jenis_pemeliharaan" in maint_data.columns:
            m5kpi = maint_data.copy()
            if "lokasi" in m5kpi.columns and block_site_list:
                m5kpi = m5kpi[m5kpi["lokasi"].isin(block_site_list)]
            if "bulan" in m5kpi.columns and month_list:
                m5kpi = m5kpi[m5kpi["bulan"].isin(month_list)]
            kat_scope5kpi = set(data["kategori"].dropna().unique())
            if "kategori" in m5kpi.columns:
                m5kpi = m5kpi[m5kpi["kategori"].isin(kat_scope5kpi)]
            elif "nama_unit" in m5kpi.columns:
                valid_units5kpi = set(data["nama_unit"].astype(str).str.strip().str.upper().unique())
                m5kpi = m5kpi[m5kpi["nama_unit"].astype(str).str.strip().str.upper().isin(valid_units5kpi)]
            if not m5kpi.empty:
                total_maint5kpi = m5kpi["biaya"].sum()
                rutin_biaya5kpi = m5kpi.loc[m5kpi["jenis_pemeliharaan"] == "RUTIN", "biaya"].sum()
                nonrutin_biaya5kpi = m5kpi.loc[m5kpi["jenis_pemeliharaan"] == "NON RUTIN", "biaya"].sum()
                if total_maint5kpi:
                    pct_rutin5 = rutin_biaya5kpi / total_maint5kpi * 100
                    pct_nonrutin5 = nonrutin_biaya5kpi / total_maint5kpi * 100
                # --- Breakdown per site (kalau site yg aktif lebih dari 1) -- Rutin & Non-Rutin masing2 jadi baris terpisah ---
                if "lokasi" in m5kpi.columns and m5kpi["lokasi"].nunique() > 1:
                    site_totals5 = m5kpi.groupby("lokasi")["biaya"].sum().sort_values(ascending=False)
                    for site5kpi, total5kpi in site_totals5.items():
                        if total5kpi <= 0:
                            continue
                        rutin5kpi_site = m5kpi.loc[(m5kpi["lokasi"] == site5kpi) & (m5kpi["jenis_pemeliharaan"] == "RUTIN"), "biaya"].sum()
                        pct_r5site = rutin5kpi_site / total5kpi * 100
                        pct_nr5site = 100 - pct_r5site
                        site_short5kpi = SITE_ABBR.get(site5kpi, site5kpi)
                        site_rutin_vals5.append(f"{site_short5kpi} {pct_r5site:.0f}%")
                        site_nonrutin_vals5.append(f"{site_short5kpi} {pct_nr5site:.0f}%")

        rutin_good5 = pct_rutin5 is not None and pct_rutin5 >= 50
        # Rincian per site 2 baris: "Rutin: KUMAI 91% · S.DANAU 34%" & "Non-Rutin: KUMAI 9% · S.DANAU 66%"
        _det3 = (["Rutin: " + "  \u00b7  ".join(site_rutin_vals5),
                  "Non-Rutin: " + "  \u00b7  ".join(site_nonrutin_vals5)] if site_rutin_vals5 else "")
        add_kpi_card_wide(s, 0.4 + 2 * (card_w5 + card_gap5), card_top5, card_w5, card_h5, "\U0001F527",
                          GREEN if rutin_good5 else GOLD, GREEN if rutin_good5 else GOLD,
                          "Rutin vs Non-Rutin", "Porsi biaya maintenance (Rutin / Non-Rutin)",
                          (f"{pct_rutin5:.0f}% / {pct_nonrutin5:.0f}%" if pct_rutin5 is not None else "-"),
                          _det3,
                          ("\u2713 Rutin Lebih Dominan" if (pct_rutin5 is not None and rutin_good5) else ("\u2717 Non-Rutin Lebih Dominan" if pct_rutin5 is not None else "Data tidak tersedia")),
                          rutin_good5)

        # ================= BARIS BAWAH =================
        panel_top5 = card_top5 + card_h5 + 0.15
        panel_bottom5 = 7.3
        panel_h5 = panel_bottom5 - panel_top5
        left_w5 = 7.3
        right_x5 = 7.9
        right_w5 = 5.0

        # --- Panel kiri: % Downtime per Site & Kelompok Unit + catatan strategi ---
        add_card_panel(s, 0.4, panel_top5, left_w5, panel_h5, accent_color=RED)
        add_panel_header(s, 0.4, panel_top5, left_w5, "\u23f8 % Downtime \u2014 per Site & Kelompok Unit", height=0.4)
        chart_top5 = panel_top5 + 0.45
        note_h5 = 0.85
        chart_h5 = panel_h5 - 0.45 - note_h5 - 0.15
        if not dt_su5.empty:
            cd_dt5 = CategoryChartData()
            cd_dt5.categories = list(dt_su5["label"])
            cd_dt5.add_series("% Capaian Downtime", tuple(_safe_chart_val(v) for v in dt_su5["cap"]))
            gframe_dt5 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55), Inches(chart_top5), Inches(7.0), Inches(chart_h5), cd_dt5)
            chart_dt5 = gframe_dt5.chart
            chart_dt5.series[0].format.fill.solid(); chart_dt5.series[0].format.fill.fore_color.rgb = RED
            chart_dt5.has_title = False
            for i, pt in enumerate(chart_dt5.series[0].points):
                cap_v = dt_su5["cap"].iloc[i]
                if cap_v <= 100:
                    pt.format.fill.solid(); pt.format.fill.fore_color.rgb = GREEN
            plot_dt5 = chart_dt5.plots[0]
            plot_dt5.gap_width = 50
            plot_dt5.has_data_labels = True
            dls_dt5 = plot_dt5.data_labels
            dls_dt5.number_format = '0"%"'; dls_dt5.number_format_is_linked = False
            label_font_dt5 = 12 if n_dt5 <= 10 else (11 if n_dt5 <= 14 else (9.5 if n_dt5 <= 20 else (8 if n_dt5 <= 25 else 6)))  # diperbesar utk presentasi
            dls_dt5.font.size = Pt(label_font_dt5); dls_dt5.font.bold = True; dls_dt5.font.color.rgb = TEXT_DARK; dls_dt5.font.name = "Calibri"
            dls_dt5.position = XL_LABEL_POSITION.OUTSIDE_END
            style_chart_light(chart_dt5, legend=False)
            cat_font_dt5 = 7.5 if n_dt5 <= 10 else (6 if n_dt5 <= 20 else (5 if n_dt5 <= 30 else 4.2))
            chart_dt5.category_axis.tick_labels.font.size = Pt(cat_font_dt5)
            chart_dt5.value_axis.tick_labels.font.size = Pt(cat_font_dt5)
            if n_dt5 > 20:
                plot_dt5.gap_width = 30
        else:
            add_textbox(s, 0.55, chart_top5 + 0.1, 6.9, 0.5, "Data Downtime belum tersedia.", size=10, italic=True, color=TEXT_MUTED)

        # --- Catatan: ringkasan portofolio (berapa unit over target) + unit paling kritis ---
        note_top5 = chart_top5 + chart_h5 + 0.1
        if not dt_su5.empty:
            worst5 = dt_su5.iloc[0]
            pct_over5 = (n_over5 / n_dt5 * 100) if n_dt5 else 0
            if n_over5 > 0:
                add_finding_box(s, 0.55, note_top5, 6.9, note_h5, "\u26A0",
                                 f"{n_over5} dari {n_dt5} unit ({pct_over5:.0f}%) melebihi target downtime. Unit paling kritis: {worst5['label']} "
                                 f"dengan Capaian Downtime {worst5['cap']:.0f}% (downtime realisasinya {worst5['cap']-100:.0f}% di atas batas yang diizinkan) \u2014 "
                                 f"prioritaskan preventive maintenance pada unit-unit ini.",
                                 RED_BG, RED, RED)
            else:
                add_finding_box(s, 0.55, note_top5, 6.9, note_h5, "\u2705",
                                 f"Seluruh {n_dt5} unit berada dalam target downtime yang diizinkan. Pertahankan jadwal preventive maintenance saat ini.",
                                 GREEN_BG, GREEN, GREEN)
        else:
            add_finding_box(s, 0.55, note_top5, 6.9, note_h5, "\u26A0",
                             "Data unit belum tersedia untuk rekomendasi strategi perbaikan.",
                             GOLD_BG, GOLD, RGBColor(0x7A, 0x5C, 0x0D))

        # --- Panel kanan: Kategori Sparepart & Nilai Rupiah, dipecah per Site (keseluruhan divisi ini) ---
        add_card_panel(s, right_x5, panel_top5, right_w5, panel_h5, accent_color=GOLD)
        add_panel_header(s, right_x5, panel_top5, right_w5, "\U0001F527 Kategori Sparepart \u2014 Nilai Tertinggi per Site", height=0.4)

        list_top5 = panel_top5 + 0.5
        list_avail5 = panel_h5 - 0.5 - 0.15
        # Agregat kategori_sparepart x lokasi & total biaya utk keseluruhan kategori (AB/TR) yg sedang dirender di slide ini
        kat_agg5 = pd.DataFrame()
        kat_site_agg5 = pd.DataFrame()
        site_order5 = []
        if maint_data is not None and not maint_data.empty and "kategori_sparepart" in maint_data.columns:
            m5 = maint_data.copy()
            if "lokasi" in m5.columns and block_site_list:
                m5 = m5[m5["lokasi"].isin(block_site_list)]
            if "bulan" in m5.columns and month_list:
                m5 = m5[m5["bulan"].isin(month_list)]
            kat_scope5 = set(data["kategori"].dropna().unique())
            if "kategori" in m5.columns:
                m5 = m5[m5["kategori"].isin(kat_scope5)]
            elif "nama_unit" in m5.columns:
                valid_units5b = set(data["nama_unit"].astype(str).str.strip().str.upper().unique())
                m5 = m5[m5["nama_unit"].astype(str).str.strip().str.upper().isin(valid_units5b)]
            if not m5.empty:
                kat_agg5 = m5.groupby("kategori_sparepart", as_index=False).agg(biaya=("biaya", "sum"))
                kat_agg5 = kat_agg5.sort_values("biaya", ascending=False).head(10)
                top_kats5 = set(kat_agg5["kategori_sparepart"])
                # Breakdown per site, HANYA utk 10 kategori teratas yg akan ditampilkan
                m5_top = m5[m5["kategori_sparepart"].isin(top_kats5)]
                kat_site_agg5 = m5_top.groupby(["kategori_sparepart", "lokasi"], as_index=False).agg(biaya=("biaya", "sum"))
                # Urutan site utk legenda & warna: berdasarkan total biaya site tsb (site kontribusi terbesar duluan)
                site_order5 = (kat_site_agg5.groupby("lokasi")["biaya"].sum().sort_values(ascending=False).index.tolist())

        if not kat_agg5.empty:
            n_kat5 = len(kat_agg5)
            kat_name_w5 = 1.55  # lebar tetap utk nama kategori (sedikit dipersempit spy kolom angka lebih lega)
            n_val_cols5 = len(site_order5) + 1  # kolom per site + 1 kolom Total
            val_area_x5 = right_x5 + 0.55 + kat_name_w5
            val_area_w5 = right_x5 + right_w5 - 0.15 - val_area_x5
            col_w5 = val_area_w5 / n_val_cols5

            # --- Header kolom (nama site & "Total"), ditulis SEKALI di atas, bukan diulang tiap baris ---
            # word_wrap DIMATIKAN & font mengecil otomatis kalau kolom site byk (mis. Mining ada 4 site) --
            # supaya nama site panjang (mis. "TANJUNG") tetap 1 baris, tdk wrap yg bikin baris jadi tdk rapi.
            header_font5 = 9 if n_val_cols5 <= 3 else (7.5 if n_val_cols5 <= 5 else 6.5)

            def _fit_font5(text, width_in, target):
                """Ukuran font TERBESAR (maks = target) yg masih muat 1 baris di kolom selebar width_in -- perkiraan
                lebar karakter Calibri (angka ~0.51 em). Angka dibuat sebesar mungkin spy jelas saat presentasi."""
                em = 0.0
                for ch in str(text):
                    em += 0.51 if ch.isdigit() else (0.23 if ch == " " else (0.25 if ch in ".,-" else (0.86 if ch in "MW" else 0.52)))
                if em <= 0:
                    return target
                return max(6.5, min(target, (width_in - 0.08) * 72 / em))
            header_h5 = 0.22 if len(site_order5) > 1 else 0
            def _add_nowrap_text(target_s, x, y, w, h, text, size, bold=False, color=TEXT_DARK, align=PP_ALIGN.CENTER):
                tb_nw = target_s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
                tf_nw = tb_nw.text_frame; tf_nw.word_wrap = False
                tf_nw.margin_left = 0; tf_nw.margin_right = 0; tf_nw.margin_top = 0; tf_nw.margin_bottom = 0
                tf_nw.vertical_anchor = MSO_ANCHOR.MIDDLE
                p_nw = tf_nw.paragraphs[0]; p_nw.alignment = align
                r_nw = p_nw.add_run(); r_nw.text = text
                r_nw.font.size = Pt(size); r_nw.font.bold = bold; r_nw.font.color.rgb = color; r_nw.font.name = "Calibri"
                return tb_nw
            if len(site_order5) > 1:
                for ci5, site5h in enumerate(site_order5):
                    site_short5h = SITE_ABBR.get(site5h, site5h)
                    hx5 = val_area_x5 + ci5 * col_w5
                    _add_nowrap_text(s, hx5, list_top5, col_w5, header_h5, site_short5h, size=header_font5, bold=True, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
                hx5_total = val_area_x5 + len(site_order5) * col_w5
                _add_nowrap_text(s, hx5_total, list_top5, col_w5, header_h5, "Total", size=header_font5, bold=True, color=TEXT_MUTED, align=PP_ALIGN.CENTER)
            list_top5b = list_top5 + header_h5
            list_avail5b = list_avail5 - header_h5

            row_gap5 = 0.06  # jarak eksplisit antar baris, supaya bar underline tidak menempel ke baris berikutnya
            max_row_cap5 = 0.42 if n_kat5 >= 5 else 0.75  # kalau kategori sedikit, baris melebar mengisi ruang (tidak kosong)
            row_h5b = min(max_row_cap5, (list_avail5b - (n_kat5 - 1) * row_gap5) / n_kat5)
            max_biaya5 = kat_agg5["biaya"].max()
            # Ukuran font SERAGAM utk seluruh tabel: dihitung dari teks TERPANJANG (bukan per sel) -- kalau per sel,
            # angka pendek spt "Rp 900" jadi tampil lebih besar dari angka lain & terlihat janggal.
            _site_txts5 = []
            for _kat5 in kat_agg5["kategori_sparepart"]:
                _kr5 = kat_site_agg5[kat_site_agg5["kategori_sparepart"] == _kat5]
                _lk5 = {rr["lokasi"]: rr["biaya"] for _, rr in _kr5.iterrows()}
                for _st5 in site_order5:
                    _v5 = _lk5.get(_st5)
                    _site_txts5.append(fmt_rp(_v5) if _v5 else "-")
            site_font5 = min([_fit_font5(t, col_w5, 10.5) for t in _site_txts5] or [10.5])
            total_font5 = min([_fit_font5(fmt_rp(v), col_w5, 11.5) for v in kat_agg5["biaya"]] or [11.5]) * 0.97
            for i5, (_, r5) in enumerate(kat_agg5.iterrows()):
                ry5c = list_top5b + i5 * (row_h5b + row_gap5)
                rank_bg5 = GOLD
                rank_txt5 = WHITE
                circ_size5 = min(0.3, row_h5b * 0.72)
                rank_circ5 = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(right_x5 + 0.15), Inches(ry5c + row_h5b / 2 - circ_size5 / 2), Inches(circ_size5), Inches(circ_size5))
                rank_circ5.fill.solid(); rank_circ5.fill.fore_color.rgb = rank_bg5
                rank_circ5.line.fill.background(); rank_circ5.shadow.inherit = False
                rtf5 = rank_circ5.text_frame; rtf5.vertical_anchor = MSO_ANCHOR.MIDDLE
                rtf5.margin_left = 0; rtf5.margin_right = 0
                rp5 = rtf5.paragraphs[0]; rp5.alignment = PP_ALIGN.CENTER
                rr5 = rp5.add_run(); rr5.text = str(i5 + 1)
                rtf5.margin_top = 0; rtf5.margin_bottom = 0
                rr5.font.size = Pt(min(10, circ_size5 * 30)); rr5.font.bold = True; rr5.font.color.rgb = rank_txt5
                font_row5 = 10 if n_kat5 <= 6 else (9 if n_kat5 <= 10 else 8)
                text_h5 = row_h5b
                _nm5 = add_textbox(s, right_x5 + 0.55, ry5c, kat_name_w5, text_h5, str(r5["kategori_sparepart"]), size=font_row5, bold=True, color=TEXT_DARK)
                _nm5.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE  # sejajar tengah dgn angka di kolom kanan
                _nm5.text_frame.margin_top = 0; _nm5.text_frame.margin_bottom = 0
                # --- Nilai per site & Total, ditaruh di kolom masing2 (tanpa label nama site diulang) ---
                kat_rows5 = kat_site_agg5[kat_site_agg5["kategori_sparepart"] == r5["kategori_sparepart"]]
                site_val_lookup5 = {row5b["lokasi"]: row5b["biaya"] for _, row5b in kat_rows5.iterrows()}
                val_font5 = max(5.5, font_row5 - 1.5) if n_val_cols5 <= 3 else max(5, font_row5 - 2.5)
                if len(site_order5) > 1:
                    for ci5, site5v in enumerate(site_order5):
                        vx5 = val_area_x5 + ci5 * col_w5
                        v5 = site_val_lookup5.get(site5v)
                        v_txt5 = fmt_rp(v5) if v5 else "-"
                        _add_nowrap_text(s, vx5, ry5c, col_w5, text_h5, v_txt5, size=site_font5, color=TEXT_DARK, align=PP_ALIGN.CENTER)
                    total_x5 = val_area_x5 + len(site_order5) * col_w5
                    _tot_txt5 = fmt_rp(r5["biaya"])
                    _add_nowrap_text(s, total_x5, ry5c, col_w5, text_h5, _tot_txt5, size=total_font5, bold=True, color=GOLD, align=PP_ALIGN.CENTER)
                else:
                    add_textbox(s, val_area_x5, ry5c, val_area_w5, text_h5, fmt_rp(r5["biaya"]), size=12, bold=True, color=GOLD, align=PP_ALIGN.RIGHT)
        else:
            add_textbox(s, right_x5 + 0.15, list_top5, right_w5 - 0.3, 0.5, "Data Maintenance belum tersedia.", size=9, italic=True, color=TEXT_MUTED)





    # Penomoran & pembagian blok slide:
    # - Kalau site yg dipilih mencakup KEDUA divisi (Plantation & Mining) sekaligus -> 3 blok berurutan:
    #   01-04 Plantation-Transportasi, 05-08 Plantation-Alat Berat, 09-12 Mining-Alat Berat (Tanjung/Buhut/Buhut LHL/Ampah)
    # - Kalau cuma 1 divisi yg dipilih -> pakai logika lama (pisah AB/TR kalau keduanya ada, kalau tidak 1 blok saja)
    kat_set_render = set(kat_list) if kat_list else set()
    plantation_sites_sel = [s for s in site_list if s in PLANTATION_SITES_PPTX]
    mining_sites_sel = [s for s in site_list if s in MINING_SITES_PPTX]
    both_divisi_selected = bool(plantation_sites_sel) and bool(mining_sites_sel)

    # ================= SLIDE PEMBUKAAN (paling depan) =================
    # Replika Slide_Pembukaan.pptx (desain 10x5.625 in, diskalakan ke 13.333x7.5 in). Teks CAWU, tahun, &
    # bulan OTOMATIS mengikuti bulan terakhir yg dipilih di filter.
    def add_cover_slide():
        import base64 as _b64
        import io as _io_c
        from pptx.dml.color import RGBColor as _RGB
        SC = 13.333 / 10.0  # faktor skala dari desain asli

        def _I(v):
            return Inches(v * SC)

        cs = prs.slides.add_slide(blank)
        add_bg(cs, _RGB(0x1E, 0x27, 0x61))

        def _shape(kind, x, y, w, h, color):
            shp = cs.shapes.add_shape(kind, _I(x), _I(y), _I(w), _I(h))
            shp.fill.solid(); shp.fill.fore_color.rgb = color
            shp.line.fill.background(); shp.shadow.inherit = False
            for el in shp._element.iter():
                if el.tag.endswith("}effectRef"):
                    el.set("idx", "0")
            return shp

        def _text(x, y, w, h, text, size, color, bold=False, spc=None, align=PP_ALIGN.LEFT):
            tb = cs.shapes.add_textbox(_I(x), _I(y), _I(w), _I(h))
            tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = Inches(0.1); tf.margin_right = Inches(0.1); tf.margin_top = 0; tf.margin_bottom = 0
            p = tf.paragraphs[0]; p.alignment = align
            r = p.add_run(); r.text = text
            r.font.size = Pt(size * SC); r.font.bold = bold; r.font.name = "Calibri"; r.font.color.rgb = color
            if spc is not None:
                r.font._element.set("spc", str(int(spc * SC)))
            return tb

        # Dekorasi: strip kiri, 2 lingkaran kanan atas, garis aksen, pita nilai perusahaan di bawah
        _shape(MSO_SHAPE.RECTANGLE, 0, 0, 0.18, 5.625, _RGB(0x00, 0xB4, 0xD8))
        _shape(MSO_SHAPE.OVAL, 6.2, -1.8, 7.0, 7.0, _RGB(0x25, 0x36, 0x80))
        _shape(MSO_SHAPE.OVAL, 7.1, -0.8, 5.0, 5.0, _RGB(0x2D, 0x3F, 0x90))
        _shape(MSO_SHAPE.RECTANGLE, 0.45, 2.88, 3.5, 0.055, _RGB(0x00, 0xB4, 0xD8))
        _shape(MSO_SHAPE.RECTANGLE, 0, 5.05, 10.0, 0.575, _RGB(0x14, 0x1D, 0x4A))

        # Periode: CAWU dari bulan terakhir; tahun = tahun berjalan, mundur 1 thn kalau bulan data > bulan sekarang
        _romawi = ["I", "II", "III"]
        if period in MONTH_ORDER:
            _ip = MONTH_ORDER.index(period)
            _thn = _now.year - 1 if _ip > _now.month - 1 else _now.year
            _cawu = f"CAWU {_romawi[_ip // 4]}"
            if _ip % 4 != 3:  # belum akhir cawu -> sebut bulan terakhirnya
                _cawu += f" (s/d {_bulan_id[_ip].upper()})"
            cawu_txt = f"{_cawu} \u2014 TAHUN {_thn}"
            tempat_tgl = f"Banjarmasin, {_bulan_id[_ip]} {_thn}"
        else:
            cawu_txt = f"TAHUN {_now.year}"
            tempat_tgl = f"Banjarmasin, {tgl_laporan}"

        WHITE_ = _RGB(0xFF, 0xFF, 0xFF); SOFT_ = _RGB(0xCA, 0xDC, 0xFC)
        CYAN_ = _RGB(0x00, 0xB4, 0xD8); GREY_ = _RGB(0x64, 0x74, 0x8B)
        _text(0.5, 0.46, 7.0, 0.3, "PT. BUANA KARYA MANDIRI SEJAHTERA", 8.5, SOFT_, bold=True, spc=200)
        _text(0.45, 0.92, 8.0, 0.98, "TINJAUAN", 60, WHITE_, bold=True)
        _text(0.45, 1.76, 8.0, 0.98, "MANAJEMEN", 60, CYAN_, bold=True)
        _text(0.45, 2.98, 6.0, 0.44, cawu_txt, 18, SOFT_)
        _text(0.45, 3.48, 5.0, 0.36, tempat_tgl, 13, GREY_)
        _text(0.45, 4.45, 5.0, 0.36, "Prepared by : Dept. SM & Sustainability", 10.5, GREY_)
        _text(0, 5.07, 10.0, 0.4,
              "Integritas  \u25CF  Kemandirian  \u25CF  Kebersamaan  \u25CF  Tanggung Jawab  \u25CF  Inovatif  \u25CF  Komitmen",
              9.5, SOFT_, spc=100, align=PP_ALIGN.CENTER)
        try:
            cs.shapes.add_picture(_io_c.BytesIO(_b64.b64decode(_COVER_ICON_B64)), _I(8.85), _I(0.32), _I(0.68), _I(0.68))
        except Exception:
            pass  # ikon hanya hiasan; jangan sampai menggagalkan pembuatan PPT

    add_cover_slide()

    _slide_counter = [1]  # dibungkus list spy bisa di-mutate dari dalam helper closure

    def _next_slide_nums(n=4):
        nums = [f"{i:02d}" for i in range(_slide_counter[0], _slide_counter[0] + n)]
        _slide_counter[0] += n
        return nums

    def _render_divisi_block(data_divisi, sasaran_mutu_divisi, label_divisi):
        """Render 4 slide utk satu divisi -- pisah AB/TR kalau keduanya ada datanya, kalau tidak 1 blok saja.
        Penomoran slide (01-04) SELALU RESET ke awal utk tiap blok baru (Plantation-TR, Plantation-AB, Mining,
        dst) -- bukan melanjutkan angka global, spy tiap blok terasa sbg laporan tersendiri yg konsisten."""
        _slide_counter[0] = 1
        d_tr = data_divisi[data_divisi["kategori"] == "TR"]
        d_ab = data_divisi[data_divisi["kategori"] == "AB"]
        if {"AB", "TR"}.issubset(kat_set_render) and not d_tr.empty and not d_ab.empty:
            sm_tr_ = sasaran_mutu_divisi[sasaran_mutu_divisi["kategori"] == "TR"].copy() if (sasaran_mutu_divisi is not None and not sasaran_mutu_divisi.empty) else sasaran_mutu_divisi
            sm_ab_ = sasaran_mutu_divisi[sasaran_mutu_divisi["kategori"] == "AB"].copy() if (sasaran_mutu_divisi is not None and not sasaran_mutu_divisi.empty) else sasaran_mutu_divisi
            n1, n2, n3, n4 = _next_slide_nums(4)
            render_6_slides(d_tr.copy(), sm_tr_, n1, n2, n3, n4, f"{label_divisi} · TRANSPORTASI")
            _slide_counter[0] = 1
            n1, n2, n3, n4 = _next_slide_nums(4)
            render_6_slides(d_ab.copy(), sm_ab_, n1, n2, n3, n4, f"{label_divisi} · ALAT BERAT")
        else:
            n1, n2, n3, n4 = _next_slide_nums(4)
            render_6_slides(data_divisi.copy(), sasaran_mutu_divisi, n1, n2, n3, n4, label_divisi)

    if both_divisi_selected:
        data_plantation = data[data["lokasi"].isin(PLANTATION_SITES_PPTX)]
        data_mining = data[data["lokasi"].isin(MINING_SITES_PPTX)]
        sm_plantation = sasaran_mutu_data[sasaran_mutu_data["lokasi"].isin(PLANTATION_SITES_PPTX)].copy() if (sasaran_mutu_data is not None and not sasaran_mutu_data.empty) else sasaran_mutu_data
        sm_mining = sasaran_mutu_data[sasaran_mutu_data["lokasi"].isin(MINING_SITES_PPTX)].copy() if (sasaran_mutu_data is not None and not sasaran_mutu_data.empty) else sasaran_mutu_data
        if not data_plantation.empty:
            _render_divisi_block(data_plantation, sm_plantation, " · PLANTATION")
        if not data_mining.empty:
            _render_divisi_block(data_mining, sm_mining, " · MINING")
    else:
        data_tr_check = data[data["kategori"] == "TR"]
        data_ab_check = data[data["kategori"] == "AB"]
        if {"AB", "TR"}.issubset(kat_set_render) and not data_tr_check.empty and not data_ab_check.empty:
            data_tr = data_tr_check.copy()
            data_ab = data_ab_check.copy()
            sm_tr = sasaran_mutu_data[sasaran_mutu_data["kategori"] == "TR"].copy() if (sasaran_mutu_data is not None and not sasaran_mutu_data.empty) else sasaran_mutu_data
            sm_ab = sasaran_mutu_data[sasaran_mutu_data["kategori"] == "AB"].copy() if (sasaran_mutu_data is not None and not sasaran_mutu_data.empty) else sasaran_mutu_data
            render_6_slides(data_tr, sm_tr, "01", "02", "03", "04", " · TRANSPORTASI")
            render_6_slides(data_ab, sm_ab, "01", "02", "03", "04", " · ALAT BERAT")
        else:
            render_6_slides(data, sasaran_mutu_data, "01", "02", "03", "04", "")

    buf = _io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

def convert_pptx_to_pdf_bytes(pptx_bytes: bytes):
    """Konversi PPTX ke PDF pakai LibreOffice (headless). Return (pdf_bytes, None) kalau berhasil,
    atau (None, pesan_error) kalau LibreOffice tdk tersedia / gagal -- supaya app tetap jalan normal
    (tombol PDF sekedar tdk muncul / kasih pesan) drpd crash total kalau server tdk py LibreOffice."""
    import subprocess, tempfile, os as _os
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pptx_path = _os.path.join(tmpdir, "input.pptx")
            with open(pptx_path, "wb") as f:
                f.write(pptx_bytes)
            result = subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmpdir, pptx_path],
                capture_output=True, text=True, timeout=120,
            )
            pdf_path = _os.path.join(tmpdir, "input.pdf")
            if result.returncode != 0 or not _os.path.exists(pdf_path):
                return None, f"LibreOffice gagal konversi: {result.stderr or result.stdout or 'tidak diketahui'}"
            with open(pdf_path, "rb") as f:
                return f.read(), None
    except FileNotFoundError:
        return None, "LibreOffice tidak ditemukan di server ini. Tambahkan 'libreoffice' ke packages.txt (Streamlit Cloud) atau install LibreOffice di server."
    except subprocess.TimeoutExpired:
        return None, "Konversi PDF timeout (>120 detik)."
    except Exception as e:
        return None, f"Gagal konversi ke PDF: {e}"

st.markdown("##### 📤 Buat & Unduh Laporan")
colDB, colPPT = st.columns(2)

with colDB:
    if st.button("📊 Buat Database Laporan (Excel)", use_container_width=True, type="primary"):
        with st.spinner("Menyusun Database Laporan..."):
            st.session_state["database_laporan_bytes"] = build_database_laporan_excel(df_raw, sasaran_mutu_raw, mttr_raw, maint_raw)
    if "database_laporan_bytes" in st.session_state:
        st.download_button(
            "⬇️ Unduh Database Laporan (Excel)",
            data=st.session_state["database_laporan_bytes"],
            file_name="Database_Laporan_BKMS.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Berisi seluruh data BKMS (Semua Data) + Sasaran Mutu + MTTR dalam 1 file Excel.",
        )

with colPPT:
    if st.button("📽️ Buat Presentasi (PPTX & PDF)", use_container_width=True, type="primary"):
        with st.spinner("Menyusun slide presentasi, PDF, & perhitungan detail..."):
            maint_for_pptx = maint_df_site_bulan if not maint_raw.empty else pd.DataFrame()
            sparepart_for_pptx = sparepart_df_site_bulan if not sparepart_raw.empty else pd.DataFrame()
            pptx_bytes = build_pptx(df, maint_for_pptx, sparepart_for_pptx, sel_site, sel_month, sel_kat, sasaran_mutu_df, mttr_raw)
            st.session_state["pptx_bytes"] = pptx_bytes
            # Detail Perhitungan PPT MODEL BARU: tiap slide dibawa ke Excel, semua angka = rumus yg tertaut ke
            # sheet data mentah. Input SAMA PERSIS dgn build_pptx di atas spy angkanya identik dgn slide.
            try:
                st.session_state["perhitungan_detail_bytes"] = build_detail_ppt_excel(
                    df, sasaran_mutu_df, maint_for_pptx, mttr_raw, sel_site, sel_month, sel_kat,
                    lookup_atribut_unit, lookup_base=df_raw)
                st.session_state.pop("perhitungan_detail_error", None)
            except Exception as _e_dx:
                st.session_state.pop("perhitungan_detail_bytes", None)
                st.session_state["perhitungan_detail_error"] = str(_e_dx)
            pdf_bytes, pdf_err = convert_pptx_to_pdf_bytes(pptx_bytes)
            if pdf_bytes is not None:
                st.session_state["pptx_pdf_bytes"] = pdf_bytes
                st.session_state.pop("pptx_pdf_error", None)
            else:
                st.session_state.pop("pptx_pdf_bytes", None)
                st.session_state["pptx_pdf_error"] = pdf_err
    if "pptx_bytes" in st.session_state:
        st.download_button(
            "⬇️ Unduh PPTX untuk RTM",
            data=st.session_state["pptx_bytes"],
            file_name="Laporan_Biaya_Pendapatan_BKMS.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )
    if "pptx_pdf_bytes" in st.session_state:
        st.download_button(
            "⬇️ Unduh PDF untuk RTM",
            data=st.session_state["pptx_pdf_bytes"],
            file_name="Laporan_Biaya_Pendapatan_BKMS.pdf",
            mime="application/pdf",
            use_container_width=True,
            help="Tampilan sama persis dgn PPTX, dlm format PDF (lebih konsisten dibuka di semua perangkat).",
        )
    elif "pptx_pdf_error" in st.session_state:
        st.caption(f"⚠️ PDF tidak tersedia: {st.session_state['pptx_pdf_error']}")
    if "perhitungan_detail_bytes" in st.session_state:
        st.download_button(
            "⬇️ Unduh Perhitungan Detail PPT (Excel)",
            data=st.session_state["perhitungan_detail_bytes"],
            file_name="Perhitungan_Detail_PPT_BKMS.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Setiap slide PPT dalam bentuk Excel (per blok: 4 sheet tampilan + 4 sheet perhitungan). Semua angka berupa RUMUS yg tertaut ke sheet data mentah (Data BKMS, Sasaran Mutu, Pemeliharaan, MTTR) -- ubah datanya, angka & chart ikut berubah.",
        )
    elif "perhitungan_detail_error" in st.session_state:
        st.caption(f"⚠️ Detail perhitungan gagal dibuat: {st.session_state['perhitungan_detail_error']}")

st.markdown("---")

# ---------------------------------------------------------------
# Klasifikasi satuan Rp/HM, Rp/KM, Rp/Tonase per baris data (dipakai di beberapa section)
# ---------------------------------------------------------------
def klasifikasi_satuan_prestasi(row):
    lok = row["lokasi"]
    kat = row["kategori"]
    if lok == "BUHUT LHL":
        return "Rp/Tonase"
    if lok in ("SUNGAI DANAU", "KUMAI"):
        if kat == "AB":
            return "Rp/HM"
        if kat == "TR":
            return "Rp/KM"
        return "Rp/HM"
    # TANJUNG, BUHUT, AMPAH, dan site lain di luar aturan eksplisit -> default Rp/HM
    return "Rp/HM"

df["satuan_prestasi"] = df.apply(klasifikasi_satuan_prestasi, axis=1)
satuan_suffix_map = {"Rp/HM": "/HM", "Rp/KM": "/KM", "Rp/Tonase": "/Ton"}

def rk_badge(pct, higher_is_better, na=False, small=False):
    cls_base = "rk-badge-sm" if small else "rk-badge"
    if na or pct is None:
        return f'<span class="{cls_base} rk-grey">N/A</span>'
    good = (pct >= 100) if higher_is_better else (pct <= 100)
    cls = "rk-green" if good else "rk-red"
    return f'<span class="{cls_base} {cls}">{pct:.1f}%</span>'

# ---------------------------------------------------------------
# 1. CAPAIAN PENDAPATAN  +  ANALISA PENYEBAB (di sampingnya)
# ---------------------------------------------------------------
if "bulan_no" in df.columns and not df.empty:
    bulan_terakhir_no = df["bulan_no"].max()
    bulan_terakhir_label = df.loc[df["bulan_no"] == bulan_terakhir_no, "bulan"].iloc[0]
    df_bulan_terakhir = df[df["bulan_no"] == bulan_terakhir_no]
else:
    bulan_terakhir_label = "-"
    df_bulan_terakhir = df

col_capaian, col_analisa = st.columns([1, 1.5])

with col_capaian:
    st.markdown('<h3 class="section-title">Capaian Pendapatan</h3>', unsafe_allow_html=True)

    pendapatan_pill, pendapatan_style = achievement_pill(ach_pendapatan, higher_is_better=True)

    st.markdown(kpi_card(
        icon="💰", icon_bg=RED, accent=RED,
        label="Pendapatan: Realisasi vs Target",
        value=fmt_rp(tot_pendapatan_r),
        budget_text=f"Target: {fmt_rp(tot_pendapatan_b)}",
        pill_text=pendapatan_pill, pill_style=pendapatan_style,
    ), unsafe_allow_html=True)

with col_analisa:
    st.markdown('<h3 class="section-title">Analisa: Penyebab Pendapatan Tidak Capai Budget</h3>', unsafe_allow_html=True)

    gap_rp = tot_pendapatan_b - tot_pendapatan_r
    rate_target_all = (tot_pendapatan_b / tot_prestasi_b) if tot_prestasi_b else None
    rate_realisasi_all = (tot_pendapatan_r / tot_prestasi_r) if tot_prestasi_r else None
    rate_ach = (rate_realisasi_all / rate_target_all * 100) if (rate_realisasi_all is not None and rate_target_all) else None

    if ach_pendapatan is not None and ach_pendapatan >= 100:
        st.markdown(
            f'<div class="insight-box">✅ Pendapatan sudah <b>mencapai/melampaui target</b> '
            f'({ach_pendapatan:.1f}%). Tidak ada gap yang perlu dianalisa lebih lanjut untuk periode/filter saat ini.</div>',
            unsafe_allow_html=True,
        )
    elif ach_pendapatan is None:
        st.markdown(
            '<div class="insight-box">⚠️ Target Pendapatan untuk kombinasi filter ini adalah <b>Rp 0</b>, '
            'sehingga capaian tidak dapat dihitung. Analisa penyebab gap tidak berlaku untuk filter saat ini.</div>',
            unsafe_allow_html=True,
        )
    else:
        drivers = []
        if pct_populasi is not None:
            drivers.append(("Populasi (jumlah unit beroperasi)", pct_populasi))
        if ach_prestasi is not None:
            drivers.append(("Prestasi (volume pekerjaan)", ach_prestasi))
        if rate_ach is not None:
            drivers.append(("Tarif/Rate Rp per satuan", rate_ach))

        penyebab_utama = min(drivers, key=lambda x: x[1]) if drivers else None

        poin = []
        poin.append(f"Pendapatan hanya mencapai <b>{ach_pendapatan:.1f}%</b> dari target (gap <b>{fmt_rp(gap_rp)}</b>).")

        if target_populasi:
            gap_pop = target_populasi - realisasi_populasi
            if gap_pop > 0:
                poin.append(
                    f"<b>Populasi:</b> dari <b>{target_populasi}</b> unit target pada bulan {bulan_terakhir_label}, "
                    f"hanya <b>{realisasi_populasi}</b> unit yang mencatatkan realisasi pendapatan — "
                    f"<b>{gap_pop} unit ({100 - pct_populasi:.1f}%) tidak beroperasi/tidak menghasilkan pendapatan sama sekali</b>."
                )
            else:
                poin.append(f"<b>Populasi:</b> seluruh unit target ({target_populasi} unit) sudah beroperasi dan mencatatkan pendapatan.")

        if ach_prestasi is not None:
            if ach_prestasi < 100:
                poin.append(f"<b>Prestasi</b> (volume pekerjaan unit yang beroperasi) juga di bawah target, hanya <b>{ach_prestasi:.1f}%</b>.")
            else:
                poin.append(f"<b>Prestasi</b> dari unit yang beroperasi sebenarnya sudah tercapai (<b>{ach_prestasi:.1f}%</b>) — bukan penyebab utama gap.")

        if rate_ach is not None:
            if rate_ach < 100:
                poin.append(f"<b>Tarif/Rate</b> Rp per satuan prestasi realisasi ({fmt_rp(rate_realisasi_all)}) juga lebih rendah dari target ({fmt_rp(rate_target_all)}), yaitu <b>{rate_ach:.1f}%</b>.")
            else:
                poin.append(f"<b>Tarif/Rate</b> Rp per satuan prestasi sudah sesuai/di atas target (<b>{rate_ach:.1f}%</b>) — bukan penyebab utama gap.")

        # Jenis Unit mana yang paling bermasalah (kontribusi gap pendapatan terbesar)
        ju_problem = df.groupby("jenis_unit", as_index=False).agg(
            target_pendapatan=("pendapatan_budget", "sum"),
            realisasi_pendapatan=("pendapatan_realisasi", "sum"),
            target_prestasi=("prestasi_budget", "sum"),
            realisasi_prestasi=("prestasi_realisasi", "sum"),
        )
        ju_problem["gap"] = ju_problem["target_pendapatan"] - ju_problem["realisasi_pendapatan"]
        ju_problem["capaian"] = ju_problem.apply(
            lambda r: (r["realisasi_pendapatan"] / r["target_pendapatan"] * 100) if r["target_pendapatan"] else None, axis=1
        )
        ju_problem["capaian_prestasi"] = ju_problem.apply(
            lambda r: (r["realisasi_prestasi"] / r["target_prestasi"] * 100) if r["target_prestasi"] else None, axis=1
        )
        ju_bermasalah = ju_problem[(ju_problem["gap"] > 0) & (ju_problem["capaian"].notna()) & (ju_problem["capaian"] < 100)]
        ju_bermasalah = ju_bermasalah.sort_values("gap", ascending=False).head(5)

        if not ju_bermasalah.empty:
            list_items = ""
            for _, jr in ju_bermasalah.iterrows():
                cap_prestasi_txt = f", prestasi {jr['capaian_prestasi']:.1f}%" if pd.notna(jr["capaian_prestasi"]) else ""
                list_items += (
                    f"<li style='margin-bottom:3px;'><b>{jr['jenis_unit']}</b> — capaian pendapatan {jr['capaian']:.1f}%"
                    f"{cap_prestasi_txt}, gap {fmt_rp(jr['gap'])}</li>"
                )
            poin.append(
                f"<b>🚩 Jenis Unit paling bermasalah</b> (kontribusi gap pendapatan terbesar):"
                f"<ul style='padding-left:16px; margin:4px 0 0 0;'>{list_items}</ul>"
            )

        if penyebab_utama:
            poin.append(f"➡️ <b>Penyebab paling dominan:</b> {penyebab_utama[0]} (capaian terendah, {penyebab_utama[1]:.1f}%).")

        bullets_html = "".join([f"<li style='margin-bottom:6px;'>{p}</li>" for p in poin])
        st.markdown(f'<div class="insight-box"><ul style="padding-left:18px; margin:0;">{bullets_html}</ul></div>', unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------
# RINGKASAN PER JENIS UNIT
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Ringkasan per Jenis Unit</h3>', unsafe_allow_html=True)

ju_target_pop = df_bulan_terakhir[df_bulan_terakhir["pendapatan_budget"] > 0].groupby("jenis_unit")["nama_unit"].nunique()
ju_real_pop = df_bulan_terakhir[df_bulan_terakhir["pendapatan_realisasi"] > 0].groupby("jenis_unit")["nama_unit"].nunique()
ju_sat_mode = df.groupby("jenis_unit")["satuan_prestasi"].agg(lambda s: s.mode().iat[0] if not s.mode().empty else "Rp/HM")

ju = df.groupby("jenis_unit", as_index=False).agg(
    target_pendapatan=("pendapatan_budget", "sum"),
    realisasi_pendapatan=("pendapatan_realisasi", "sum"),
    target_prestasi=("prestasi_budget", "sum"),
    realisasi_prestasi=("prestasi_realisasi", "sum"),
)
ju["target_populasi"] = ju["jenis_unit"].map(ju_target_pop).fillna(0).astype(int)
ju["realisasi_populasi"] = ju["jenis_unit"].map(ju_real_pop).fillna(0).astype(int)
ju["satuan"] = ju["jenis_unit"].map(ju_sat_mode).fillna("Rp/HM")
ju["suffix"] = ju["satuan"].map(satuan_suffix_map)
ju["rate_target"] = ju.apply(lambda r: (r["target_pendapatan"] / r["target_prestasi"]) if r["target_prestasi"] else None, axis=1)
ju["rate_realisasi"] = ju.apply(lambda r: (r["realisasi_pendapatan"] / r["realisasi_prestasi"]) if r["realisasi_prestasi"] else None, axis=1)
ju["capaian"] = ju.apply(lambda r: (r["realisasi_pendapatan"] / r["target_pendapatan"] * 100) if r["target_pendapatan"] else None, axis=1)
ju["selisih_pendapatan"] = ju["realisasi_pendapatan"] - ju["target_pendapatan"]
ju = ju.sort_values("selisih_pendapatan", ascending=False)

def fmt_rp_signed(x, pct=None):
    if x is None or pd.isna(x):
        return "-"
    sign = "▲ +" if x > 0 else ("▼ -" if x < 0 else "")
    base = f"{sign}{fmt_rp(abs(x))}" if x != 0 else fmt_rp(0)
    if pct is not None and pd.notna(pct):
        pct_sign = "+" if pct > 0 else ("" if pct < 0 else "+")
        base += f" ({pct_sign}{pct:.1f}%)"
    return base

ju["selisih_pct"] = ju.apply(
    lambda r: (r["selisih_pendapatan"] / r["target_pendapatan"] * 100) if r["target_pendapatan"] else None, axis=1
)

show_ju = pd.DataFrame({
    "Jenis Unit": ju["jenis_unit"],
    "Target Populasi": ju["target_populasi"],
    "Realisasi Populasi": ju["realisasi_populasi"],
    "Target Pendapatan": ju["target_pendapatan"].apply(fmt_rp),
    "Realisasi Pendapatan": ju["realisasi_pendapatan"].apply(fmt_rp),
    "Selisih (Realisasi − Target)": ju.apply(lambda r: fmt_rp_signed(r["selisih_pendapatan"], r["selisih_pct"]), axis=1),
    "Target Prestasi": ju["target_prestasi"].apply(lambda v: f"{v:,.0f}"),
    "Realisasi Prestasi": ju["realisasi_prestasi"].apply(lambda v: f"{v:,.0f}"),
    "Target (Rp/Satuan)": ju.apply(lambda r: f"{fmt_rp(r['rate_target'])}{r['suffix']}" if pd.notna(r["rate_target"]) else "-", axis=1),
    "Realisasi (Rp/Satuan)": ju.apply(lambda r: f"{fmt_rp(r['rate_realisasi'])}{r['suffix']}" if pd.notna(r["rate_realisasi"]) else "-", axis=1),
    "Capaian (%)": ju["capaian"],
})

def _color_selisih(val):
    if isinstance(val, str):
        if val.startswith("▲"):
            return f"color: {CHART_GREEN}; font-weight: 700;"
        if val.startswith("▼"):
            return f"color: {RED}; font-weight: 700;"
    return ""

try:
    styled_ju = show_ju.style.map(_color_selisih, subset=["Selisih (Realisasi − Target)"])
except AttributeError:
    styled_ju = show_ju.style.applymap(_color_selisih, subset=["Selisih (Realisasi − Target)"])

st.dataframe(
    styled_ju,
    use_container_width=True,
    hide_index=True,
    height=480,
    column_config={
        "Capaian (%)": st.column_config.ProgressColumn(
            "Capaian (%)", format="%.1f%%", min_value=0, max_value=150,
        ),
    },
)

st.markdown("---")

# ---------------------------------------------------------------
# CAPAIAN PRESTASI PER SATUAN (Rp/HM, Rp/KM, Rp/Tonase)
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Capaian Prestasi per Satuan</h3>', unsafe_allow_html=True)

satuan_order = ["Rp/HM", "Rp/KM", "Rp/Tonase"]
satuan_icon = {"Rp/HM": ("⏱️", CHART_GREEN), "Rp/KM": ("🚚", GOLD), "Rp/Tonase": ("⚖️", RED)}
satuan_suffix = {"Rp/HM": "/HM", "Rp/KM": "/KM", "Rp/Tonase": "/Ton"}
cols_satuan = st.columns(3)
for i, sat in enumerate(satuan_order):
    sub = df[df["satuan_prestasi"] == sat]
    pendapatan_r = sub["pendapatan_realisasi"].sum()
    pendapatan_b = sub["pendapatan_budget"].sum()
    prestasi_r = sub["prestasi_realisasi"].sum()
    prestasi_b = sub["prestasi_budget"].sum()
    rate_r = (pendapatan_r / prestasi_r) if prestasi_r else None
    rate_b = (pendapatan_b / prestasi_b) if prestasi_b else None
    ach = (rate_r / rate_b * 100) if (rate_r is not None and rate_b) else None
    pill_txt, pill_style = achievement_pill(ach, higher_is_better=True)
    icon, icon_color = satuan_icon[sat]
    suf = satuan_suffix[sat]
    with cols_satuan[i]:
        st.markdown(kpi_card(
            icon=icon, icon_bg=icon_color, accent=icon_color,
            label=f"Capaian {sat} (Pendapatan ÷ Prestasi)",
            value=(f"{fmt_rp(rate_r)}{suf}" if rate_r is not None else "-"),
            budget_text=(f"Target: {fmt_rp(rate_b)}{suf} • {sub['nama_unit'].nunique():,} unit" if rate_b is not None else f"{sub['nama_unit'].nunique():,} unit"),
            pill_text=pill_txt, pill_style=pill_style,
        ), unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------
# CAPAIAN BIAYA PER SATUAN (Rp/HM, Rp/KM, Rp/Tonase) — pembagian sama dengan Prestasi
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Capaian Biaya per Satuan</h3>', unsafe_allow_html=True)

cols_satuan_biaya = st.columns(3)
for i, sat in enumerate(satuan_order):
    sub = df[df["satuan_prestasi"] == sat]
    biaya_r = sub["total_biaya_realisasi"].sum()
    biaya_b = sub["total_biaya_budget"].sum()
    prestasi_r = sub["prestasi_realisasi"].sum()
    prestasi_b = sub["prestasi_budget"].sum()
    rate_r = (biaya_r / prestasi_r) if prestasi_r else None
    rate_b = (biaya_b / prestasi_b) if prestasi_b else None
    ach = (rate_r / rate_b * 100) if (rate_r is not None and rate_b) else None
    pill_txt, pill_style = achievement_pill(ach, higher_is_better=False)
    icon, icon_color = satuan_icon[sat]
    suf = satuan_suffix[sat]
    with cols_satuan_biaya[i]:
        st.markdown(kpi_card(
            icon=icon, icon_bg=icon_color, accent=icon_color,
            label=f"Capaian Biaya {sat} (Biaya ÷ Prestasi)",
            value=(f"{fmt_rp(rate_r)}{suf}" if rate_r is not None else "-"),
            budget_text=(f"Target: {fmt_rp(rate_b)}{suf} • {sub['nama_unit'].nunique():,} unit" if rate_b is not None else f"{sub['nama_unit'].nunique():,} unit"),
            pill_text=pill_txt, pill_style=pill_style,
        ), unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------
# RINGKASAN BIAYA (tabel Budget vs Aktual vs Capaian)
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Ringkasan Biaya</h3>', unsafe_allow_html=True)

tot_prestasi_r_all = df["prestasi_realisasi"].sum()
tot_prestasi_b_all = df["prestasi_budget"].sum()
ach_prestasi_all = (tot_prestasi_r_all / tot_prestasi_b_all * 100) if tot_prestasi_b_all else None
tot_qty_bbm_b_all = df["qty_bbm_budget"].sum()
tot_qty_bbm_r_all = df["qty_bbm_realisasi"].sum()

if sel_kat == ["TR"]:
    kat_label_suffix = "/KM"
elif sel_kat == ["AB"]:
    kat_label_suffix = "/satuan"
else:
    kat_label_suffix = ""

def biaya_row(label, real_col, budget_col, is_bbm=False, raw=False):
    comp_r_raw = df[real_col].sum()
    comp_b_raw = df[budget_col].sum()

    if raw:
        rate_b = comp_b_raw
        rate_r = comp_r_raw
        suffix = ""
        display_label = label
    elif is_bbm:
        rate_b = (comp_b_raw / tot_qty_bbm_b_all) if tot_qty_bbm_b_all else None
        rate_r = (comp_r_raw / tot_qty_bbm_r_all) if tot_qty_bbm_r_all else None
        suffix = "/Ltr"
        display_label = f"{label}/Ltr"
    else:
        rate_b = (comp_b_raw / tot_prestasi_b_all) if tot_prestasi_b_all else None
        rate_r = (comp_r_raw / tot_prestasi_r_all) if tot_prestasi_r_all else None
        suffix = ""
        display_label = f"{label}{kat_label_suffix}"

    ach = (rate_r / rate_b * 100) if (rate_r is not None and rate_b) else None
    return dict(label=display_label, budget=rate_b, aktual=rate_r, suffix=suffix, ach=ach,
                capaian_prestasi=ach_prestasi_all, aktual_raw=comp_r_raw)

ringkasan_rows = [
    biaya_row("Total Biaya", "total_biaya_realisasi", "total_biaya_budget", raw=True),
    biaya_row("Upah Operator", "upah_realisasi", "upah_budget"),
    biaya_row("Biaya BBM", "biaya_bbm_realisasi", "biaya_bbm_budget", is_bbm=True),
    biaya_row("Biaya Maintenance", "maintenance_realisasi", "maintenance_budget"),
    biaya_row("Penyusutan", "penyusutan_realisasi", "penyusutan_budget"),
    biaya_row("Lainnya", "lainnya_realisasi", "lainnya_budget"),
    biaya_row("Biaya Tidak Langsung", "biaya_tidak_langsung_realisasi", "biaya_tidak_langsung_budget"),
]

table_rows_html = ""
for row in ringkasan_rows:
    budget_disp = f"{fmt_rp(row['budget'])}{row['suffix']}" if row["budget"] is not None else "-"
    aktual_disp = f"{fmt_rp(row['aktual'])}{row['suffix']}" if row["aktual"] is not None else "-"
    hide_cp = row["label"] in ("Total Biaya", "Biaya Tidak Langsung")
    table_rows_html += f"""
    <tr>
        <td>{row['label']}</td>
        <td>{budget_disp}</td>
        <td>{aktual_disp}</td>
        <td>{rk_badge(row['ach'], higher_is_better=False, na=(row['ach'] is None), small=True)}</td>
        <td>{rk_badge(row['capaian_prestasi'], higher_is_better=True, na=(hide_cp or row['capaian_prestasi'] is None), small=True)}</td>
    </tr>"""

col_tbl, col_pie = st.columns([1, 1])
with col_tbl:
    st.markdown("##### Ringkasan Biaya (Budget vs Aktual)")
    st.markdown(f"""
    <table class="ringkasan-table-sm">
        <thead>
            <tr><th>Metrik</th><th>Budget</th><th>Aktual</th><th>Capaian</th><th>Capaian Prestasi</th></tr>
        </thead>
        <tbody>{table_rows_html}
        </tbody>
    </table>
    """, unsafe_allow_html=True)
with col_pie:
    st.markdown("##### Komposisi Biaya Aktual terhadap Total Biaya")
    comp_pie_df = pd.DataFrame({
        "Komponen": [r["label"] for r in ringkasan_rows if r["label"] != "Total Biaya"],
        "Biaya": [r["aktual_raw"] for r in ringkasan_rows if r["label"] != "Total Biaya"],
    })
    comp_pie_df = comp_pie_df[comp_pie_df["Biaya"] > 0]
    if not comp_pie_df.empty:
        fig_comp = px.pie(comp_pie_df, names="Komponen", values="Biaya", hole=0.5)
        fig_comp.update_traces(textinfo="percent", textfont=dict(size=11))
        fig_comp.update_layout(
            height=360, margin=dict(t=8, b=8, l=8, r=8),
            showlegend=True, legend=dict(font=dict(size=10)),
        )
        st.plotly_chart(style_fig(fig_comp), use_container_width=True)
    else:
        st.info("Data biaya aktual belum tersedia untuk ditampilkan sebagai diagram komposisi.")

st.markdown("---")

# ---------------------------------------------------------------
# 4. REKAP BIAYA MAINTENANCE (filter ID Unit + Rutin/Non Rutin + frekuensi)
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Rekap Biaya Maintenance</h3>', unsafe_allow_html=True)

sel_unit_maint = []

if maint_raw.empty:
    st.info("Data maintenance belum tersedia. Upload file Pemeliharaan (.xls/.xlsx) di sidebar untuk menampilkan bagian ini.")
else:
    maint_df_site_bulan = maint_df_site_bulan.copy()
    maint_df_site_bulan["unit_label"] = maint_df_site_bulan["nama_unit"].apply(_unit_label)
    unit_maint_opts = sorted(maint_df_site_bulan["unit_label"].dropna().unique().tolist())

    # Rekonsiliasi: Total Maintenance = Pemakaian Persediaan (Sparepart) + Service Luar (residual)
    total_maint_all = maint_df_site_bulan["biaya"].sum()
    total_persediaan_all = sparepart_df_site_bulan["biaya"].sum() if not sparepart_raw.empty else 0
    service_luar_all = total_maint_all - total_persediaan_all
    pct_persediaan = (total_persediaan_all / total_maint_all * 100) if total_maint_all else 0
    pct_service_luar = (service_luar_all / total_maint_all * 100) if total_maint_all else 0

    st.markdown("##### Rekonsiliasi: Total Maintenance = Pemakaian Persediaan + Service Luar")
    rc1, rc2, rc3 = st.columns(3)
    with rc1:
        st.markdown(kpi_card(
            icon="🔧", icon_bg=GREY, accent=GREY,
            label="Total Biaya Maintenance", value=fmt_rp(total_maint_all),
            budget_text="Persediaan + Service Luar",
            pill_text="100%", pill_style="kpi-pill-amber",
        ), unsafe_allow_html=True)
    with rc2:
        st.markdown(kpi_card(
            icon="📦", icon_bg=CHART_GREEN, accent=CHART_GREEN,
            label="Pemakaian Persediaan (Sparepart)", value=fmt_rp(total_persediaan_all),
            budget_text="Dari data Rincian Pemakaian",
            pill_text=f"{pct_persediaan:.1f}% dari total", pill_style="kpi-pill-green",
        ), unsafe_allow_html=True)
    with rc3:
        st.markdown(kpi_card(
            icon="🛠️", icon_bg=GOLD, accent=GOLD,
            label="Service Luar (di luar persediaan)", value=fmt_rp(service_luar_all),
            budget_text="Selisih Total − Persediaan",
            pill_text=f"{pct_service_luar:.1f}% dari total", pill_style="kpi-pill-amber",
        ), unsafe_allow_html=True)

    st.markdown("---")

    sel_unit_maint = st.multiselect(
        "Filter berdasarkan ID Unit (opsional, kosongkan = semua unit) — ketik ID Unit atau nama unit",
        unit_maint_opts, default=[],
    )

    maint_df = maint_df_site_bulan
    if sel_unit_maint:
        maint_df = maint_df[maint_df["unit_label"].isin(sel_unit_maint)]

    if maint_df.empty:
        st.warning("Tidak ada data maintenance untuk kombinasi filter yang dipilih.")
    else:
        n_transaksi = len(maint_df)
        rutin_biaya = maint_df.loc[maint_df["jenis_pemeliharaan"] == "RUTIN", "biaya"].sum()
        nonrutin_biaya = maint_df.loc[maint_df["jenis_pemeliharaan"] == "NON RUTIN", "biaya"].sum()
        rutin_n = int((maint_df["jenis_pemeliharaan"] == "RUTIN").sum())
        nonrutin_n = int((maint_df["jenis_pemeliharaan"] == "NON RUTIN").sum())

        # Total Biaya Maintenance = total biaya di data_maintenance.csv (maint_df, sudah difilter ID Unit)
        total_maint = maint_df["biaya"].sum()

        # Workshop Sendiri = total biaya di data_sparepart.csv (pemakaian persediaan), scope ID Unit yang sama
        if not sparepart_raw.empty:
            sparepart_scope = sparepart_df_site_bulan.copy()
            sparepart_scope["unit_label"] = sparepart_scope["nama_unit"].apply(_unit_label)
            if sel_unit_maint:
                sparepart_scope = sparepart_scope[sparepart_scope["unit_label"].isin(sel_unit_maint)]
        else:
            sparepart_scope = pd.DataFrame(columns=["biaya"])
        workshop_biaya = sparepart_scope["biaya"].sum() if not sparepart_scope.empty else 0
        workshop_n = len(sparepart_scope)

        # Service Luar = selisih Total Biaya Maintenance (data_maintenance.csv) - Workshop Sendiri (data_sparepart.csv)
        service_luar_biaya = total_maint - workshop_biaya

        # Budget Maintenance diambil dari kolom maintenance_budget di data_bkms.csv, dengan
        # scope site/bulan/kategori yang sama, dan ikut mengikuti filter ID Unit jika dipilih.
        if sel_unit_maint:
            budget_scope = df[df["nama_unit"].apply(_unit_label).isin(sel_unit_maint)]
        else:
            budget_scope = df
        total_maint_budget = budget_scope["maintenance_budget"].sum()
        maint_ach = achievement(total_maint, total_maint_budget)
        if maint_ach is not None:
            diff_pp = maint_ach - 100  # positif = over budget (buruk), negatif = under budget (baik)
            maint_delta = f"{diff_pp:+.1f}% vs Budget {fmt_rp(total_maint_budget)}"
        else:
            maint_delta = "Budget belum tersedia"

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Total Biaya Maintenance", fmt_rp(total_maint), maint_delta, delta_color="inverse")
        k2.metric("Workshop Sendiri", fmt_rp(workshop_biaya))
        k3.metric("Service Luar", fmt_rp(service_luar_biaya))
        k4.metric("Biaya Rutin", fmt_rp(rutin_biaya))
        k5.metric("Biaya Non Rutin", fmt_rp(nonrutin_biaya))

        rekap = maint_df.groupby(["kategori_sparepart", "jenis_pemeliharaan"], as_index=False).agg(
            jumlah_transaksi=("biaya", "count"),
            total_biaya=("biaya", "sum"),
        )
        rekap["total_biaya_jt"] = rekap["total_biaya"] / 1e6
        rekap["label_biaya"] = rekap["total_biaya"].apply(fmt_rp)

        # Urutkan kategori berdasarkan total biaya (terbesar di atas) supaya chart menyamping rapi
        kategori_order = (
            rekap.groupby("kategori_sparepart")["total_biaya"].sum().sort_values(ascending=True).index.tolist()
        )

        fig_rekap = px.bar(
            rekap, y="kategori_sparepart", x="total_biaya_jt", color="jenis_pemeliharaan",
            orientation="h", barmode="group", color_discrete_map={"RUTIN": CHART_GREEN, "NON RUTIN": GOLD},
            labels={"kategori_sparepart": "Kategori Sparepart / Sistem", "total_biaya_jt": "Total Biaya (Juta Rupiah)", "jenis_pemeliharaan": "Jenis"},
            text="label_biaya",
            category_orders={"kategori_sparepart": kategori_order},
        )
        fig_rekap.update_traces(textposition="outside", textfont=dict(size=10, color=TEXT_LIGHT))
        fig_rekap.update_layout(title="Maintenance atas Apa Saja — Rutin vs Non Rutin", height=550,
                                 legend=dict(orientation="h", y=1.08), margin=dict(t=60, b=10, l=10))
        fig_rekap.update_xaxes(ticksuffix=" Jt")
        st.plotly_chart(style_fig(fig_rekap), use_container_width=True)

        st.markdown("##### Rincian: Kategori, Jenis, Frekuensi (Berapa Kali), Total Biaya")
        rekap_tbl = rekap.sort_values("total_biaya", ascending=False)[
            ["kategori_sparepart", "jenis_pemeliharaan", "jumlah_transaksi", "total_biaya"]
        ].rename(columns={
            "kategori_sparepart": "Kategori (Maintenance atas Apa Saja)",
            "jenis_pemeliharaan": "Jenis (Rutin / Non Rutin)",
            "jumlah_transaksi": "Berapa Kali (Jumlah Transaksi)",
            "total_biaya": "Total Biaya",
        })
        total_row = pd.DataFrame([{
            "Kategori (Maintenance atas Apa Saja)": "TOTAL",
            "Jenis (Rutin / Non Rutin)": "",
            "Berapa Kali (Jumlah Transaksi)": rekap_tbl["Berapa Kali (Jumlah Transaksi)"].sum(),
            "Total Biaya": rekap_tbl["Total Biaya"].sum(),
        }])
        rekap_tbl_display = pd.concat([rekap_tbl, total_row], ignore_index=True)
        st.dataframe(
            rekap_tbl_display, use_container_width=True, hide_index=True, height=420,
            column_config={"Total Biaya": st.column_config.NumberColumn(format="Rp %,.0f")},
        )
        csv_rekap = rekap_tbl_display.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Unduh Rekap Maintenance (CSV)", csv_rekap, file_name="rekap_maintenance_bkms.csv", mime="text/csv")

st.markdown("---")

# ---------------------------------------------------------------
# REKAP PEMAKAIAN SPAREPART (PERSEDIAAN)
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Rekap Pemakaian Sparepart (Persediaan)</h3>', unsafe_allow_html=True)

if sparepart_raw.empty:
    st.info("Data pemakaian sparepart belum tersedia. Upload file Rincian Pemakaian (.xls/.xlsx) di sidebar untuk menampilkan bagian ini.")
else:
    sparepart_df_site_bulan = sparepart_df_site_bulan.copy()
    sparepart_df_site_bulan["unit_label"] = sparepart_df_site_bulan["nama_unit"].apply(_unit_label)

    sparepart_df = sparepart_df_site_bulan
    if sel_unit_maint:
        sparepart_df = sparepart_df[sparepart_df["unit_label"].isin(sel_unit_maint)]

    if sel_unit_maint:
        st.caption(f"🔗 Sedang difilter mengikuti ID Unit: {', '.join(sel_unit_maint)}")

    if sparepart_df.empty:
        st.warning("Tidak ada data pemakaian sparepart untuk kombinasi filter yang dipilih.")
    else:
        total_sp = sparepart_df["biaya"].sum()
        total_qty_trx = len(sparepart_df)
        n_jenis_barang = sparepart_df["nama_barang"].nunique()

        s1, s2, s3 = st.columns(3)
        s1.metric("Total Biaya Pemakaian Sparepart", fmt_rp(total_sp))
        s2.metric("Jumlah Transaksi Pengambilan", f"{total_qty_trx:,}")
        s3.metric("Jenis Barang Berbeda", f"{n_jenis_barang:,}")

        colS1, colS2 = st.columns([3, 2])

        # Peta warna konsisten per kategori sparepart, dipakai bersama oleh chart Top 15 Barang & pie chart
        all_cats_sp = sorted(sparepart_df["kategori_sparepart"].dropna().unique().tolist())
        _palette_sp = px.colors.qualitative.Plotly
        color_map_sp = {cat: _palette_sp[i % len(_palette_sp)] for i, cat in enumerate(all_cats_sp)}

        with colS1:
            top_barang = sparepart_df.groupby("nama_barang", as_index=False).agg(
                total_qty=("qty", "sum"), total_biaya=("biaya", "sum"),
            ).sort_values("total_biaya", ascending=False).head(15)

            # Tentukan kategori sparepart dominan (berdasarkan biaya terbesar) untuk tiap barang
            item_cat = sparepart_df.groupby(["nama_barang", "kategori_sparepart"], as_index=False)["biaya"].sum()
            item_cat = item_cat.sort_values("biaya", ascending=False).drop_duplicates("nama_barang")
            top_barang = top_barang.merge(item_cat[["nama_barang", "kategori_sparepart"]], on="nama_barang", how="left")

            top_barang["total_biaya_jt"] = top_barang["total_biaya"] / 1e6
            top_barang["label_biaya"] = top_barang["total_biaya"].apply(fmt_rp)

            fig_sp1 = px.bar(
                top_barang, y="nama_barang", x="total_biaya_jt", color="kategori_sparepart",
                orientation="h", color_discrete_map=color_map_sp, text="label_biaya",
                labels={"nama_barang": "Barang", "total_biaya_jt": "Juta Rupiah", "kategori_sparepart": "Kategori"},
            )
            fig_sp1.update_traces(textposition="outside", textfont=dict(size=10, color=TEXT_LIGHT))
            fig_sp1.update_layout(title="Top 15 Barang berdasarkan Biaya", xaxis_title="Juta Rupiah",
                                   height=560, margin=dict(t=60, b=10, l=10, r=70),
                                   legend=dict(font=dict(size=9), title="Kategori"))
            fig_sp1.update_xaxes(ticksuffix=" Jt")
            fig_sp1.update_yaxes(autorange="reversed")
            st.plotly_chart(style_fig(fig_sp1), use_container_width=True)

        with colS2:
            cat_sp = sparepart_df.groupby("kategori_sparepart", as_index=False)["biaya"].sum()
            fig_sp2 = px.pie(cat_sp, names="kategori_sparepart", values="biaya", hole=0.5,
                              color="kategori_sparepart", color_discrete_map=color_map_sp)
            fig_sp2.update_layout(title="Komposisi per Kategori Sparepart", height=460, margin=dict(t=60, b=10),
                                   showlegend=True, legend=dict(font=dict(size=9)))
            st.plotly_chart(style_fig(fig_sp2), use_container_width=True)

        st.markdown("##### Rincian Pemakaian per Barang")
        search_sp = st.text_input("🔍 Cari nama barang / part number...", "", key="search_sparepart")
        _sp_cols_base = ["tanggal", "lokasi", "nama_unit", "kategori_sparepart", "jenis_pemeliharaan",
                          "kode_barang", "part_number", "nama_barang", "qty", "satuan", "biaya"]
        _sp_rename = {
            "tanggal": "Tanggal", "lokasi": "Site", "nama_unit": "Nama Unit", "kategori_sparepart": "Kategori Sparepart",
            "jenis_pemeliharaan": "Jenis", "kode_barang": "Kode Barang", "part_number": "Part Number",
            "nama_barang": "Nama Barang", "qty": "Qty", "satuan": "Satuan", "biaya": "Biaya",
        }
        if "jenis_unit" in sparepart_df.columns:
            _sp_cols_base.insert(3, "jenis_unit")  # taruh setelah nama_unit
            _sp_rename["jenis_unit"] = "Jenis Unit"
        show_sp = sparepart_df[_sp_cols_base].rename(columns=_sp_rename)
        if search_sp:
            mask = (show_sp["Nama Barang"].str.contains(search_sp, case=False, na=False) |
                    show_sp["Part Number"].str.contains(search_sp, case=False, na=False))
            show_sp = show_sp[mask]
        st.dataframe(
            show_sp.sort_values("Biaya", ascending=False),
            use_container_width=True, height=380,
            column_config={"Biaya": st.column_config.NumberColumn(format="Rp %,.0f")},
        )
        csv_sp = show_sp.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Unduh Rincian Pemakaian Sparepart (CSV)", csv_sp, file_name="rincian_sparepart_bkms.csv", mime="text/csv")

st.markdown("---")

# ---------------------------------------------------------------
# 6. ANALISA: PENYEBAB CAPAIAN PENDAPATAN
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Analisa: Penyebab Capaian Pendapatan</h3>', unsafe_allow_html=True)

if ach_pendapatan is None:
    st.info("Target Pendapatan belum tersedia untuk kombinasi filter ini, sehingga analisa capaian tidak bisa dihitung.")
elif ach_pendapatan >= 100:
    st.success(f"Realisasi Pendapatan sudah mencapai **{ach_pendapatan:.1f}%** dari target — tidak ada gap yang perlu dianalisa lebih lanjut untuk periode/filter ini.")
else:
    gap_rp = tot_pendapatan_b - tot_pendapatan_r
    insights = []
    insights.append(
        f"Realisasi Pendapatan mencapai <b>{ach_pendapatan:.1f}%</b> dari target, dengan selisih (gap) sebesar <b>{fmt_rp(gap_rp)}</b>."
    )

    if ach_prestasi is not None:
        diff = ach_pendapatan - ach_prestasi
        if ach_prestasi < 100 and abs(diff) <= 10:
            insights.append(
                f"Prestasi juga hanya mencapai <b>{ach_prestasi:.1f}%</b> dari target — pola ini sejalan dengan capaian Pendapatan, "
                f"mengindikasikan bahwa <b>volume pekerjaan/prestasi unit yang belum tercapai</b> menjadi salah satu faktor utama rendahnya Pendapatan."
            )
        elif ach_prestasi < 100:
            lebih = "lebih kecil" if ach_prestasi > ach_pendapatan else "lebih besar"
            insights.append(
                f"Prestasi mencapai <b>{ach_prestasi:.1f}%</b> dari target — meski sama-sama di bawah target, gap-nya {lebih} dibanding Pendapatan, "
                f"sehingga faktor prestasi kemungkinan <b>{'turut berkontribusi namun bukan penyebab dominan' if ach_prestasi > ach_pendapatan else 'menjadi kontributor signifikan'}</b>."
            )
        else:
            insights.append(
                f"Prestasi justru mencapai <b>{ach_prestasi:.1f}%</b> (di atas target), sehingga rendahnya Pendapatan kemungkinan besar "
                f"<b>bukan disebabkan oleh volume pekerjaan/prestasi</b>, melainkan faktor lain seperti tarif/harga satuan atau piutang yang belum tertagih."
            )

    if target_populasi:
        gap_pop = target_populasi - realisasi_populasi
        gap_pop_pct = gap_pop / target_populasi * 100
        if gap_pop > 0:
            insights.append(
                f"Sebanyak <b>{gap_pop} unit ({gap_pop_pct:.1f}%)</b> dari total populasi yang ditargetkan <b>tidak mencatatkan realisasi Pendapatan sama sekali</b> "
                f"pada periode/filter ini — indikasi kuat adanya <b>unit yang tidak beroperasi (downtime/idle)</b>, yang turut menekan capaian Pendapatan secara keseluruhan."
            )
        else:
            insights.append(
                "Seluruh unit yang ditargetkan sudah mencatatkan realisasi Pendapatan (tidak ada indikasi unit idle/downtime dari sisi populasi)."
            )

    site_group = df.groupby("lokasi").agg(
        realisasi=("pendapatan_realisasi", "sum"),
        budget=("pendapatan_budget", "sum"),
    ).reset_index()
    site_group = site_group[site_group["budget"] > 0]
    if not site_group.empty:
        site_group["capaian"] = site_group["realisasi"] / site_group["budget"] * 100
        worst = site_group.sort_values("capaian").iloc[0]
        if worst["capaian"] < 100:
            insights.append(
                f"Site dengan capaian Pendapatan terendah adalah <b>{worst['lokasi']}</b> ({worst['capaian']:.1f}% dari target), "
                f"menjadi kontributor terbesar terhadap gap Pendapatan secara keseluruhan pada filter ini."
            )

    bullets_html = "".join([f"<li>{ins}</li>" for ins in insights])
    st.markdown(f'<div class="insight-box"><ul>{bullets_html}</ul></div>', unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------
# 7. ANALISA: UNIT TIDAK PRODUKTIF
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Analisa: Unit Tidak Produktif</h3>', unsafe_allow_html=True)

# --- Agregasi per unit dari data utama: Pendapatan, Prestasi, Total Biaya ---
unit_fin = df.groupby(["id_unit", "nama_unit"], as_index=False).agg(
    lokasi=("lokasi", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]),
    kategori=("kategori", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]),
    pendapatan_r=("pendapatan_realisasi", "sum"),
    pendapatan_b=("pendapatan_budget", "sum"),
    prestasi_r=("prestasi_realisasi", "sum"),
    prestasi_b=("prestasi_budget", "sum"),
    total_biaya_r=("total_biaya_realisasi", "sum"),
)
unit_fin["unit_label"] = unit_fin["nama_unit"].apply(_unit_label)

# --- Agregasi maintenance per unit: frekuensi & biaya (scope site/bulan yang sama) ---
if not maint_raw.empty:
    maint_unit_agg = maint_df_site_bulan.copy()
    maint_unit_agg["unit_label"] = maint_unit_agg["nama_unit"].apply(_unit_label)
    maint_unit_agg = maint_unit_agg.groupby("unit_label", as_index=False).agg(
        maintenance_biaya=("biaya", "sum"),
        maintenance_freq=("biaya", "count"),
    )
else:
    maint_unit_agg = pd.DataFrame(columns=["unit_label", "maintenance_biaya", "maintenance_freq"])

unit_analysis = unit_fin.merge(maint_unit_agg, on="unit_label", how="left")
unit_analysis["maintenance_biaya"] = unit_analysis["maintenance_biaya"].fillna(0)
unit_analysis["maintenance_freq"] = unit_analysis["maintenance_freq"].fillna(0).astype(int)

unit_analysis["capaian_pendapatan"] = unit_analysis.apply(lambda r: achievement(r["pendapatan_r"], r["pendapatan_b"]), axis=1)
unit_analysis["capaian_prestasi"] = unit_analysis.apply(lambda r: achievement(r["prestasi_r"], r["prestasi_b"]), axis=1)
unit_analysis["margin"] = unit_analysis["pendapatan_r"] - unit_analysis["total_biaya_r"]

nonzero_freq = unit_analysis.loc[unit_analysis["maintenance_freq"] > 0, "maintenance_freq"]
if len(nonzero_freq) > 0:
    freq_p75 = nonzero_freq.quantile(0.75)
    unit_analysis["flag_maintenance_sering"] = unit_analysis["maintenance_freq"] >= freq_p75
else:
    unit_analysis["flag_maintenance_sering"] = False

unit_analysis["flag_pendapatan"] = unit_analysis["capaian_pendapatan"].apply(lambda v: (v is not None) and v < 100)
unit_analysis["flag_prestasi"] = unit_analysis["capaian_prestasi"].apply(lambda v: (v is not None) and v < 100)
unit_analysis["flag_margin_negatif"] = unit_analysis["margin"] < 0
unit_analysis["skor_masalah"] = (
    unit_analysis["flag_pendapatan"].astype(int)
    + unit_analysis["flag_prestasi"].astype(int)
    + unit_analysis["flag_maintenance_sering"].astype(int)
)
unit_analysis["tidak_produktif"] = unit_analysis["flag_margin_negatif"] & (unit_analysis["skor_masalah"] >= 2)

tp_df = unit_analysis[unit_analysis["tidak_produktif"]].sort_values("margin")

if tp_df.empty:
    st.success("Tidak ada unit yang teridentifikasi **Tidak Produktif** berdasarkan kriteria di atas pada filter saat ini.")
else:
    total_rugi = tp_df["margin"].sum()  # sudah negatif
    avg_capaian_pdt = tp_df["capaian_pendapatan"].mean()
    avg_freq_maint = tp_df["maintenance_freq"].mean()

    u1, u2, u3, u4 = st.columns(4)
    with u1:
        st.markdown(kpi_card(
            icon="⚠️", icon_bg=RED, accent=RED,
            label="Jumlah Unit Tidak Produktif",
            value=f"{len(tp_df):,} unit",
            budget_text=f"dari {len(unit_analysis):,} unit teranalisa",
            pill_text="Perlu Tindak Lanjut", pill_style="kpi-pill-red",
        ), unsafe_allow_html=True)
    with u2:
        st.markdown(kpi_card(
            icon="📉", icon_bg=RED, accent=RED,
            label="Total Margin Negatif (Kerugian)",
            value=fmt_rp(total_rugi),
            budget_text="Pendapatan − Total Biaya (unit tidak produktif)",
            pill_text="Rugi", pill_style="kpi-pill-red",
        ), unsafe_allow_html=True)
    with u3:
        st.markdown(kpi_card(
            icon="💰", icon_bg=GOLD, accent=GOLD,
            label="Rata-rata Capaian Pendapatan",
            value=(f"{avg_capaian_pdt:.1f}%" if pd.notna(avg_capaian_pdt) else "-"),
            budget_text="Rata-rata unit tidak produktif",
            pill_text="vs Budget", pill_style="kpi-pill-amber",
        ), unsafe_allow_html=True)
    with u4:
        st.markdown(kpi_card(
            icon="🔧", icon_bg=GOLD, accent=GOLD,
            label="Rata-rata Frekuensi Maintenance",
            value=f"{avg_freq_maint:.1f}x",
            budget_text="Rata-rata unit tidak produktif",
            pill_text="Sering", pill_style="kpi-pill-amber",
        ), unsafe_allow_html=True)

    st.markdown("##### Chart: Unit dengan Margin Ternegatif (Top 10)")
    top10 = tp_df.head(10).copy()
    top10["margin_jt"] = top10["margin"] / 1e6
    top10["label_margin"] = top10["margin"].apply(fmt_rp)
    top10["unit_chart_label"] = top10["id_unit"].astype(str) + " — " + top10["nama_unit"].astype(str)
    fig_tp = px.bar(
        top10.sort_values("margin_jt", ascending=False),
        y="unit_chart_label", x="margin_jt", orientation="h",
        text="label_margin",
        labels={"unit_chart_label": "Unit", "margin_jt": "Margin (Juta Rupiah)"},
    )
    fig_tp.update_traces(marker_color=RED, textposition="outside", textfont=dict(size=10, color=TEXT_LIGHT))
    fig_tp.update_layout(title="Top 10 Unit dengan Margin (Pendapatan − Biaya) Ternegatif", height=450, margin=dict(t=60, b=10, l=10))
    st.plotly_chart(style_fig(fig_tp), use_container_width=True)

    st.markdown("##### Rincian Unit Tidak Produktif")
    disp = tp_df.copy()
    disp["Status"] = disp["skor_masalah"].apply(
        lambda s: "🔴 Sangat Tidak Produktif (3 indikator)" if s == 3 else "🟠 Tidak Produktif (2 indikator)"
    )
    show_tp = pd.DataFrame({
        "ID Unit": disp["id_unit"],
        "Nama Unit": disp["nama_unit"],
        "Site": disp["lokasi"],
        "Kategori": disp["kategori"].map(lambda k: KATEGORI_LABEL.get(k, k)),
        "Pendapatan Realisasi": disp["pendapatan_r"].apply(fmt_rp),
        "Capaian Pendapatan": disp["capaian_pendapatan"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "-"),
        "Capaian Prestasi": disp["capaian_prestasi"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "-"),
        "Total Biaya": disp["total_biaya_r"].apply(fmt_rp),
        "Margin (Pendapatan − Biaya)": disp["margin"].apply(fmt_rp),
        "Frekuensi Maintenance": disp["maintenance_freq"],
        "Biaya Maintenance": disp["maintenance_biaya"].apply(fmt_rp),
        "Status": disp["Status"],
    })
    st.dataframe(show_tp, use_container_width=True, hide_index=True, height=420)
    csv_tp = show_tp.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Unduh Daftar Unit Tidak Produktif (CSV)", csv_tp, file_name="unit_tidak_produktif_bkms.csv", mime="text/csv")

    worst3 = tp_df.head(3)
    poin = []
    for _, r in worst3.iterrows():
        cap_pdt = f"{r['capaian_pendapatan']:.1f}%" if pd.notna(r["capaian_pendapatan"]) else "tanpa budget"
        cap_prs = f"{r['capaian_prestasi']:.1f}%" if pd.notna(r["capaian_prestasi"]) else "tanpa budget"
        poin.append(
            f"<b>{r['id_unit']} — {r['nama_unit']}</b> (site {r['lokasi']}): margin <b>{fmt_rp(r['margin'])}</b>, "
            f"capaian Pendapatan {cap_pdt}, capaian Prestasi {cap_prs}, maintenance {int(r['maintenance_freq'])} kali "
            f"({fmt_rp(r['maintenance_biaya'])})."
        )
    bullets_tp_html = "".join([f"<li>{p}</li>" for p in poin])
    st.markdown(f'<div class="insight-box"><b>3 unit paling bermasalah:</b><ul>{bullets_tp_html}</ul></div>', unsafe_allow_html=True)

st.markdown("---")
st.caption("Dashboard Operational Review • PT Buana Karya Mandiri Sejahtera (BKMS) • Dibuat oleh ALIP BA TA")
