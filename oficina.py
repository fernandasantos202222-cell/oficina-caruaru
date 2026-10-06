import streamlit as st
import sqlite3, pandas as pd, re
from datetime import date, timedelta
from urllib.parse import quote
from fpdf import FPDF

DB = "oficina.db"
conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY, nome TEXT, telefone TEXT, moto TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, data_revisao TEXT, status TEXT)")
conn.commit()

def limpa_tel(t):
    num = re.sub(r'\D','', str(t))
    if num.startswith('55'): num = num[2:]
    return num

def pdf_bonito(row):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20,20,20)
    pdf.rect(0,0,210,32,'F')
    pdf.set_text_color(255,255,255)
    pdf.set_font("Arial","B",18)
    pdf.set_y(8); pdf.cell(0,10,"OFICINA CARUARU", align="C", ln=True)
    pdf.set_font("Arial","",9); pdf.cell(0,5,"Recibo de Servico - Manutencao e Revisao", align="C", ln=True)
    pdf.ln(15); pdf.set_text_color(0,0,0)
    pdf.set_font("Arial","B",12); pdf.cell(0,9,f"Cliente: {row['cliente']}", ln=True)
    pdf.set_font("Arial","",11); pdf.cell(0,7,f"Telefone: {row['telefone']} | Entrada: {row['data_entrada']}", ln=True)
    pdf.cell(0,7,f"Proxima Revisao: {row['data_revisao']}", ln=True)
    pdf.ln(4)
    pdf.set_font("Arial","B",11); pdf.cell(0,7,"Descricao do Servico Executado:", ln=True)
    pdf.set_font("Arial","",11); pdf.multi_cell(0,7,row['descricao'])
    pdf.ln(6)
    pdf.set_font("Arial","B",14); pdf.set_fill_color(230,230,230)
    pdf.cell(0,12,f"Valor Total: R$ {float(row['valor']):.2f} - Status: {row['status']}", border=1, fill=True, align="C", ln=True)
    pdf.ln(12); pdf.set_font("Arial","I",9); pdf.cell(0,5,"Obrigado pela preferencia! Volte sempre.", align="C")
    return pdf.output(dest='S').encode('latin1')

st.set_page_config(page_title="Oficina Caruaru", layout="wide")
st.title("🏍️ Oficina Caruaru - Sistema Oficial")
menu = st.sidebar.selectbox("Menu", ["Dashboard","Clientes","Servicos"])

# DASHBOARD COM FATURAMENTO E TICKET MEDIO
if menu == "Dashboard":
    df = pd.read_sql_query("SELECT * FROM servicos", conn)
    fat_total = df['valor'].sum() if not df.empty else 0
    ticket = df['valor'].mean() if not df.empty else 0
    qtd = len(df)
    c1,c2,c3 = st.columns(3)
    c1.metric("Faturamento Total", f"R$ {fat_total:.2f}")
    c2.metric("Ticket Medio por Moto", f"R$ {ticket:.2f}")
    c3.metric("Total de Servicos", qtd)
    st.divider()
    st.dataframe(df, use_container_width=True)

elif menu == "Clientes":
    st.subheader("Novo Cliente")
    n = st.text_input("Nome do Cliente")
    t = st.text_input("WhatsApp com DDD (ex: 81999999999)")
    m = st.text_input("Moto / Placa")
    if st.button("Salvar Cliente"):
        cur.execute("INSERT INTO clientes VALUES (NULL,?,?,?)",(n, limpa_tel(t), m)); conn.commit(); st.success("Cliente salvo!"); st.rerun()

    st.divider()
    st.subheader("Editar / Deletar Cliente")
    cli_df = pd.read_sql_query("SELECT * FROM clientes", conn)
    st.dataframe(cli_df, use_container_width=True)
    if not cli_df.empty:
        id_sel = st.selectbox("Selecione o ID para editar", cli_df['id'].tolist())
        row = cli_df[cli_df['id']==id_sel].iloc[0]
        en = st.text_input("Editar Nome", value=row['nome'])
        et = st.text_input("Editar Telefone", value=row['telefone'])
        em = st.text_input("Editar Moto", value=row['moto'])
        c1,c2 = st.columns(2)
        if c1.button("💾 Atualizar Cliente"):
            cur.execute("UPDATE clientes SET nome=?, telefone=?, moto=? WHERE id=?",(en, limpa_tel(et), em, id_sel)); conn.commit(); st.success("Atualizado!"); st.rerun()
        if c2.button("🗑️ Deletar Cliente"):
            cur.execute("DELETE FROM clientes WHERE id=?",(id_sel,)); conn.commit(); st.warning("Deletado!"); st.rerun()

else: # SERVICOS
    st.subheader("Novo Servico")
    cli_df = pd.read_sql_query("SELECT * FROM clientes", conn)
    cli = st.selectbox("Selecione o Cliente", [""]+cli_df['nome'].tolist() if not cli_df.empty else [])
    tel = cli_df[cli_df['nome']==cli]['telefone'].values[0] if cli else ""
    desc = st.text_area("O que foi feito na moto?")
    val = st.number_input("Valor do Servico R$", 0.0)
    dt_rev = st.date_input("Data da Proxima Revisao", date.today()+timedelta(days=90))
    status = st.selectbox("Status", ["Em andamento","Pronto","Entregue"])
    if st.button("Salvar Servico"):
        cur.execute("INSERT INTO servicos VALUES (NULL,?,?,?,?,?,?,?)",(cli, tel, desc, val, str(date.today()), str(dt_rev), status)); conn.commit(); st.success("Servico salvo!"); st.rerun()

    st.divider()
    df = pd.read_sql_query("SELECT * FROM servicos ORDER BY id DESC", conn)
    for _, r in df.iterrows():
        with st.expander(f"#{r['id']} - {r['cliente']} - {r['status']} - R$ {r['valor']:.2f}"):
            st.write(f"**Descricao:** {r['descricao']}")
            tel_limpo = limpa_tel(r['telefone'])
            msg = f"Ola {r['cliente']}! Sua moto esta PRONTA na Oficina Caruaru!\nServico: {r['descricao']}\nValor: R$ {float(r['valor']):.2f}\nPode vir buscar!"
            link = f"https://wa.me/55{tel_limpo}?text={quote(msg)}"
            st.link_button(f"📲 Enviar WhatsApp para {r['cliente']}", link, use_container_width=True)
            st.download_button("📄 Baixar Recibo", pdf_bonito(r), f"recibo_{r['id']}.pdf", "application/pdf", use_container_width=True, key=f"pdf{r['id']}")
            st.divider()
            nd = st.text_area("Editar Descricao", value=r['descricao'], key=f"ed{r['id']}")
            nv = st.number_input("Editar Valor", value=float(r['valor']), key=f"ev{r['id']}")
            ns = st.selectbox("Editar Status", ["Em andamento","Pronto","Entregue"], index=["Em andamento","Pronto","Entregue"].index(r['status']), key=f"es{r['id']}")
            c1,c2 = st.columns(2)
            if c1.button("Atualizar", key=f"up{r['id']}"):
                cur.execute("UPDATE servicos SET descricao=?, valor=?, status=? WHERE id=?",(nd, nv, ns, r['id'])); conn.commit(); st.rerun()
            if c2.button("Deletar Servico", key=f"del{r['id']}"):
                cur.execute("DELETE FROM servicos WHERE id=?",(r['id'],)); conn.commit(); st.rerun()
