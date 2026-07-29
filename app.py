import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
import base64
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
    /* Force a black background, consistent regardless of browser/system settings */
    html, body, [data-testid="stAppViewContainer"], .main {{
        background-color: {DARK_BG} !important;
    }}
    [data-testid="stHeader"] {{ background-color: rgba(0,0,0,0) !important; }}
    [data-testid="stSidebar"] {{ background-color: {CARD_BG} !important; border-right: 1px solid {BORDER}; }}
    [data-testid="stSidebar"] * {{ color: {TEXT_LIGHT} !important; }}
    .block-container {{ padding-top: 1.5rem; }}

    /* KPI metric cards */
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

    /* General text/headers on the black background */
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

    /* Dataframe / table area */
    [data-testid="stDataFrame"] {{ background-color: {CARD_BG} !important; }}

    /* Text input / multiselect chips */
    .stTextInput input {{ background-color: {CARD_BG} !important; color: {TEXT_LIGHT} !important; }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# DATA LOADING
# ---------------------------------------------------------------
DATA_PATH = Path(__file__).parent / "data_bkms.csv"
MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
KATEGORI_LABEL = {"AB": "Alat Berat (AB)", "TR": "Truck / Ritase (TR)"}

@st.cache_data
def load_data(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    return df

def load_from_upload(uploaded_file: "st.runtime.uploaded_file_manager.UploadedFile") -> pd.DataFrame:
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

    st.markdown("---")
    unit_opts = sorted(df_raw["nama_unit"].dropna().unique().tolist())
    sel_unit = st.multiselect("Unit (opsional, kosongkan = semua)", unit_opts, default=[])

# ---------------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------------
df = df_raw[
    df_raw["lokasi"].isin(sel_site) &
    df_raw["bulan"].isin(sel_month) &
    df_raw["kategori"].isin(sel_kat)
].copy()
if sel_unit:
    df = df[df["nama_unit"].isin(sel_unit)]

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

# ---------------------------------------------------------------
# POWERPOINT EXPORT
# ---------------------------------------------------------------
def build_pptx(data: pd.DataFrame, site_list, month_list, kat_list) -> bytes:
    """Build a PPTX summary of the (already filtered) dashboard data.
    Uses python-pptx only (no Node/pptxgenjs) so it runs inside a deployed
    Streamlit Cloud app."""
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    import io as _io

    GREEN = RGBColor(0x0B, 0x3D, 0x2E)
    GREEN_LIGHT = RGBColor(0x3F, 0xA7, 0x72)
    GOLD_C = RGBColor(0xC9, 0xA2, 0x27)
    DARK_BG = RGBColor(0x0A, 0x0A, 0x0A)
    CARD_BG = RGBColor(0x16, 0x1B, 0x22)
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
        bg.fill.fore_color.rgb = DARK_BG
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

    def add_card(slide, left, top, width, height, label, value, sub=None, sub_color=GREEN_LIGHT):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
        card.adjustments[0] = 0.06
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
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
        r2.font.size = Pt(24)
        r2.font.bold = True
        r2.font.color.rgb = WHITE
        if sub:
            p3 = tf.add_paragraph()
            r3 = p3.add_run()
            r3.text = sub
            r3.font.size = Pt(12)
            r3.font.bold = True
            r3.font.color.rgb = sub_color
        return card

    def style_chart(chart, categories_color=WHITE, legend=True):
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

    # ---------- SLIDE 2: KPI SUMMARY ----------
    s = add_slide()
    add_textbox(s, 0.6, 0.35, 11, 0.6, "Ringkasan Target vs Realisasi", size=26, bold=True, color=GOLD_C)

    tpr = data["pendapatan_realisasi"].sum()
    tpb = data["pendapatan_budget"].sum()
    tprest_r = data["prestasi_realisasi"].sum()
    tprest_b = data["prestasi_budget"].sum()
    tbr = data["total_biaya_realisasi"].sum()
    tbb = data["total_biaya_budget"].sum()
    margin_v = tpr - tbr

    def ach_txt(real, budget, label="Budget"):
        if budget == 0:
            return f"{label} = 0"
        pct = real / budget * 100 - 100
        return f"{pct:+.1f}% vs {label}"

    card_w, card_h, gap = 2.75, 1.9, 0.35
    start_x = 0.6
    y = 1.3
    add_card(s, start_x, y, card_w, card_h, "PENDAPATAN (REALISASI)", fmt_rp(tpr), ach_txt(tpr, tpb, "Budget"))
    add_card(s, start_x + (card_w + gap), y, card_w, card_h, "PRESTASI (REALISASI)", f"{tprest_r:,.0f}", ach_txt(tprest_r, tprest_b, "Target"))
    add_card(s, start_x + 2 * (card_w + gap), y, card_w, card_h, "TOTAL BIAYA (REALISASI)", fmt_rp(tbr), ach_txt(tbr, tbb, "Budget"), sub_color=RED_C)
    add_card(s, start_x + 3 * (card_w + gap), y, card_w, card_h, "MARGIN", fmt_rp(margin_v), "Pendapatan - Biaya", sub_color=GOLD_C)

    # mini chart: pendapatan vs biaya
    cd = CategoryChartData()
    cd.categories = ["Pendapatan", "Total Biaya"]
    cd.add_series("Budget", (tpb, tbb))
    cd.add_series("Realisasi", (tpr, tbr))
    gframe = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(3.6), Inches(11.9), Inches(3.4), cd)
    chart = gframe.chart
    chart.series[0].format.fill.solid()
    chart.series[0].format.fill.fore_color.rgb = MUTED
    chart.series[1].format.fill.solid()
    chart.series[1].format.fill.fore_color.rgb = GREEN_LIGHT
    style_chart(chart)

    # ---------- SLIDE 3: TARGET VS REALISASI PER SITE ----------
    s = add_slide()
    add_textbox(s, 0.6, 0.35, 11, 0.6, "Target vs Realisasi per Site", size=26, bold=True, color=GOLD_C)

    site_agg = data.groupby("lokasi", as_index=False).agg(
        pendapatan_realisasi=("pendapatan_realisasi", "sum"),
        pendapatan_budget=("pendapatan_budget", "sum"),
    ).sort_values("pendapatan_realisasi", ascending=False)

    cd2 = CategoryChartData()
    cd2.categories = list(site_agg["lokasi"])
    cd2.add_series("Budget", tuple(site_agg["pendapatan_budget"]))
    cd2.add_series("Realisasi", tuple(site_agg["pendapatan_realisasi"]))
    gframe2 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.2), Inches(11.9), Inches(5.7), cd2)
    chart2 = gframe2.chart
    chart2.series[0].format.fill.solid()
    chart2.series[0].format.fill.fore_color.rgb = MUTED
    chart2.series[1].format.fill.solid()
    chart2.series[1].format.fill.fore_color.rgb = GREEN_LIGHT
    chart2.has_title = True
    chart2.chart_title.text_frame.text = "Pendapatan: Budget vs Realisasi"
    chart2.chart_title.text_frame.paragraphs[0].runs[0].font.color.rgb = WHITE
    chart2.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
    style_chart(chart2)

    # ---------- SLIDE 4: KOMPONEN BIAYA ----------
    s = add_slide()
    add_textbox(s, 0.6, 0.35, 11, 0.6, "Perbandingan Komponen Biaya", size=26, bold=True, color=GOLD_C)

    comp_labels = ["Upah", "BBM", "Maintenance", "Penyusutan", "Lainnya"]
    comp_pairs = [
        ("upah_realisasi", "upah_budget"), ("biaya_bbm_realisasi", "biaya_bbm_budget"),
        ("maintenance_realisasi", "maintenance_budget"), ("penyusutan_realisasi", "penyusutan_budget"),
        ("lainnya_realisasi", "lainnya_budget"),
    ]
    real_vals = tuple(data[r].sum() for r, b in comp_pairs)
    budget_vals = tuple(data[b].sum() for r, b in comp_pairs)

    cd3 = CategoryChartData()
    cd3.categories = comp_labels
    cd3.add_series("Budget", budget_vals)
    cd3.add_series("Realisasi", real_vals)
    gframe3 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(1.2), Inches(7.0), Inches(5.7), cd3)
    chart3 = gframe3.chart
    chart3.series[0].format.fill.solid()
    chart3.series[0].format.fill.fore_color.rgb = MUTED
    chart3.series[1].format.fill.solid()
    chart3.series[1].format.fill.fore_color.rgb = GOLD_C
    style_chart(chart3)

    cd4 = CategoryChartData()
    cd4.categories = comp_labels
    cd4.add_series("Realisasi", real_vals)
    gframe4 = s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(7.8), Inches(1.2), Inches(4.9), Inches(5.7), cd4)
    chart4 = gframe4.chart
    chart4.has_legend = True
    chart4.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart4.legend.include_in_layout = False
    chart4.legend.font.color.rgb = WHITE
    chart4.legend.font.size = Pt(11)
    pie_colors = [GREEN_LIGHT, GOLD_C, RGBColor(0x4E, 0x8D, 0x7C), RGBColor(0xA9, 0xC7, 0xB8), RED_C]
    for i, point in enumerate(chart4.series[0].points):
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = pie_colors[i % len(pie_colors)]
    chart4.plots[0].has_data_labels = True
    chart4.plots[0].data_labels.font.color.rgb = WHITE
    chart4.plots[0].data_labels.font.size = Pt(10)

    # ---------- SLIDE 5: BIAYA LANGSUNG VS TIDAK LANGSUNG + TOTAL ----------
    s = add_slide()
    add_textbox(s, 0.6, 0.35, 11, 0.6, "Biaya Langsung vs Tidak Langsung", size=26, bold=True, color=GOLD_C)

    bl_r = data["biaya_langsung_realisasi"].sum()
    bl_b = data["biaya_langsung_budget"].sum()
    btl_r = data["biaya_tidak_langsung_realisasi"].sum()
    btl_b = data["biaya_tidak_langsung_budget"].sum()

    add_card(s, 0.6, 1.3, 3.6, 1.7, "BIAYA LANGSUNG (REALISASI)", fmt_rp(bl_r), ach_txt(bl_r, bl_b, "Budget"), sub_color=RED_C)
    add_card(s, 4.4, 1.3, 3.6, 1.7, "BIAYA TIDAK LANGSUNG (REALISASI)", fmt_rp(btl_r), ach_txt(btl_r, btl_b, "Budget"), sub_color=RED_C)
    add_card(s, 8.2, 1.3, 4.3, 1.7, "TOTAL BIAYA KESELURUHAN", fmt_rp(bl_r + btl_r), "Langsung + Tidak Langsung", sub_color=GOLD_C)

    cd5 = CategoryChartData()
    cd5.categories = ["Biaya Langsung", "Biaya Tidak Langsung"]
    cd5.add_series("Budget", (bl_b, btl_b))
    cd5.add_series("Realisasi", (bl_r, btl_r))
    gframe5 = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.6), Inches(3.35), Inches(6.6), Inches(3.6), cd5)
    chart5 = gframe5.chart
    chart5.series[0].format.fill.solid()
    chart5.series[0].format.fill.fore_color.rgb = MUTED
    chart5.series[1].format.fill.solid()
    chart5.series[1].format.fill.fore_color.rgb = GREEN_LIGHT
    style_chart(chart5)

    cd6 = CategoryChartData()
    cd6.categories = ["Biaya Langsung", "Biaya Tidak Langsung"]
    cd6.add_series("Realisasi", (bl_r, btl_r))
    gframe6 = s.shapes.add_chart(XL_CHART_TYPE.PIE, Inches(7.5), Inches(3.35), Inches(5.2), Inches(3.6), cd6)
    chart6 = gframe6.chart
    chart6.has_legend = True
    chart6.legend.position = XL_LEGEND_POSITION.BOTTOM
    chart6.legend.include_in_layout = False
    chart6.legend.font.color.rgb = WHITE
    chart6.legend.font.size = Pt(11)
    for i, point in enumerate(chart6.series[0].points):
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = [GREEN_LIGHT, GOLD_C][i % 2]
    chart6.plots[0].has_data_labels = True
    chart6.plots[0].data_labels.font.color.rgb = WHITE
    chart6.plots[0].data_labels.font.size = Pt(10)

    # ---------- SLIDE 6: TOP 10 UNIT BY TOTAL BIAYA ----------
    s = add_slide()
    add_textbox(s, 0.6, 0.35, 11, 0.6, "Top 10 Unit - Total Biaya Realisasi", size=26, bold=True, color=GOLD_C)

    top10 = data.groupby("nama_unit", as_index=False).agg(
        total_biaya_realisasi=("total_biaya_realisasi", "sum"),
        pendapatan_realisasi=("pendapatan_realisasi", "sum"),
        lokasi=("lokasi", "first"),
    ).sort_values("total_biaya_realisasi", ascending=False).head(10)

    rows, cols = len(top10) + 1, 4
    tbl_left, tbl_top, tbl_w, tbl_h = Inches(0.6), Inches(1.2), Inches(11.9), Inches(5.7)
    gframe_t = s.shapes.add_table(rows, cols, tbl_left, tbl_top, tbl_w, tbl_h)
    table = gframe_t.table
    headers = ["Nama Unit", "Site", "Total Biaya (Realisasi)", "Pendapatan (Realisasi)"]
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = GREEN
        p = cell.text_frame.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = WHITE
        p.runs[0].font.size = Pt(12)
    for i, (_, row) in enumerate(top10.iterrows(), start=1):
        vals = [str(row["nama_unit"])[:45], str(row["lokasi"]), fmt_rp(row["total_biaya_realisasi"]), fmt_rp(row["pendapatan_realisasi"])]
        for j, v in enumerate(vals):
            cell = table.cell(i, j)
            cell.text = v
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD_BG if i % 2 == 0 else RGBColor(0x1E, 0x24, 0x2C)
            p = cell.text_frame.paragraphs[0]
            p.runs[0].font.size = Pt(11)
            p.runs[0].font.color.rgb = WHITE

    buf = _io.BytesIO()
    prs.save(buf)
    return buf.getvalue()

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

