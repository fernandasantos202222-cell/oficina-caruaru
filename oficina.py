import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, timedelta
import io
from urllib.parse import quote
from fpdf import FPDF

DB = "oficina.db"
conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, data_revisao TEXT, status TEXT)")
conn.commit()

st.set_page_config(page_title="Oficina Caruaru", layout="wide")
st.title("🏍️ Sistema da Oficina - Caruaru")
menu = st.sidebar.selectbox("Menu", ["Dashboard", "Clientes", "Servicos", "Alertas Revisao"])

if menu == "Dashboard":
    fat = cur.execute("SELECT SUM(valor) FROM servicos").fetchone()[0] or 0
    st.metric("Faturamento", f"R$ {fat:.2f}")
    df = pd.read_sql_query("SELECT * FROM servicos ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        st.download_button("📥 Baixar Relatorio Excel", buffer.getvalue(), f"relatorio_{date.today()}.xlsx")

elif menu == "Clientes":
    nome = st.text_input("Nome")
    tel = st.text_input("WhatsApp com DDD ex: 81999999999")
    moto = st.text_input("Moto / Placa")
    if st.button("Salvar Cliente"):
        cur.execute("INSERT INTO clientes (nome, telefone, moto) VALUES (?,?,?)", (nome, tel, moto))
        conn.commit()
        st.success("Salvo!")
    st.dataframe(pd.read_sql_query("SELECT * FROM clientes", conn))

elif menu == "Servicos":
    clientes = pd.read_sql_query("SELECT nome, telefone FROM clientes", conn)
    cli = st.selectbox("Cliente", [""] + clientes['nome'].tolist() if not clientes.empty else [])
    tel_auto = clientes[clientes['nome']==cli]['telefone'].values[0] if cli and not clientes.empty else ""
    desc = st.text_area("O que foi feito?")
    val = st.number_input("Valor R$", min_value=0.0)
    data_ent = st.date_input("Data entrada", value=date.today())
    data_rev = st.date_input("Proxima revisao", value=date.today()+timedelta(days=90))
    status = st.selectbox("Status", ["Em andamento", "Pronto", "Entregue"])
    if st.button("Salvar Servico"):
        cur.execute("INSERT INTO servicos (cliente, telefone, descricao, valor, data_entrada, data_revisao, status) VALUES (?,?,?,?,?,?,?)", (cli, tel_auto, desc, val, str(data_ent), str(data_rev), status))
        conn.commit()
        st.success("Servico salvo!")
    df = pd.read_sql_query("SELECT * FROM servicos ORDER BY id DESC", conn)
    for _, row in df.iterrows():
        st.write(f"**{row['cliente']}** - {row['descricao']} - R$ {row['valor']}")
        msg = f"Ola {row['cliente']}! Sua moto esta PRONTA! {row['descricao']} - R$ {row['valor']:.2f}"
        link = f"https://wa.me/55{row['telefone']}?text={quote(msg)}"
        st.markdown(f"[📲 Mandar Zap]({link})")
        if st.button(f"Gerar PDF {row['id']}", key=f"pdf{row['id']}"):
            pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial","B",16)
            pdf.cell(0,10,"OFICINA CARUARU",ln=True,align="C"); pdf.ln(10)
            pdf.set_font("Arial","",12); pdf.cell(0,8,f"Cliente: {row['cliente']}",ln=True)
            pdf.multi_cell(0,8,f"Servico: {row['descricao']}"); pdf.cell(0,10,f"Valor: R$ {row['valor']:.2f}",ln=True)
            b = pdf.output(dest='S').encode('latin1')
            st.download_button("📄 Baixar PDF", b, f"recibo_{row['id']}.pdf", key=f"d{row['id']}")

else:
    st.write("Revisoes proximas")
    df = pd.read_sql_query("SELECT * FROM servicos", conn)
    st.dataframe(df)
