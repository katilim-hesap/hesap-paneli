import streamlit as st
import io
import requests
import base64
import os
from datetime import datetime
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit # Alt satıra geçiş için gerekli

# --- 0. AYARLAR VE VERI YONETIMI ---
AYAR_DOSYASI = "birim_fiyatlar.txt"

def fiyatlari_yukle():
    varsayilan = {"su": 4352.38, "kanal": 7395.14, "kesif": 2470.39, "konut": 7137.86, "konut_disi": 7137.86}
    if os.path.exists(AYAR_DOSYASI):
        try:
            with open(AYAR_DOSYASI, "r") as f:
                data = f.read().splitlines()
                return {"su": float(data[0]), "kanal": float(data[1]), "kesif": float(data[2]), "konut": float(data[3]), "konut_disi": float(data[4])}
        except: return varsayilan
    return varsayilan

def fiyatlari_kaydet(su, kanal, kesif, konut, kd):
    try:
        with open(AYAR_DOSYASI, "w") as f: f.write(f"{su}\n{kanal}\n{kesif}\n{konut}\n{kd}")
        return True
    except: return False

def belge_al(f, u):
    if f: return f.read()
    if u:
        try:
            with requests.get(u, timeout=20, stream=True) as r:
                r.raise_for_status()
                return r.content
        except: return None
    return None

def oran_kat(o): 
    return {"%100": 1.0, "%75": 0.75, "%25": 0.25}.get(o, 0.0)

def tr_duzelt(metin):
    if not metin: return ""
    duzeltmeler = {"İ":"I", "ı":"i", "Ş":"S", "ş":"s", "Ğ":"G", "ğ":"g", "Ü":"U", "ü":"u", "Ö":"O", "ö":"o", "Ç":"C", "ç":"c"}
    for eski, yeni in duzeltmeler.items(): metin = metin.replace(eski, yeni)
    return metin

# --- 1. PDF ISLEME ---
def pdf_islemek(eski_pdf, tablo, g_top, su_ok, genel_not, su_detay="", kanal_detay=""):
    try:
        old_p = PdfReader(io.BytesIO(eski_pdf))
        output = PdfWriter()
        simdi = datetime.now().strftime("%d.%m.%Y %H:%M")
        GIZLE_LISTESI = ["Tarim Alani", "Ucretsiz", "Meskun", "Muaf"]
        
        for i in range(len(old_p.pages)):
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)
            can.setFillColor(colors.white)
            can.rect(400, 740, 190, 105, fill=1, stroke=0)
            
            if i == 0:
                can.rect(45, 405, 510, 145, fill=1, stroke=0)
                can.rect(45, 90, 510, 215, fill=1, stroke=0)
            
            can.setFillColor(colors.black)
            if i == 0:
                if not su_ok:
                    can.setFont("Helvetica-Bold", 11); can.setFillColor(colors.red)
                    can.drawCentredString(300, 290, "!!! SU ABONESI OLUNAMAZ !!!")
                    can.setFillColor(colors.black)
                
                can.setFont("Helvetica-Bold", 12)
                can.drawCentredString(300, 270, "HESAPLAMA TABLOSU")
                
                y_pos = 250
                can.setLineWidth(0.5); can.setFont("Helvetica-Bold", 8)
                can.line(50, y_pos+12, 540, y_pos+12)
                can.drawString(55, y_pos, "TUR"); can.drawString(130, y_pos, "CEPHE/ADET"); can.drawString(220, y_pos, "ORAN/DETAY"); can.drawString(310, y_pos, "BIRIM FIYAT"); can.drawRightString(535, y_pos, "TUTAR (TL)")
                can.line(50, y_pos-3, 540, y_pos-3)
                
                can.setFont("Helvetica", 8)
                for r in tablo:
                    gizle = r['o'] in GIZLE_LISTESI
                    y_pos -= 13
                    can.drawString(55, y_pos, tr_duzelt(str(r['tip'])))
                    can.drawString(220, y_pos, tr_duzelt(str(r['o'])))
                    if not gizle:
                        can.drawString(130, y_pos, tr_duzelt(str(r['m'])))
                        can.drawString(310, y_pos, str(r['b']))
                        can.drawRightString(535, y_pos, f"{r['t']:,.2f}")
                    can.line(50, y_pos-3, 540, y_pos-3)
                
                for pos in [50, 125, 215, 305, 420, 540]: can.line(pos, 262, pos, y_pos-3)
                
                y_pos -= 18
                can.setFont("Helvetica-Bold", 10)
                can.drawRightString(535, y_pos, f"TOPLAM: {g_top:,.2f} TL")
                
                # --- YENI: DINAMIK VE COK SATIRLI NOTLAR ---
                y_pos -= 20
                
                def metin_ekle_ve_kaydir(baslik, metin, curr_y):
                    if not metin: return curr_y
                    can.setFont("Helvetica-Bold", 7)
                    can.drawString(50, curr_y, baslik)
                    can.setFont("Helvetica", 7)
                    # 430 birim genişliğe göre metni böler
                    satirlar = simpleSplit(tr_duzelt(metin), "Helvetica", 7, 430)
                    for satir in satirlar:
                        can.drawString(110, curr_y, satir)
                        curr_y -= 9 # Satır aralığı
                    return curr_y - 2

                y_pos = metin_ekle_ve_kaydir("Aciklama:", genel_not, y_pos)
                y_pos = metin_ekle_ve_kaydir("Su Cephe:", su_detay, y_pos)
                y_pos = metin_ekle_ve_kaydir("Kanal Cephe:", kanal_detay, y_pos)
                
                y_final = 105
                can.setFont("Helvetica", 8)
                can.drawRightString(535, y_final + 12, tr_duzelt(f"Islem Tarihi: {simdi}"))
                can.setFont("Helvetica-Bold", 9)
                can.drawRightString(535, y_final, tr_duzelt("Kase ve Imza"))
            
            can.save(); packet.seek(0)
            new_p = PdfReader(packet)
            page = old_p.pages[i]
            page.merge_page(new_p.pages[0])
            output.add_page(page)
            
        out = io.BytesIO(); output.write(out); return out.getvalue()
    except Exception as e: st.error(f"Hata: {e}"); return eski_pdf