st.caption(f"Menampilkan **{len(df):,}** baris data unit • Site: {', '.join(sel_site) if len(sel_site)<=4 else f'{len(sel_site)} site'} • Bulan: {', '.join(sel_month)}")

colX, colY = st.columns([5, 1.4])
with colY:
    if st.button("📽️ Buat Presentasi (PPTX)", use_container_width=True, type="primary"):
        with st.spinner("Menyusun slide presentasi..."):
            pptx_bytes = build_pptx(df, sel_site, sel_month, sel_kat)
        st.session_state["pptx_bytes"] = pptx_bytes
    if "pptx_bytes" in st.session_state:
        st.download_button(
            "⬇️ Unduh PPTX",
            data=st.session_state["pptx_bytes"],
            file_name="Laporan_Biaya_Pendapatan_BKMS.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            use_container_width=True,
        )

# ---------------------------------------------------------------
# KPI SUMMARY
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

st.markdown('<h3 class="section-title">Ringkasan Target vs Realisasi</h3>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Pendapatan (Realisasi)", fmt_rp(tot_pendapatan_r),
          f"{ach_pendapatan-100:+.1f}% vs Budget ({fmt_rp(tot_pendapatan_b)})" if ach_pendapatan is not None else "Budget = 0")
c2.metric("Prestasi (Realisasi)", f"{tot_prestasi_r:,.0f}",
          f"{ach_prestasi-100:+.1f}% vs Target ({tot_prestasi_b:,.0f})" if ach_prestasi is not None else "Target = 0")
