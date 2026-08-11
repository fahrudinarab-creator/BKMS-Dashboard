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
# APPLY FILTERS (data utama)
# ---------------------------------------------------------------
df = df_raw[
    df_raw["lokasi"].isin(sel_site) &
    df_raw["bulan"].isin(sel_month) &
    df_raw["kategori"].isin(sel_kat)
].copy()

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
tot_biaya_langsung_r = df["biaya_langsung_realisasi"].sum()
tot_biaya_langsung_b = df["biaya_langsung_budget"].sum()
tot_biaya_tidak_langsung_r = df["biaya_tidak_langsung_realisasi"].sum()
tot_biaya_tidak_langsung_b = df["biaya_tidak_langsung_budget"].sum()

# Total biaya tetap dipertahankan untuk kebutuhan bagian lain.
tot_biaya_r = df["total_biaya_realisasi"].sum()
tot_biaya_b = df["total_biaya_budget"].sum()

ach_pendapatan = achievement(tot_pendapatan_r, tot_pendapatan_b)
ach_prestasi = achievement(tot_prestasi_r, tot_prestasi_b)
ach_biaya_langsung = achievement(tot_biaya_langsung_r, tot_biaya_langsung_b)
ach_biaya_tidak_langsung = achievement(
    tot_biaya_tidak_langsung_r, tot_biaya_tidak_langsung_b
)
ach_biaya = achievement(tot_biaya_r, tot_biaya_b)

target_populasi = df.loc[df["pendapatan_budget"] > 0, "nama_unit"].nunique()
realisasi_populasi = df.loc[df["pendapatan_realisasi"] > 0, "nama_unit"].nunique()
pct_populasi = (realisasi_populasi / target_populasi * 100) if target_populasi else None

