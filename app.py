import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import base64
import re
from pathlib import Path

pio.templates.default = "plotly_dark"

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
    page_title="Dashboard Biaya & Pendapatan | PT BKMS",
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
        border-left: 5px solid {GOLD};
        padding-left: 10px;
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
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
KATEGORI_LABEL = {"AB": "Alat Berat (AB)", "TR": "Truck / Ritase (TR)"}

@st.cache_data
def load_data(file) -> pd.DataFrame:
    return pd.read_csv(file)

@st.cache_data
def load_maintenance_data(file) -> pd.DataFrame:
    if not Path(file).exists():
        return pd.DataFrame()
    return pd.read_csv(file)

@st.cache_data
def load_sparepart_data(file) -> pd.DataFrame:
    if not Path(file).exists():
        return pd.DataFrame()
    return pd.read_csv(file)

def load_from_upload(uploaded_file) -> pd.DataFrame:
    """Parse an uploaded 'Gabungan.xlsx' file with the same fixed layout used to build data_bkms.csv."""
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
        lokasi = ws.cell(row=r, column=29).value
        bulan_nama = ws.cell(row=r, column=30).value
        kategori = ws.cell(row=r, column=31).value
        if not lokasi or not bulan_nama:
            continue
        rows.append(dict(
            id_unit=id_unit, kode_unit=ws.cell(row=r, column=2).value,
            nama_unit=ws.cell(row=r, column=3).value, nilai_asset=ws.cell(row=r, column=4).value or 0,
            lokasi=lokasi, bulan=bulan_nama, bulan_no=month_map.get(bulan_nama, 0), kategori=kategori,
            prestasi_realisasi=ws.cell(row=r, column=5).value or 0, prestasi_budget=ws.cell(row=r, column=6).value or 0,
            pendapatan_realisasi=ws.cell(row=r, column=7).value or 0, pendapatan_budget=ws.cell(row=r, column=8).value or 0,
            upah_realisasi=ws.cell(row=r, column=9).value or 0, upah_budget=ws.cell(row=r, column=10).value or 0,
            qty_bbm_realisasi=ws.cell(row=r, column=11).value or 0, qty_bbm_budget=ws.cell(row=r, column=12).value or 0,
            harga_bbm_realisasi=ws.cell(row=r, column=13).value or 0, harga_bbm_budget=ws.cell(row=r, column=14).value or 0,
            biaya_bbm_realisasi=ws.cell(row=r, column=15).value or 0, biaya_bbm_budget=ws.cell(row=r, column=16).value or 0,
            maintenance_realisasi=ws.cell(row=r, column=17).value or 0, maintenance_budget=ws.cell(row=r, column=18).value or 0,
            penyusutan_realisasi=ws.cell(row=r, column=19).value or 0, penyusutan_budget=ws.cell(row=r, column=20).value or 0,
            lainnya_realisasi=ws.cell(row=r, column=21).value or 0, lainnya_budget=ws.cell(row=r, column=22).value or 0,
            biaya_langsung_realisasi=ws.cell(row=r, column=23).value or 0, biaya_langsung_budget=ws.cell(row=r, column=24).value or 0,
            biaya_tidak_langsung_realisasi=ws.cell(row=r, column=25).value or 0, biaya_tidak_langsung_budget=ws.cell(row=r, column=26).value or 0,
            total_biaya_realisasi=ws.cell(row=r, column=27).value or 0, total_biaya_budget=ws.cell(row=r, column=28).value or 0,
        ))
    return pd.DataFrame(rows)

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

with st.sidebar:
    st.markdown("### 📁 Sumber Data")
    uploaded = st.file_uploader("Upload file Gabungan.xlsx terbaru (opsional)", type=["xlsx"])
    if uploaded is not None:
        try:
            df_raw = load_from_upload(uploaded)
            st.success(f"Berhasil memuat {len(df_raw):,} baris dari file upload.")
        except Exception as e:
            st.error(f"Gagal membaca file: {e}")
            df_raw = load_data(DATA_PATH)
    else:
        df_raw = load_data(DATA_PATH)

    uploaded_maint = st.file_uploader("Upload data Maintenance (Pemeliharaan) terbaru (opsional)", type=["xls", "xlsx"])
    if uploaded_maint is not None:
        try:
            maint_raw = load_from_upload_maintenance(uploaded_maint)
            st.success(f"Berhasil memuat {len(maint_raw):,} baris data maintenance dari file upload.")
        except Exception as e:
            st.error(f"Gagal membaca file maintenance: {e}")
            maint_raw = load_maintenance_data(MAINT_DATA_PATH)
    else:
        maint_raw = load_maintenance_data(MAINT_DATA_PATH)

    uploaded_sparepart = st.file_uploader("Upload data Rincian Pemakaian Sparepart terbaru (opsional)", type=["xls", "xlsx"])
    if uploaded_sparepart is not None:
        try:
            sparepart_raw = load_from_upload_sparepart(uploaded_sparepart)
            st.success(f"Berhasil memuat {len(sparepart_raw):,} baris data pemakaian sparepart dari file upload.")
        except Exception as e:
            st.error(f"Gagal membaca file sparepart: {e}")
            sparepart_raw = load_sparepart_data(SPAREPART_DATA_PATH)
    else:
        sparepart_raw = load_sparepart_data(SPAREPART_DATA_PATH)

    st.markdown("---")
    st.markdown("### 🔎 Filter")

    site_opts = sorted(df_raw["lokasi"].dropna().unique().tolist())
    sel_site = st.multiselect("Site / Lokasi", site_opts, default=site_opts)

    month_opts = [m for m in MONTH_ORDER if m in df_raw["bulan"].unique()]
    sel_month = st.multiselect("Bulan", month_opts, default=month_opts)

    kat_opts = sorted(df_raw["kategori"].dropna().unique().tolist())
    kat_labels = [KATEGORI_LABEL.get(k, k) for k in kat_opts]
    sel_kat_labels = st.multiselect("Kategori Unit", kat_labels, default=kat_labels)
    sel_kat = [k for k in kat_opts if KATEGORI_LABEL.get(k, k) in sel_kat_labels]

# ---------------------------------------------------------------
# KLASIFIKASI SATUAN PRESTASI: Rp/KM, Rp/HM, Rp/Tonase per site
# ---------------------------------------------------------------
# Aturan (sesuai arahan):
# 1. Rp/KM     -> Transportasi (kategori TR) di site Sungai Danau & Kumai
# 2. Rp/HM     -> Alat Berat (kategori AB) di site Sungai Danau & Kumai
# 3. Rp/Tonase -> site LHL
# 4. Khusus (override) -> site Tanjung & Buhut selalu masuk Rp/HM
SATUAN_LABEL = {"KM": "Rp / KM (Transportasi)", "HM": "Rp / HM (Alat Berat)", "TONASE": "Rp / Tonase"}
SATUAN_ICON = {"KM": "🚚", "HM": "🚜", "TONASE": "⚖️"}
SATUAN_COLOR = {"KM": CHART_GREEN, "HM": GOLD, "TONASE": "#2E7D9A"}