c3.metric("Total Biaya (Realisasi)", fmt_rp(tot_biaya_r),
          f"{ach_biaya-100:+.1f}% vs Budget ({fmt_rp(tot_biaya_b)})" if ach_biaya is not None else "Budget = 0",
          delta_color="inverse")
margin = tot_pendapatan_r - tot_biaya_r
c4.metric("Margin (Pendapatan - Biaya)", fmt_rp(margin))

st.markdown("---")

# ---------------------------------------------------------------
# UNIT PRODUKTIF VS TIDAK PRODUKTIF
# ---------------------------------------------------------------
PRODUKTIF_THRESHOLD = 70  # persen realisasi terhadap target/budget

st.markdown('<h3 class="section-title">Unit Produktif vs Tidak Produktif</h3>', unsafe_allow_html=True)
st.caption(f"Unit dikategorikan **Produktif** jika realisasi ≥ {PRODUKTIF_THRESHOLD}% dari target/budget (dijumlahkan per unit sesuai filter & periode yang dipilih), selain itu **Tidak Produktif**.")

def hitung_produktif(data: pd.DataFrame, col_real: str, col_target: str, threshold: float = PRODUKTIF_THRESHOLD):
    agg = data.groupby("nama_unit", as_index=False).agg(
        realisasi=(col_real, "sum"),
        target=(col_target, "sum"),
    )
    def pct(row):
        if row["target"] > 0:
            return row["realisasi"] / row["target"] * 100
        return 100.0 if row["realisasi"] > 0 else 0.0
    agg["pct"] = agg.apply(pct, axis=1)
    agg["status"] = agg["pct"].apply(lambda p: "Produktif" if p >= threshold else "Tidak Produktif")
    return agg

