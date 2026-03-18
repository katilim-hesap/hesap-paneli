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

# --- 0. AYARLAR VE VERI YONETIMI ---
AYAR_DOSYASI = "birim_fiyatlar.txt"

def fiyatlari_yukle():
    varsayilan = {"su": 4352.38, "kanal": 7395.14, "kesif": 2470.39, "konut": 500.0, "konut_disi": 750.0}
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
            r = requests.get(u, timeout=10)
            if r.status_code == 200: return r.content
        except Exception as e: st.error(f"Baglanti Hatasi: {e}")
    return None

def oran_kat(o): 
    return {"%100": 1.0, "%75": 0.75, "%25": 0.25}.get(o, 0.0)

def tr_duzelt(metin):
    duzeltmeler = {"İ":"I", "ı":"i", "Ş":"S", "ş":"s", "Ğ":"G", "ğ":"g", "Ü":"U", "ü":"u", "Ö":"O", "ö":"o", "Ç":"C", "ç":"c"}
    for eski, yeni in duzeltmeler.items(): metin = metin.replace(eski, yeni)
    return metin

# --- 1. PDF ISLEME ---
def pdf_islemek(eski_pdf, tablo, g_top, su_ok, genel_not):
    try:
        old_p = PdfReader(io.BytesIO(eski_pdf))
        output = PdfWriter()
        simdi = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        # Rakamların gizleneceği özel durumlar
        GIZLE_LISTESI = ["Tarim Alani", "Ucretsiz", "Meskun", "Muaf"]
        
        for i in range(len(old_p.pages)):
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=A4)
            
            # A. MASKELEME (Sağ üst tarih alanı)
            can.setFillColor(colors.white)
            can.rect(400, 740, 190, 105, fill=1, stroke=0)
            
            if i == 0:
                can.rect(45, 405, 510, 145, fill=1, stroke=0) # Orta alan
                can.rect(45, 90, 510, 215, fill=1, stroke=0)  # Alt tablo alanı
            
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
                    # Rakamlar gizlensin mi?
                    gizle = r['o'] in GIZLE_LISTESI
                    
                    y_pos -= 13
                    can.drawString(55, y_pos, tr_duzelt(str(r['tip'])))
                    
                    # Oran her zaman yazılır
                    can.drawString(220, y_pos, tr_duzelt(str(r['o'])))
                    
                    # Gizleme durumuna göre rakamsal alanlar
                    if not gizle:
                        can.drawString(130, y_pos, tr_duzelt(str(r['m'])))
                        can.drawString(310, y_pos, str(r['b']))
                        can.drawRightString(535, y_pos, f"{r['t']:,.2f}")
                    else:
                        # Gizle seçiliyse rakam yerine boş kalsın
                        can.drawString(130, y_pos, "")
                        can.drawString(310, y_pos, "")
                        can.drawRightString(535, y_pos, "")
                        
                    can.line(50, y_pos-3, 540, y_pos-3)
                
                for pos in [50, 125, 215, 305, 420, 540]: can.line(pos, 262, pos, y_pos-3)
                
                y_pos -= 20
                can.setFont("Helvetica-Bold", 10)
                can.drawRightString(535, y_pos, f"TOPLAM: {g_top:,.2f} TL")
                
                if genel_not:
                    y_pos -= 12
                    can.setFont("Helvetica-Bold", 7); can.drawString(50, y_pos, "Aciklama:"); 
                    can.setFont("Helvetica", 7); can.drawString(95, y_pos, tr_duzelt(genel_not[:100]))
                
                y_final = y_pos - 35
                can.setFont("Helvetica", 9)
                can.drawRightString(535, y_final + 12, tr_duzelt(f"Islem Tarihi: {simdi}"))
                can.setFont("Helvetica-Bold", 10)
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

st.title("🏛️ Belediye Hesaplama Sistemi")
mod = st.sidebar.radio("📌 Menü", ["💰 Katılım Bedeli", "📋 Proje İnceleme Ücreti"])