def classify_satuan(lokasi, kategori):
    """Tentukan tipe satuan (KM/HM/TONASE) berdasarkan site & kategori unit."""
    if not isinstance(lokasi, str):
        return None
    loc = lokasi.strip().lower()
    kat = str(kategori).strip().upper() if kategori is not None else ""

    # Rule 4 (khusus/override): Tanjung & Buhut -> Rp/HM
    if loc in ("tanjung", "buhut"):
        return "HM"
    # Rule 3: LHL -> Rp/Tonase
    if loc in ("lhl", "buhut lhl"):
        return "TONASE"
    # Rule 1 & 2: Sungai Danau & Kumai -> Rp/KM (TR) atau Rp/HM (AB)
    if loc in ("sungai danau", "kumai"):
        if kat == "TR":
            return "KM"
        if kat == "AB":
            return "HM"
    return None

# ---------------------------------------------------------------
# APPLY FILTERS (data utama)
# ---------------------------------------------------------------
df = df_raw[
    df_raw["lokasi"].isin(sel_site) &
    df_raw["bulan"].isin(sel_month) &
    df_raw["kategori"].isin(sel_kat)
].copy()
df["satuan_tipe"] = df.apply(lambda r: classify_satuan(r["lokasi"], r["kategori"]), axis=1)

maint_df_site_bulan = pd.DataFrame()
if not maint_raw.empty:
    maint_df_site_bulan = maint_raw[
        maint_raw["lokasi"].isin(sel_site) &
        maint_raw["bulan"].isin(sel_month)
    ].copy()

sparepart_df_site_bulan = pd.DataFrame()
if not sparepart_raw.empty:
    sparepart_df_site_bulan = sparepart_raw[
        sparepart_raw["lokasi"].isin(sel_site) &
        sparepart_raw["bulan"].isin(sel_month)
    ].copy()

def fmt_rp(x):
    if abs(x) >= 1e9:
        return f"Rp {x/1e9:,.2f} M"
    if abs(x) >= 1e6:
        return f"Rp {x/1e6:,.1f} Jt"
    return f"Rp {x:,.0f}"

def achievement(real, budget):
    if budget == 0:
        return None
    return real / budget * 100

_unit_code_pattern = re.compile(r'(\d{3}-\d{3})\s*$')
def _unit_label(name):
    if not isinstance(name, str):
        return name
    m = _unit_code_pattern.search(name)
    code = m.group(1) if m else "?"
    return f"{code} — {name}"

# ---------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------
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
    <h1>📊 Dashboard Biaya & Pendapatan</h1>
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

target_populasi = df.loc[df["pendapatan_budget"] > 0, "nama_unit"].nunique()
realisasi_populasi = df.loc[df["pendapatan_realisasi"] > 0, "nama_unit"].nunique()
pct_populasi = (realisasi_populasi / target_populasi * 100) if target_populasi else None

