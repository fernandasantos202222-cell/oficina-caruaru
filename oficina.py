import streamlit as st
import sqlite3, pandas as pd
from datetime import date, timedelta
import io, re
from urllib.parse import quote
from fpdf import FPDF

DB = "oficina.db"
conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, moto TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, data_revisao TEXT, status TEXT)")
conn.commit()

def limpa_tel(tel):
    num = re.sub(r'\D', '', str(tel))
    if num.startswith('55'): num = num[2:]
    return num

def pdf_bonito(row):
    pdf = FPDF()
    pdf.add_page()
    # Header
    pdf.set_fill_color(0,0,0)
    pdf.rect(0,0,210,35,'F')
    pdf.set_text_color(255,255,255)
    pdf.set_font("Arial","B",20)
    pdf.set_y(10)
    pdf.cell(0,10,"OFICINA CARUARU", align="C", ln=True)
    pdf.set_font("Arial","",10)
    pdf.cell(0,5,"Recibo de Servico - Revisao e Manutencao", align="C", ln=True)
    pdf.ln(15)
    pdf.set_text_color(0,0,0)
    pdf.set_font("Arial","B",12)
    pdf.cell(0,10,f"CLIENTE: {row['cliente']}", ln=True)
    pdf.set_font("Arial","",11)
    pdf.cell(0,7,f"Telefone: {row['telefone']}", ln=True)
    pdf.cell(0,7,f"Data Entrada: {row['data_entrada']} | Prox. Revisao: {row['data_revisao']}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial","B",11)
    pdf.cell(0,7,"DESCRICAO DO SERVICO:", ln=True)
    pdf.set_font("Arial","",11)
    pdf.multi_cell(0,8,row['descricao'])
    pdf.ln(5)
    pdf.set_font("Arial","B",14)
    pdf.set_fill_color(240,240,240)
    pdf.cell(0,12,f"VALOR TOTAL: R$ {float(row['valor']):.2f} | STATUS: {row['status']}", border=1, fill=True, ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial","I",9)
    pdf.cell(0,5,"Obrigado pela preferencia! Qualquer problema, chama no Zap.", align="C")
    return pdf.output(dest='S').encode('latin1')

st.set_page_config(page_title="Oficina Caruaru", layout="wide")
st.title("🏍️ Oficina Caruaru")
menu = st.sidebar.selectbox("Menu", ["Servicos","Clientes","Dashboard"])

if menu == "Clientes":
    st.subheader("Novo Cliente")
    n = st.text_input("Nome")
    t = st.text_input("Zap com DDD: 81999999999")
    m = st.text_input("Moto")
    if st.button("Salvar"):
        cur.execute("INSERT INTO clientes VALUES (NULL,?,?,?)",(n,limpa_tel(t),m)); conn.commit(); st.success("Salvo!"); st.rerun()
    st.dataframe(pd.read_sql_query("SELECT * FROM clientes", conn))

elif menu == "Servicos":
    st.subheader("Novo Servico")
    cli_df = pd.read_sql_query("SELECT * FROM clientes", conn)
    cli = st.selectbox("Cliente", [""]+cli_df['nome'].tolist() if not cli_df.empty else [])
    tel = cli_df[cli_df['nome']==cli]['telefone'].values[0] if cli else ""
    desc = st.text_area("O que foi feito?")
    val = st.number_input("Valor", 0.0)
    dt_rev = st.date_input("Revisao", date.today()+timedelta(days=90))
    status = st.selectbox("Status", ["Em andamento","Pronto","Entregue"])
    if st.button("Salvar Servico"):
        cur.execute("INSERT INTO servicos VALUES (NULL,?,?,?,?,?,?,?)",(cli,tel,desc,val,str(date.today()),str(dt_rev),status)); conn.commit(); st.success("Salvo!"); st.rerun()

    st.divider()
    df = pd.read_sql_query("SELECT * FROM servicos ORDER BY id DESC", conn)
    for _, r in df.iterrows():
        with st.expander(f"#{r['id']} {r['cliente']} - {r['status']} - R$ {r['valor']}"):
            st.write(r['descricao'])
            tel_limpo = limpa_tel(r['telefone'])
            if tel_limpo:
                msg = f"Olá {r['cliente']}! 👋\n\nSua moto está *PRONTA* na Oficina Caruaru! 🏍️\n\nServiço: {r['descricao']}\nValor: R$ {float(r['valor']):.2f}\n\nPode vir buscar! Obrigado!"
                link = f"https://wa.me/55{tel_limpo}?text={quote(msg)}"
                st.link_button(f"📲 Mandar Zap para {r['cliente']}", link, use_container_width=True)
            else:
                st.error("Cliente sem telefone cadastrado!")

            pdf_bytes = pdf_bonito(r)
            st.download_button("📄 Baixar Recibo Bonito PDF", pdf_bytes, f"recibo_{r['id']}.pdf", "application/pdf", use_container_width=True, key=f"pdf{r['id']}")

            if st.button("🗑️ Deletar", key=f"del{r['id']}"):
                cur.execute("DELETE FROM servicos WHERE id=?",(r['id'],)); conn.commit(); st.rerun()
else:
    st.dataframe(pd.read_sql_query("SELECT * FROM servicos", conn))