if mod == "💰 Katılım Bedeli":
    c_up1, c_up2 = st.columns(2)
    f_pdf = c_up1.file_uploader("📂 PDF Yükle", type="pdf", key="k_pdf_up")
    u_pdf = c_up2.text_input("🔗 Bağlantı Adresi (URL)", key="k_url_up")
    
    c1, c2, c3 = st.columns(3)
    sc, so = c1.number_input("Su m", 0.0, key="k_s_m"), c1.selectbox("Su Oranı", SEC, key="k_s_o")
    kc, ko = c2.number_input("Kanal m", 0.0, key="k_k_m"), c2.selectbox("Kanal Oranı", SEC, key="k_k_o")
    ksf, g_not = c3.number_input("Keşif", 0, key="k_ks_a"), st.text_input("Not", key="k_n_t")
    
    top = (sc*F_SU*oran_kat(so)) + (kc*F_KANAL*oran_kat(ko)) + (ksf*F_KESIF)
    st.markdown(f'<div class="top-bilgi">TOPLAM: {top:,.2f} TL</div>', unsafe_allow_html=True)
    
    if st.button("🚀 Rapor Oluştur ve Önizle", key="k_btn"):
        b = belge_al(f_pdf, u_pdf)
        if b:
            v = [{'tip':'Su','m':sc,'o':so,'b':f"{F_SU:,.2f}",'t':sc*F_SU*oran_kat(so)}, {'tip':'Kanal','m':kc,'o':ko,'b':f"{F_KANAL:,.2f}",'t':kc*F_KANAL*oran_kat(ko)}, {'tip':'Kesif','m':ksf,'o':'-','b':f"{F_KESIF:,.2f}",'t':ksf*F_KESIF}]
            res = pdf_islemek(b, v, top, (so not in ["%25", "Tarim Alani"]), g_not)
            b64 = base64.b64encode(res).decode()
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>', unsafe_allow_html=True)
            st.download_button("📥 PDF İndir / Yazdır", res, "Katilim_Bedeli.pdf")

else: # --- DINAMIK PROJE İNCELEME ---
    cp_up1, cp_up2 = st.columns(2)
    f_p = cp_up1.file_uploader("📂 Proje PDF Yükle", type="pdf", key="p_pdf_up")
    u_p = cp_up2.text_input("🔗 Bağlantı Adresi (URL)", key="p_url_up")
    
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
                tut = r['m'] * F_SU * oran_kat(r['o'])
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
                tut = r['m'] * F_KANAL * oran_kat(r['o'])
                cc.markdown(f'<div class="satir-tutar">{tut:,.2f} TL</div>', unsafe_allow_html=True)
                if cd.button("❌", key=f"dk_{i}"): st.session_state.p_ka.pop(i); st.rerun()
                t_kat += tut; p_tablo.append({'tip':'Kanal','m':r['m'],'o':r['o'],'b':f"{F_KANAL:,.2f}",'t':tut})

    st.divider()
    t_konut, t_isyeri = 0.0, 0.0
    if st.checkbox("🏠 Konut Hesaplaması Ekle"):
        c1, c2, c3 = st.columns([1.5, 1.5, 1])
        k_adt = c1.number_input("Konut Sayısı", 0, key="kon_say")
        k_tip = c2.selectbox("Tipi", ["Daire", "Müstakil"], key="kon_tip")
        t_konut = k_adt * (F_KONUT / 2 if k_tip == "Daire" else F_KONUT)
        c3.markdown(f'<div class="satir-tutar">{t_konut:,.2f} TL</div>', unsafe_allow_html=True)
        p_tablo.append({'tip':'Konut','m':k_adt,'o':k_tip,'b':f"{F_KONUT/2:,.2f}" if k_tip=="Daire" else f"{F_KONUT:,.2f}",'t':t_konut})

    if st.checkbox("🏭 İş Yeri Hesaplaması Ekle"):
        c1, c2, c3 = st.columns([1.5, 1.5, 1])
        kd_adt = c1.number_input("İş Yeri Sayısı", 0, key="is_say")
        kd_aln = c2.number_input("Toplam Alan (m2)", 0.0, key="is_alan")
        t_isyeri = (kd_aln * F_KONUT_DISI) / 100
        c3.markdown(f'<div class="satir-tutar">{t_isyeri:,.2f} TL</div>', unsafe_allow_html=True)
        p_tablo.append({'tip':'Is Yeri','m':kd_adt,'o':f"{kd_aln}m2",'b':f"{F_KONUT_DISI:,.2f}",'t':t_isyeri})

    st.divider()
    p_ksf = st.number_input("🔍 Keşif Adedi", 0, key="pro_kesif")
    t_ksf = p_ksf * F_KESIF
    p_tablo.append({'tip':'Kesif','m':p_ksf,'o':'-','b':f"{F_KESIF:,.2f}",'t':t_ksf})
    
    p_not = st.text_input("📝 Rapor Notu", key="pro_not")
    gt = t_kat + t_konut + t_isyeri + t_ksf
    st.markdown(f'<div class="top-bilgi">GENEL TOPLAM: {gt:,.2f} TL</div>', unsafe_allow_html=True)

    if st.button("🚀 Raporu Oluştur ve Önizle", key="p_btn_bas"):
        b_p = belge_al(f_p, u_p)
        if b_p:
            res = pdf_islemek(b_p, p_tablo, gt, su_ok_p, p_not)
            b64 = base64.b64encode(res).decode()
            st.markdown(f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="600"></iframe>', unsafe_allow_html=True)
            st.download_button("📥 PDF İndir / Yazdır", res, "Proje_Detayli.pdf")