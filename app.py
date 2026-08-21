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
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
KATEGORI_LABEL = {"AB": "Alat Berat (AB)", "TR": "Transportasi (TR)"}

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

@st.cache_data
def load_sasaran_mutu_data(file) -> pd.DataFrame:
    if not Path(file).exists():
        return pd.DataFrame()
    return pd.read_csv(file, dtype={"id_unit": str})

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
    MINING_SITES = ["TANJUNG", "BUHUT", "BUHUT LHL", "AMPAH"]
    PLANTATION_SITES = ["SUNGAI DANAU", "KUMAI"]
    DIVISI_MAP = {"Mining": MINING_SITES, "Plantation": PLANTATION_SITES}

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

    sasaran_mutu_raw = load_sasaran_mutu_data(SASARAN_MUTU_PATH)

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
        sasaran_mutu_raw["kategori"].isin(sel_kat) &
        (~sasaran_mutu_raw["unit_sewa"])
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
    if budget == 0:
        return None
    return real / budget * 100

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
def build_pptx(data, maint_data, sparepart_data, site_list, month_list, kat_list, sasaran_mutu_data=None) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    import io as _io

    # Khusus site TANJUNG: gabungkan kategori TR ke AB (tidak dipisah AB/TR di seluruh chart PPTX)
    data = data.copy()
    data.loc[data["lokasi"] == "TANJUNG", "kategori"] = "AB"
    if sasaran_mutu_data is not None and not sasaran_mutu_data.empty:
        sasaran_mutu_data = sasaran_mutu_data.copy()
        sasaran_mutu_data.loc[sasaran_mutu_data["lokasi"] == "TANJUNG", "kategori"] = "AB"
        sasaran_mutu_data.loc[sasaran_mutu_data["lokasi"] == "TANJUNG", "Jenis_Sarmut"] = "Sarmut Kelompok Alat Berat"

    # Singkatan nama site dipakai konsisten di semua chart yg padat kategori
    SITE_ABBR = {"SUNGAI DANAU": "S.DANAU", "BUHUT LHL": "B.LHL", "TANJUNG": "TANJUNG",
                 "BUHUT": "BUHUT", "KUMAI": "KUMAI", "AMPAH": "AMPAH"}

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

    def add_card_panel(slide, left, top, width, height, accent_color=None):
        card = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.fill.solid(); card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = BORDER; card.line.width = Pt(0.75)
        card.shadow.inherit = False
        if accent_color:
            strip = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(0.06))
            strip.fill.solid(); strip.fill.fore_color.rgb = accent_color
            strip.line.fill.background(); strip.shadow.inherit = False
        return card

    def add_note_callout(slide, left, top, width, height, icon, text, text_color=RED, size=11):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame; tf.word_wrap = True
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = f"{icon} {text}"
        r.font.size = Pt(size); r.font.bold = True; r.font.italic = True
        r.font.color.rgb = text_color; r.font.name = "Calibri"
        return tb

    def add_finding_box(slide, left, top, width, height, icon, text, bg_color, border_color, text_color):
        box = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        box.fill.solid(); box.fill.fore_color.rgb = bg_color
        box.line.color.rgb = border_color; box.line.width = Pt(1)
        box.shadow.inherit = False
        tf = box.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.15); tf.margin_right = Inches(0.15)
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = f"{icon} {text}"
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
        r = p.add_run(); r.text = f"{icon}  {text}"
        r.font.size = Pt(12.5); r.font.bold = True; r.font.color.rgb = text_color; r.font.name = "Calibri"
        return box

    def add_table(slide, left, top, width, height, headers, rows, status_col=None, col_widths=None,
                  fill_badge=False, font_size=11.5, header_size=12):
        n_rows = len(rows) + 1
        n_cols = len(headers)
        gframe = slide.shapes.add_table(n_rows, n_cols, Inches(left), Inches(top), Inches(width), Inches(height))
        table = gframe.table
        if col_widths:
            total = sum(col_widths)
            for i, w in enumerate(col_widths):
                table.columns[i].width = Inches(width * w / total)
        status_cols = [status_col] if isinstance(status_col, int) else (status_col or [])
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
                is_status = j in status_cols
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
        tf = bar.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.15); tf.margin_right = Inches(0.1)
        p = tf.paragraphs[0]
        r = p.add_run(); r.text = text
        r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = "Calibri"
        return bar

    def ach_txt_pct(real, budget):
        if budget == 0:
            return None
        return real / budget * 100

    import datetime as _dt

    period = sorted(month_list, key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99)[-1] if month_list else "-"
    site_txt = ", ".join(site_list) if len(site_list) <= 6 else f"{len(site_list)} site"
    kat_txt = ", ".join([KATEGORI_LABEL.get(k, k) for k in kat_list])
    _bulan_id = ["Januari","Februari","Maret","April","Mei","Juni","Juli","Agustus","September","Oktober","November","Desember"]
    _now = _dt.datetime.now()
    tgl_laporan = f"{_bulan_id[_now.month-1]} {_now.year}"

    r_ = data["pendapatan_realisasi"].sum(); b_ = data["pendapatan_budget"].sum()
    pr_ = data["prestasi_realisasi"].sum(); pb_ = data["prestasi_budget"].sum()
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

    avg_avail_r = sasaran_mutu_data["availability_pct"].mean() if not sasaran_mutu_data.empty else None
    avg_avail_t = sasaran_mutu_data["availability_target"].mean() if not sasaran_mutu_data.empty else None
    avg_util_r = sasaran_mutu_data["utilisasi_pct"].mean() if not sasaran_mutu_data.empty else None
    avg_util_t = sasaran_mutu_data["utilisasi_target"].mean() if not sasaran_mutu_data.empty else None
    ach_avail = ach_txt_pct(avg_avail_r, avg_avail_t) if (avg_avail_r is not None and avg_avail_t) else None
    ach_util = ach_txt_pct(avg_util_r, avg_util_t) if (avg_util_r is not None and avg_util_t) else None

    # ================= SLIDE 1: KPI DASHBOARD — PERFORMANCE KESELURUHAN =================
    s = add_content_slide(f"KPI DASHBOARD — Performance Keseluruhan s/d {period}", "Ringkasan Kinerja · 01")

    card_w4, card_h4, gap4, cy4 = 2.85, 2.3, 0.25, 1.15
    add_kpi_card(s, 0.55, cy4, card_w4, card_h4, "⚙", TEAL, TEAL if (ach_avail is not None and ach_avail < 100) else GREEN,
                 "Realisasi Availability (Avg)", (f"{avg_avail_r:.1f}%" if avg_avail_r is not None else "-"),
                 f"Target: {avg_avail_t:.1f}%" if avg_avail_t is not None else "Target: -",
                 (f"✓ {ach_avail:.1f}% dari Target" if ach_avail is not None and ach_avail >= 100 else (f"✗ {ach_avail:.1f}% dari Target" if ach_avail is not None else "Data tidak tersedia")),
                 ach_avail is not None and ach_avail >= 100)
    add_kpi_card(s, 0.55 + (card_w4 + gap4), cy4, card_w4, card_h4, "🎯", GOLD, GOLD if (ach_util is not None and ach_util < 100) else GREEN,
                 "Realisasi Utilisasi (Avg)", (f"{avg_util_r:.1f}%" if avg_util_r is not None else "-"),
                 f"Target: {avg_util_t:.1f}%" if avg_util_t is not None else "Target: -",
                 (f"✓ {ach_util:.1f}% dari Target" if ach_util is not None and ach_util >= 100 else (f"✗ {ach_util:.1f}% dari Target" if ach_util is not None else "Data tidak tersedia")),
                 ach_util is not None and ach_util >= 100)
    add_kpi_card(s, 0.55 + 2 * (card_w4 + gap4), cy4, card_w4, card_h4, "💰", GREEN, GREEN if (ach_bl is not None and ach_bl <= 100) else RED,
                 "Biaya Langsung (Rp/Prestasi)", (fmt_rp(bl_r) if bl_r is not None else "-"),
                 f"Budget: {fmt_rp(bl_b)}" if bl_b is not None else "Budget: -",
                 (f"✓ {ach_bl:.1f}% — Under Budget" if ach_bl is not None and ach_bl <= 100 else (f"✗ {ach_bl:.1f}% — Over Budget" if ach_bl is not None else "Target = 0")),
                 ach_bl is not None and ach_bl <= 100)
    add_kpi_card(s, 0.55 + 3 * (card_w4 + gap4), cy4, card_w4, card_h4, "🧾", TEAL, GREEN if (ach_btl is not None and ach_btl <= 100) else RED,
                 "Biaya Tidak Langsung (Rp/Prestasi)", (fmt_rp(btl_r) if btl_r is not None else "-"),
                 f"Budget: {fmt_rp(btl_b)}" if btl_b is not None else "Budget: -",
                 (f"✓ {ach_btl:.1f}% — Under Budget" if ach_btl is not None and ach_btl <= 100 else (f"✗ {ach_btl:.1f}% — Over Budget" if ach_btl is not None else "Target = 0")),
                 ach_btl is not None and ach_btl <= 100)

    add_textbox(s, 0.55, 3.85, 11.5, 0.4, "Realisasi Utilisasi vs Target Utilisasi (Avg) — per Site & Jenis Sarmut", size=13, bold=True, color=TEXT_DARK)
    if not sasaran_mutu_data.empty:
        sm_data = sasaran_mutu_data.copy()
        sm_data["sarmut_label"] = sm_data["Jenis_Sarmut"].astype(str).str.replace("Sarmut Kelompok ", "", regex=False)
        sm_data.loc[sasaran_mutu_data["Jenis_Sarmut"].isna(), "sarmut_label"] = None
        sm_data = sm_data.dropna(subset=["sarmut_label"])
        site_util = sm_data.groupby(["lokasi", "sarmut_label"], as_index=False).agg(
            util_r=("utilisasi_pct", "mean"), util_t=("utilisasi_target", "mean"),
        )
        site_util["site_short"] = site_util["lokasi"].map(SITE_ABBR).fillna(site_util["lokasi"])
        site_util["label"] = site_util["site_short"] + " (" + site_util["sarmut_label"] + ")"
        site_util = site_util.sort_values(["lokasi", "sarmut_label"], ascending=[True, True])
        cd = CategoryChartData()
        cd.categories = list(site_util["label"])
        cd.add_series("Target Utilisasi (%)", tuple(round(v, 1) for v in site_util["util_t"]))
        cd.add_series("Realisasi Utilisasi (%)", tuple(round(v, 1) for v in site_util["util_r"]))
        gframe = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.55), Inches(4.3), Inches(12.2), Inches(2.85), cd)
        chart = gframe.chart
        chart.series[0].format.fill.solid(); chart.series[0].format.fill.fore_color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
        chart.series[1].format.fill.solid(); chart.series[1].format.fill.fore_color.rgb = TEAL
        chart.has_title = False
        plot_u = chart.plots[0]
        plot_u.has_data_labels = True
        dls_u = plot_u.data_labels
        dls_u.number_format = '0"%"'; dls_u.number_format_is_linked = False
        dls_u.font.size = Pt(8); dls_u.font.bold = True; dls_u.font.color.rgb = TEXT_DARK; dls_u.font.name = "Calibri"
        dls_u.position = XL_LABEL_POSITION.OUTSIDE_END
        style_chart_light(chart, legend=True, legend_pos=XL_LEGEND_POSITION.BOTTOM)
    else:
        add_textbox(s, 0.55, 4.3, 12.2, 0.6, "Data Sasaran Mutu (Availability/Utilisasi) belum tersedia untuk periode/filter ini.",
                    size=12, italic=True, color=TEXT_MUTED)

    # ================= SLIDE 2: TREN BULANAN & PRESTASI PER SITE =================
    s = add_content_slide(f"PRESTASI — Tren Bulanan {_now.year}", "Tren Bulanan · 02")

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

    data = data.copy()
    data["satuan_lokal"] = data.apply(klasifikasi_satuan_lokal, axis=1)

    bln_agg = data.groupby("bulan", as_index=False).agg(
        prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum"),
    )
    bln_agg["order"] = bln_agg["bulan"].apply(lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99)
    bln_agg = bln_agg.sort_values("order")
    add_textbox(s, 0.55, 1.05, 6, 0.35, "Tren Bulanan: Prestasi (Realisasi vs Budget)", size=13, bold=True, color=TEXT_DARK)
    cd4 = CategoryChartData()
    cd4.categories = list(bln_agg["bulan"])
    cd4.add_series("Prestasi Budget", tuple(bln_agg["prestasi_b"]))
    cd4.add_series("Prestasi Realisasi", tuple(bln_agg["prestasi_r"]))
    gframe4 = s.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(0.55), Inches(1.45), Inches(6.1), Inches(4.35), cd4)
    chart4 = gframe4.chart
    chart4.series[0].format.line.color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
    chart4.series[0].format.line.width = Pt(2)
    chart4.series[1].format.line.color.rgb = TEAL
    chart4.series[1].format.line.width = Pt(2.5)
    chart4.has_title = False
    # Label % capaian (Realisasi/Budget) di tiap titik garis Realisasi
    for i, pt in enumerate(chart4.series[1].points):
        b_val = bln_agg["prestasi_b"].iloc[i]
        r_val = bln_agg["prestasi_r"].iloc[i]
        pct_val = (r_val / b_val * 100) if b_val else None
        if pct_val is not None:
            dl = pt.data_label
            dl.has_text_frame = True
            dl.text_frame.text = f"{pct_val:.0f}%"
            r0 = dl.text_frame.paragraphs[0].runs[0]
            r0.font.size = Pt(9); r0.font.bold = True; r0.font.color.rgb = TEAL; r0.font.name = "Calibri"
    style_chart_light(chart4)

    tbl4_rows = [
        ["Prestasi Budget"] + [f"{v:,.0f}" for v in bln_agg["prestasi_b"]],
        ["Prestasi Realisasi"] + [f"{v:,.0f}" for v in bln_agg["prestasi_r"]],
    ]
    add_table(s, 0.55, 5.9, 6.1, 1.0, ["Metrik"] + list(bln_agg["bulan"]), tbl4_rows,
              col_widths=[1.6] + [1.0] * len(bln_agg), font_size=9.5, header_size=9.5)

    site_prs2 = data.groupby(["lokasi", "satuan_lokal"], as_index=False).agg(
        prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum"),
    )
    site_prs2 = site_prs2[(site_prs2["prestasi_r"] > 0) | (site_prs2["prestasi_b"] > 0)].copy()
    site_prs2["site_short"] = site_prs2["lokasi"].map(SITE_ABBR).fillna(site_prs2["lokasi"])
    site_prs2["label"] = site_prs2["site_short"] + " (" + site_prs2["satuan_lokal"] + ")"
    site_prs2 = site_prs2.sort_values(["lokasi", "satuan_lokal"], ascending=[True, True])
    add_textbox(s, 6.85, 1.05, 6, 0.35, "Prestasi Aktual vs Target — per Site & Satuan (HM/KM/Ton)", size=13, bold=True, color=TEXT_DARK)
    cd5 = CategoryChartData()
    cd5.categories = list(site_prs2["label"])
    cd5.add_series("Target", tuple(site_prs2["prestasi_b"]))
    cd5.add_series("Aktual", tuple(site_prs2["prestasi_r"]))
    gframe5 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(6.85), Inches(1.45), Inches(5.9), Inches(4.35), cd5)
    chart5 = gframe5.chart
    chart5.series[0].format.fill.solid(); chart5.series[0].format.fill.fore_color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
    chart5.series[1].format.fill.solid(); chart5.series[1].format.fill.fore_color.rgb = TEAL
    chart5.has_title = False
    # Label % capaian (Aktual/Target) di tiap bar Aktual
    for i, pt in enumerate(chart5.series[1].points):
        b_val = site_prs2["prestasi_b"].iloc[i]
        r_val = site_prs2["prestasi_r"].iloc[i]
        pct_val = (r_val / b_val * 100) if b_val else None
        if pct_val is not None:
            dl = pt.data_label
            dl.has_text_frame = True
            dl.text_frame.text = f"{pct_val:.0f}%"
            r0 = dl.text_frame.paragraphs[0].runs[0]
            r0.font.size = Pt(9); r0.font.bold = True; r0.font.color.rgb = TEAL; r0.font.name = "Calibri"
    style_chart_light(chart5)

    tbl5_rows = [
        ["Target"] + [f"{v:,.0f}" for v in site_prs2["prestasi_b"]],
        ["Aktual"] + [f"{v:,.0f}" for v in site_prs2["prestasi_r"]],
    ]
    n5 = len(site_prs2)
    add_table(s, 6.85, 5.9, 5.9, 1.0, ["Metrik"] + list(site_prs2["label"]), tbl5_rows,
              col_widths=[1.1] + [0.9] * n5, font_size=8, header_size=8)

    # ================= SLIDE 3: BIAYA OPERASIONAL =================
    s = add_content_slide(f"BIAYA OPERASIONAL — Budget vs Aktual s/d {period}", "Biaya Operasional · 03")

    tot_prestasi_r_pptx = data["prestasi_realisasi"].sum()
    tot_prestasi_b_pptx = data["prestasi_budget"].sum()
    ach_prestasi_pptx = ach_txt_pct(tot_prestasi_r_pptx, tot_prestasi_b_pptx)
    tot_qty_bbm_b_pptx = data["qty_bbm_budget"].sum()
    tot_qty_bbm_r_pptx = data["qty_bbm_realisasi"].sum()

    if kat_list == ["TR"]:
        kat_label_suffix_pptx = "/KM"
    elif kat_list == ["AB"]:
        kat_label_suffix_pptx = "/satuan"
    else:
        kat_label_suffix_pptx = ""

    def biaya_row_pptx(label, real_col, budget_col, is_bbm=False, raw=False):
        comp_r = data[real_col].sum(); comp_b = data[budget_col].sum()
        if raw:
            rate_b, rate_r, suffix = comp_b, comp_r, ""
            display_label = label
        elif is_bbm:
            rate_b = (comp_b / tot_qty_bbm_b_pptx) if tot_qty_bbm_b_pptx else None
            rate_r = (comp_r / tot_qty_bbm_r_pptx) if tot_qty_bbm_r_pptx else None
            suffix = "/Ltr"
            display_label = f"{label}/Ltr"
        else:
            rate_b = (comp_b / tot_prestasi_b_pptx) if tot_prestasi_b_pptx else None
            rate_r = (comp_r / tot_prestasi_r_pptx) if tot_prestasi_r_pptx else None
            suffix = ""
            display_label = f"{label}{kat_label_suffix_pptx}"
        ach = ach_txt_pct(rate_r, rate_b) if (rate_r is not None and rate_b) else None
        return display_label, rate_b, rate_r, suffix, ach, label

    ringkasan_rows_pptx = [
        biaya_row_pptx("Total Biaya", "total_biaya_realisasi", "total_biaya_budget", raw=True),
        biaya_row_pptx("Upah Operator", "upah_realisasi", "upah_budget"),
        biaya_row_pptx("Biaya BBM", "biaya_bbm_realisasi", "biaya_bbm_budget", is_bbm=True),
        biaya_row_pptx("Biaya Maintenance", "maintenance_realisasi", "maintenance_budget"),
        biaya_row_pptx("Penyusutan", "penyusutan_realisasi", "penyusutan_budget"),
        biaya_row_pptx("Lainnya", "lainnya_realisasi", "lainnya_budget"),
        biaya_row_pptx("Biaya Tidak Langsung", "biaya_tidak_langsung_realisasi", "biaya_tidak_langsung_budget"),
    ]
    tbl_rows = []
    worst_row = None  # (label, ach_row) untuk catatan OVER BUDGET terburuk
    for label, rb, rr, suffix, ach_row, base_label in ringkasan_rows_pptx:
        budget_disp = f"{fmt_rp(rb)}{suffix}" if rb is not None else "-"
        aktual_disp = f"{fmt_rp(rr)}{suffix}" if rr is not None else "-"
        ach_disp = (f"✓ {ach_row:.1f}%" if ach_row is not None and ach_row <= 100
                    else (f"✗ {ach_row:.1f}%" if ach_row is not None else "-"))
        hide_cp = base_label in ("Total Biaya", "Biaya Tidak Langsung")
        if hide_cp or ach_prestasi_pptx is None:
            cp_disp = "N/A"
        else:
            cp_disp = f"✓ {ach_prestasi_pptx:.1f}%" if ach_prestasi_pptx >= 100 else f"✗ {ach_prestasi_pptx:.1f}%"
        tbl_rows.append([label, budget_disp, aktual_disp, ach_disp, cp_disp])
        if base_label != "Total Biaya" and ach_row is not None and ach_row > 100:
            if worst_row is None or ach_row > worst_row[1]:
                worst_row = (label, ach_row)

    add_card_panel(s, 0.4, 0.98, 6.3, 6.2)
    add_textbox(s, 0.65, 1.14, 5.9, 0.4, "Ringkasan Biaya PT. BKMS", size=16, bold=True, color=TEXT_DARK)
    add_table(s, 0.65, 1.65, 5.85, 4.15, ["Metrik", "Budget", "Aktual", "Capaian", "Capaian Prestasi"], tbl_rows,
              status_col=[3, 4], col_widths=[1.95, 1.2, 1.2, 0.85, 1.05], fill_badge=True,
              font_size=11.5, header_size=12)
    if worst_row:
        add_note_callout(s, 0.65, 6.0, 5.85, 1.1, "📌",
                          f"{worst_row[0]} OVER BUDGET ({worst_row[1]:.1f}%) — perlu efisiensi biaya s/d {period}.",
                          text_color=RED, size=12.5)
    else:
        add_note_callout(s, 0.65, 6.0, 5.85, 1.1, "✅",
                          "Seluruh komponen biaya berada dalam/di bawah budget.", text_color=GREEN, size=12.5)

    btl_site = data.groupby("lokasi", as_index=False).agg(
        btl_r=("biaya_tidak_langsung_realisasi", "sum"), btl_b=("biaya_tidak_langsung_budget", "sum"),
    )
    total_btl_r = btl_site["btl_r"].sum()
    btl_rows = []
    over_sites = []
    for _, rw in btl_site.sort_values("btl_r", ascending=False).iterrows():
        pct_target = (rw["btl_r"] / rw["btl_b"] * 100) if rw["btl_b"] else None
        pct_share = (rw["btl_r"] / total_btl_r * 100) if total_btl_r else 0
        pct_disp = (f"✓ {pct_target:.0f}%" if pct_target is not None and pct_target <= 100
                    else (f"✗ {pct_target:.0f}%" if pct_target is not None else "-"))
        btl_rows.append([rw["lokasi"], fmt_rp(rw["btl_b"]), fmt_rp(rw["btl_r"]), pct_disp, f"{pct_share:.1f}%"])
        if pct_target is not None and pct_target > 100:
            over_sites.append(rw["lokasi"])

    add_card_panel(s, 6.85, 0.98, 6.05, 6.2)
    if not over_sites:
        add_status_banner(s, 7.1, 1.15, 5.55, 0.55, "✅",
                           "BTL — UNDER BUDGET secara keseluruhan", GREEN_BG, GREEN, GREEN)
    else:
        over_txt = " & ".join(over_sites[:3]) + (", dll" if len(over_sites) > 3 else "")
        add_status_banner(s, 7.1, 1.15, 5.55, 0.55, "⚠️",
                           f"BTL — UNDER BUDGET, kecuali {over_txt}", RED_BG, RED, RED)
    add_textbox(s, 7.1, 1.82, 5.55, 0.35, "BTL per Site (Rp) — Merah = Over Budget", size=11.5, italic=True, color=TEXT_MUTED)
    add_table(s, 7.1, 2.2, 5.55, 2.3, ["Site", "Budget", "Aktual", "% Target", "% BTL"], btl_rows,
              status_col=3, col_widths=[1.6, 1.2, 1.2, 0.8, 0.8], font_size=11.5, header_size=12)

    maint_site = data.groupby(["lokasi", "kategori"], as_index=False).agg(
        maint_r=("maintenance_realisasi", "sum"), maint_b=("maintenance_budget", "sum"),
        prestasi_r=("prestasi_realisasi", "sum"), prestasi_b=("prestasi_budget", "sum"),
    )
    maint_site = maint_site[maint_site["maint_b"] > 0].copy()
    maint_site["site_short"] = maint_site["lokasi"].map(SITE_ABBR).fillna(maint_site["lokasi"])
    maint_site["label"] = maint_site["site_short"] + " (" + maint_site["kategori"] + ")"
    add_textbox(s, 7.1, 4.6, 5.55, 0.3, "Biaya Maintenance Rp/Prestasi % — Aktual vs Plan per Site & Kategori", size=11, bold=True, color=TEXT_DARK)
    if not maint_site.empty:
        maint_site["rate_r"] = maint_site.apply(lambda r: (r["maint_r"] / r["prestasi_r"]) if r["prestasi_r"] else None, axis=1)
        maint_site["rate_b"] = maint_site.apply(lambda r: (r["maint_b"] / r["prestasi_b"]) if r["prestasi_b"] else None, axis=1)
        maint_site["pct"] = maint_site.apply(lambda r: (r["rate_r"] / r["rate_b"] * 100) if (r["rate_r"] is not None and r["rate_b"]) else None, axis=1)
        maint_site = maint_site.dropna(subset=["pct"])
        maint_site = maint_site.sort_values("pct", ascending=False)
        cd6 = CategoryChartData()
        cd6.categories = list(maint_site["label"])
        cd6.add_series("% Aktual vs Plan", tuple(round(v, 1) for v in maint_site["pct"]))
        gframe6 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(7.1), Inches(4.92), Inches(5.55), Inches(1.15), cd6)
        chart6 = gframe6.chart
        chart6.series[0].format.fill.solid(); chart6.series[0].format.fill.fore_color.rgb = TEAL
        plot6 = chart6.plots[0]
        plot6.has_data_labels = True
        dls6 = plot6.data_labels
        dls6.font.size = Pt(7.5); dls6.font.bold = True; dls6.font.color.rgb = TEXT_DARK; dls6.font.name = "Calibri"
        dls6.position = XL_LABEL_POSITION.OUTSIDE_END
        for i, pt in enumerate(chart6.series[0].points):
            pct_val = maint_site["pct"].iloc[i]
            if pct_val > 105:
                pt.format.fill.solid(); pt.format.fill.fore_color.rgb = RED
            dl = pt.data_label
            dl.has_text_frame = True
            dl.text_frame.text = f"{pct_val:.0f}%"
            r0 = dl.text_frame.paragraphs[0].runs[0]
            r0.font.size = Pt(7.5); r0.font.bold = True; r0.font.color.rgb = TEXT_DARK; r0.font.name = "Calibri"
        chart6.has_title = False
        style_chart_light(chart6, legend=False)

        tbl6_rows = [
            ["Budget (Rp/Prestasi)"] + [fmt_rp(v) if v is not None else "-" for v in maint_site["rate_b"]],
            ["Realisasi (Rp/Prestasi)"] + [fmt_rp(v) if v is not None else "-" for v in maint_site["rate_r"]],
        ]
        n6 = len(maint_site)
        add_table(s, 7.1, 6.15, 5.55, 0.95, ["Metrik"] + list(maint_site["label"]), tbl6_rows,
                  col_widths=[1.3] + [0.85] * n6, font_size=7, header_size=7)

    # ================= SLIDE 4: ANALISIS BIAYA vs CAPAIAN PRESTASI & MAINTENANCE =================
    s = add_content_slide(f"ANALISIS: Biaya vs Capaian Prestasi & Maintenance — s/d {period}", "Analisis Biaya · 04")

    add_card_panel(s, 0.5, 1.05, 6.15, 5.6)
    add_panel_header(s, 0.5, 1.05, 6.15, "Biaya vs Budget 🔷 vs Capaian Prestasi ⬛ — Total Keseluruhan")

    komponen_labels = ["Lainnya", "Penyusutan", "Biaya Maintenance", "Biaya BBM", "Upah Operator"]
    komponen_ach = {row[5]: row[4] for row in ringkasan_rows_pptx}
    komponen_display = {row[5]: row[0] for row in ringkasan_rows_pptx}
    cats7 = [komponen_display[lbl] for lbl in komponen_labels if komponen_ach.get(lbl) is not None]
    biaya_vals = [round(komponen_ach[lbl], 1) for lbl in komponen_labels if komponen_ach.get(lbl) is not None]
    prestasi_vals = [round(ach_prestasi_pptx, 1) if ach_prestasi_pptx is not None else 0 for _ in cats7]

    cd7 = CategoryChartData()
    cd7.categories = cats7 if cats7 else ["Tidak ada data"]
    cd7.add_series("% Capaian Prestasi", tuple(prestasi_vals) if cats7 else (0,))
    cd7.add_series("% Biaya vs Budget", tuple(biaya_vals) if cats7 else (0,))
    gframe7 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.65), Inches(1.65), Inches(5.85), Inches(3.7), cd7)
    chart7 = gframe7.chart
    chart7.series[0].format.fill.solid(); chart7.series[0].format.fill.fore_color.rgb = TEAL
    chart7.series[1].format.fill.solid(); chart7.series[1].format.fill.fore_color.rgb = NAVY
    plot7 = chart7.plots[0]
    plot7.has_data_labels = True
    dls7 = plot7.data_labels
    dls7.number_format = '0.0"%"'; dls7.number_format_is_linked = False
    dls7.font.size = Pt(10.5); dls7.font.bold = True; dls7.font.color.rgb = TEXT_DARK; dls7.font.name = "Calibri"
    chart7.has_title = False
    style_chart_light(chart7, legend=True, legend_pos=XL_LEGEND_POSITION.TOP)

    if worst_row:
        add_finding_box(s, 0.75, 5.3, 5.65, 1.15, "📌",
                         f"{worst_row[0]}: OVER BUDGET, karena penggunaan biaya {worst_row[1]:.1f}% "
                         f"tapi Capaian Prestasi hanya {ach_prestasi_pptx:.1f}% — Inefisiensi kritis!",
                         GOLD_BG, GOLD, RGBColor(0x8A, 0x5D, 0x00))
    else:
        add_finding_box(s, 0.75, 5.3, 5.65, 1.15, "✅",
                         "Seluruh komponen biaya sejalan dengan capaian Prestasi — tidak ada inefisiensi kritis.",
                         GREEN_BG, GREEN, GREEN)

    add_card_panel(s, 6.85, 1.05, 5.95, 5.6)
    add_panel_header(s, 6.85, 1.05, 5.95, "Biaya Maintenance ⬜ Realisasi vs Budget 🔷 — per Site")

    maint_site7 = data.groupby(["lokasi", "kategori"], as_index=False).agg(
        maint_r=("maintenance_realisasi", "sum"), maint_b=("maintenance_budget", "sum"),
    )
    maint_site7 = maint_site7[(maint_site7["maint_r"] > 0) | (maint_site7["maint_b"] > 0)].copy()
    maint_site7["site_short"] = maint_site7["lokasi"].map(SITE_ABBR).fillna(maint_site7["lokasi"])
    maint_site7["label"] = maint_site7["site_short"] + " (" + maint_site7["kategori"] + ")"
    maint_site7 = maint_site7.sort_values("maint_b", ascending=False)

    if not maint_site7.empty:
        cd8 = CategoryChartData()
        cd8.categories = list(maint_site7["label"])
        cd8.add_series("Budget", tuple(maint_site7["maint_b"] / 1e6))
        cd8.add_series("Realisasi", tuple(maint_site7["maint_r"] / 1e6))
        gframe8 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(7.0), Inches(1.65), Inches(5.65), Inches(3.7), cd8)
        chart8 = gframe8.chart
        chart8.series[0].format.fill.solid(); chart8.series[0].format.fill.fore_color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
        chart8.series[1].format.fill.solid(); chart8.series[1].format.fill.fore_color.rgb = TEAL
        chart8.has_title = False
        plot8 = chart8.plots[0]
        plot8.has_data_labels = True
        dls8 = plot8.data_labels
        dls8.number_format = '#,##0" Jt"'; dls8.number_format_is_linked = False
        dls8.font.size = Pt(8.5); dls8.font.bold = True; dls8.font.color.rgb = TEXT_DARK; dls8.font.name = "Calibri"
        dls8.position = XL_LABEL_POSITION.OUTSIDE_END
        style_chart_light(chart8, legend=True, legend_pos=XL_LEGEND_POSITION.TOP)

        total_maint_b7 = maint_site7["maint_b"].sum()
        total_maint_r7 = maint_site7["maint_r"].sum()
        maint_site7["pct"] = maint_site7.apply(lambda r: (r["maint_r"] / r["maint_b"] * 100) if r["maint_b"] else None, axis=1)
        over_sites7 = maint_site7[maint_site7["pct"] > 100].sort_values("pct", ascending=False)

        if total_maint_r7 > total_maint_b7:
            worst7 = over_sites7.iloc[0] if not over_sites7.empty else None
            worst_txt = f" Site paling over: {worst7['label']} ({worst7['pct']:.0f}%)." if worst7 is not None else ""
            finding_txt = (f"Realisasi Maintenance keseluruhan ({fmt_rp(total_maint_r7)}) melebihi Budget ({fmt_rp(total_maint_b7)}).{worst_txt} "
                           f"Perlu efisiensi biaya maintenance.")
            add_finding_box(s, 7.1, 5.3, 5.45, 1.15, "🔴", finding_txt, RED_BG, RED, RED)
        else:
            finding_txt = (f"Realisasi Maintenance ({fmt_rp(total_maint_r7)}) masih di bawah Budget ({fmt_rp(total_maint_b7)}) "
                           f"secara keseluruhan — biaya maintenance terkendali.")
            add_finding_box(s, 7.1, 5.3, 5.45, 1.15, "✅", finding_txt, GREEN_BG, GREEN, GREEN)
    else:
        add_textbox(s, 7.1, 2.8, 5.45, 0.8, "Data Budget/Realisasi Maintenance belum tersedia untuk periode/filter ini.",
                    size=12, italic=True, color=TEXT_MUTED)

    # ================= SLIDE 5: POPULASI UNIT =================
    card_w, card_h, gap, cy = 3.75, 2.4, 0.35, 1.25
    s = add_content_slide("POPULASI UNIT — Target vs Realisasi", "Populasi Unit · 05")
    tp = data.loc[data["pendapatan_budget"] > 0, "nama_unit"].nunique()
    rp = data.loc[data["pendapatan_realisasi"] > 0, "nama_unit"].nunique()
    pct_p = (rp / tp * 100) if tp else None

    add_kpi_card(s, 0.55, cy, card_w, card_h, "🏁", RGBColor(0xB8, 0xBE, 0xCC), RGBColor(0xB8, 0xBE, 0xCC),
                 "Target Populasi", f"{tp:,}", "Unit dengan target Pendapatan", "Baseline", True)
    add_kpi_card(s, 0.55 + (card_w + gap), cy, card_w, card_h, "✅", GREEN, GREEN,
                 "Realisasi Populasi", f"{rp:,}", "Unit dengan realisasi Pendapatan", f"vs Target: {tp:,}", True)
    pct_good = pct_p is not None and pct_p >= 100
    add_kpi_card(s, 0.55 + 2 * (card_w + gap), cy, card_w, card_h, "📈", GOLD, GREEN if pct_good else RED,
                 "Capaian Populasi", f"{pct_p:.1f}%" if pct_p is not None else "-", "Realisasi vs Target Populasi",
                 (f"✓ {pct_p:.1f}% — Tercapai" if pct_good else (f"✗ {pct_p:.1f}% vs Target" if pct_p is not None else "-")), pct_good)

    cd3 = CategoryChartData()
    pop_kat = data.groupby(["lokasi", "kategori"]).apply(
        lambda g: pd.Series({
            "target": g.loc[g["pendapatan_budget"] > 0, "nama_unit"].nunique(),
            "realisasi": g.loc[g["pendapatan_realisasi"] > 0, "nama_unit"].nunique(),
        })
    ).reset_index()
    pop_kat = pop_kat[(pop_kat["target"] > 0) | (pop_kat["realisasi"] > 0)].copy()
    pop_kat["site_short"] = pop_kat["lokasi"].map(SITE_ABBR).fillna(pop_kat["lokasi"])
    pop_kat["label"] = pop_kat["site_short"] + " (" + pop_kat["kategori"] + ")"
    pop_kat = pop_kat.sort_values(["lokasi", "kategori"])
    chart3_h = min(3.0, max(2.6, 0.32 * len(pop_kat)))
    cd3.categories = list(pop_kat["label"])
    cd3.add_series("Target", tuple(int(v) for v in pop_kat["target"]))
    cd3.add_series("Realisasi", tuple(int(v) for v in pop_kat["realisasi"]))
    gframe3 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(2.0), Inches(4.3), Inches(9.5), Inches(chart3_h), cd3)
    chart3 = gframe3.chart
    chart3.series[0].format.fill.solid(); chart3.series[0].format.fill.fore_color.rgb = RGBColor(0xB8, 0xBE, 0xCC)
    chart3.series[1].format.fill.solid(); chart3.series[1].format.fill.fore_color.rgb = GREEN
    plot3 = chart3.plots[0]
    plot3.has_data_labels = True
    dls3 = plot3.data_labels
    dls3.font.size = Pt(9); dls3.font.bold = True; dls3.font.color.rgb = TEXT_DARK; dls3.font.name = "Calibri"
    dls3.position = XL_LABEL_POSITION.OUTSIDE_END
    style_chart_light(chart3)

    buf = _io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

colX, colY = st.columns([5, 1.4])
with colY:
    if st.button("📽️ Buat Presentasi (PPTX)", use_container_width=True, type="primary"):
        with st.spinner("Menyusun slide presentasi..."):
            maint_for_pptx = maint_df_site_bulan if not maint_raw.empty else pd.DataFrame()
            sparepart_for_pptx = sparepart_df_site_bulan if not sparepart_raw.empty else pd.DataFrame()
            pptx_bytes = build_pptx(df, maint_for_pptx, sparepart_for_pptx, sel_site, sel_month, sel_kat, sasaran_mutu_df)
        st.session_state["pptx_bytes"] = pptx_bytes
    if "pptx_bytes" in st.session_state:
        st.download_button(
            "⬇️ Unduh PPTX untuk RTM",
            data=st.session_state["pptx_bytes"],
            file_name="Laporan_Biaya_Pendapatan_BKMS.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )

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