unit_pendapatan_agg = hitung_produktif(df, "pendapatan_realisasi", "pendapatan_budget")
produktif_pendapatan = int((unit_pendapatan_agg["status"] == "Produktif").sum())
tidak_produktif_pendapatan = int((unit_pendapatan_agg["status"] == "Tidak Produktif").sum())
total_unit_pendapatan = produktif_pendapatan + tidak_produktif_pendapatan
budget_produktif_pendapatan = unit_pendapatan_agg.loc[unit_pendapatan_agg["status"] == "Produktif", "target"].sum()
budget_tidak_produktif_pendapatan = unit_pendapatan_agg.loc[unit_pendapatan_agg["status"] == "Tidak Produktif", "target"].sum()

unit_prestasi_agg = hitung_produktif(df, "prestasi_realisasi", "prestasi_budget")
produktif_prestasi = int((unit_prestasi_agg["status"] == "Produktif").sum())
tidak_produktif_prestasi = int((unit_prestasi_agg["status"] == "Tidak Produktif").sum())
total_unit_prestasi = produktif_prestasi + tidak_produktif_prestasi
target_produktif_prestasi = unit_prestasi_agg.loc[unit_prestasi_agg["status"] == "Produktif", "target"].sum()
target_tidak_produktif_prestasi = unit_prestasi_agg.loc[unit_prestasi_agg["status"] == "Tidak Produktif", "target"].sum()