# ---------------------------------------------------------------
# POWERPOINT EXPORT — didesain mengikuti gaya "Tinjauan Manajemen" (RTM):
# background terang, header bar navy, kartu KPI ikon+pill status, tabel
# dengan indikator warna, dan kotak analisis.
# ---------------------------------------------------------------
def build_pptx(data, maint_data, sparepart_data, site_list, month_list, kat_list) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    import io as _io

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
            tb2 = s.shapes.add_textbox(Inches(9.5), Inches(0.28), Inches(3.4), Inches(0.4))
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

    def add_kpi_card(slide, left, top, width, height, icon_txt, icon_color, accent_color,
                      label, value, sub_text, pill_text, pill_good):
        # accent strip (top border)
        strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.06))
        strip.fill.solid(); strip.fill.fore_color.rgb = accent_color
        strip.line.fill.background(); strip.shadow.inherit = False
        # card body
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top + 0.05), Inches(width), Inches(height - 0.05))
        card.adjustments[0] = 0.045
        card.fill.solid(); card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = BORDER; card.line.width = Pt(0.75)
        card.shadow.inherit = False
        # icon circle
        icon_size = 0.5
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left + 0.25), Inches(top + 0.25), Inches(icon_size), Inches(icon_size))
        circ.fill.solid(); circ.fill.fore_color.rgb = icon_color
        circ.line.fill.background(); circ.shadow.inherit = False
        ic_tf = circ.text_frame; ic_tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        ic_tf.margin_left = 0; ic_tf.margin_right = 0
        icp = ic_tf.paragraphs[0]; icp.alignment = PP_ALIGN.CENTER
        icr = icp.add_run(); icr.text = icon_txt
        icr.font.size = Pt(15); icr.font.bold = True; icr.font.color.rgb = WHITE
        # label
        add_textbox(slide, left + 0.95, top + 0.27, width - 1.1, 0.4, label, size=11.5, bold=False, color=TEXT_MUTED)
        # value
        add_textbox(slide, left + 0.25, top + 0.85, width - 0.5, 0.55, value, size=23, bold=True, color=TEXT_DARK)
        # sub text
        if sub_text:
            add_textbox(slide, left + 0.25, top + 1.38, width - 0.5, 0.35, sub_text, size=10.5, color=TEXT_MUTED)
        # pill
        pbg, ptxt = pill_colors(pill_good)
        pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left + 0.25), Inches(top + height - 0.55), Inches(width - 0.5), Inches(0.38))
        pill.adjustments[0] = 0.5
        pill.fill.solid(); pill.fill.fore_color.rgb = pbg
        pill.line.fill.background(); pill.shadow.inherit = False
        ptf = pill.text_frame; ptf.vertical_anchor = MSO_ANCHOR.MIDDLE
        pp = ptf.paragraphs[0]; pp.alignment = PP_ALIGN.CENTER
        pr = pp.add_run(); pr.text = pill_text
        pr.font.size = Pt(11); pr.font.bold = True; pr.font.color.rgb = ptxt

    def add_table(slide, left, top, width, height, headers, rows, status_col=None, col_widths=None):
        n_rows = len(rows) + 1
        n_cols = len(headers)
        gframe = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top), Inches(width), Inches(height))
        table = gframe.table
        if col_widths:
            total = sum(col_widths)
            for i, w in enumerate(col_widths):
                table.columns[i].width = Inches(width * w / total)
        for j, h in enumerate(headers):
            cell = table.cell(0, j)
            cell.text = h
            cell.fill.solid(); cell.fill.fore_color.rgb = NAVY
            p = cell.text_frame.paragraphs[0]
            p.runs[0].font.bold = True; p.runs[0].font.size = Pt(11); p.runs[0].font.color.rgb = WHITE
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        for i, row in enumerate(rows, start=1):
            for j, val in enumerate(row):
                cell = table.cell(i, j)
                text = str(val)
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if i % 2 == 1 else RGBColor(0xF5, 0xF7, 0xFB)
                good = None
                if status_col is not None and j == status_col:
                    good = text.startswith("✓")
                    if good:
                        _, col = pill_colors(True)
                    else:
                        _, col = pill_colors(False)
                cell.text_frame.paragraphs[0].text = ""
                p = cell.text_frame.paragraphs[0]
                r = p.add_run(); r.text = text
                r.font.size = Pt(10.5)
                r.font.color.rgb = (col if status_col is not None and j == status_col else TEXT_DARK)
                r.font.bold = (status_col is not None and j == status_col)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
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

    def style_chart_light(chart, legend=True):
        chart.has_title = False
        chart.has_legend = legend
        if legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
            chart.legend.font.color.rgb = TEXT_DARK
            chart.legend.font.size = Pt(10.5)
        cat_ax = chart.category_axis
        cat_ax.tick_labels.font.color.rgb = TEXT_DARK
        cat_ax.tick_labels.font.size = Pt(9.5)
        cat_ax.format.line.color.rgb = BORDER
        val_ax = chart.value_axis
        val_ax.tick_labels.font.color.rgb = TEXT_DARK
        val_ax.tick_labels.font.size = Pt(9.5)
        val_ax.format.line.color.rgb = BORDER
        val_ax.has_major_gridlines = True
        val_ax.major_gridlines.format.line.color.rgb = BORDER

    def ach_txt_pct(real, budget):
        if budget == 0:
            return None
        return real / budget * 100

    # ================= SLIDE 1: TITLE =================
    s = prs.slides.add_slide(blank)
    add_bg(s, NAVY_DARK)
    accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(3.3), Inches(6.2), Inches(0.06))
    accent.fill.solid(); accent.fill.fore_color.rgb = TEAL
    accent.line.fill.background(); accent.shadow.inherit = False
    add_textbox(s, 0.8, 1.35, 11, 0.5, "PT BUANA KARYA MANDIRI SEJAHTERA (BKMS)", size=13, bold=True,
                color=RGBColor(0xB9, 0xC2, 0xDE))
    add_textbox(s, 0.8, 1.9, 11.5, 1.3, "DASHBOARD BIAYA", size=44, bold=True, color=WHITE)
    add_textbox(s, 0.8, 2.65, 11.5, 1.0, "& PENDAPATAN", size=44, bold=True, color=TEAL)
    period = ", ".join(month_list) if month_list else "-"
    site_txt = ", ".join(site_list) if len(site_list) <= 6 else f"{len(site_list)} site"
    kat_txt = ", ".join([KATEGORI_LABEL.get(k, k) for k in kat_list])
    add_textbox(s, 0.8, 3.6, 11, 0.4, f"PERIODE {period.upper()} — TAHUN 2026", size=15, color=RGBColor(0xD8, 0xDC, 0xEC))
    add_textbox(s, 0.8, 4.9, 11, 1.0, f"Site: {site_txt}\nKategori: {kat_txt}", size=12, color=RGBColor(0x9A, 0xA3, 0xC4))
    footer = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(6.95), prs.slide_width, Inches(0.55))
    footer.fill.solid(); footer.fill.fore_color.rgb = NAVY
    footer.line.fill.background(); footer.shadow.inherit = False
    add_textbox(s, 0, 7.06, 13.333, 0.4, "Integritas  •  Kemandirian  •  Kebersamaan  •  Tanggung Jawab  •  Inovatif  •  Komitmen",
                size=10.5, color=RGBColor(0xC9, 0xCF, 0xE0), align=PP_ALIGN.CENTER)

    # ================= SLIDE 2: CAPAIAN UTAMA (KPI CARDS) =================
    s = add_content_slide("KPI DASHBOARD — Capaian Utama", "Capaian Utama · 01")
    r_ = data["pendapatan_realisasi"].sum(); b_ = data["pendapatan_budget"].sum()
    pr_ = data["prestasi_realisasi"].sum(); pb_ = data["prestasi_budget"].sum()
    bl_r = data["biaya_langsung_realisasi"].sum(); bl_b = data["biaya_langsung_budget"].sum()
    btl_r = data["biaya_tidak_langsung_realisasi"].sum(); btl_b = data["biaya_tidak_langsung_budget"].sum()
    ach_r = ach_txt_pct(r_, b_); ach_p = ach_txt_pct(pr_, pb_)
    ach_bl = ach_txt_pct(bl_r, bl_b); ach_btl = ach_txt_pct(btl_r, btl_b)

    card_w4, card_h4, gap4, cy4 = 2.85, 2.3, 0.25, 1.15
    add_kpi_card(s, 0.55, cy4, card_w4, card_h4, "Rp", RED, RED if (ach_r is not None and ach_r < 100) else GREEN,
                 "Pendapatan (Realisasi)", fmt_rp(r_), f"Target: {fmt_rp(b_)}",
                 (f"✓ {ach_r:.1f}% — Tercapai" if ach_r is not None and ach_r >= 100 else (f"✗ {ach_r:.1f}% vs Target" if ach_r is not None else "Target = 0")),
                 ach_r is not None and ach_r >= 100)
    add_kpi_card(s, 0.55 + (card_w4 + gap4), cy4, card_w4, card_h4, "▲", TEAL, TEAL if (ach_p is not None and ach_p < 100) else GREEN,
                 "Prestasi (Realisasi)", f"{pr_:,.0f}", f"Target: {pb_:,.0f}",
                 (f"✓ {ach_p:.1f}% — Tercapai" if ach_p is not None and ach_p >= 100 else (f"✗ {ach_p:.1f}% vs Target" if ach_p is not None else "Target = 0")),
                 ach_p is not None and ach_p >= 100)
    add_kpi_card(s, 0.55 + 2 * (card_w4 + gap4), cy4, card_w4, card_h4, "◆", GOLD, GREEN if (ach_bl is not None and ach_bl <= 100) else RED,
                 "Biaya Langsung (Realisasi)", fmt_rp(bl_r), f"Target: {fmt_rp(bl_b)}",
                 (f"✓ {ach_bl:.1f}% — Under Budget" if ach_bl is not None and ach_bl <= 100 else (f"✗ {ach_bl:.1f}% — Over Budget" if ach_bl is not None else "Target = 0")),
                 ach_bl is not None and ach_bl <= 100)
    add_kpi_card(s, 0.55 + 3 * (card_w4 + gap4), cy4, card_w4, card_h4, "🧾", RGBColor(0xB8, 0xBE, 0xCC), GREEN if (ach_btl is not None and ach_btl <= 100) else RED,
                 "Biaya Tdk Langsung (Realisasi)", fmt_rp(btl_r), f"Target: {fmt_rp(btl_b)}",
                 (f"✓ {ach_btl:.1f}% — Under Budget" if ach_btl is not None and ach_btl <= 100 else (f"✗ {ach_btl:.1f}% — Over Budget" if ach_btl is not None else "Target = 0")),
                 ach_btl is not None and ach_btl <= 100)

    add_textbox(s, 0.55, 3.85, 6, 0.4, "Pendapatan: Realisasi vs Target", size=13, bold=True, color=TEXT_DARK)
    cd = CategoryChartData()
    cd.categories = ["Pendapatan"]
    cd.add_series("Target", (b_,))
    cd.add_series("Realisasi", (r_,))
    gframe = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55), Inches(4.25), Inches(6.0), Inches(3.0), cd)
    chart = gframe.chart
    chart.series[0].format.fill.solid(); chart.series[0].format.fill.fore_color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
    chart.series[1].format.fill.solid(); chart.series[1].format.fill.fore_color.rgb = TEAL
    style_chart_light(chart)

    add_textbox(s, 6.9, 3.85, 6, 0.4, "Biaya Langsung vs Tidak Langsung: Realisasi vs Target", size=13, bold=True, color=TEXT_DARK)
    cd2 = CategoryChartData()
    cd2.categories = ["Biaya Langsung", "Biaya Tdk Langsung"]
    cd2.add_series("Target", (bl_b, btl_b))
    cd2.add_series("Realisasi", (bl_r, btl_r))
    gframe2 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(6.9), Inches(4.25), Inches(5.9), Inches(3.0), cd2)
    chart2 = gframe2.chart
    chart2.series[0].format.fill.solid(); chart2.series[0].format.fill.fore_color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
    chart2.series[1].format.fill.solid(); chart2.series[1].format.fill.fore_color.rgb = GOLD
    style_chart_light(chart2)

    # ================= SLIDE 3: POPULASI UNIT =================
    card_w, card_h, gap, cy = 3.75, 2.4, 0.35, 1.25
    s = add_content_slide("POPULASI UNIT — Target vs Realisasi", "Populasi Unit · 02")
    tp = data.loc[data["pendapatan_budget"] > 0, "nama_unit"].nunique()
    rp = data.loc[data["pendapatan_realisasi"] > 0, "nama_unit"].nunique()
    pct_p = (rp / tp * 100) if tp else None

    add_kpi_card(s, 0.55, cy, card_w, card_h, "T", RGBColor(0xB8, 0xBE, 0xCC), RGBColor(0xB8, 0xBE, 0xCC),
                 "Target Populasi", f"{tp:,}", "Unit dengan target Pendapatan", "Baseline", True)
    add_kpi_card(s, 0.55 + (card_w + gap), cy, card_w, card_h, "R", GREEN, GREEN,
                 "Realisasi Populasi", f"{rp:,}", "Unit dengan realisasi Pendapatan", f"vs Target: {tp:,}", True)
    pct_good = pct_p is not None and pct_p >= 100
    add_kpi_card(s, 0.55 + 2 * (card_w + gap), cy, card_w, card_h, "%", GOLD, GREEN if pct_good else RED,
                 "Capaian Populasi", f"{pct_p:.1f}%" if pct_p is not None else "-", "Realisasi vs Target Populasi",
                 (f"✓ {pct_p:.1f}% — Tercapai" if pct_good else (f"✗ {pct_p:.1f}% vs Target" if pct_p is not None else "-")), pct_good)

    cd3 = CategoryChartData()
    cd3.categories = ["Populasi Unit"]
    cd3.add_series("Target", (tp,))
    cd3.add_series("Realisasi", (rp,))
    gframe3 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(2.7), Inches(4.3), Inches(8.0), Inches(2.9), cd3)
    chart3 = gframe3.chart
    chart3.series[0].format.fill.solid(); chart3.series[0].format.fill.fore_color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
    chart3.series[1].format.fill.solid(); chart3.series[1].format.fill.fore_color.rgb = GREEN
    style_chart_light(chart3)

    # ================= SLIDE 4: REKAP BIAYA MAINTENANCE =================
    if maint_data is not None and not maint_data.empty:
        s = add_content_slide("REKAP BIAYA MAINTENANCE", "Maintenance · 03")

        total_m = maint_data["biaya"].sum()
        n_trx = len(maint_data)
        total_sp = sparepart_data["biaya"].sum() if sparepart_data is not None and not sparepart_data.empty else 0
        service_luar = total_m - total_sp
        pct_sp = (total_sp / total_m * 100) if total_m else 0
        pct_luar = (service_luar / total_m * 100) if total_m else 0
        rutin_b = maint_data.loc[maint_data["jenis_pemeliharaan"] == "RUTIN", "biaya"].sum()
        nonrutin_b = maint_data.loc[maint_data["jenis_pemeliharaan"] == "NON RUTIN", "biaya"].sum()

        add_kpi_card(s, 0.55, cy, card_w, card_h, "Σ", RGBColor(0xB8, 0xBE, 0xCC), RGBColor(0xB8, 0xBE, 0xCC),
                     "Total Biaya Maintenance", fmt_rp(total_m), f"{n_trx:,} transaksi", "100%", True)
        add_kpi_card(s, 0.55 + (card_w + gap), cy, card_w, card_h, "P", GREEN, GREEN,
                     "Pemakaian Persediaan", fmt_rp(total_sp), "Dari Rincian Pemakaian Sparepart", f"{pct_sp:.1f}% dari total", True)
        add_kpi_card(s, 0.55 + 2 * (card_w + gap), cy, card_w, card_h, "L", GOLD, GOLD,
                     "Service Luar", fmt_rp(service_luar), "Selisih Total − Persediaan", f"{pct_luar:.1f}% dari total", True)

        rekap = maint_data.groupby(["kategori_sparepart", "jenis_pemeliharaan"], as_index=False).agg(
            n=("biaya", "count"), biaya=("biaya", "sum")
        ).sort_values("biaya", ascending=False).head(10)
        rows = [[r["kategori_sparepart"], r["jenis_pemeliharaan"], f"{int(r['n']):,}", fmt_rp(r["biaya"])] for _, r in rekap.iterrows()]
        add_textbox(s, 0.55, 4.0, 6, 0.35, "Top 10 Kategori — Maintenance atas Apa Saja", size=13, bold=True, color=TEXT_DARK)
        add_table(s, 0.55, 4.4, 7.3, 2.75, ["Kategori", "Jenis", "Berapa Kali", "Total Biaya"], rows,
                  col_widths=[2.4, 1.3, 1.0, 1.5])

        add_insight_box(s, 8.1, 4.0, 4.65, 3.15, "Ringkasan Rekonsiliasi",
                         [f"Biaya Rutin: {fmt_rp(rutin_b)}", f"Biaya Non Rutin: {fmt_rp(nonrutin_b)}",
                          f"Pemakaian Persediaan menyumbang {pct_sp:.1f}% dari total biaya maintenance.",
                          f"Sisanya, {pct_luar:.1f}%, dianggap sebagai Service Luar (di luar pemakaian persediaan)."],
                         border_color=TEAL)

    # ================= SLIDE 5: REKAP PEMAKAIAN SPAREPART =================
    if sparepart_data is not None and not sparepart_data.empty:
        s = add_content_slide("REKAP PEMAKAIAN SPAREPART (PERSEDIAAN)", "Sparepart · 04")
        total_sp2 = sparepart_data["biaya"].sum()
        n_item = sparepart_data["nama_barang"].nunique()
        n_trx2 = len(sparepart_data)

        m1w, m1h = 3.9, 1.5
        for i, (lbl, val, ic, col) in enumerate([
            ("Total Biaya Pemakaian", fmt_rp(total_sp2), "Rp", TEAL),
            ("Jenis Barang Berbeda", f"{n_item:,}", "B", GOLD),
            ("Jumlah Transaksi", f"{n_trx2:,}", "#", GREEN),
        ]):
            x = 0.55 + i * (m1w + 0.3)
            card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(1.2), Inches(m1w), Inches(m1h))
            card.adjustments[0] = 0.06
            card.fill.solid(); card.fill.fore_color.rgb = WHITE
            card.line.color.rgb = col; card.line.width = Pt(1.25)
            card.shadow.inherit = False
            tf = card.text_frame; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf.margin_left = Inches(0.2)
            p1 = tf.paragraphs[0]; r1 = p1.add_run(); r1.text = lbl
            r1.font.size = Pt(11); r1.font.color.rgb = TEXT_MUTED; r1.font.bold = True
            p2 = tf.add_paragraph(); r2 = p2.add_run(); r2.text = val
            r2.font.size = Pt(22); r2.font.bold = True; r2.font.color.rgb = TEXT_DARK

        top_barang = sparepart_data.groupby("nama_barang", as_index=False)["biaya"].sum().sort_values("biaya", ascending=False).head(8)
        cd5 = CategoryChartData()
        cd5.categories = list(top_barang["nama_barang"])
        cd5.add_series("Biaya", tuple(top_barang["biaya"]))
        add_textbox(s, 0.55, 3.05, 6, 0.35, "Top 8 Barang berdasarkan Biaya", size=13, bold=True, color=TEXT_DARK)
        gframe5 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.55), Inches(3.45), Inches(6.9), Inches(3.65), cd5)
        chart5 = gframe5.chart
        chart5.series[0].format.fill.solid(); chart5.series[0].format.fill.fore_color.rgb = TEAL
        style_chart_light(chart5, legend=False)

        cat_sp = sparepart_data.groupby("kategori_sparepart", as_index=False)["biaya"].sum().sort_values("biaya", ascending=False)
        cd6 = CategoryChartData()
        cd6.categories = list(cat_sp["kategori_sparepart"])
        cd6.add_series("Biaya", tuple(cat_sp["biaya"]))
        add_textbox(s, 7.75, 3.05, 5, 0.35, "Komposisi per Kategori", size=13, bold=True, color=TEXT_DARK)
        gframe6 = s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(7.75), Inches(3.45), Inches(5.0), Inches(3.65), cd6)
        chart6 = gframe6.chart
        chart6.has_title = False
        chart6.has_legend = True
        chart6.legend.position = XL_LEGEND_POSITION.RIGHT
        chart6.legend.include_in_layout = False
        chart6.legend.font.size = Pt(8.5)
        chart6.legend.font.color.rgb = TEXT_DARK
        pie_palette = [TEAL, GOLD, GREEN, RED, RGBColor(0x8E, 0x7C, 0xC3), RGBColor(0xB8, 0xBE, 0xCC)]
        for i, pt in enumerate(chart6.series[0].points):
            pt.format.fill.solid(); pt.format.fill.fore_color.rgb = pie_palette[i % len(pie_palette)]

    # ================= SLIDE 6: ANALISA =================
    s = add_content_slide("ANALISA — Penyebab Capaian Pendapatan", "Analisa · 05")
    ach_r2 = ach_txt_pct(tot_pendapatan_r, tot_pendapatan_b)
    if ach_r2 is None:
        bullets = ["Target Pendapatan belum tersedia untuk kombinasi filter ini."]
    elif ach_r2 >= 100:
        bullets = [f"Realisasi Pendapatan sudah mencapai {ach_r2:.1f}% dari target — tidak ada gap yang perlu dianalisa."]
    else:
        gap_rp = tot_pendapatan_b - tot_pendapatan_r
        bullets = [f"Realisasi Pendapatan mencapai {ach_r2:.1f}% dari target, dengan gap sebesar {fmt_rp(gap_rp)}."]
        if ach_prestasi is not None:
            diff = ach_r2 - ach_prestasi
            if ach_prestasi < 100 and abs(diff) <= 10:
                bullets.append(f"Prestasi juga hanya {ach_prestasi:.1f}% dari target — sejalan dengan Pendapatan, mengindikasikan volume pekerjaan yang belum tercapai sebagai faktor utama.")
            elif ach_prestasi < 100:
                bullets.append(f"Prestasi mencapai {ach_prestasi:.1f}% dari target — turut berkontribusi meski bukan faktor dominan.")
            else:
                bullets.append(f"Prestasi mencapai {ach_prestasi:.1f}% (di atas target) — rendahnya Pendapatan kemungkinan bukan dari volume pekerjaan, melainkan tarif atau piutang.")
        if target_populasi:
            gap_pop = target_populasi - realisasi_populasi
            if gap_pop > 0:
                gap_pop_pct = gap_pop / target_populasi * 100
                bullets.append(f"{gap_pop} unit ({gap_pop_pct:.1f}%) tidak mencatatkan realisasi Pendapatan sama sekali — indikasi unit idle/downtime.")
        site_group = data.groupby("lokasi").agg(realisasi=("pendapatan_realisasi", "sum"), budget=("pendapatan_budget", "sum")).reset_index()
        site_group = site_group[site_group["budget"] > 0]
        if not site_group.empty:
            site_group["capaian"] = site_group["realisasi"] / site_group["budget"] * 100
            worst = site_group.sort_values("capaian").iloc[0]
            if worst["capaian"] < 100:
                bullets.append(f"Site dengan capaian terendah: {worst['lokasi']} ({worst['capaian']:.1f}% dari target) — kontributor terbesar gap Pendapatan.")
    add_insight_box(s, 0.55, 1.3, 12.2, 4.8, "Temuan Utama", bullets, border_color=(RED if (ach_r2 is not None and ach_r2 < 100) else GREEN))
    add_textbox(s, 0.55, 6.3, 12.2, 0.5,
                "Catatan: analisa bersifat indikatif berdasarkan pola data (Prestasi & Populasi unit), bukan kesimpulan pasti penyebab operasional di lapangan.",
                size=10, italic=True, color=TEXT_MUTED)

    # ================= SLIDE 7: TERIMA KASIH =================
    s = prs.slides.add_slide(blank)
    add_bg(s, NAVY_DARK)
    add_textbox(s, 0.8, 0.7, 10, 1.0, "TERIMA KASIH", size=40, bold=True, color=WHITE)
    add_textbox(s, 0.8, 1.55, 10, 0.5, "Ringkasan Dashboard Biaya & Pendapatan — PT BKMS", size=15, color=TEAL)

    summary_rows = [
        ["Pendapatan (Realisasi vs Target)", fmt_rp(tot_pendapatan_r), (f"{ach_pendapatan:.1f}%" if ach_pendapatan is not None else "-")],
        ["Prestasi (Realisasi vs Target)", f"{tot_prestasi_r:,.0f}", (f"{ach_prestasi:.1f}%" if ach_prestasi is not None else "-")],
        ["Biaya Langsung (Realisasi vs Target)", fmt_rp(tot_biaya_langsung_r), (f"{ach_biaya_langsung:.1f}%" if ach_biaya_langsung is not None else "-")],
        ["Biaya Tdk Langsung (Realisasi vs Target)", fmt_rp(tot_biaya_tdklangsung_r), (f"{ach_biaya_tdklangsung:.1f}%" if ach_biaya_tdklangsung is not None else "-")],
        ["Populasi Unit (Realisasi vs Target)", f"{realisasi_populasi:,} / {target_populasi:,}", (f"{pct_populasi:.1f}%" if pct_populasi is not None else "-")],
    ]
    tbl_box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(2.2), Inches(11.7), Inches(4.2))
    tbl_box.adjustments[0] = 0.03
    tbl_box.fill.solid(); tbl_box.fill.fore_color.rgb = RGBColor(0x1F, 0x28, 0x4E)
    tbl_box.line.color.rgb = RGBColor(0x33, 0x3E, 0x6B); tbl_box.line.width = Pt(1)
    tbl_box.shadow.inherit = False
    gframe_sum = s.shapes.add_table(len(summary_rows) + 1, 3, Inches(1.05), Inches(2.45), Inches(11.2), Inches(3.7))
    tsum = gframe_sum.table
    for j, h in enumerate(["Metrik", "Realisasi", "Capaian"]):
        cell = tsum.cell(0, j)
        cell.text = h
        cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0x2A, 0x35, 0x66)
        p = cell.text_frame.paragraphs[0]
        p.runs[0].font.bold = True; p.runs[0].font.size = Pt(12); p.runs[0].font.color.rgb = WHITE
    for i, row in enumerate(summary_rows, start=1):
        for j, val in enumerate(row):
            cell = tsum.cell(i, j)
            cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0x1F, 0x28, 0x4E)
            p = cell.text_frame.paragraphs[0]
            r = p.add_run(); r.text = str(val)
            r.font.size = Pt(12); r.font.color.rgb = WHITE

    footer2 = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(6.95), prs.slide_width, Inches(0.55))
    footer2.fill.solid(); footer2.fill.fore_color.rgb = NAVY
    footer2.line.fill.background(); footer2.shadow.inherit = False
    add_textbox(s, 0, 7.06, 13.333, 0.4, "Integritas  •  Kemandirian  •  Kebersamaan  •  Tanggung Jawab  •  Inovatif  •  Komitmen",
                size=10.5, color=RGBColor(0xC9, 0xCF, 0xE0), align=PP_ALIGN.CENTER)

    buf = _io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