# --- 2. ARAYUZ ---
st.set_page_config(page_title="Hesaplama Paneli", layout="wide")
st.sidebar.title("🔐 Sistem Ayarları")
kayitli_fiyatlar = fiyatlari_yukle()
pin = st.sidebar.text_input("PIN:", type="password")

if pin == "1234":
    F_SU = st.sidebar.number_input("Su Birim Fiyatı", value=kayitli_fiyatlar["su"])
    F_KANAL = st.sidebar.number_input("Kanal Birim Fiyatı", value=kayitli_fiyatlar["kanal"])
    F_KESIF = st.sidebar.number_input("Keşif Bedeli", value=kayitli_fiyatlar["kesif"])
    F_KONUT = st.sidebar.number_input("Konut Birim Fiyatı", value=kayitli_fiyatlar["konut"])
    F_KONUT_DISI = st.sidebar.number_input("İş Yeri Birim Fiyatı", value=kayitli_fiyatlar["konut_disi"])
    if st.sidebar.button("💾 Kaydet"):
        fiyatlari_kaydet(F_SU, F_KANAL, F_KESIF, F_KONUT, F_KONUT_DISI)
        st.sidebar.success("Ayarlar Güncellendi!")
else:
    F_SU, F_KANAL, F_KESIF, F_KONUT, F_KONUT_DISI = kayitli_fiyatlar.values()

SEC = ["%100", "%75", "%25", "Tarim Alani", "Meskun", "Muaf", "Ucretsiz"]
st.markdown("""<style>.stApp { background-color: #f0f9ff; } .top-bilgi { padding: 15px; border-radius: 10px; background-color: #0369a1; color: white; font-size: 24px; font-weight: bold; text-align: center; } .satir-tutar { color: #0369a1; font-weight: bold; margin-top: 32px; }</style>""", unsafe_allow_html=True)
st.title("🏛️ İZSU Katılım Bedelleri Hesaplama Sistemi")
mod = st.sidebar.radio("📌 Menü", ["💰 Katılım Bedeli", "📋 Proje İnceleme Ücreti"])

if "pdf_content" not in st.session_state: st.session_state.pdf_content = None