colP1, colP2 = st.columns(2)

with colP1:
    m1, m2 = st.columns(2)
    m1.metric("Unit Produktif (Pendapatan)", f"{produktif_pendapatan:,}",
               f"{produktif_pendapatan/total_unit_pendapatan*100:.1f}% dari total" if total_unit_pendapatan else "")
    m1.caption(f"Budget: {fmt_rp(budget_produktif_pendapatan)}")
    m2.metric("Unit Tidak Produktif (Pendapatan)", f"{tidak_produktif_pendapatan:,}",
               f"{tidak_produktif_pendapatan/total_unit_pendapatan*100:.1f}% dari total" if total_unit_pendapatan else "",
               delta_color="inverse")
    m2.caption(f"Budget: {fmt_rp(budget_tidak_produktif_pendapatan)}")
    pie_pend = pd.DataFrame({
        "Status": ["Produktif", "Tidak Produktif"],
        "Jumlah": [produktif_pendapatan, tidak_produktif_pendapatan],
    })
    fig_p1 = px.pie(pie_pend, names="Status", values="Jumlah", hole=0.5,
                     title=f"Unit Berdasarkan Pendapatan (≥{PRODUKTIF_THRESHOLD}% Budget)",
                     color_discrete_sequence=[CHART_GREEN, RED])
    fig_p1.update_layout(height=340, margin=dict(t=60, b=10))
    st.plotly_chart(style_fig(fig_p1), use_container_width=True)

with colP2:
    m3, m4 = st.columns(2)
    m3.metric("Unit Produktif (Prestasi)", f"{produktif_prestasi:,}",
               f"{produktif_prestasi/total_unit_prestasi*100:.1f}% dari total" if total_unit_prestasi else "")
    m3.caption(f"Target: {target_produktif_prestasi:,.0f}")
    m4.metric("Unit Tidak Produktif (Prestasi)", f"{tidak_produktif_prestasi:,}",
               f"{tidak_produktif_prestasi/total_unit_prestasi*100:.1f}% dari total" if total_unit_prestasi else "",
               delta_color="inverse")
    m4.caption(f"Target: {target_tidak_produktif_prestasi:,.0f}")
    pie_prest = pd.DataFrame({
        "Status": ["Produktif", "Tidak Produktif"],
        "Jumlah": [produktif_prestasi, tidak_produktif_prestasi],
    })
    fig_p2 = px.pie(pie_prest, names="Status", values="Jumlah", hole=0.5,
                     title=f"Unit Berdasarkan Prestasi (≥{PRODUKTIF_THRESHOLD}% Target)",
                     color_discrete_sequence=[CHART_GREEN, RED])
    fig_p2.update_layout(height=340, margin=dict(t=60, b=10))
    st.plotly_chart(style_fig(fig_p2), use_container_width=True)