colX, colY = st.columns([5, 1.4])
with colY:
    if st.button("📽️ Buat Presentasi (PPTX)", use_container_width=True, type="primary"):
        with st.spinner("Menyusun slide presentasi..."):
            maint_for_pptx = maint_df_site_bulan if not maint_raw.empty else pd.DataFrame()
            sparepart_for_pptx = sparepart_df_site_bulan if not sparepart_raw.empty else pd.DataFrame()
            pptx_bytes = build_pptx(df, maint_for_pptx, sparepart_for_pptx, sel_site, sel_month, sel_kat)
        st.session_state["pptx_bytes"] = pptx_bytes
    if "pptx_bytes" in st.session_state:
        st.download_button(
            "⬇️ Unduh PPTX",
            data=st.session_state["pptx_bytes"],
            file_name="Laporan_Biaya_Pendapatan_BKMS.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )

st.markdown("---")

# ---------------------------------------------------------------
# 1-3. CAPAIAN: PENDAPATAN, PRESTASI, BIAYA LANGSUNG & TIDAK LANGSUNG
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Capaian Utama</h3>', unsafe_allow_html=True)

pendapatan_pill, pendapatan_style = achievement_pill(ach_pendapatan, higher_is_better=True)
prestasi_pill, prestasi_style = achievement_pill(ach_prestasi, higher_is_better=True)
biaya_langsung_pill, biaya_langsung_style = achievement_pill(ach_biaya_langsung, higher_is_better=False)
biaya_tdklangsung_pill, biaya_tdklangsung_style = achievement_pill(ach_biaya_tdklangsung, higher_is_better=False)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(kpi_card(
        icon="💰", icon_bg=RED, accent=RED,
        label="Pendapatan: Realisasi vs Target",
        value=fmt_rp(tot_pendapatan_r),
        budget_text=f"Target: {fmt_rp(tot_pendapatan_b)}",
        pill_text=pendapatan_pill, pill_style=pendapatan_style,
    ), unsafe_allow_html=True)
with c2:
    st.markdown(kpi_card(
        icon="📈", icon_bg=CHART_GREEN, accent=CHART_GREEN,
        label="Prestasi: Realisasi vs Target",
        value=f"{tot_prestasi_r:,.0f}",
        budget_text=f"Target: {tot_prestasi_b:,.0f}",
        pill_text=prestasi_pill, pill_style=prestasi_style,
    ), unsafe_allow_html=True)
with c3:
    st.markdown(kpi_card(
        icon="⚙️", icon_bg=GOLD, accent=GOLD,
        label="Biaya Langsung: Realisasi vs Target",
        value=fmt_rp(tot_biaya_langsung_r),
        budget_text=f"Target: {fmt_rp(tot_biaya_langsung_b)}",
        pill_text=biaya_langsung_pill, pill_style=biaya_langsung_style,
    ), unsafe_allow_html=True)
with c4:
    st.markdown(kpi_card(
        icon="🧾", icon_bg=GREY, accent=GREY,
        label="Biaya Tdk Langsung: Realisasi vs Target",
        value=fmt_rp(tot_biaya_tdklangsung_r),
        budget_text=f"Target: {fmt_rp(tot_biaya_tdklangsung_b)}",
        pill_text=biaya_tdklangsung_pill, pill_style=biaya_tdklangsung_style,
    ), unsafe_allow_html=True)

st.markdown("---")

# ---------------------------------------------------------------
# CAPAIAN PRESTASI PER SATUAN: Rp/KM, Rp/HM, Rp/Tonase
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Capaian Prestasi per Satuan (Rp/KM · Rp/HM · Rp/Tonase)</h3>', unsafe_allow_html=True)
st.caption(
    "Rp/Satuan = Pendapatan ÷ Prestasi.  •  Rp/KM: Transportasi di site Sungai Danau & Kumai.  •  "
    "Rp/HM: Alat Berat di site Sungai Danau & Kumai, serta khusus site Tanjung & Buhut.  •  Rp/Tonase: site Buhut LHL.  •  "
    "Site Ampah tidak termasuk breakdown ini."
)

satuan_group = df[df["satuan_tipe"].notna()].groupby("satuan_tipe", as_index=False).agg(
    pendapatan_r=("pendapatan_realisasi", "sum"), pendapatan_b=("pendapatan_budget", "sum"),
    prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum"),
)

sat_cols = st.columns(3)
for i, tipe in enumerate(["KM", "HM", "TONASE"]):
    row = satuan_group[satuan_group["satuan_tipe"] == tipe]
    with sat_cols[i]:
        if row.empty:
            st.markdown(kpi_card(
                icon=SATUAN_ICON[tipe], icon_bg=GREY, accent=GREY,
                label=SATUAN_LABEL[tipe],
                value="Tidak ada data",
                budget_text="Site terkait tidak ditemukan pada filter saat ini",
                pill_text="—", pill_style="kpi-pill-amber",
            ), unsafe_allow_html=True)
            continue
        pr_ = row["pendapatan_r"].iloc[0]; pb_ = row["pendapatan_b"].iloc[0]
        prr_ = row["prestasi_r"].iloc[0]; prb_ = row["prestasi_b"].iloc[0]
        rate_r = (pr_ / prr_) if prr_ else None
        rate_b = (pb_ / prb_) if prb_ else None
        ach_rate = achievement(rate_r, rate_b) if (rate_r is not None and rate_b) else None
        pill_txt, pill_sty = achievement_pill(ach_rate, higher_is_better=True)
        val_txt = fmt_rp(rate_r) if rate_r is not None else "-"
        budget_txt = f"Target: {fmt_rp(rate_b)}" if rate_b is not None else "Target belum tersedia (Prestasi Budget = 0)"
        st.markdown(kpi_card(
            icon=SATUAN_ICON[tipe], icon_bg=SATUAN_COLOR[tipe], accent=SATUAN_COLOR[tipe],
            label=SATUAN_LABEL[tipe],
            value=val_txt,
            budget_text=budget_txt,
            pill_text=pill_txt, pill_style=pill_sty,
        ), unsafe_allow_html=True)

with st.expander("📋 Rincian Rp/Satuan per Site & Kategori"):
    detail = df[df["satuan_tipe"].notna()].groupby(["satuan_tipe", "lokasi", "kategori"], as_index=False).agg(
        pendapatan_r=("pendapatan_realisasi", "sum"), pendapatan_b=("pendapatan_budget", "sum"),
        prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum"),
    )
    detail["rate_r"] = detail.apply(lambda r: (r["pendapatan_r"] / r["prestasi_r"]) if r["prestasi_r"] else None, axis=1)
    detail["rate_b"] = detail.apply(lambda r: (r["pendapatan_b"] / r["prestasi_b"]) if r["prestasi_b"] else None, axis=1)
    detail["capaian"] = detail.apply(
        lambda r: (r["rate_r"] / r["rate_b"] * 100) if (r["rate_r"] is not None and r["rate_b"]) else None, axis=1
    )
    show = pd.DataFrame({
        "Satuan": detail["satuan_tipe"].map(SATUAN_LABEL),
        "Site": detail["lokasi"],
        "Kategori": detail["kategori"].map(lambda k: KATEGORI_LABEL.get(k, k)),
        "Pendapatan Realisasi": detail["pendapatan_r"].apply(fmt_rp),
        "Prestasi Realisasi": detail["prestasi_r"].apply(lambda v: f"{v:,.0f}"),
        "Rp/Satuan (Realisasi)": detail["rate_r"].apply(lambda v: fmt_rp(v) if pd.notna(v) else "-"),
        "Rp/Satuan (Target)": detail["rate_b"].apply(lambda v: fmt_rp(v) if pd.notna(v) else "-"),
        "Capaian (%)": detail["capaian"].apply(lambda v: f"{v:.1f}%" if pd.notna(v) else "-"),
    })
    st.dataframe(show, use_container_width=True, hide_index=True)

unmapped_sites = sorted(df.loc[df["satuan_tipe"].isna(), "lokasi"].dropna().unique().tolist())
EXCLUDED_SITES_KNOWN = {"ampah"}  # sengaja tidak dimasukkan ke breakdown Rp/Satuan
truly_unmapped = [s for s in unmapped_sites if s.strip().lower() not in EXCLUDED_SITES_KNOWN]
known_excluded = [s for s in unmapped_sites if s.strip().lower() in EXCLUDED_SITES_KNOWN]

if known_excluded:
    st.caption(f"ℹ️ Site {', '.join(known_excluded)} tidak dimasukkan ke breakdown Rp/Satuan ini (di luar cakupan Rp/KM, Rp/HM, Rp/Tonase).")

if truly_unmapped:
    st.warning(
        "Site berikut belum termasuk kategori Rp/KM, Rp/HM, atau Rp/Tonase (nama site tidak cocok dengan aturan "
        "Sungai Danau / Kumai / Buhut LHL / Tanjung / Buhut): **" + ", ".join(truly_unmapped) + "**. "
        "Jika nama site di data Anda berbeda ejaannya, beri tahu nama persisnya agar pemetaan bisa disesuaikan."
    )

st.markdown("---")

# ---------------------------------------------------------------
# 4. REKAP BIAYA MAINTENANCE (filter ID Unit + Rutin/Non Rutin + frekuensi)
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Rekap Biaya Maintenance</h3>', unsafe_allow_html=True)

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

    fig_rekon = go.Figure()
    fig_rekon.add_bar(
        y=["Total Maintenance"], x=[total_persediaan_all], name="Pemakaian Persediaan",
        orientation="h", marker_color=CHART_GREEN,
    )
    fig_rekon.add_bar(
        y=["Total Maintenance"], x=[service_luar_all], name="Service Luar",
        orientation="h", marker_color=GOLD,
    )
    fig_rekon.update_layout(
        barmode="stack", height=160, margin=dict(t=10, b=10, l=10, r=10),
        xaxis_title="Rupiah", legend=dict(orientation="h", y=1.3),
    )
    st.plotly_chart(style_fig(fig_rekon), use_container_width=True)
    if not sparepart_raw.empty:
        st.caption("Pemakaian Persediaan dihitung dari data Rincian Pemakaian Sparepart. Service Luar adalah selisih Total Maintenance dikurangi Pemakaian Persediaan.")
    else:
        st.caption("Data Rincian Pemakaian Sparepart belum diupload, sehingga seluruh Total Biaya Maintenance sementara dihitung sebagai Service Luar.")

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
        total_maint = maint_df["biaya"].sum()
        n_transaksi = len(maint_df)
        rutin_biaya = maint_df.loc[maint_df["jenis_pemeliharaan"] == "RUTIN", "biaya"].sum()
        nonrutin_biaya = maint_df.loc[maint_df["jenis_pemeliharaan"] == "NON RUTIN", "biaya"].sum()
        rutin_n = int((maint_df["jenis_pemeliharaan"] == "RUTIN").sum())
        nonrutin_n = int((maint_df["jenis_pemeliharaan"] == "NON RUTIN").sum())

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Biaya Maintenance", fmt_rp(total_maint), f"{n_transaksi:,} transaksi")
        k2.metric("Unit Ter-maintenance", f"{maint_df['nama_unit'].nunique():,}")
        k3.metric("Biaya Rutin", fmt_rp(rutin_biaya), f"{rutin_n:,} kali")
        k4.metric("Biaya Non Rutin", fmt_rp(nonrutin_biaya), f"{nonrutin_n:,} kali")

        rekap = maint_df.groupby(["kategori_sparepart", "jenis_pemeliharaan"], as_index=False).agg(
            jumlah_transaksi=("biaya", "count"),
            total_biaya=("biaya", "sum"),
        )

        fig_rekap = px.bar(
            rekap, x="kategori_sparepart", y="total_biaya", color="jenis_pemeliharaan",
            barmode="group", color_discrete_map={"RUTIN": CHART_GREEN, "NON RUTIN": GOLD},
            labels={"kategori_sparepart": "Kategori Sparepart / Sistem", "total_biaya": "Total Biaya (Rp)", "jenis_pemeliharaan": "Jenis"},
        )
        fig_rekap.update_layout(title="Maintenance atas Apa Saja — Rutin vs Non Rutin", height=460,
                                 legend=dict(orientation="h", y=1.15), margin=dict(t=60, b=10), xaxis_tickangle=-30)
        st.plotly_chart(style_fig(fig_rekap), use_container_width=True)

        st.markdown("##### Rincian: Kategori, Jenis, Frekuensi (Berapa Kali), Total Biaya")
        rekap_tbl = rekap.sort_values("total_biaya", ascending=False).rename(columns={
            "kategori_sparepart": "Kategori (Maintenance atas Apa Saja)",
            "jenis_pemeliharaan": "Jenis (Rutin / Non Rutin)",
            "jumlah_transaksi": "Berapa Kali (Jumlah Transaksi)",
            "total_biaya": "Total Biaya",
        })
        st.dataframe(
            rekap_tbl, use_container_width=True, hide_index=True, height=380,
            column_config={"Total Biaya": st.column_config.NumberColumn(format="Rp %,.0f")},
        )
        csv_rekap = rekap_tbl.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Unduh Rekap Maintenance (CSV)", csv_rekap, file_name="rekap_maintenance_bkms.csv", mime="text/csv")

st.markdown("---")

# ---------------------------------------------------------------
# REKAP PEMAKAIAN SPAREPART (PERSEDIAAN)
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Rekap Pemakaian Sparepart (Persediaan)</h3>', unsafe_allow_html=True)
st.caption(
    "Data ini hanya mencakup **pemakaian sparepart dari persediaan/gudang** (item, part number, dan quantity per transaksi maintenance). "
    "Biaya maintenance di luar pemakaian persediaan ini (alokasi workshop, dan lainnya) dianggap sebagai **service luar** — lihat bagian Rekap Biaya Maintenance di atas untuk totalnya."
)

if sparepart_raw.empty:
    st.info("Data pemakaian sparepart belum tersedia. Upload file Rincian Pemakaian (.xls/.xlsx) di sidebar untuk menampilkan bagian ini.")
else:
    sparepart_df_site_bulan = sparepart_df_site_bulan.copy()
    sparepart_df_site_bulan["unit_label"] = sparepart_df_site_bulan["nama_unit"].apply(_unit_label)
    unit_sparepart_opts = sorted(sparepart_df_site_bulan["unit_label"].dropna().unique().tolist())

    sel_unit_sparepart = st.multiselect(
        "Filter berdasarkan ID Unit (opsional, kosongkan = semua unit) — ketik ID Unit atau nama unit",
        unit_sparepart_opts, default=[], key="sel_unit_sparepart",
    )

    sparepart_df = sparepart_df_site_bulan
    if sel_unit_sparepart:
        sparepart_df = sparepart_df[sparepart_df["unit_label"].isin(sel_unit_sparepart)]

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
        with colS1:
            top_barang = sparepart_df.groupby("nama_barang", as_index=False).agg(
                total_qty=("qty", "sum"), total_biaya=("biaya", "sum"),
            ).sort_values("total_biaya", ascending=False).head(15)
            fig_sp1 = go.Figure()
            fig_sp1.add_bar(y=top_barang["nama_barang"], x=top_barang["total_biaya"], orientation="h", marker_color=CHART_GREEN)
            fig_sp1.update_layout(title="Top 15 Barang berdasarkan Biaya", xaxis_title="Rupiah",
                                   height=460, margin=dict(t=60, b=10, l=10))
            fig_sp1.update_yaxes(autorange="reversed")
            st.plotly_chart(style_fig(fig_sp1), use_container_width=True)

        with colS2:
            cat_sp = sparepart_df.groupby("kategori_sparepart", as_index=False)["biaya"].sum()
            fig_sp2 = px.pie(cat_sp, names="kategori_sparepart", values="biaya", hole=0.5)
            fig_sp2.update_layout(title="Komposisi per Kategori Sparepart", height=460, margin=dict(t=60, b=10),
                                   showlegend=True, legend=dict(font=dict(size=9)))
            st.plotly_chart(style_fig(fig_sp2), use_container_width=True)

        st.markdown("##### Rincian Pemakaian per Barang")
        search_sp = st.text_input("🔍 Cari nama barang / part number...", "", key="search_sparepart")
        show_sp = sparepart_df[["tanggal", "lokasi", "nama_unit", "kategori_sparepart", "jenis_pemeliharaan",
                                 "kode_barang", "part_number", "nama_barang", "qty", "satuan", "biaya"]].rename(columns={
            "tanggal": "Tanggal", "lokasi": "Site", "nama_unit": "Nama Unit", "kategori_sparepart": "Kategori Sparepart",
            "jenis_pemeliharaan": "Jenis", "kode_barang": "Kode Barang", "part_number": "Part Number",
            "nama_barang": "Nama Barang", "qty": "Qty", "satuan": "Satuan", "biaya": "Biaya",
        })
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
# 5. POPULASI: TARGET VS REALISASI
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Populasi Unit: Target vs Realisasi</h3>', unsafe_allow_html=True)
st.caption("**Target Populasi** = jumlah unit yang memiliki target/budget Pendapatan (budget > 0). **Realisasi Populasi** = jumlah unit yang memiliki realisasi Pendapatan (realisasi > 0).")

populasi_pill, populasi_style = achievement_pill(pct_populasi, higher_is_better=True)

p1, p2, p3 = st.columns(3)
with p1:
    st.markdown(kpi_card(
        icon="🎯", icon_bg=GREY, accent=GREY,
        label="Target Populasi", value=f"{target_populasi:,}",
        budget_text="Unit dengan target Pendapatan",
        pill_text="Baseline", pill_style="kpi-pill-amber",
    ), unsafe_allow_html=True)
with p2:
    st.markdown(kpi_card(
        icon="✅", icon_bg=CHART_GREEN, accent=CHART_GREEN,
        label="Realisasi Populasi", value=f"{realisasi_populasi:,}",
        budget_text="Unit dengan realisasi Pendapatan",
        pill_text=f"vs Target: {target_populasi:,}", pill_style="kpi-pill-amber",
    ), unsafe_allow_html=True)
with p3:
    st.markdown(kpi_card(
        icon="📊", icon_bg=GOLD, accent=GOLD,
        label="Capaian Populasi", value=f"{pct_populasi:.1f}%" if pct_populasi is not None else "-",
        budget_text="Realisasi vs Target Populasi",
        pill_text=populasi_pill, pill_style=populasi_style,
    ), unsafe_allow_html=True)

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
    st.caption("Catatan: analisa ini bersifat indikatif berdasarkan pola data (capaian Prestasi & Populasi unit), bukan kesimpulan pasti atas penyebab operasional di lapangan.")

st.markdown("---")
st.caption("Dashboard Biaya & Pendapatan • PT Buana Karya Mandiri Sejahtera (BKMS) • Dibuat dengan Streamlit")
