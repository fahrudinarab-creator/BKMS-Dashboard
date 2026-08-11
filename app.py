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

    [data-testid="stDataFrame"] {{ background-color: {CARD_BG} !important; }}
    .stTextInput input {{ background-color: {CARD_BG} !important; color: {TEXT_LIGHT} !important; }}
</style>
""", unsafe_allow_html=True)

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
tot_biaya_r = df["total_biaya_realisasi"].sum()
tot_biaya_b = df["total_biaya_budget"].sum()

ach_pendapatan = achievement(tot_pendapatan_r, tot_pendapatan_b)
ach_prestasi = achievement(tot_prestasi_r, tot_prestasi_b)
ach_biaya = achievement(tot_biaya_r, tot_biaya_b)

target_populasi = df.loc[df["pendapatan_budget"] > 0, "nama_unit"].nunique()
realisasi_populasi = df.loc[df["pendapatan_realisasi"] > 0, "nama_unit"].nunique()
pct_populasi = (realisasi_populasi / target_populasi * 100) if target_populasi else None

# ---------------------------------------------------------------
# POWERPOINT EXPORT
# ---------------------------------------------------------------
def build_pptx(data, maint_data, site_list, month_list, kat_list) -> bytes:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    import io as _io

    GREEN = RGBColor(0x0B, 0x3D, 0x2E)
    GREEN_LIGHT = RGBColor(0x3F, 0xA7, 0x72)
    GOLD_C = RGBColor(0xC9, 0xA2, 0x27)
    DARK_BG_C = RGBColor(0x0A, 0x0A, 0x0A)
    CARD_BG_C = RGBColor(0x16, 0x1B, 0x22)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    MUTED = RGBColor(0x9C, 0xA3, 0xAF)
    RED_C = RGBColor(0xE4, 0x57, 0x4C)

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    def add_slide():
        s = prs.slides.add_slide(blank)
        bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
        bg.fill.solid()
        bg.fill.fore_color.rgb = DARK_BG_C
        bg.line.fill.background()
        bg.shadow.inherit = False
        s.shapes._spTree.remove(bg._element)
        s.shapes._spTree.insert(2, bg._element)
        return s

    def add_textbox(slide, left, top, width, height, text, size=18, bold=False,
                     color=WHITE, align=PP_ALIGN.LEFT, font="Calibri"):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = align
        run = p.add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = font
        return tb

    def add_bullets(slide, left, top, width, height, lines, size=14):
        tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            r = p.add_run()
            r.text = f"•  {line}"
            r.font.size = Pt(size)
            r.font.color.rgb = WHITE
            p.space_after = Pt(10)
        return tb

    def add_card(slide, left, top, width, height, label, value, sub=None, sub_color=GREEN_LIGHT):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.adjustments[0] = 0.06
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG_C
        card.line.color.rgb = GOLD_C
        card.line.width = Pt(1.5)
        card.shadow.inherit = False
        tf = card.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Inches(0.18)
        tf.margin_right = Inches(0.18)
        p1 = tf.paragraphs[0]
        r1 = p1.add_run()
        r1.text = label
        r1.font.size = Pt(12)
        r1.font.color.rgb = MUTED
        r1.font.bold = True
        p2 = tf.add_paragraph()
        r2 = p2.add_run()
        r2.text = value
        r2.font.size = Pt(22)
        r2.font.bold = True
        r2.font.color.rgb = WHITE
        if sub:
            p3 = tf.add_paragraph()
            r3 = p3.add_run()
            r3.text = sub
            r3.font.size = Pt(11)
            r3.font.bold = True
            r3.font.color.rgb = sub_color
        return card

    def style_chart(chart, legend=True):
        chart.has_legend = legend
        if legend:
            chart.legend.position = XL_LEGEND_POSITION.BOTTOM
            chart.legend.include_in_layout = False
            chart.legend.font.color.rgb = WHITE
            chart.legend.font.size = Pt(11)
        cat_ax = chart.category_axis
        cat_ax.tick_labels.font.color.rgb = WHITE
        cat_ax.tick_labels.font.size = Pt(10)
        cat_ax.format.line.color.rgb = MUTED
        val_ax = chart.value_axis
        val_ax.tick_labels.font.color.rgb = WHITE
        val_ax.tick_labels.font.size = Pt(10)
        val_ax.format.line.color.rgb = MUTED
        val_ax.has_major_gridlines = True
        val_ax.major_gridlines.format.line.color.rgb = RGBColor(0x2D, 0x33, 0x3B)

    def ach_txt(real, budget, label="Target"):
        if budget == 0:
            return f"{label} = 0"
        pct = real / budget * 100
        return f"{pct:.1f}% dari {label.lower()}"

    # ---------- SLIDE 1: TITLE ----------
    s = add_slide()
    accent = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(3.15), prs.slide_width, Inches(1.2))
    accent.fill.solid()
    accent.fill.fore_color.rgb = GREEN
    accent.line.fill.background()
    accent.shadow.inherit = False
    add_textbox(s, 0.8, 2.05, 11.7, 1.0, "Dashboard Biaya & Pendapatan", size=40, bold=True, color=GOLD_C)
    add_textbox(s, 0.8, 3.35, 11.7, 0.6, "PT BUANA KARYA MANDIRI SEJAHTERA (BKMS)", size=20, bold=True, color=WHITE)
    period = ", ".join(month_list) if month_list else "-"
    site_txt = ", ".join(site_list) if len(site_list) <= 6 else f"{len(site_list)} site"
    kat_txt = ", ".join([KATEGORI_LABEL.get(k, k) for k in kat_list])
    add_textbox(s, 0.8, 4.7, 11.7, 1.4,
                f"Periode: {period}\nSite: {site_txt}\nKategori: {kat_txt}",
                size=14, color=MUTED)

    # ---------- SLIDE 2: CAPAIAN UTAMA ----------
    s = add_slide()
    add_textbox(s, 0.6, 0.35, 11, 0.6, "Capaian Utama: Pendapatan, Prestasi, Biaya", size=24, bold=True, color=GOLD_C)

    r_ = data["pendapatan_realisasi"].sum(); b_ = data["pendapatan_budget"].sum()
    pr_ = data["prestasi_realisasi"].sum(); pb_ = data["prestasi_budget"].sum()
    br_ = data["total_biaya_realisasi"].sum(); bb_ = data["total_biaya_budget"].sum()

    card_w, card_h, gap = 3.7, 1.9, 0.4
    add_card(s, 0.6, 1.2, card_w, card_h, "PENDAPATAN", fmt_rp(r_), ach_txt(r_, b_, "Target"))
    add_card(s, 0.6 + (card_w + gap), 1.2, card_w, card_h, "PRESTASI", f"{pr_:,.0f}", ach_txt(pr_, pb_, "Target"))
    add_card(s, 0.6 + 2 * (card_w + gap), 1.2, card_w, card_h, "BIAYA", fmt_rp(br_), ach_txt(br_, bb_, "Target"), sub_color=RED_C)

    cd = CategoryChartData()
    cd.categories = ["Pendapatan", "Biaya"]
    cd.add_series("Target", (b_, bb_))
    cd.add_series("Realisasi", (r_, br_))
    gframe = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(3.6), Inches(6.2), Inches(3.5), cd)
    chart = gframe.chart
    chart.series[0].format.fill.solid(); chart.series[0].format.fill.fore_color.rgb = MUTED
    chart.series[1].format.fill.solid(); chart.series[1].format.fill.fore_color.rgb = GREEN_LIGHT
    style_chart(chart)

    cd2 = CategoryChartData()
    cd2.categories = ["Prestasi"]
    cd2.add_series("Target", (pb_,))
    cd2.add_series("Realisasi", (pr_,))
    gframe2 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(7.1), Inches(3.6), Inches(5.6), Inches(3.5), cd2)
    chart2 = gframe2.chart
    chart2.series[0].format.fill.solid(); chart2.series[0].format.fill.fore_color.rgb = MUTED
    chart2.series[1].format.fill.solid(); chart2.series[1].format.fill.fore_color.rgb = GOLD_C
    style_chart(chart2)

    # ---------- SLIDE 3: POPULASI UNIT ----------
    s = add_slide()
    add_textbox(s, 0.6, 0.35, 11, 0.6, "Populasi Unit: Target vs Realisasi", size=24, bold=True, color=GOLD_C)
    tp = data.loc[data["pendapatan_budget"] > 0, "nama_unit"].nunique()
    rp = data.loc[data["pendapatan_realisasi"] > 0, "nama_unit"].nunique()
    pct_p = (rp / tp * 100) if tp else 0
    add_card(s, 0.6, 1.4, 3.9, 1.9, "TARGET POPULASI", f"{tp:,}", "Unit dengan target Pendapatan")
    add_card(s, 4.75, 1.4, 3.9, 1.9, "REALISASI POPULASI", f"{rp:,}", "Unit dengan realisasi Pendapatan")
    add_card(s, 8.9, 1.4, 3.85, 1.9, "CAPAIAN POPULASI", f"{pct_p:.1f}%", "Realisasi vs Target", sub_color=GOLD_C)

    cd3 = CategoryChartData()
    cd3.categories = ["Populasi Unit"]
    cd3.add_series("Target", (tp,))
    cd3.add_series("Realisasi", (rp,))
    gframe3 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(2.5), Inches(3.8), Inches(8.3), Inches(3.2), cd3)
    chart3 = gframe3.chart
    chart3.series[0].format.fill.solid(); chart3.series[0].format.fill.fore_color.rgb = MUTED
    chart3.series[1].format.fill.solid(); chart3.series[1].format.fill.fore_color.rgb = GREEN_LIGHT
    style_chart(chart3)

    # ---------- SLIDE 4: MAINTENANCE REKAP ----------
    if maint_data is not None and not maint_data.empty:
        s = add_slide()
        add_textbox(s, 0.6, 0.35, 11, 0.6, "Rekap Biaya Maintenance", size=24, bold=True, color=GOLD_C)

        total_m = maint_data["biaya"].sum()
        n_trx = len(maint_data)
        rutin_b = maint_data.loc[maint_data["jenis_pemeliharaan"] == "RUTIN", "biaya"].sum()
        nonrutin_b = maint_data.loc[maint_data["jenis_pemeliharaan"] == "NON RUTIN", "biaya"].sum()

        add_card(s, 0.6, 1.2, 3.7, 1.6, "TOTAL BIAYA MAINTENANCE", fmt_rp(total_m), f"{n_trx:,} transaksi")
        add_card(s, 4.5, 1.2, 3.7, 1.6, "BIAYA RUTIN", fmt_rp(rutin_b))
        add_card(s, 8.4, 1.2, 4.3, 1.6, "BIAYA NON RUTIN", fmt_rp(nonrutin_b), sub_color=RED_C)

        cat_agg = maint_data.groupby("kategori_sparepart", as_index=False)["biaya"].sum().sort_values("biaya", ascending=False).head(10)
        cd4 = CategoryChartData()
        cd4.categories = list(cat_agg["kategori_sparepart"])
        cd4.add_series("Biaya", tuple(cat_agg["biaya"]))
        gframe4 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.6), Inches(3.1), Inches(12.1), Inches(4.1), cd4)
        chart4 = gframe4.chart
        chart4.series[0].format.fill.solid(); chart4.series[0].format.fill.fore_color.rgb = GREEN_LIGHT
        chart4.has_title = False
        style_chart(chart4, legend=False)

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
# 1-3. CAPAIAN: PENDAPATAN, PRESTASI, BIAYA
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Capaian Utama</h3>', unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric(
    "Pendapatan: Realisasi vs Target",
    fmt_rp(tot_pendapatan_r),
    f"{ach_pendapatan:.1f}% dari target ({fmt_rp(tot_pendapatan_b)})" if ach_pendapatan is not None else "Target = 0",
)
c2.metric(
    "Prestasi: Realisasi vs Target",
    f"{tot_prestasi_r:,.0f}",
    f"{ach_prestasi:.1f}% dari target ({tot_prestasi_b:,.0f})" if ach_prestasi is not None else "Target = 0",
)
c3.metric(
    "Biaya: Realisasi vs Target",
    fmt_rp(tot_biaya_r),
    f"{ach_biaya:.1f}% dari target ({fmt_rp(tot_biaya_b)})" if ach_biaya is not None else "Target = 0",
    delta_color="inverse",
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
    rc1.metric("Total Biaya Maintenance", fmt_rp(total_maint_all))
    rc2.metric("Pemakaian Persediaan (Sparepart)", fmt_rp(total_persediaan_all), f"{pct_persediaan:.1f}% dari total")
    rc3.metric("Service Luar (di luar persediaan)", fmt_rp(service_luar_all), f"{pct_service_luar:.1f}% dari total", delta_color="inverse")

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

p1, p2, p3 = st.columns(3)
p1.metric("Target Populasi", f"{target_populasi:,}", "Unit dengan target Pendapatan")
p2.metric("Realisasi Populasi", f"{realisasi_populasi:,}", "Unit dengan realisasi Pendapatan")
p3.metric(
    "Capaian Populasi",
    f"{pct_populasi:.1f}%" if pct_populasi is not None else "-",
    "Realisasi vs Target Populasi",
)

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