with st.expander("🔍 Lihat detail % pencapaian per unit"):
    dcol1, dcol2 = st.columns(2)
    with dcol1:
        st.markdown("**Pendapatan (Realisasi vs Budget)**")
        show_pend = unit_pendapatan_agg.rename(columns={
            "nama_unit": "Nama Unit", "realisasi": "Realisasi", "target": "Budget",
            "pct": "% Pencapaian", "status": "Status",
        }).sort_values("% Pencapaian")
        st.dataframe(show_pend, use_container_width=True, height=300,
                     column_config={
                         "Realisasi": st.column_config.NumberColumn(format="Rp %,.0f"),
                         "Budget": st.column_config.NumberColumn(format="Rp %,.0f"),
                         "% Pencapaian": st.column_config.NumberColumn(format="%.1f%%"),
                     })
    with dcol2:
        st.markdown("**Prestasi (Realisasi vs Target)**")
        show_prest = unit_prestasi_agg.rename(columns={
            "nama_unit": "Nama Unit", "realisasi": "Realisasi", "target": "Target",
            "pct": "% Pencapaian", "status": "Status",
        }).sort_values("% Pencapaian")
        st.dataframe(show_prest, use_container_width=True, height=300,
                     column_config={
                         "Realisasi": st.column_config.NumberColumn(format="%,.0f"),
                         "Target": st.column_config.NumberColumn(format="%,.0f"),
                         "% Pencapaian": st.column_config.NumberColumn(format="%.1f%%"),
                     })

st.markdown("---")


st.markdown('<h3 class="section-title">Target vs Realisasi per Site</h3>', unsafe_allow_html=True)

colA, colB = st.columns(2)

site_agg = df.groupby("lokasi", as_index=False).agg(
    pendapatan_realisasi=("pendapatan_realisasi", "sum"),
    pendapatan_budget=("pendapatan_budget", "sum"),
    prestasi_realisasi=("prestasi_realisasi", "sum"),
    prestasi_budget=("prestasi_budget", "sum"),
).sort_values("pendapatan_realisasi", ascending=False)

with colA:
    fig = go.Figure()
    fig.add_bar(x=site_agg["lokasi"], y=site_agg["pendapatan_budget"], name="Budget", marker_color=GREY)
    fig.add_bar(x=site_agg["lokasi"], y=site_agg["pendapatan_realisasi"], name="Realisasi", marker_color=CHART_GREEN)
    fig.update_layout(title="Pendapatan: Budget vs Realisasi", barmode="group",
                       yaxis_title="Rupiah", legend=dict(orientation="h", y=1.12), height=380,
                       margin=dict(t=60, b=10))
    st.plotly_chart(style_fig(fig), use_container_width=True)

with colB:
    fig2 = go.Figure()
    fig2.add_bar(x=site_agg["lokasi"], y=site_agg["prestasi_budget"], name="Target", marker_color=GOLD)
    fig2.add_bar(x=site_agg["lokasi"], y=site_agg["prestasi_realisasi"], name="Realisasi", marker_color=CHART_GREEN)
    fig2.update_layout(title="Prestasi: Target vs Realisasi", barmode="group",
                        yaxis_title="Unit Prestasi", legend=dict(orientation="h", y=1.12), height=380,
                        margin=dict(t=60, b=10))
    st.plotly_chart(style_fig(fig2), use_container_width=True)

# ---------------------------------------------------------------
# TREND BULANAN
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Tren Bulanan</h3>', unsafe_allow_html=True)

