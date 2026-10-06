import streamlit as st, pandas as pd, re, io
from urllib.parse import quote
from fpdf import FPDF
from datetime import date
import libsql_experimental as libsql

st.set_page_config(page_title="Oficina Caruaru", layout="wide")

URL = st.secrets["TURSO_URL"]
TOKEN = st.secrets["TURSO_TOKEN"]
conn = libsql.connect(database=URL, auth_token=TOKEN)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, status TEXT)")

def limpa(t):
    n=re.sub(r'\D','',str(t))
    return n[2:] if n.startswith('55') and len(n)>11 else n

def pdf_recibo(r):
    p=FPDF();p.add_page();p.set_fill_color(20,20,20);p.rect(0,0,210,30,'F')
    p.set_text_color(255,255,255);p.set_font("Arial","B",18);p.set_y(8);p.cell(0,10,"OFICINA CARUARU",align="C",ln=True)
    p.ln(15);p.set_text_color(0,0,0);p.set_font("Arial","B",12);p.cell(0,9,f"Cliente: {r[1]}",ln=True)
    p.set_font("Arial","",11);p.cell(0,7,f"Tel: {r[2]} | Data: {r[5]}",ln=True);p.ln(4)
    p.set_font("Arial","B",11);p.cell(0,7,"Descricao do Servico / Relatorio:",ln=True)
    p.set_font("Arial","",11);p.multi_cell(0,7,r[3]);p.ln(6)
    p.set_font("Arial","B",14);p.cell(0,12,f"Valor: R$ {float(r[4]):.2f} - {r[6]}",border=1,align="C",ln=True)
    return p.output(dest='S').encode('latin1')

def pdf_relatorio(df):
    p=FPDF();p.add_page();p.set_fill_color(20,20,20);p.rect(0,0,210,30,'F')
    p.set_text_color(255,255,255);p.set_font("Arial","B",16);p.set_y(8);p.cell(0,10,"RELATORIO - OFICINA CARUARU",align="C",ln=True)
    p.ln(18);p.set_text_color(0,0,0);p.set_font("Arial","B",11)
    p.cell(0,8,f"Data: {date.today()} | Faturamento: R$ {df['valor'].sum():.2f} | Ticket Medio: R$ {df['valor'].mean():.2f}",ln=True);p.ln(2)
    p.set_font("Arial","B",8);p.set_fill_color(230,230,230)
    p.cell(10,7,"ID",1,0,'C',True);p.cell(35,7,"CLIENTE",1,0,'C',True);p.cell(80,7,"DESCRICAO",1,0,'C',True);p.cell(20,7,"VALOR",1,0,'C',True);p.cell(30,7,"STATUS",1,1,'C',True)
    p.set_font("Arial","",7)
    for _,row in df.iterrows():
        p.cell(10,6,str(row['id']),1);p.cell(35,6,str(row['cliente'])[:18],1);p.cell(80,6,str(row['descricao'])[:45],1);p.cell(20,6,f"{float(row['valor']):.2f}",1);p.cell(30,6,str(row['status']),1,1)
    return p.output(dest='S').encode('latin1')

st.title("🏍️ Oficina Caruaru - Permanente")
menu=st.sidebar.selectbox("Menu",["Dashboard / Relatorio","Clientes","Novo Servico"])