if mod == "💰 Katılım Bedeli":
    c_up1, c_up2 = st.columns(2)
    f_pdf = c_up1.file_uploader("📂 PDF Yükle", type="pdf", key="k_pdf_up")
    u_pdf = c_up2.text_input("🔗 PDF URL Adresi", key="k_url_up")
    
    if u_pdf and c_up2.button("📥 URL'den Dosyayı Getir"):
        res_content = belge_al(None, u_pdf)
        if res_content: st.session_state.pdf_content = res_content; st.success("Dosya yüklendi!")

    c1, c2, c3 = st.columns(3)
    sc, so = c1.number_input("Su m", 0.0, key="k_s_m"), c1.selectbox("Su Oranı", SEC, key="k_s_o")
    kc, ko = c2.number_input("Kanal m", 0.0, key="k_k_m"), c2.selectbox("Kanal Oranı", SEC, key="k_k_o")
    ksf = c3.number_input("Keşif", 0, key="k_ks_a")
    
    st.divider()
    st.subheader("📝 Rapor Detayları")
    g_not = st.text_area("Genel Not / Açıklama", height=80, placeholder="Raporun en altında görünecek ana not...")
    cd1, cd2 = st.columns(2)
    s_detay = cd1.text_area("Su Cephe Hesabı Detayı", height=68, placeholder="Örn: 20m + 15m / 2...")
    k_detay = cd2.text_area("Kanal Cephe Hesabı Detayı", height=68, placeholder="Örn: 10m + 12m / 2...")
    
    top = (sc * F_SU / 2 * oran_kat(so)) + (kc * F_KANAL / 2 * oran_kat(ko)) + (ksf * F_KESIF)
    st.markdown(f'<div class="top-bilgi">TOPLAM: {top:,.2f} TL</div>', unsafe_allow_html=True)
    
    if st.button("🚀 Rapor Oluştur ve Önizle"):
        b = f_pdf.read() if f_pdf else st.session_state.pdf_content
        if b:
            v = [
                {'tip':'Su','m':sc,'o':so,'b':f"{F_SU:,.2f}",'t': (sc * F_SU / 2 * oran_kat(so))}, 
                {'tip':'Kanal','m':kc,'o':ko,'b':f"{F_KANAL:,.2f}",'t': (kc * F_KANAL / 2 * oran_kat(ko))}, 
                {'tip':'Kesif','m':ksf,'o':'-','b':f"{F_KESIF:,.2f}",'t':ksf*F_KESIF}
            ]
            res = pdf_islemek(b, v, top, (so not in ["%25", "Tarim Alani"]), g_not, s_detay, k_detay)
            b64 = base64.b64encode(res).decode()
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800"></iframe>', unsafe_allow_html=True)
            st.download_button("📥 PDF İndir", res, "Katilim_Bedeli.pdf")
        else: st.warning("Lütfen PDF yükleyin.")