# ---------------------------------------------------------------
# POWERPOINT EXPORT
# ---------------------------------------------------------------
def build_pptx(data, maint_data, site_list, month_list, kat_list) -> bytes:
    """
    Generate PPTX using the visual language of the supplied RTM PDF:
    - 16:9 layout
    - navy top header
    - very light blue page background
    - Calibri typography
    - cyan / purple / green / red section accents
    - KPI cards with colored top line and icon circle
    - white chart/table panels with thin grey borders
    - dark divider slides for major sections

    Dashboard Streamlit itself is NOT changed; only the PPT export is styled here.
    """
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.chart.data import CategoryChartData
    from pptx.enum.dml import MSO_LINE
    import io as _io

    # ------------------------------------------------------------
    # COLORS TAKEN FROM THE VISUAL PALETTE OF THE SUPPLIED PDF
    # ------------------------------------------------------------
    NAVY = RGBColor(0x1E, 0x27, 0x61)
    BG = RGBColor(0xF3, 0xF7, 0xFF)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    TEXT = RGBColor(0x20, 0x29, 0x3D)
    MUTED = RGBColor(0x70, 0x78, 0x8C)
    GRID = RGBColor(0xD9, 0xDF, 0xEB)
    PALE_BLUE = RGBColor(0xE8, 0xEE, 0xFA)

    CYAN = RGBColor(0x00, 0xB4, 0xD7)
    PURPLE = RGBColor(0x7C, 0x3A, 0xED)
    GREEN = RGBColor(0x04, 0x96, 0x69)
    RED = RGBColor(0xED, 0x44, 0x44)
    AMBER = RGBColor(0xF5, 0xA0, 0x0A)
    BLUE = RGBColor(0x0D, 0x7D, 0xB0)

    PALE_GREEN = RGBColor(0xD8, 0xF4, 0xE9)
    PALE_RED = RGBColor(0xFD, 0xE0, 0xE0)
    PALE_AMBER = RGBColor(0xFF, 0xF0, 0xD1)
    PALE_CYAN = RGBColor(0xE0, 0xF6, 0xFB)
    PALE_PURPLE = RGBColor(0xEF, 0xE7, 0xFF)

    FONT = "Calibri"

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # ------------------------------------------------------------
    # BASIC HELPERS
    # ------------------------------------------------------------
    def add_rect(slide, left, top, width, height, fill, line=None, radius=False):
        shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
        shp = slide.shapes.add_shape(
            shape_type,
            Inches(left), Inches(top),
            Inches(width), Inches(height)
        )
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
        if line is None:
            shp.line.fill.background()
        else:
            shp.line.color.rgb = line
            shp.line.width = Pt(0.8)
        if radius:
            try:
                shp.adjustments[0] = 0.08
            except Exception:
                pass
        return shp

    def add_text(slide, left, top, width, height, text, size=12,
                 color=TEXT, bold=False, align=PP_ALIGN.LEFT,
                 valign=MSO_ANCHOR.MIDDLE, font=FONT):
        tb = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = tb.text_frame
        tf.clear()
        tf.word_wrap = True
        tf.vertical_anchor = valign
        tf.margin_left = Inches(0)
        tf.margin_right = Inches(0)
        tf.margin_top = Inches(0)
        tf.margin_bottom = Inches(0)
        p = tf.paragraphs[0]
        p.alignment = align
        r = p.add_run()
        r.text = str(text)
        r.font.name = font
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        return tb

    def add_rich_text(slide, left, top, width, height, parts,
                      size=12, align=PP_ALIGN.LEFT):
        """parts = [(text, color, bold), ...]"""
        tb = slide.shapes.add_textbox(
            Inches(left), Inches(top), Inches(width), Inches(height)
        )
        tf = tb.text_frame
        tf.clear()
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = align
        for txt, color, bold in parts:
            r = p.add_run()
            r.text = str(txt)
            r.font.name = FONT
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.color.rgb = color
        return tb

    def add_slide_base():
        slide = prs.slides.add_slide(blank)
        add_rect(slide, 0, 0, 13.333, 7.5, BG)
        return slide

    def add_header(slide, title, section=""):
        add_rect(slide, 0, 0, 13.333, 0.70, NAVY)
        add_text(
            slide, 0.68, 0.12, 9.8, 0.36,
            title, size=16, color=WHITE, bold=True
        )
        if section:
            add_text(
                slide, 10.2, 0.13, 2.45, 0.32,
                section, size=9, color=RGBColor(0xC9, 0xD0, 0xE8),
                align=PP_ALIGN.RIGHT
            )

    def add_footer(slide, page_no):
        add_text(
            slide, 0.68, 7.18, 10.5, 0.18,
            "Integritas  •  Kemandirian  •  Kebersamaan  •  Tanggung Jawab  •  Inovatif  •  Komitmen",
            size=7.5, color=MUTED
        )
        add_text(
            slide, 12.0, 7.18, 0.65, 0.18,
            str(page_no), size=7.5, color=MUTED,
            align=PP_ALIGN.RIGHT
        )

    def add_section_divider(slide, number, title1, title2, subtitle, accent, icon_text):
        add_rect(slide, 0, 0, 13.333, 7.5, NAVY)
        add_rect(slide, 0, 0, 0.25, 7.5, accent)
        add_rect(
            slide, 0.55, 0.82, 4.05, 1.65,
            RGBColor(0x27, 0x31, 0x70)
        )

        add_text(
            slide, 0.82, 1.06, 3.2, 0.50,
            title1.upper(), size=31, color=WHITE, bold=True
        )
        add_text(
            slide, 0.82, 1.62, 4.2, 0.55,
            title2.upper(), size=31, color=accent, bold=True
        )
        add_rect(slide, 0.82, 2.35, 3.8, 0.05, accent)
        add_text(
            slide, 0.82, 2.62, 5.8, 0.45,
            subtitle, size=13, color=RGBColor(0xD7, 0xDF, 0xF4)
        )
        add_text(
            slide, 0.82, 0.38, 0.55, 0.35,
            f"{number:02d}", size=12, color=accent, bold=True
        )

        # simple white icon inside accent circle, matching the PDF's visual
        circle = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(10.45), Inches(1.25),
            Inches(1.45), Inches(1.45)
        )
        circle.fill.solid()
        circle.fill.fore_color.rgb = accent
        circle.line.fill.background()
        add_text(
            slide, 10.45, 1.58, 1.45, 0.72,
            icon_text, size=30, color=WHITE, bold=True,
            align=PP_ALIGN.CENTER
        )

    def add_kpi_card(slide, left, top, width, height, accent,
                     icon_text, label, value, budget_text,
                     status_text, status_kind="good"):
        # White card + colored top line
        add_rect(slide, left, top, width, height, WHITE, GRID, radius=False)
        add_rect(slide, left, top, width, 0.07, accent)

        # icon circle
        circle = slide.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(left + 0.18), Inches(top + 0.16),
            Inches(0.50), Inches(0.50)
        )
        circle.fill.solid()
        circle.fill.fore_color.rgb = accent
        circle.line.fill.background()
        add_text(
            slide, left + 0.18, top + 0.25, 0.50, 0.26,
            icon_text, size=16, color=WHITE, bold=True,
            align=PP_ALIGN.CENTER
        )

        add_text(
            slide, left + 0.82, top + 0.18,
            width - 1.00, 0.36,
            label, size=9.5, color=MUTED, bold=False
        )

        add_text(
            slide, left + 0.18, top + 0.72,
            width - 0.36, 0.42,
            value, size=22, color=TEXT, bold=True
        )

        add_text(
            slide, left + 0.18, top + 1.18,
            width - 0.36, 0.30,
            budget_text, size=8.5, color=MUTED
        )

        status_fill = PALE_GREEN if status_kind == "good" else (
            PALE_RED if status_kind == "bad" else PALE_AMBER
        )
        status_color = GREEN if status_kind == "good" else (
            RED if status_kind == "bad" else AMBER
        )

        add_rect(
            slide, left + 0.18, top + height - 0.40,
            width - 0.36, 0.28,
            status_fill
        )
        add_text(
            slide, left + 0.25, top + height - 0.38,
            width - 0.50, 0.23,
            status_text, size=8.2,
            color=status_color, bold=True,
            align=PP_ALIGN.CENTER
        )

    def add_panel(slide, left, top, width, height, title=None,
                  title_color=TEXT, top_accent=None):
        add_rect(slide, left, top, width, height, WHITE, GRID)
        if top_accent is not None:
            add_rect(slide, left, top, width, 0.06, top_accent)
        if title:
            add_text(
                slide, left + 0.28, top + 0.16,
                width - 0.56, 0.32,
                title, size=11.5, color=TEXT, bold=True
            )
        return None

    def add_note(slide, left, top, width, height, text,
                 fill=PALE_AMBER, accent=AMBER, color=TEXT):
        add_rect(slide, left, top, width, height, fill, accent)
        add_rect(slide, left, top, 0.06, height, accent)
        add_text(
            slide, left + 0.20, top + 0.07,
            width - 0.35, height - 0.12,
            text, size=8.7, color=color, bold=True
        )

    def set_chart_common(chart, legend=True):
        chart.has_legend = legend
        try:
            chart.chart_area.format.fill.solid()
            chart.chart_area.format.fill.fore_color.rgb = WHITE
            chart.chart_area.format.line.color.rgb = GRID
        except Exception:
            pass
        try:
            chart.plot_area.format.fill.solid()
            chart.plot_area.format.fill.fore_color.rgb = WHITE
            chart.plot_area.format.line.fill.background()
        except Exception:
            pass
        if legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
            chart.legend.font.name = FONT
            chart.legend.font.size = Pt(8)
            chart.legend.font.color.rgb = MUTED
        try:
            ca = chart.category_axis
            ca.tick_labels.font.name = FONT
            ca.tick_labels.font.size = Pt(8)
            ca.tick_labels.font.color.rgb = MUTED
            ca.format.line.color.rgb = GRID
        except Exception:
            pass
        try:
            va = chart.value_axis
            va.tick_labels.font.name = FONT
            va.tick_labels.font.size = Pt(8)
            va.tick_labels.font.color.rgb = MUTED
            va.format.line.color.rgb = GRID
            va.has_major_gridlines = True
            va.major_gridlines.format.line.color.rgb = GRID
        except Exception:
            pass

    def add_table(slide, left, top, width, height, headers, rows,
                  col_widths=None, header_fill=NAVY, font_size=8.2):
        table_shape = slide.shapes.add_table(
            len(rows) + 1, len(headers),
            Inches(left), Inches(top),
            Inches(width), Inches(height)
        )
        table = table_shape.table

        if col_widths:
            for i, cw in enumerate(col_widths):
                table.columns[i].width = Inches(cw)

        # header
        for j, h in enumerate(headers):
            cell = table.cell(0, j)
            cell.text = str(h)
            cell.fill.solid()
            cell.fill.fore_color.rgb = header_fill
            cell.margin_left = Inches(0.06)
            cell.margin_right = Inches(0.06)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.CENTER
                for r in p.runs:
                    r.font.name = FONT
                    r.font.size = Pt(font_size)
                    r.font.bold = True
                    r.font.color.rgb = WHITE

        for i, row in enumerate(rows, start=1):
            fill = WHITE if i % 2 else PALE_BLUE
            for j, val in enumerate(row):
                cell = table.cell(i, j)
                cell.text = str(val)
                cell.fill.solid()
                cell.fill.fore_color.rgb = fill
                cell.margin_left = Inches(0.06)
                cell.margin_right = Inches(0.06)
                cell.margin_top = Inches(0.025)
                cell.margin_bottom = Inches(0.025)
                for p in cell.text_frame.paragraphs:
                    p.alignment = PP_ALIGN.LEFT if j == 0 else PP_ALIGN.CENTER
                    for r in p.runs:
                        r.font.name = FONT
                        r.font.size = Pt(font_size)
                        r.font.color.rgb = TEXT
        return table_shape

    def money(x):
        try:
            return fmt_rp(float(x))
        except Exception:
            return str(x)

    def pct(x):
        try:
            return f"{float(x):.1f}%"
        except Exception:
            return "-"

    # ------------------------------------------------------------
    # FILTER / PERIOD
    # ------------------------------------------------------------
    period = ", ".join(month_list) if month_list else "-"
    site_txt = (
        ", ".join(site_list)
        if len(site_list) <= 5 else f"{len(site_list)} Site"
    )
    kat_txt = ", ".join([KATEGORI_LABEL.get(k, k) for k in kat_list])

    # ------------------------------------------------------------
    # MAIN METRICS
    # ------------------------------------------------------------
    pend_r = data["pendapatan_realisasi"].sum()
    pend_b = data["pendapatan_budget"].sum()
    prest_r = data["prestasi_realisasi"].sum()
    prest_b = data["prestasi_budget"].sum()
    biaya_r = data["total_biaya_realisasi"].sum()
    biaya_b = data["total_biaya_budget"].sum()

    ach_pend = (pend_r / pend_b * 100) if pend_b else 0
    ach_prest = (prest_r / prest_b * 100) if prest_b else 0
    ach_biaya = (biaya_r / biaya_b * 100) if biaya_b else 0

    target_pop = data.loc[
        data["pendapatan_budget"] > 0, "nama_unit"
    ].nunique()
    real_pop = data.loc[
        data["pendapatan_realisasi"] > 0, "nama_unit"
    ].nunique()
    ach_pop = (real_pop / target_pop * 100) if target_pop else 0

    # ------------------------------------------------------------
    # SLIDE 1 — COVER, closely following PDF cover
    # ------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_rect(s, 0, 0, 13.333, 7.5, NAVY)
    add_rect(s, 0, 0, 0.25, 7.5, CYAN)

    # subtle large circles on right
    for left, top, size, col in [
        (9.15, -1.0, 5.0, RGBColor(0x2C, 0x38, 0x80)),
        (10.00, -0.45, 4.0, RGBColor(0x34, 0x40, 0x89)),
        (10.72, 0.10, 3.0, RGBColor(0x3B, 0x48, 0x95)),
    ]:
        circ = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(left), Inches(top),
            Inches(size), Inches(size)
        )
        circ.fill.solid()
        circ.fill.fore_color.rgb = col
        circ.line.fill.background()

    add_text(
        s, 0.75, 0.58, 8.0, 0.25,
        "PT. BUANA KARYA MANDIRI SEJAHTERA (BKMS)",
        size=8.5, color=RGBColor(0xC9, 0xD0, 0xE8), bold=True
    )

    add_text(
        s, 0.75, 1.55, 8.0, 0.70,
        "DASHBOARD",
        size=33, color=WHITE, bold=True
    )
    add_text(
        s, 0.75, 2.20, 8.5, 0.72,
        "BIAYA & PENDAPATAN",
        size=33, color=CYAN, bold=True
    )
    add_rect(s, 0.75, 3.03, 4.65, 0.06, CYAN)

    add_text(
        s, 0.75, 3.34, 7.0, 0.35,
        "TARGET VS REALISASI",
        size=15, color=WHITE, bold=True
    )
    add_text(
        s, 0.75, 3.78, 8.2, 0.34,
        f"Periode {period}",
        size=12, color=RGBColor(0xD7, 0xDF, 0xF4)
    )

    add_text(
        s, 0.75, 5.95, 8.0, 0.25,
        f"Site: {site_txt}",
        size=8.5, color=RGBColor(0x9D, 0xA8, 0xC8)
    )
    add_text(
        s, 0.75, 6.25, 8.0, 0.25,
        f"Kategori: {kat_txt}",
        size=8.5, color=RGBColor(0x9D, 0xA8, 0xC8)
    )
    add_text(
        s, 0.75, 6.78, 8.0, 0.22,
        "Prepared automatically from Dashboard Biaya & Pendapatan",
        size=7.5, color=RGBColor(0x9D, 0xA8, 0xC8)
    )

    add_text(
        s, 10.05, 6.75, 2.35, 0.25,
        "Cawu / Management Report",
        size=7.5, color=RGBColor(0xC9, 0xD0, 0xE8),
        align=PP_ALIGN.RIGHT
    )

    # ------------------------------------------------------------
    # SLIDE 2 — AGENDA, same 2x2 visual language as PDF
    # ------------------------------------------------------------
    s = add_slide_base()
    add_header(s, "AGENDA DASHBOARD — TARGET VS REALISASI", "Dashboard")
    add_text(
        s, 0.68, 0.83, 11.8, 0.28,
        "Struktur: Performance Keseluruhan → Maintenance → Sparepart → Populasi & Insights",
        size=8.5, color=MUTED
    )

    agenda = [
        ("01", "Performance", "Pendapatan · Prestasi · Biaya", CYAN, "↗"),
        ("02", "Maintenance", "Rekap biaya · Rutin · Non Rutin", PURPLE, "⚙"),
        ("03", "Sparepart", "Top barang · Kategori · Pemakaian", GREEN, "▦"),
        ("04", "Populasi & Insights", "Target · Realisasi · Analisa gap", RED, "$"),
    ]
    positions = [
        (0.55, 1.35), (6.78, 1.35),
        (0.55, 4.00), (6.78, 4.00)
    ]
    for (num, title, sub, accent, icon), (x, y) in zip(agenda, positions):
        add_rect(s, x, y, 5.98, 2.28, WHITE, GRID)
        add_rect(s, x, y, 0.08, 2.28, accent)
        add_text(s, x + 0.35, y + 0.32, 0.70, 0.40,
                 num, size=26, color=accent, bold=True)
        add_text(s, x + 0.35, y + 0.92, 3.9, 0.32,
                 title, size=13, color=TEXT, bold=True)
        add_text(s, x + 0.35, y + 1.42, 4.4, 0.35,
                 sub, size=8.5, color=MUTED)
        c = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(x + 5.05), Inches(y + 0.45),
            Inches(0.82), Inches(0.82)
        )
        c.fill.solid(); c.fill.fore_color.rgb = accent; c.line.fill.background()
        add_text(s, x + 5.05, y + 0.65, 0.82, 0.30,
                 icon, size=17, color=WHITE, bold=True,
                 align=PP_ALIGN.CENTER)

    add_rect(s, 0.55, 6.78, 12.0, 0.28, NAVY)
    add_text(
        s, 0.70, 6.80, 11.7, 0.20,
        "Data mengikuti filter Dashboard saat tombol PPTX ditekan",
        size=7.5, color=WHITE, bold=True,
        align=PP_ALIGN.CENTER
    )
    add_footer(s, 2)

    # ------------------------------------------------------------
    # SLIDE 3 — DIVIDER: PERFORMANCE
    # ------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_section_divider(
        s, 1, "PERFORMANCE", "KESELURUHAN",
        "Pendapatan · Prestasi · Biaya · Populasi",
        CYAN, "↗"
    )

    # ------------------------------------------------------------
    # SLIDE 4 — KPI DASHBOARD, closest to PDF KPI page
    # ------------------------------------------------------------
    s = add_slide_base()
    add_header(
        s,
        "KPI DASHBOARD — Performance Keseluruhan",
        "Performance Keseluruhan · 01"
    )

    pend_kind = "good" if ach_pend >= 100 else "bad"
    prest_kind = "good" if ach_prest >= 100 else "bad"
    biaya_kind = "good" if ach_biaya <= 100 else "bad"
    pop_kind = "good" if ach_pop >= 100 else "bad"

    add_kpi_card(
        s, 0.38, 0.98, 3.05, 1.88, RED,
        "Rp", "Pendapatan (Realisasi)",
        money(pend_r),
        f"Target: {money(pend_b)}",
        f"{ach_pend:.1f}% vs Target",
        pend_kind
    )
    add_kpi_card(
        s, 3.62, 0.98, 3.05, 1.88, CYAN,
        "↗", "Prestasi (Realisasi)",
        f"{prest_r:,.0f}",
        f"Target: {prest_b:,.0f}",
        f"{ach_prest:.1f}% vs Target",
        prest_kind
    )
    add_kpi_card(
        s, 6.86, 0.98, 3.05, 1.88, GREEN,
        "⚙", "Total Biaya (Realisasi)",
        money(biaya_r),
        f"Budget: {money(biaya_b)}",
        f"{ach_biaya:.1f}% — {'Under Budget' if ach_biaya <= 100 else 'Over Budget'}",
        biaya_kind
    )
    add_kpi_card(
        s, 10.10, 0.98, 2.85, 1.88, PURPLE,
        "◎", "Populasi Unit",
        f"{real_pop:,}",
        f"Target: {target_pop:,}",
        f"{ach_pop:.1f}% vs Target",
        pop_kind
    )

    # target vs actual chart
    add_panel(s, 0.38, 3.05, 7.55, 3.55,
              "Target vs Realisasi — Pendapatan & Biaya",
              top_accent=CYAN)

    cd = CategoryChartData()
    cd.categories = ["Pendapatan", "Biaya"]
    cd.add_series("Target", (pend_b, biaya_b))
    cd.add_series("Realisasi", (pend_r, biaya_r))
    frame = s.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.60), Inches(3.55),
        Inches(7.10), Inches(2.72), cd
    )
    chart = frame.chart
    chart.series[0].format.fill.solid()
    chart.series[0].format.fill.fore_color.rgb = RGBColor(0xB9, 0xC0, 0xCC)
    chart.series[1].format.fill.solid()
    chart.series[1].format.fill.fore_color.rgb = CYAN
    set_chart_common(chart)

    # achievement summary panel
    add_panel(s, 8.15, 3.05, 4.80, 3.55,
              "Ringkasan Capaian",
              top_accent=GREEN)
    add_text(s, 8.45, 3.55, 4.1, 0.30, "Pendapatan", size=9, color=MUTED)
    add_text(s, 8.45, 3.86, 3.8, 0.50,
             f"{ach_pend:.1f}%", size=25,
             color=GREEN if ach_pend >= 100 else RED, bold=True)
    add_text(s, 8.45, 4.43, 3.8, 0.25,
             "Realisasi dibanding target", size=8, color=MUTED)

    add_rect(s, 8.45, 4.86, 3.95, 0.02, GRID)
    add_text(s, 8.45, 5.08, 3.8, 0.28,
             f"Prestasi  {ach_prest:.1f}%", size=10,
             color=GREEN if ach_prest >= 100 else RED, bold=True)
    add_text(s, 8.45, 5.50, 3.8, 0.28,
             f"Biaya      {ach_biaya:.1f}%", size=10,
             color=GREEN if ach_biaya <= 100 else RED, bold=True)
    add_text(s, 8.45, 5.92, 3.8, 0.28,
             f"Populasi  {ach_pop:.1f}%", size=10,
             color=GREEN if ach_pop >= 100 else RED, bold=True)

    add_footer(s, 4)

    # ------------------------------------------------------------
    # SLIDE 5 — TREND / MONTHLY PERFORMANCE
    # ------------------------------------------------------------
    s = add_slide_base()
    add_header(
        s,
        "PERFORMANCE — Pendapatan, Prestasi & Biaya Bulanan",
        "Performance Keseluruhan · 01"
    )

    monthly = (
        data.groupby("bulan_no", as_index=False)
        .agg(
            pend_r=("pendapatan_realisasi", "sum"),
            pend_b=("pendapatan_budget", "sum"),
            biaya_r=("total_biaya_realisasi", "sum"),
            biaya_b=("total_biaya_budget", "sum"),
            prest_r=("prestasi_realisasi", "sum"),
            prest_b=("prestasi_budget", "sum"),
        )
        .sort_values("bulan_no")
    )
    month_labels = [
        MONTH_ORDER[int(x)-1] if 1 <= int(x) <= 12 else str(x)
        for x in monthly["bulan_no"]
    ] if not monthly.empty else []

    add_panel(s, 0.38, 0.98, 7.75, 5.70,
              "Tren Bulanan: Pendapatan & Biaya",
              top_accent=CYAN)

    if not monthly.empty:
        cd5 = CategoryChartData()
        cd5.categories = month_labels
        cd5.add_series("Pendapatan Aktual", tuple(monthly["pend_r"]))
        cd5.add_series("Biaya Aktual", tuple(monthly["biaya_r"]))
        f5 = s.shapes.add_chart(
            XL_CHART_TYPE.LINE_MARKERS,
            Inches(0.58), Inches(1.50),
            Inches(7.35), Inches(4.80), cd5
        )
        c5 = f5.chart
        c5.series[0].format.line.color.rgb = CYAN
        c5.series[0].format.line.width = Pt(2.5)
        c5.series[1].format.line.color.rgb = RED
        c5.series[1].format.line.width = Pt(2.5)
        set_chart_common(c5)

    add_panel(s, 8.38, 0.98, 4.57, 5.70,
              "Capaian Bulanan",
              top_accent=GREEN)

    if not monthly.empty:
        rows = []
        for _, rr in monthly.iterrows():
            p = rr["pend_r"] / rr["pend_b"] * 100 if rr["pend_b"] else 0
            b = rr["biaya_r"] / rr["biaya_b"] * 100 if rr["biaya_b"] else 0
            pr = rr["prest_r"] / rr["prest_b"] * 100 if rr["prest_b"] else 0
            mname = MONTH_ORDER[int(rr["bulan_no"]) - 1]
            rows.append([mname, f"{p:.1f}%", f"{pr:.1f}%", f"{b:.1f}%"])
        add_table(
            s, 8.60, 1.55, 4.12, 3.70,
            ["Bulan", "Pend.", "Prest.", "Biaya"],
            rows,
            col_widths=[0.95, 1.00, 1.00, 1.00],
            font_size=7.5
        )
    else:
        add_text(s, 8.65, 2.00, 3.9, 0.5,
                 "Tidak ada data bulanan.", size=10, color=MUTED)

    add_note(
        s, 8.60, 5.55, 4.12, 0.75,
        "Gunakan tabel ini untuk melihat bulan yang menjadi penyumbang utama gap terhadap target.",
        fill=PALE_CYAN, accent=CYAN
    )
    add_footer(s, 5)

    # ------------------------------------------------------------
    # SLIDE 6 — DIVIDER: MAINTENANCE
    # ------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_section_divider(
        s, 2, "MAINTENANCE", "ANALYSIS",
        "Rekap biaya · Rutin · Non Rutin · Kategori",
        PURPLE, "⚙"
    )

    # ------------------------------------------------------------
    # SLIDE 7 — MAINTENANCE, matching PDF table + insight layout
    # ------------------------------------------------------------
    if maint_data is not None and not maint_data.empty:
        s = add_slide_base()
        add_header(
            s,
            "REKAP BIAYA MAINTENANCE — Budget / Realisasi & Analisis",
            "Maintenance · 02"
        )

        total_m = maint_data["biaya"].sum()
        rutin_b = maint_data.loc[
            maint_data["jenis_pemeliharaan"] == "RUTIN", "biaya"
        ].sum()
        nonrutin_b = maint_data.loc[
            maint_data["jenis_pemeliharaan"] == "NON RUTIN", "biaya"
        ].sum()
        n_trx = len(maint_data)

        add_kpi_card(
            s, 0.38, 0.98, 3.75, 1.55, GREEN,
            "Σ", "Total Biaya Maintenance",
            money(total_m),
            f"{n_trx:,} transaksi",
            "100% dari maintenance",
            "good"
        )
        add_kpi_card(
            s, 4.36, 0.98, 3.75, 1.55, CYAN,
            "R", "Biaya Rutin",
            money(rutin_b),
            f"{(rutin_b/total_m*100 if total_m else 0):.1f}% dari total",
            "RUTIN",
            "good"
        )
        add_kpi_card(
            s, 8.34, 0.98, 4.61, 1.55, RED,
            "N", "Biaya Non Rutin",
            money(nonrutin_b),
            f"{(nonrutin_b/total_m*100 if total_m else 0):.1f}% dari total",
            "NON RUTIN",
            "bad" if nonrutin_b > rutin_b else "amber"
        )

        cat = (
            maint_data.groupby("kategori_sparepart", as_index=False)["biaya"]
            .sum().sort_values("biaya", ascending=False)
        )

        add_panel(s, 0.38, 2.78, 7.70, 3.72,
                  "Maintenance atas Apa Saja — Top Kategori",
                  top_accent=PURPLE)

        topcat = cat.head(10)
        if not topcat.empty:
            cd7 = CategoryChartData()
            cd7.categories = list(topcat["kategori_sparepart"].astype(str))
            cd7.add_series("Biaya", tuple(topcat["biaya"]))
            f7 = s.shapes.add_chart(
                XL_CHART_TYPE.BAR_CLUSTERED,
                Inches(0.58), Inches(3.28),
                Inches(7.30), Inches(2.95), cd7
            )
            c7 = f7.chart
            c7.series[0].format.fill.solid()
            c7.series[0].format.fill.fore_color.rgb = PURPLE
            set_chart_common(c7, legend=False)

        add_panel(s, 8.34, 2.78, 4.61, 3.72,
                  "Analisis Maintenance",
                  top_accent=RED)

        top_name = str(topcat.iloc[0]["kategori_sparepart"]) if not topcat.empty else "-"
        top_value = float(topcat.iloc[0]["biaya"]) if not topcat.empty else 0
        add_text(
            s, 8.65, 3.30, 3.9, 0.30,
            "Kategori biaya terbesar", size=9, color=MUTED
        )
        add_text(
            s, 8.65, 3.65, 3.9, 0.45,
            top_name, size=15, color=TEXT, bold=True
        )
        add_text(
            s, 8.65, 4.12, 3.9, 0.35,
            money(top_value), size=13, color=RED, bold=True
        )
        add_rect(s, 8.65, 4.62, 3.8, 0.02, GRID)

        if total_m:
            r_pct = rutin_b / total_m * 100
            n_pct = nonrutin_b / total_m * 100
        else:
            r_pct = n_pct = 0

        add_text(
            s, 8.65, 4.86, 3.8, 0.30,
            f"Rutin       {r_pct:.1f}%", size=9.5, color=GREEN, bold=True
        )
        add_text(
            s, 8.65, 5.25, 3.8, 0.30,
            f"Non Rutin  {n_pct:.1f}%", size=9.5, color=RED, bold=True
        )
        add_note(
            s, 8.65, 5.70, 3.80, 0.55,
            "Prioritaskan review pada kategori dengan biaya terbesar.",
            fill=PALE_RED, accent=RED
        )
        add_footer(s, 7)

    # ------------------------------------------------------------
    # SLIDE 8 — SPAREPART
    # ------------------------------------------------------------
    if maint_data is not None and not maint_data.empty:
        # Use maintenance data as base even if sparepart detail is absent.
        s = add_slide_base()
        add_header(
            s,
            "REKAP PEMAKAIAN SPAREPART — Top Barang & Komposisi",
            "Sparepart · 03"
        )

        # derive from available detail if present in globals is not possible here,
        # so use maintenance categories as a safe fallback.
        catsp = (
            maint_data.groupby("kategori_sparepart", as_index=False)["biaya"]
            .sum().sort_values("biaya", ascending=False)
        )

        total_sp = catsp["biaya"].sum() if not catsp.empty else 0
        n_jenis = len(catsp)

        add_kpi_card(
            s, 0.38, 0.98, 3.75, 1.55, CYAN,
            "Σ", "Biaya Maintenance Terklasifikasi",
            money(total_sp),
            f"{n_jenis:,} kategori",
            "Basis analisis kategori",
            "good"
        )
        add_kpi_card(
            s, 4.36, 0.98, 3.75, 1.55, GREEN,
            "▦", "Kategori Sparepart",
            f"{n_jenis:,}",
            "Kategori teridentifikasi",
            "Monitoring",
            "good"
        )
        add_kpi_card(
            s, 8.34, 0.98, 4.61, 1.55, PURPLE,
            "↗", "Top Kategori",
            str(catsp.iloc[0]["kategori_sparepart"]) if not catsp.empty else "-",
            money(catsp.iloc[0]["biaya"]) if not catsp.empty else "-",
            "Prioritas review",
            "amber"
        )

        add_panel(
            s, 0.38, 2.78, 7.70, 3.72,
            "Komposisi Biaya per Kategori",
            top_accent=CYAN
        )
        if not catsp.empty:
            cd8 = CategoryChartData()
            cd8.categories = list(catsp.head(10)["kategori_sparepart"].astype(str))
            cd8.add_series("Biaya", tuple(catsp.head(10)["biaya"]))
            f8 = s.shapes.add_chart(
                XL_CHART_TYPE.BAR_CLUSTERED,
                Inches(0.58), Inches(3.28),
                Inches(7.30), Inches(2.95), cd8
            )
            c8 = f8.chart
            c8.series[0].format.fill.solid()
            c8.series[0].format.fill.fore_color.rgb = CYAN
            set_chart_common(c8, legend=False)

        add_panel(
            s, 8.34, 2.78, 4.61, 3.72,
            "Top 5 Kategori",
            top_accent=GREEN
        )
        rows8 = []
        for _, rr in catsp.head(5).iterrows():
            share = rr["biaya"] / total_sp * 100 if total_sp else 0
            rows8.append([
                str(rr["kategori_sparepart"]),
                money(rr["biaya"]),
                f"{share:.1f}%"
            ])
        if rows8:
            add_table(
                s, 8.55, 3.28, 4.18, 2.55,
                ["Kategori", "Biaya", "%"],
                rows8,
                col_widths=[1.75, 1.35, 0.75],
                font_size=7.2
            )
        add_note(
            s, 8.55, 5.95, 4.18, 0.40,
            "Top kategori = prioritas awal untuk review penggunaan biaya.",
            fill=PALE_GREEN, accent=GREEN
        )
        add_footer(s, 8)

    # ------------------------------------------------------------
    # SLIDE 9 — DIVIDER: POPULASI & INSIGHTS
    # ------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_section_divider(
        s, 4, "POPULASI &", "INSIGHTS",
        "Target · Realisasi · Site Performance · Gap",
        RED, "$"
    )

    # ------------------------------------------------------------
    # SLIDE 10 — POPULATION + SITE ANALYSIS
    # ------------------------------------------------------------
    s = add_slide_base()
    add_header(
        s,
        "ANALISIS — Populasi Unit & Penyebab Gap Pendapatan",
        "Populasi & Insights · 04"
    )

    add_kpi_card(
        s, 0.38, 0.98, 3.75, 1.55, NAVY,
        "T", "Target Populasi",
        f"{target_pop:,}",
        "Unit dengan budget Pendapatan",
        "Baseline",
        "amber"
    )
    add_kpi_card(
        s, 4.36, 0.98, 3.75, 1.55, GREEN,
        "✓", "Realisasi Populasi",
        f"{real_pop:,}",
        "Unit dengan realisasi Pendapatan",
        f"{ach_pop:.1f}% vs Target",
        "good" if ach_pop >= 100 else "bad"
    )
    add_kpi_card(
        s, 8.34, 0.98, 4.61, 1.55, RED,
        "!", "Gap Pendapatan",
        money(pend_b - pend_r),
        f"Target {money(pend_b)}",
        f"{ach_pend:.1f}% tercapai",
        "good" if ach_pend >= 100 else "bad"
    )

    # site chart
    add_panel(
        s, 0.38, 2.78, 7.70, 3.72,
        "Capaian Pendapatan per Site",
        top_accent=CYAN
    )

    site_group = (
        data.groupby("lokasi", as_index=False)
        .agg(realisasi=("pendapatan_realisasi", "sum"),
             budget=("pendapatan_budget", "sum"))
    )
    site_group = site_group[site_group["budget"] > 0].copy()
    if not site_group.empty:
        site_group["capaian"] = (
            site_group["realisasi"] / site_group["budget"] * 100
        )
        site_group = site_group.sort_values("capaian", ascending=True).head(10)

        cd10 = CategoryChartData()
        cd10.categories = list(site_group["lokasi"].astype(str))
        cd10.add_series("Capaian %", tuple(site_group["capaian"]))
        f10 = s.shapes.add_chart(
            XL_CHART_TYPE.BAR_CLUSTERED,
            Inches(0.58), Inches(3.25),
            Inches(7.30), Inches(2.98), cd10
        )
        c10 = f10.chart
        c10.series[0].format.fill.solid()
        c10.series[0].format.fill.fore_color.rgb = CYAN
        set_chart_common(c10, legend=False)

    # insights panel
    add_panel(
        s, 8.34, 2.78, 4.61, 3.72,
        "Key Insights",
        top_accent=RED
    )

    gap_rp = pend_b - pend_r
    gap_pop = target_pop - real_pop

    insight_lines = [
        f"Pendapatan: {ach_pend:.1f}% dari target.",
        f"Gap pendapatan: {money(gap_rp)}.",
        f"Gap populasi: {gap_pop:,} unit.",
    ]
    if not site_group.empty:
        worst = site_group.iloc[0]
        insight_lines.append(
            f"Site terendah: {worst['lokasi']} ({worst['capaian']:.1f}%)."
        )
    if ach_prest < 100:
        insight_lines.append(
            f"Prestasi {ach_prest:.1f}% turut menekan pendapatan."
        )
    else:
        insight_lines.append(
            "Prestasi sudah mencapai target; evaluasi faktor pendapatan lainnya."
        )

    y = 3.30
    for line in insight_lines:
        c = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(8.62), Inches(y + 0.04),
            Inches(0.12), Inches(0.12)
        )
        c.fill.solid(); c.fill.fore_color.rgb = RED; c.line.fill.background()
        add_text(
            s, 8.86, y, 3.72, 0.42,
            line, size=8.4, color=TEXT
        )
        y += 0.52

    add_note(
        s, 8.60, 5.82, 4.08, 0.45,
        "Prioritas: fokus pada site dengan capaian terendah dan unit yang belum menghasilkan Pendapatan.",
        fill=PALE_RED, accent=RED
    )
    add_footer(s, 10)

    # ------------------------------------------------------------
    # FINAL SLIDE — THANK YOU / SUMMARY, matching PDF closing style
    # ------------------------------------------------------------
    s = prs.slides.add_slide(blank)
    add_rect(s, 0, 0, 13.333, 7.5, NAVY)
    add_rect(s, 0, 0, 0.25, 7.5, CYAN)

    for left, top, size, col in [
        (9.25, -0.9, 4.8, RGBColor(0x2C, 0x38, 0x80)),
        (10.10, -0.35, 3.9, RGBColor(0x34, 0x40, 0x89)),
    ]:
        circ = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(left), Inches(top),
            Inches(size), Inches(size)
        )
        circ.fill.solid(); circ.fill.fore_color.rgb = col
        circ.line.fill.background()

    add_text(
        s, 0.75, 0.75, 7.0, 0.75,
        "TERIMA KASIH",
        size=31, color=WHITE, bold=True
    )
    add_text(
        s, 0.75, 1.48, 7.0, 0.38,
        "Ringkasan Dashboard — Target vs Realisasi",
        size=13, color=CYAN, bold=True
    )

    # summary box
    add_rect(
        s, 0.68, 2.20, 7.35, 3.65,
        RGBColor(0x27, 0x31, 0x70), None
    )
    add_text(
        s, 0.98, 2.45, 6.6, 0.30,
        f"RINGKASAN OPERASIONAL — {period}",
        size=10, color=RGBColor(0xC9, 0xD0, 0xE8), bold=True
    )

    summary_rows = [
        ("Pendapatan", money(pend_r), f"{ach_pend:.1f}% dari target"),
        ("Prestasi", f"{prest_r:,.0f}", f"{ach_prest:.1f}% dari target"),
        ("Total Biaya", money(biaya_r), f"{ach_biaya:.1f}% dari budget"),
        ("Populasi Unit", f"{real_pop:,}", f"{ach_pop:.1f}% dari target"),
    ]

    sy = 3.00
    for label, val, note in summary_rows:
        add_text(s, 1.00, sy, 1.70, 0.30, label, size=8.5,
                 color=RGBColor(0xC9, 0xD0, 0xE8))
        add_text(s, 2.72, sy, 2.25, 0.30, val, size=10,
                 color=WHITE, bold=True)
        add_text(s, 5.00, sy, 2.60, 0.30, note, size=7.8,
                 color=RGBColor(0xA7, 0xB2, 0xD0))
        sy += 0.62

    # right summary
    add_text(
        s, 8.55, 2.48, 3.7, 0.30,
        "RINGKASAN MANAGEMENT",
        size=10, color=WHITE, bold=True
    )
    bullets = [
        f"Pendapatan tercapai {ach_pend:.1f}% dari target.",
        f"Prestasi tercapai {ach_prest:.1f}% dari target.",
        f"Biaya berada di {ach_biaya:.1f}% terhadap budget.",
        f"Populasi terealisasi {real_pop:,} dari {target_pop:,} unit.",
    ]
    by = 3.05
    for b in bullets:
        add_text(s, 8.55, by, 0.20, 0.24, "●",
                 size=9, color=CYAN, bold=True)
        add_text(s, 8.85, by, 3.25, 0.52, b,
                 size=8.5, color=WHITE)
        by += 0.72

    add_text(
        s, 0.75, 6.70, 7.0, 0.22,
        "Integritas  •  Kemandirian  •  Kebersamaan  •  Tanggung Jawab  •  Inovatif  •  Komitmen",
        size=7.5, color=RGBColor(0xC9, 0xD0, 0xE8)
    )

    # ------------------------------------------------------------
    # SAVE
    # ------------------------------------------------------------
    buf = _io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