# DASHBOARD
if menu=="Dashboard / Relatorio":
    rows=cur.execute("SELECT * FROM servicos ORDER BY id DESC").fetchall()
    df=pd.DataFrame(rows,columns=["id","cliente","telefone","descricao","valor","data_entrada","status"]) if rows else pd.DataFrame()
    if df.empty:
        st.info("Nenhum servico cadastrado ainda.")
    else:
        c1,c2,c3=st.columns(3)
        c1.metric("💰 Faturamento Total",f"R$ {df['valor'].sum():.2f}")
        c2.metric("🎫 Ticket Medio",f"R$ {df['valor'].mean():.2f}")
        c3.metric("🔧 Qtd Servicos",len(df))

        st.dataframe(df,use_container_width=True)

        # Botoes Excel e PDF do Relatorio
        b1,b2=st.columns(2)
        buf=io.BytesIO(); df.to_excel(buf,index=False)
        b1.download_button("📥 Baixar Excel (Relatorio Completo)",buf.getvalue(),f"relatorio_oficina_{date.today()}.xlsx",use_container_width=True)
        b2.download_button("📄 Baixar PDF (Relatorio Completo)",pdf_relatorio(df),f"relatorio_oficina_{date.today()}.pdf",use_container_width=True)

        st.divider()
        st.subheader("Acoes Rapidas")
        for r in rows:
            with st.expander(f"#{r[0]} {r[1]} - {r[6]} - R$ {float(r[4]):.2f}"):
                msg=f"Ola {r[1]}! Oficina Caruaru: Servico '{r[3]}' Status: {r[6]} Valor: R$ {float(r[4]):.2f}"
                st.link_button(f"📲 Enviar WhatsApp para {r[1]}",f"https://wa.me/55{limpa(r[2])}?text={quote(msg)}",use_container_width=True)
                st.download_button("📄 Baixar Recibo",pdf_recibo(r),f"recibo_{r[0]}.pdf",use_container_width=True,key=f"pdf{r[0]}")
                if st.button("🗑️ Deletar Servico",key=f"del{r[0]}"):
                    cur.execute("DELETE FROM servicos WHERE id=?",(r[0],)); conn.commit(); st.rerun()

# CLIENTES
elif menu=="Clientes":
    st.subheader("Clientes")
    n=st.text_input("Nome"); t=st.text_input("WhatsApp"); m=st.text_input("Moto")
    if st.button("Salvar Cliente",type="primary"):
        cur.execute("INSERT INTO clientes (nome,telefone,moto) VALUES (?,?,?)",(n,limpa(t),m)); conn.commit(); st.success("Salvo!"); st.rerun()

    rows=cur.execute("SELECT * FROM clientes ORDER BY id DESC").fetchall()
    df=pd.DataFrame(rows,columns=["id","nome","telefone","moto"]) if rows else pd.DataFrame()
    st.dataframe(df,use_container_width=True)

    if not df.empty:
        buf=io.BytesIO(); df.to_excel(buf,index=False)
        st.download_button("📥 Baixar Excel Clientes",buf.getvalue(),"clientes.xlsx")
        st.divider()
        sel=st.selectbox("Selecione ID para EDITAR ou DELETAR",df['id'].tolist())
        dados=cur.execute("SELECT * FROM clientes WHERE id=?",(sel,)).fetchone()
        en=st.text_input("Editar Nome",dados[1]); et=st.text_input("Editar WhatsApp",dados[2]); em=st.text_input("Editar Moto",dados[3])
        c1,c2=st.columns(2)
        if c1.button("✏️ Atualizar Cliente"):
            cur.execute("UPDATE clientes SET nome=?, telefone=?, moto=? WHERE id=?",(en,limpa(et),em,sel)); conn.commit(); st.success("Atualizado!"); st.rerun()
        if c2.button("🗑️ Deletar Cliente"):
            cur.execute("DELETE FROM clientes WHERE id=?",(sel,)); conn.commit(); st.success("Deletado!"); st.rerun()

# NOVO SERVICO
else:
    st.subheader("Novo Servico - Estilo Relatorio (sem data de revisao)")
    cli=cur.execute("SELECT nome,telefone FROM clientes").fetchall()
    df_cli=pd.DataFrame(cli,columns=["nome","telefone"]) if cli else pd.DataFrame()
    nome=st.selectbox("Cliente",df_cli['nome'].tolist() if not df_cli.empty else ["Cadastre um cliente primeiro"])
    tel=df_cli[df_cli['nome']==nome]['telefone'].values[0] if not df_cli.empty else ""
    desc=st.text_area("Descricao / Relatorio do que foi feito"); val=st.number_input("Valor R$",0.0,step=10.0); status=st.selectbox("Status",["Em andamento","Pronto","Entregue"])
    if st.button("Salvar Servico",type="primary"):
        if nome and desc:
            cur.execute("INSERT INTO servicos (cliente,telefone,descricao,valor,data_entrada,status) VALUES (?,?,?,?,?,?)",(nome,tel,desc,val,str(date.today()),status))
            conn.commit(); st.success("Servico salvo! Vai aparecer no Relatorio!"); st.rerun()
        else:
            st.error("Preencha cliente e descricao")