else: # --- PROJE İNCELEME ---
    cp_up1, cp_up2 = st.columns(2)
    f_p = cp_up1.file_uploader("📂 Proje PDF Yükle", type="pdf")
    u_p = cp_up2.text_input("🔗 Proje PDF URL")
    
    if u_p and cp_up2.button("📥 URL'den Getir"):
        res_content = belge_al(None, u_p)
        if res_content: st.session_state.pdf_content = res_content; st.success("Dosya yüklendi!")

    h_kat = st.checkbox("✅ Katılım Bedellerini Hesapla", value=True)
    t_kat, su_ok_p, p_tablo = 0.0, True, []

    if h_kat:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("💧 Su")
            if 'p_su' not in st.session_state: st.session_state.p_su = []
            if st.button("➕ Su Satırı Ekle"): st.session_state.p_su.append({'m':0.0, 'o':'%100'})
            for i, r in enumerate(st.session_state.p_su):
                ca, cb, cc, cd = st.columns([1.5, 1.5, 1, 0.4])
                r['m'] = ca.number_input(f"Metre {i+1}", value=r['m'], key=f"psm_{i}")
                r['o'] = cb.selectbox(f"Oran {i+1}", SEC, index=SEC.index(r['o']), key=f"pso_{i}")
                tut = (r['m'] * F_SU / 2) * oran_kat(r['o'])
                cc.markdown(f'<div class="satir-tutar">{tut:,.2f} TL</div>', unsafe_allow_html=True)
                if cd.button("❌", key=f"ds_{i}"): st.session_state.p_su.pop(i); st.rerun()
                t_kat += tut; p_tablo.append({'tip':'Su','m':r['m'],'o':r['o'],'b':f"{F_SU:,.2f}",'t':tut})
                if r['o'] in ["%25", "Tarim Alani"]: su_ok_p = False

        with col2:
            st.subheader("🚽 Kanal")
            if 'p_ka' not in st.session_state: st.session_state.p_ka = []
            if st.button("➕ Kanal Satırı Ekle"): st.session_state.p_ka.append({'m':0.0, 'o':'%100'})
            for i, r in enumerate(st.session_state.p_ka):
                ca, cb, cc, cd = st.columns([1.5, 1.5, 1, 0.4])
                r['m'] = ca.number_input(f"Metre {i+1}", value=r['m'], key=f"pkm_{i}")
                r['o'] = cb.selectbox(f"Oran {i+1}", SEC, index=SEC.index(r['o']), key=f"pko_{i}")
                tut = (r['m'] * F_KANAL / 2) * oran_kat(r['o'])
                cc.markdown(f'<div class="satir-tutar">{tut:,.2f} TL</div>', unsafe_allow_html=True)
                if cd.button("❌", key=f"dk_{i}"): st.session_state.p_ka.pop(i); st.rerun()
                t_kat += tut; p_tablo.append({'tip':'Kanal','m':r['m'],'o':r['o'],'b':f"{F_KANAL:,.2f}",'t':tut})

    st.divider()
    t_konut, t_isyeri = 0.0, 0.0
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        if st.checkbox("🏠 Konut Hesaplaması Ekle"):
            k_adt = st.number_input("Konut Sayısı", 0)
            k_tip = st.selectbox("Tipi", ["Daire", "Müstakil"])
            t_konut = k_adt * (F_KONUT / 2 if k_tip == "Daire" else F_KONUT)
            p_tablo.append({'tip':'Konut','m':k_adt,'o':k_tip,'b':f"{F_KONUT/2:,.2f}" if k_tip=="Daire" else f"{F_KONUT:,.2f}",'t':t_konut})
    with col_k2:
        if st.checkbox("🏭 İş Yeri Hesaplaması Ekle"):
            kd_adt = st.number_input("İş Yeri Sayısı", 0)
            kd_aln = st.number_input("Toplam Alan (m2)", 0.0)
            t_isyeri = (kd_aln * F_KONUT_DISI) / 100
            p_tablo.append({'tip':'Is Yeri','m':kd_adt,'o':f"{kd_aln}m2",'b':f"{F_KONUT_DISI:,.2f}",'t':t_isyeri})

    st.divider()
    p_ksf = st.number_input("🔍 Keşif Adedi", 0)
    t_ksf = p_ksf * F_KESIF
    p_tablo.append({'tip':'Kesif','m':p_ksf,'o':'-','b':f"{F_KESIF:,.2f}",'t':t_ksf})
    
    st.subheader("📝 Rapor Detayları")
    p_not = st.text_area("Genel Not", height=80)
    pcd1, pcd2 = st.columns(2)
    ps_detay = pcd1.text_area("Proje Su Cephe Detayı", height=68)
    pk_detay = pcd2.text_area("Proje Kanal Cephe Detayı", height=68)

    gt = t_kat + t_konut + t_isyeri + t_ksf
    st.markdown(f'<div class="top-bilgi">GENEL TOPLAM: {gt:,.2f} TL</div>', unsafe_allow_html=True)

    if st.button("🚀 Raporu Oluştur ve Önizle"):
        b_p = f_p.read() if f_p else st.session_state.pdf_content
        if b_p:
            res = pdf_islemek(b_p, p_tablo, gt, su_ok_p, p_not, ps_detay, pk_detay)
            b64 = base64.b64encode(res).decode()
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="800"></iframe>', unsafe_allow_html=True)
            st.download_button("📥 PDF İndir", res, "Proje_Detayli.pdf")
        else: st.warning("PDF yükleyin.")