colX, colY = st.columns([5, 1.4])
with colY:
    if st.button("📽️ Buat Presentasi (PPTX)", use_container_width=True, type="primary"):
        with st.spinner("Menyusun slide presentasi..."):
            maint_for_pptx = maint_df_site_bulan if not maint_raw.empty else pd.DataFrame()
            pptx_bytes = build_pptx(df, maint_for_pptx, sel_site, sel_month, sel_kat)
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
# 1-4. CAPAIAN UTAMA: PENDAPATAN, PRESTASI, BIAYA LANGSUNG & BTL
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Capaian Utama</h3>', unsafe_allow_html=True)

pendapatan_pill, pendapatan_style = achievement_pill(
    ach_pendapatan, higher_is_better=True
)
prestasi_pill, prestasi_style = achievement_pill(
    ach_prestasi, higher_is_better=True
)
biaya_langsung_pill, biaya_langsung_style = achievement_pill(
    ach_biaya_langsung, higher_is_better=False
)
biaya_tidak_langsung_pill, biaya_tidak_langsung_style = achievement_pill(
    ach_biaya_tidak_langsung, higher_is_better=False
)

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
        icon="🔧", icon_bg=GOLD, accent=GOLD,
        label="Biaya Langsung: Realisasi vs Target",
        value=fmt_rp(tot_biaya_langsung_r),
        budget_text=f"Target: {fmt_rp(tot_biaya_langsung_b)}",
        pill_text=biaya_langsung_pill,
        pill_style=biaya_langsung_style,
    ), unsafe_allow_html=True)

with c4:
    st.markdown(kpi_card(
        icon="🏢", icon_bg=PURPLE, accent=PURPLE,
        label="Biaya Tidak Langsung: Realisasi vs Target",
        value=fmt_rp(tot_biaya_tidak_langsung_r),
        budget_text=f"Target: {fmt_rp(tot_biaya_tidak_langsung_b)}",
        pill_text=biaya_tidak_langsung_pill,
        pill_style=biaya_tidak_langsung_style,
    ), unsafe_allow_html=True)

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
st.caption("Dashboard Biaya & Pendapatan • PT Buana Karya Mandiri Sejahtera (BKMS) • Dibuat Oleh Fahrudin")