month_agg = df.groupby(["bulan_no", "bulan"], as_index=False).agg(
    pendapatan_realisasi=("pendapatan_realisasi", "sum"),
    pendapatan_budget=("pendapatan_budget", "sum"),
    total_biaya_realisasi=("total_biaya_realisasi", "sum"),
    total_biaya_budget=("total_biaya_budget", "sum"),
).sort_values("bulan_no")

fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=month_agg["bulan"], y=month_agg["pendapatan_budget"], name="Budget Pendapatan",
                           mode="lines+markers", line=dict(color=GREY, dash="dash")))
fig3.add_trace(go.Scatter(x=month_agg["bulan"], y=month_agg["pendapatan_realisasi"], name="Realisasi Pendapatan",
                           mode="lines+markers", line=dict(color=CHART_GREEN, width=3)))
fig3.add_trace(go.Scatter(x=month_agg["bulan"], y=month_agg["total_biaya_realisasi"], name="Realisasi Total Biaya",
                           mode="lines+markers", line=dict(color=RED, width=3)))
fig3.update_layout(height=400, yaxis_title="Rupiah", legend=dict(orientation="h", y=1.12), margin=dict(t=50, b=10))
st.plotly_chart(style_fig(fig3), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------
# BIAYA BREAKDOWN
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Perbandingan Komponen Biaya</h3>', unsafe_allow_html=True)

cost_components = {
    "Upah": ("upah_realisasi", "upah_budget"),
    "BBM": ("biaya_bbm_realisasi", "biaya_bbm_budget"),
    "Maintenance": ("maintenance_realisasi", "maintenance_budget"),
    "Penyusutan": ("penyusutan_realisasi", "penyusutan_budget"),
    "Lainnya": ("lainnya_realisasi", "lainnya_budget"),
}
comp_rows = []
for label, (rcol, bcol) in cost_components.items():
    comp_rows.append(dict(Komponen=label, Realisasi=df[rcol].sum(), Budget=df[bcol].sum()))
comp_df = pd.DataFrame(comp_rows)

colC, colD = st.columns([3, 2])

with colC:
    fig4 = go.Figure()
    fig4.add_bar(x=comp_df["Komponen"], y=comp_df["Budget"], name="Budget", marker_color=GREY)
    fig4.add_bar(x=comp_df["Komponen"], y=comp_df["Realisasi"], name="Realisasi", marker_color=GOLD)
    fig4.update_layout(title="Biaya per Komponen: Budget vs Realisasi", barmode="group",
                        yaxis_title="Rupiah", legend=dict(orientation="h", y=1.12), height=400,
                        margin=dict(t=60, b=10))
    st.plotly_chart(style_fig(fig4), use_container_width=True)

with colD:
    fig5 = px.pie(comp_df, names="Komponen", values="Realisasi", hole=0.5,
                   color_discrete_sequence=[CHART_GREEN, GOLD, "#4E8D7C", "#A9C7B8", RED])
    fig5.update_layout(title="Komposisi Biaya Realisasi", height=400, margin=dict(t=60, b=10))
    st.plotly_chart(style_fig(fig5), use_container_width=True)

# Biaya Langsung vs Tidak Langsung
st.markdown("##### Biaya Langsung vs Biaya Tidak Langsung")
colE, colF = st.columns([2, 3])

bl_r = df["biaya_langsung_realisasi"].sum()
bl_b = df["biaya_langsung_budget"].sum()
btl_r = df["biaya_tidak_langsung_realisasi"].sum()
btl_b = df["biaya_tidak_langsung_budget"].sum()

with colE:
    dl_df = pd.DataFrame({
        "Jenis": ["Biaya Langsung", "Biaya Tidak Langsung"],
        "Realisasi": [bl_r, btl_r],
    })
    fig6 = px.pie(dl_df, names="Jenis", values="Realisasi", hole=0.5,
                   color_discrete_sequence=[CHART_GREEN, GOLD])
    fig6.update_layout(title="Komposisi: Langsung vs Tidak Langsung", height=360, margin=dict(t=60, b=10))
    st.plotly_chart(style_fig(fig6), use_container_width=True)

with colF:
    m1, m2 = st.columns(2)
    a1 = achievement(bl_r, bl_b)
    a2 = achievement(btl_r, btl_b)
    m1.metric("Biaya Langsung (Realisasi)", fmt_rp(bl_r), f"{a1-100:+.1f}% vs Budget" if a1 is not None else "Budget = 0", delta_color="inverse")
    m2.metric("Biaya Tidak Langsung (Realisasi)", fmt_rp(btl_r), f"{a2-100:+.1f}% vs Budget" if a2 is not None else "Budget = 0", delta_color="inverse")

    fig7 = go.Figure()
    fig7.add_bar(x=["Biaya Langsung", "Biaya Tidak Langsung"], y=[bl_b, btl_b], name="Budget", marker_color=GREY)
    fig7.add_bar(x=["Biaya Langsung", "Biaya Tidak Langsung"], y=[bl_r, btl_r], name="Realisasi", marker_color=CHART_GREEN)
    fig7.update_layout(barmode="group", height=280, yaxis_title="Rupiah",
                        legend=dict(orientation="h", y=1.15), margin=dict(t=30, b=10))
    st.plotly_chart(style_fig(fig7), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------
# PER SITE x KATEGORI BREAKDOWN
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Biaya per Site & Kategori</h3>', unsafe_allow_html=True)

site_kat = df.groupby(["lokasi", "kategori"], as_index=False).agg(
    total_biaya_realisasi=("total_biaya_realisasi", "sum"),
    total_biaya_budget=("total_biaya_budget", "sum"),
    pendapatan_realisasi=("pendapatan_realisasi", "sum"),
)
site_kat["kategori_label"] = site_kat["kategori"].map(KATEGORI_LABEL).fillna(site_kat["kategori"])

fig8 = px.bar(site_kat, x="lokasi", y="total_biaya_realisasi", color="kategori_label",
              barmode="stack", color_discrete_sequence=[CHART_GREEN, GOLD],
              labels={"total_biaya_realisasi": "Total Biaya Realisasi (Rp)", "lokasi": "Site", "kategori_label": "Kategori"})
fig8.update_layout(height=380, legend=dict(orientation="h", y=1.12), margin=dict(t=50, b=10))
st.plotly_chart(style_fig(fig8), use_container_width=True)

st.markdown("---")

# ---------------------------------------------------------------
# DETAIL TABLE - PER UNIT
# ---------------------------------------------------------------
st.markdown('<h3 class="section-title">Detail Data per Unit</h3>', unsafe_allow_html=True)

detail_cols = {
    "nama_unit": "Nama Unit", "lokasi": "Site", "bulan": "Bulan", "kategori": "Kategori",
    "pendapatan_realisasi": "Pendapatan (Real)", "pendapatan_budget": "Pendapatan (Budget)",
    "prestasi_realisasi": "Prestasi (Real)", "prestasi_budget": "Prestasi (Target)",
    "upah_realisasi": "Upah", "biaya_bbm_realisasi": "BBM",
    "maintenance_realisasi": "Maintenance", "lainnya_realisasi": "Lainnya",
    "biaya_langsung_realisasi": "Biaya Langsung", "biaya_tidak_langsung_realisasi": "Biaya Tdk Langsung",
    "total_biaya_realisasi": "Total Biaya",
}
detail_df = df[list(detail_cols.keys())].rename(columns=detail_cols)
detail_df["kategori"] = detail_df["Kategori"].map(KATEGORI_LABEL).fillna(detail_df["Kategori"]) if "Kategori" in detail_df.columns else None

search = st.text_input("🔍 Cari nama unit...", "")
show_df = detail_df.copy()
if search:
    show_df = show_df[show_df["Nama Unit"].str.contains(search, case=False, na=False)]

st.dataframe(
    show_df.sort_values("Total Biaya", ascending=False),
    use_container_width=True,
    height=420,
    column_config={
        c: st.column_config.NumberColumn(format="Rp %,.0f")
        for c in ["Pendapatan (Real)", "Pendapatan (Budget)", "Upah", "BBM", "Maintenance",
                   "Lainnya", "Biaya Langsung", "Biaya Tdk Langsung", "Total Biaya"]
    },
)

csv_export = show_df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Unduh Data (CSV)", csv_export, file_name="detail_biaya_pendapatan_bkms.csv", mime="text/csv")

st.markdown("---")
st.caption("Dashboard Biaya & Pendapatan • PT Buana Karya Mandiri Sejahtera (BKMS) • Dibuat dengan Streamlit")
