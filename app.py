import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio
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
        padding: 22px 28px;
        border-radius: 12px;
        margin-bottom: 18px;
        border: 1px solid {BORDER};
    }}
    .header-banner h1 {{ color: white !important; margin: 0; font-size: 26px; }}
    .header-banner p {{ color: {GOLD} !important; margin: 2px 0 0 0; font-size: 14px; letter-spacing: 0.5px; }}
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
# HEADER
# ---------------------------------------------------------------
st.markdown("""
<div class="header-banner">
    <h1>📊 Dashboard Biaya & Pendapatan</h1>
    <p>PT BUANA KARYA MANDIRI SEJAHTERA (BKMS) &nbsp;•&nbsp; Target vs Realisasi</p>
</div>
""", unsafe_allow_html=True)

if df.empty:
    st.warning("Tidak ada data untuk kombinasi filter yang dipilih. Silakan ubah filter di sidebar.")
    st.stop()

st.caption(f"Menampilkan **{len(df):,}** baris data unit • Site: {', '.join(sel_site) if len(sel_site)<=4 else f'{len(sel_site)} site'} • Bulan: {', '.join(sel_month)}")

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
          f"{ach_pendapatan-100:+.1f}% vs Budget" if ach_pendapatan is not None else "Budget = 0")
c2.metric("Prestasi (Realisasi)", f"{tot_prestasi_r:,.0f}",
          f"{ach_prestasi-100:+.1f}% vs Target" if ach_prestasi is not None else "Target = 0")
c3.metric("Total Biaya (Realisasi)", fmt_rp(tot_biaya_r),
          f"{ach_biaya-100:+.1f}% vs Budget" if ach_biaya is not None else "Budget = 0",
          delta_color="inverse")
margin = tot_pendapatan_r - tot_biaya_r
c4.metric("Margin (Pendapatan - Biaya)", fmt_rp(margin))

st.markdown("---")

# ---------------------------------------------------------------
# TARGET VS REALISASI - PENDAPATAN & PRESTASI PER SITE
# ---------------------------------------------------------------
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
