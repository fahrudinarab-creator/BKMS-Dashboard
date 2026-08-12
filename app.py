import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os
import io
import re

# Library untuk Export PPTX
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

# ---------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------
st.set_page_config(
    page_title="Dashboard Biaya & Pendapatan | PT BKMS",
    page_icon="🚜",  # <--- Updated to Excavator / Heavy Equipment Icon
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------
# CUSTOM CSS (Dark Theme, RTM Cards, Modern UI)
# ---------------------------------------------------------------
st.markdown("""
<style>
    /* Dark Theme Base & Typography */
    .stApp {
        background-color: #0E1117;
        color: #E0E0E0;
    }
    
    /* Header Banner Styling */
    .header-banner {
        background: linear-gradient(135deg, #1E2640 0%, #0F172A 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        display: flex;
        align-items: center;
        gap: 20px;
    }
    .header-banner h1 {
        color: #F8FAFC;
        font-size: 1.8rem;
        font-weight: 700;
        margin: 0;
    }
    .header-banner p {
        color: #94A3B8;
        margin: 4px 0 0 0;
        font-size: 0.95rem;
    }

    /* RTM KPI Card Base */
    .rtm-card {
        background-color: #1E293B;
        border-radius: 10px;
        padding: 16px;
        border-left: 5px solid #3B82F6;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        margin-bottom: 12px;
    }
    .rtm-card.success { border-left-color: #10B981; }
    .rtm-card.danger { border-left-color: #EF4444; }
    .rtm-card.warning { border-left-color: #F59E0B; }
    .rtm-card.info { border-left-color: #06B6D4; }

    .rtm-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .rtm-value {
        font-size: 1.4rem;
        font-weight: 700;
        color: #F8FAFC;
        margin: 4px 0;
    }
    .rtm-subtext {
        font-size: 0.8rem;
        color: #CBD5E1;
    }

    /* Badge Indicators */
    .badge {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    .badge-success { background-color: rgba(16, 185, 129, 0.2); color: #34D399; }
    .badge-danger { background-color: rgba(239, 68, 68, 0.2); color: #F87171; }
    .badge-warning { background-color: rgba(245, 158, 11, 0.2); color: #FBBF24; }

    /* Section Divider Header */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #38BDF8;
        border-bottom: 2px solid #334155;
        padding-bottom: 8px;
        margin-top: 24px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------
def format_rupiah(val):
    if pd.isna(val) or val == 0:
        return "Rp 0"
    if abs(val) >= 1_000_000_000:
        return f"Rp {val/1_000_000_000:,.2f} M"
    elif abs(val) >= 1_000_000:
        return f"Rp {val/1_000_000:,.2f} Jt"
    else:
        return f"Rp {val:,.0f}"

def format_number(val, decimals=2):
    if pd.isna(val):
        return "0"
    return f"{val:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def clean_column_names(df):
    df.columns = df.columns.str.strip()
    return df

@st.cache_data
def load_data():
    file_bkms = 'data_bkms.csv'
    file_maint = 'data_maintenance.csv'
    file_part = 'data_sparepart.csv'

    df_bkms = pd.read_csv(file_bkms) if os.path.exists(file_bkms) else pd.DataFrame()
    df_maint = pd.read_csv(file_maint) if os.path.exists(file_maint) else pd.DataFrame()
    df_part = pd.read_csv(file_part) if os.path.exists(file_part) else pd.DataFrame()

    if not df_bkms.empty:
        df_bkms = clean_column_names(df_bkms)
    if not df_maint.empty:
        df_maint = clean_column_names(df_maint)
    if not df_part.empty:
        df_part = clean_column_names(df_part)

    # Standardize numeric types
    num_cols = [
        'Pendapatan_Target', 'Pendapatan_Realisasi',
        'Prestasi_Target', 'Prestasi_Realisasi',
        'Upah_Target', 'Upah_Realisasi',
        'BBM_Target', 'BBM_Realisasi',
        'Maint_Target', 'Maint_Realisasi',
        'Depresiasi_Target', 'Depresiasi_Realisasi',
        'Biaya_Langsung_Target', 'Biaya_Langsung_Realisasi',
        'Biaya_Tdk_Langsung_Target', 'Biaya_Tdk_Langsung_Realisasi'
    ]
    for c in num_cols:
        if c in df_bkms.columns:
            df_bkms[c] = pd.to_numeric(df_bkms[c], errors='coerce').fillna(0)

    if 'Biaya' in df_maint.columns:
        df_maint['Biaya'] = pd.to_numeric(df_maint['Biaya'], errors='coerce').fillna(0)
    if 'Biaya_Total' in df_part.columns:
        df_part['Biaya_Total'] = pd.to_numeric(df_part['Biaya_Total'], errors='coerce').fillna(0)
    if 'Qty' in df_part.columns:
        df_part['Qty'] = pd.to_numeric(df_part['Qty'], errors='coerce').fillna(0)

    return df_bkms, df_maint, df_part

df_bkms, df_maint, df_part = load_data()

# ---------------------------------------------------------------
# SATUAN PRESTASI & BIAYA CALCULATION
# ---------------------------------------------------------------
def get_satuan_prestasi(site, kategori_unit):
    site_clean = str(site).strip().upper()
    kat_clean = str(kategori_unit).strip().upper()

    if 'BUHUT LHL' in site_clean:
        return 'Tonase', 'Rp / Ton'
    elif site_clean in ['TANJUNG', 'BUHUT']:
        return 'HM', 'Rp / HM'
    elif site_clean in ['SUNGAI DANAU', 'KUMAI']:
        if kat_clean == 'TR':
            return 'KM', 'Rp / KM'
        else:
            return 'HM', 'Rp / HM'
    else:
        return 'HM', 'Rp / HM'

if not df_bkms.empty:
    df_bkms['Satuan_Prestasi'], df_bkms['Satuan_Biaya_Prestasi'] = zip(*df_bkms.apply(
        lambda r: get_satuan_prestasi(r['Site'], r['Kategori_Unit']), axis=1
    ))

    df_bkms['Total_Biaya_Target'] = df_bkms['Biaya_Langsung_Target'] + df_bkms['Biaya_Tdk_Langsung_Target']
    df_bkms['Total_Biaya_Realisasi'] = df_bkms['Biaya_Langsung_Realisasi'] + df_bkms['Biaya_Tdk_Langsung_Realisasi']
    df_bkms['Margin_Target'] = df_bkms['Pendapatan_Target'] - df_bkms['Total_Biaya_Target']
    df_bkms['Margin_Realisasi'] = df_bkms['Pendapatan_Realisasi'] - df_bkms['Total_Biaya_Realisasi']

# ---------------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------------
st.sidebar.title("🔍 Filter Analisis")

if not df_bkms.empty:
    list_site = ['Semua Site'] + sorted(df_bkms['Site'].dropna().unique().tolist())
    selected_site = st.sidebar.selectbox("Pilih Location / Site:", list_site)

    list_kategori = ['Semua Kategori'] + sorted(df_bkms['Kategori_Unit'].dropna().unique().tolist())
    selected_kategori = st.sidebar.selectbox("Pilih Kategori Unit:", list_kategori)

    list_bulan = ['Semua Bulan'] + sorted(df_bkms['Bulan'].dropna().unique().tolist())
    selected_bulan = st.sidebar.selectbox("Pilih Periode Bulan:", list_bulan)

    # Filter Applications
    df_filtered = df_bkms.copy()
    if selected_site != 'Semua Site':
        df_filtered = df_filtered[df_filtered['Site'] == selected_site]
    if selected_kategori != 'Semua Kategori':
        df_filtered = df_filtered[df_filtered['Kategori_Unit'] == selected_kategori]
    if selected_bulan != 'Semua Bulan':
        df_filtered = df_filtered[df_filtered['Bulan'] == selected_bulan]

    df_maint_filtered = df_maint.copy()
    df_part_filtered = df_part.copy()

    if not df_maint_filtered.empty:
        if selected_site != 'Semua Site':
            df_maint_filtered = df_maint_filtered[df_maint_filtered['Site'] == selected_site]
        if selected_bulan != 'Semua Bulan':
            df_maint_filtered = df_maint_filtered[df_maint_filtered['Bulan'] == selected_bulan]

    if not df_part_filtered.empty:
        if selected_site != 'Semua Site':
            df_part_filtered = df_part_filtered[df_part_filtered['Site'] == selected_site]
        if selected_bulan != 'Semua Bulan':
            df_part_filtered = df_part_filtered[df_part_filtered['Bulan'] == selected_bulan]

# ---------------------------------------------------------------
# HEADER BANNER (With Excavator Icon 🚜)
# ---------------------------------------------------------------
st.markdown("""
<div class="header-banner">
    <div>
        <h1>🚜 Dashboard Biaya & Pendapatan Operasional</h1>
        <p>PT BUANA KARYA MANDIRI SEJAHTERA (BKMS) &nbsp;•&nbsp; Tinjauan Manajemen & Analisis Performa Unit</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# TABS
# ---------------------------------------------------------------
tab_eksekutif, tab_operasional, tab_maintenance, tab_rtm_export = st.tabs([
    "📊 Ringkasan Eksekutif", 
    "🚛 Performa Unit & Prestasi", 
    "🔧 Maintenance & Sparepart", 
    "📑 Generator Laporan RTM (PPTX)"
])

# ===============================================================
# TAB 1: RINGKASAN EKSEKUTIF
# ===============================================================
with tab_eksekutif:
    st.markdown("<div class=\"section-header\">📈 Indikator Kinerja Utama (KPI Ringkasan)</div>", unsafe_allow_html=True)

    rev_target = df_filtered['Pendapatan_Target'].sum()
    rev_real = df_filtered['Pendapatan_Realisasi'].sum()
    rev_ach = (rev_real / rev_target * 100) if rev_target > 0 else 0

    cost_target = df_filtered['Total_Biaya_Target'].sum()
    cost_real = df_filtered['Total_Biaya_Realisasi'].sum()
    cost_ach = (cost_real / cost_target * 100) if cost_target > 0 else 0

    margin_target = df_filtered['Margin_Target'].sum()
    margin_real = df_filtered['Margin_Realisasi'].sum()

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

    with col_kpi1:
        status_class = "success" if rev_ach >= 100 else ("warning" if rev_ach >= 85 else "danger")
        badge_class = f"badge-{status_class}"
        st.markdown(f"""
        <div class="rtm-card {status_class}">
            <div class="rtm-title">Total Pendapatan</div>
            <div class="rtm-value">{format_rupiah(rev_real)}</div>
            <div class="rtm-subtext">Target: {format_rupiah(rev_target)} &nbsp;<span class="badge {badge_class}">{rev_ach:.1f}%</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col_kpi2:
        status_class = "success" if cost_real <= cost_target else "danger"
        badge_class = f"badge-{status_class}"
        st.markdown(f"""
        <div class="rtm-card {status_class}">
            <div class="rtm-title">Total Biaya Operasional</div>
            <div class="rtm-value">{format_rupiah(cost_real)}</div>
            <div class="rtm-subtext">Budget: {format_rupiah(cost_target)} &nbsp;<span class="badge {badge_class}">{cost_ach:.1f}%</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col_kpi3:
        status_class = "success" if margin_real >= margin_target else "danger"
        badge_class = f"badge-{status_class}"
        st.markdown(f"""
        <div class="rtm-card {status_class}">
            <div class="rtm-title">Margin Operasional</div>
            <div class="rtm-value">{format_rupiah(margin_real)}</div>
            <div class="rtm-subtext">Target Margin: {format_rupiah(margin_target)}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_kpi4:
        ratio_cost_rev = (cost_real / rev_real * 100) if rev_real > 0 else 0
        status_class = "success" if ratio_cost_rev <= 80 else ("warning" if ratio_cost_rev <= 90 else "danger")
        st.markdown(f"""
        <div class="rtm-card {status_class}">
            <div class="rtm-title">Cost to Revenue Ratio</div>
            <div class="rtm-value">{ratio_cost_rev:.1f}%</div>
            <div class="rtm-subtext">Efisiensi Biaya terhadap Pendapatan</div>
        </div>
        """, unsafe_allow_html=True)

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("<div class=\"section-header\">🏢 Target vs Realisasi Pendapatan per Site</div>", unsafe_allow_html=True)
        df_site_summary = df_filtered.groupby('Site')[['Pendapatan_Target', 'Pendapatan_Realisasi']].sum().reset_index()

        fig_site = go.Figure()
        fig_site.add_trace(go.Bar(x=df_site_summary['Site'], y=df_site_summary['Pendapatan_Target'], name='Target', marker_color='#3B82F6'))
        fig_site.add_trace(go.Bar(x=df_site_summary['Site'], y=df_site_summary['Pendapatan_Realisasi'], name='Realisasi', marker_color='#10B981'))
        fig_site.update_layout(barmode='group', template='plotly_dark', height=380, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_site, use_container_width=True)

    with col_chart2:
        st.markdown("<div class=\"section-header\">💸 Breakdown Struktur Biaya Operasional</div>", unsafe_allow_html=True)
        cost_breakdown = {
            'Kategori Biaya': ['Upah / Gaji', 'BBM', 'Maintenance', 'Depresiasi', 'Biaya Tdk Langsung'],
            'Nilai': [
                df_filtered['Upah_Realisasi'].sum(),
                df_filtered['BBM_Realisasi'].sum(),
                df_filtered['Maint_Realisasi'].sum(),
                df_filtered['Depresiasi_Realisasi'].sum(),
                df_filtered['Biaya_Tdk_Langsung_Realisasi'].sum()
            ]
        }
        df_cost = pd.DataFrame(cost_breakdown)
        fig_pie = px.pie(df_cost, names='Kategori Biaya', values='Nilai', hole=0.4, template='plotly_dark',
                         color_discrete_sequence=px.colors.qualitative.Pastel)
        fig_pie.update_layout(height=380, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("<div class=\"section-header\">💡 Analisis Penyebab Capaian Pendapatan</div>", unsafe_allow_html=True)
    if rev_ach < 100:
        gap = rev_target - rev_real
        st.warning(f"⚠️ **Pendapatan di bawah target sebesar {format_rupiah(gap)} ({rev_ach:.1f}% terhitung).**")
        
        df_filtered['Prestasi_Gap'] = df_filtered['Prestasi_Realisasi'] - df_filtered['Prestasi_Target']
        under_perf_units = df_filtered[df_filtered['Prestasi_Gap'] < 0]
        
        st.write("📋 **Faktor Utama Penyebab Tidak Tercapainya Target:**")
        st.markdown(f"- Terdapat **{len(under_perf_units)} unit** yang tidak mencapai target jam kerja/prestasi operasional.")
        total_p_target = df_filtered['Prestasi_Target'].sum()
        total_p_real = df_filtered['Prestasi_Realisasi'].sum()
        p_ach = (total_p_real / total_p_target * 100) if total_p_target > 0 else 0
        st.markdown(f"- Rata-rata ketercapaian prestasi unit di site terpilih adalah **{p_ach:.1f}%**.")
    else:
        st.success(f"🎉 **Selamat! Target Pendapatan Tercapai {rev_ach:.1f}% dari Target.**")

# ===============================================================
# TAB 2: PERFORMA UNIT & PRESTASI
# ===============================================================
with tab_operasional:
    st.markdown("<div class=\"section-header\">🚜 Performa Unit Operasional & Satuan Prestasi</div>", unsafe_allow_html=True)

    df_unit_display = df_filtered.copy()
    df_unit_display['Ach_Prestasi (%)'] = (df_unit_display['Prestasi_Realisasi'] / df_unit_display['Prestasi_Target'] * 100).round(1)
    df_unit_display['Ach_Pendapatan (%)'] = (df_unit_display['Pendapatan_Realisasi'] / df_unit_display['Pendapatan_Target'] * 100).round(1)
    df_unit_display['Biaya_per_Prestasi'] = df_unit_display['Total_Biaya_Realisasi'] / df_unit_display['Prestasi_Realisasi'].replace(0, np.nan)

    cols_to_show = [
        'Kode_Unit', 'Site', 'Kategori_Unit', 'Satuan_Prestasi', 
        'Prestasi_Target', 'Prestasi_Realisasi', 'Ach_Prestasi (%)',
        'Pendapatan_Realisasi', 'Total_Biaya_Realisasi', 'Satuan_Biaya_Prestasi', 'Biaya_per_Prestasi'
    ]

    st.dataframe(
        df_unit_display[cols_to_show].style.format({
            'Prestasi_Target': '{:,.1f}',
            'Prestasi_Realisasi': '{:,.1f}',
            'Pendapatan_Realisasi': lambda x: format_rupiah(x),
            'Total_Biaya_Realisasi': lambda x: format_rupiah(x),
            'Biaya_per_Prestasi': lambda x: f"Rp {x:,.0f}" if pd.notnull(x) else "Rp 0"
        }),
        use_container_width=True,
        height=400
    )

# ===============================================================
# TAB 3: MAINTENANCE & SPAREPART
# ===============================================================
with tab_maintenance:
    st.markdown("<div class=\"section-header\">🔧 Rekonsiliasi & Detail Biaya Maintenance</div>", unsafe_allow_html=True)

    col_maint1, col_maint2 = st.columns(2)

    with col_maint1:
        st.subheader("🛠️ Pengeluaran Sparepart / Persediaan")
        st.dataframe(df_part_filtered, use_container_width=True, height=350)

    with col_maint2:
        st.subheader("📋 Transaksi Service & Workshop Luar")
        st.dataframe(df_maint_filtered, use_container_width=True, height=350)

# ===============================================================
# TAB 4: GENERATOR LAPORAN RTM (PPTX)
# ===============================================================
with tab_rtm_export:
    st.markdown("<div class=\"section-header\">📄 Ekspor Laporan Tinjauan Manajemen ke PPTX</div>", unsafe_allow_html=True)
    st.write("Fitur ini memungkinkan Anda mengunduh ringkasan eksekutif dan performa operasional langsung dalam bentuk slide presentasi PowerPoint (PPTX) otomatis.")

    def create_pptx_report(df_summary):
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_slide_layout = prs.slide_layouts[6]

        # Slide 1: Judul Laporan
        slide = prs.slides.add_slide(blank_slide_layout)
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = RGBColor(15, 23, 42)

        txBox = slide.shapes.add_textbox(Inches(1), Inches(2.5), Inches(11.333), Inches(2))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        p.text = "LAPORAN TINJAUAN MANAJEMEN (RTM)"
        p.font.size = Pt(36)
        p.font.bold = True
        p.font.color.rgb = RGBColor(248, 250, 252)

        p2 = tf.add_paragraph()
        p2.text = f"PT BUANA KARYA MANDIRI SEJAHTERA\nPeriode: {selected_bulan} | Site: {selected_site}"
        p2.font.size = Pt(20)
        p2.font.color.rgb = RGBColor(148, 163, 184)

        # Slide 2: Ringkasan Eksekutif KPI
        slide2 = prs.slides.add_slide(blank_slide_layout)
        slide2.background.fill.solid()
        slide2.background.fill.fore_color.rgb = RGBColor(15, 23, 42)

        txBox2 = slide2.shapes.add_textbox(Inches(0.8), Inches(0.8), Inches(11), Inches(1))
        tf2 = txBox2.text_frame
        p_title = tf2.paragraphs[0]
        p_title.text = "Ringkasan Performa Keuangan & Operasional"
        p_title.font.size = Pt(28)
        p_title.font.bold = True
        p_title.font.color.rgb = RGBColor(248, 250, 252)

        buffer = io.BytesIO()
        prs.save(buffer)
        buffer.seek(0)
        return buffer

    if st.button("🚀 Generate & Download Slide PPTX"):
        pptx_data = create_pptx_report(df_filtered)
        st.download_button(
            label="📥 Download Laporan_RTM_BKMS.pptx",
            data=pptx_data,
            file_name=f"Laporan_RTM_BKMS_{selected_site}_{selected_bulan}.pptx",
            mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
