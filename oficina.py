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
    st.metric("Faturamento Total", f"R$ {fat:.2f}")
    df = pd.read_sql_query("SELECT * FROM servicos ORDER BY id DESC", conn)
    st.dataframe(df, use_container_width=True)
    if not df.empty:
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        st.download_button("📥 Baixar Relatorio Excel", buffer.getvalue(), f"relatorio_{date.today()}.xlsx")

elif menu == "Clientes":
    st.subheader("Novo Cliente")
    nome = st.text_input("Nome")
    tel = st.text_input("WhatsApp DDD ex: 81999999999")
    moto = st.text_input("Moto / Placa")
    if st.button("Salvar Cliente"):
        cur.execute("INSERT INTO clientes (nome, telefone, moto) VALUES (?,?,?)", (nome, tel, moto))
        conn.commit()
        st.success("Salvo!"); st.rerun()

    st.divider()
    st.subheader("Editar / Deletar Cliente")
    df_cli = pd.read_sql_query("SELECT * FROM clientes", conn)
    st.dataframe(df_cli, use_container_width=True)
    if not df_cli.empty:
        id_sel = st.selectbox("Escolha ID para editar/deletar", df_cli['id'].tolist())
        cli_sel = df_cli[df_cli['id']==id_sel].iloc[0]
        novo_nome = st.text_input("Nome editar", value=cli_sel['nome'], key="enome")
        novo_tel = st.text_input("Telefone editar", value=cli_sel['telefone'], key="etel")
        novo_moto = st.text_input("Moto editar", value=cli_sel['moto'], key="emoto")
        c1,c2 = st.columns(2)
        if c1.button("💾 Atualizar"):
            cur.execute("UPDATE clientes SET nome=?, telefone=?, moto=? WHERE id=?", (novo_nome, novo_tel, novo_moto, id_sel))
            conn.commit(); st.success("Atualizado!"); st.rerun()
        if c2.button("🗑️ Deletar"):
            cur.execute("DELETE FROM clientes WHERE id=?", (id_sel,))
            conn.commit(); st.warning("Deletado!"); st.rerun()

elif menu == "Servicos":
    st.subheader("Novo Serviço")
    clientes = pd.read_sql_query("SELECT nome, telefone FROM clientes", conn)
    lista = clientes['nome'].tolist() if not clientes.empty else []
    cli = st.selectbox("Cliente", [""] + lista)
    tel_auto = clientes[clientes['nome']==cli]['telefone'].values[0] if cli and not clientes.empty else ""
    desc = st.text_area("O que foi feito?")
    val = st.number_input("Valor R$", min_value=0.0)
    data_ent = st.date_input("Data entrada", value=date.today())
    data_rev = st.date_input("Proxima revisao", value=date.today()+timedelta(days=90))
    status = st.selectbox("Status", ["Em andamento", "Pronto", "Entregue"])
    if st.button("Salvar Servico"):
        cur.execute("INSERT INTO servicos (cliente, telefone, descricao, valor, data_entrada, data_revisao, status) VALUES (?,?,?,?,?,?,?)", (cli, tel_auto, desc, val, str(data_ent), str(data_rev), status))
        conn.commit(); st.success("Salvo!"); st.rerun()

    st.divider()
    st.subheader("Lista - Editar / Deletar / Zap / PDF")
    df = pd.read_sql_query("SELECT * FROM servicos ORDER BY id DESC", conn)
    for _, row in df.iterrows():
        with st.expander(f"{row['id']} - {row['cliente']} - {row['status']} - R$ {row['valor']}"):
            st.write(f"**Descrição:** {row['descricao']}")
            st.write(f"**Entrada:** {row['data_entrada']} | **Revisão:** {row['data_revisao']}")
            # BOTÃO ZAP QUE FUNCIONA
            msg = f"Ola {row['cliente']}! Sua moto esta PRONTA na Oficina Caruaru! Servico: {row['descricao']} - Valor: R$ {row['valor']:.2f}"
            link = f"https://wa.me/55{row['telefone']}?text={quote(msg)}"
            st.link_button("📲 Mandar Zap PRONTO", link)

            # PDF
            if st.button(f"Gerar PDF {row['id']}", key=f"pdf{row['id']}"):
                pdf = FPDF(); pdf.add_page(); pdf.set_font("Arial","B",16)
                pdf.cell(0,10,"OFICINA CARUARU",ln=True,align="C"); pdf.ln(10)
                pdf.set_font("Arial","",12); pdf.cell(0,8,f"Cliente: {row['cliente']}",ln=True)
                pdf.cell(0,8,f"Tel: {row['telefone']}",ln=True)
                pdf.multi_cell(0,8,f"Servico: {row['descricao']}"); pdf.cell(0,10,f"Valor: R$ {row['valor']:.2f}",ln=True)
                b = pdf.output(dest='S').encode('latin1')
                st.download_button("📄 Baixar PDF", b, f"recibo_{row['id']}.pdf", key=f"d{row['id']}")

            st.divider()
            # EDITAR
            n_desc = st.text_area("Editar descrição", value=row['descricao'], key=f"d{row['id']}")
            n_val = st.number_input("Editar valor", value=float(row['valor']), key=f"v{row['id']}")
            n_status = st.selectbox("Editar status", ["Em andamento", "Pronto", "Entregue"], index=["Em andamento", "Pronto", "Entregue"].index(row['status']), key=f"s{row['id']}")
            c1,c2 = st.columns(2)
            if c1.button("Atualizar", key=f"up{row['id']}"):
                cur.execute("UPDATE servicos SET descricao=?, valor=?, status=? WHERE id=?", (n_desc, n_val, n_status, row['id']))
                conn.commit(); st.rerun()
            if c2.button("Deletar", key=f"del{row['id']}"):
                cur.execute("DELETE FROM servicos WHERE id=?", (row['id'],))
                conn.commit(); st.rerun()

else:
    st.subheader("Revisões próximos 7 dias")
    df = pd.read_sql_query("SELECT * FROM servicos", conn)
    if not df.empty:
        df['data_revisao'] = pd.to_datetime(df['data_revisao'], errors='coerce')
        hoje = date.today()
        limite = hoje + timedelta(days=7)
        alertas = df[(df['data_revisao'].dt.date >= hoje) & (df['data_revisao'].dt.date <= limite)]
        st.dataframe(alertas, use_container_width=True)
