import streamlit as st, pandas as pd, re
from urllib.parse import quote
from fpdf import FPDF
from datetime import date, timedelta

st.set_page_config(page_title="Oficina Caruaru", layout="wide")

URL = st.secrets["TURSO_URL"]
TOKEN = st.secrets["TURSO_TOKEN"]
conn = libsql.connect(database=URL, auth_token=TOKEN)
cur.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, data_revisao TEXT, status TEXT)")

def limpa(t):
    n=re.sub(r'\D','',str(t))
    return n[2:] if n.startswith('55') and len(n)>11 else n

def pdf_recibo(r):
    p=FPDF();p.add_page();p.set_fill_color(20,20,20);p.rect(0,0,210,32,'F')
    p.set_text_color(255,255,255);p.set_font("Arial","B",18);p.set_y(8);p.cell(0,10,"OFICINA CARUARU",align="C",ln=True)
    p.set_font("Arial","",9);p.cell(0,5,"Recibo de Servico",align="C",ln=True);p.ln(15);p.set_text_color(0,0,0)
    p.set_font("Arial","B",12);p.cell(0,9,f"Cliente: {r[1]}",ln=True);p.set_font("Arial","",11)
    p.cell(0,7,f"Tel: {r[2]} | Entrada: {r[5]} | Revisao: {r[6]}",ln=True);p.ln(4)
    p.set_font("Arial","B",11);p.cell(0,7,"Descricao:",ln=True);p.set_font("Arial","",11);p.multi_cell(0,7,r[3]);p.ln(6)
    p.set_font("Arial","B",14);p.set_fill_color(230,230,230);p.cell(0,12,f"Valor: R$ {float(r[4]):.2f} - {r[7]}",border=1,fill=True,align="C",ln=True)
    return p.output(dest='S').encode('latin1')

st.title("🏍️ Oficina Caruaru - Permanente")
menu=st.sidebar.selectbox("Menu",["Dashboard","Clientes","Servicos"])

if menu=="Dashboard":
    rows=cur.execute("SELECT * FROM servicos").fetchall()
    df=pd.DataFrame(rows,columns=["id","cliente","telefone","descricao","valor","data_entrada","data_revisao","status"]) if rows else pd.DataFrame()
    c1,c2,c3=st.columns(3)
    c1.metric("Faturamento Total",f"R$ {df['valor'].sum():.2f}" if not df.empty else "R$ 0,00")
    c2.metric("Ticket Medio",f"R$ {df['valor'].mean():.2f}" if not df.empty else "R$ 0,00")
    c3.metric("Total Servicos",len(df))
    if not df.empty:
        st.dataframe(df,use_container_width=True)
        st.bar_chart(df.groupby("status")["valor"].sum())
    else:
        st.info("Ainda sem servicos cadastrados")

elif menu=="Clientes":
    st.subheader("Novo Cliente")
    n=st.text_input("Nome"); t=st.text_input("WhatsApp"); m=st.text_input("Moto")
    if st.button("Salvar Cliente",type="primary"):
        cur.execute("INSERT INTO clientes (nome,telefone,moto) VALUES (?,?,?)",(n,limpa(t),m));conn.commit();st.success("Salvo!");st.rerun()
    rows=cur.execute("SELECT * FROM clientes ORDER BY id DESC").fetchall()
    df=pd.DataFrame(rows,columns=["id","nome","telefone","moto"]) if rows else pd.DataFrame()
    st.dataframe(df,use_container_width=True)
    if not df.empty:
        sel=st.selectbox("Selecione ID para editar/deletar",df['id'].tolist())
        r=df[df['id']==sel].iloc[0]
        en=st.text_input("Editar Nome",r['nome']); et=st.text_input("Editar Tel",r['telefone']); em=st.text_input("Editar Moto",r['moto'])
        c1,c2=st.columns(2)
        if c1.button("Atualizar Cliente"): cur.execute("UPDATE clientes SET nome=?, telefone=?, moto=? WHERE id=?",(en,limpa(et),em,sel));conn.commit();st.rerun()
        if c2.button("Deletar Cliente"): cur.execute("DELETE FROM clientes WHERE id=?",(sel,));conn.commit();st.rerun()

else:
    cli=cur.execute("SELECT nome,telefone FROM clientes").fetchall()
    df_cli=pd.DataFrame(cli,columns=["nome","telefone"]) if cli else pd.DataFrame()
    nome=st.selectbox("Cliente",[""]+(df_cli['nome'].tolist() if not df_cli.empty else []))
    tel=df_cli[df_cli['nome']==nome]['telefone'].values[0] if nome and not df_cli.empty and nome in df_cli['nome'].values else ""
    desc=st.text_area("O que foi feito?"); val=st.number_input("Valor R$",0.0,step=10.0); dt=st.date_input("Data Revisao",date.today()+timedelta(days=90)); status=st.selectbox("Status",["Em andamento","Pronto","Entregue"])
    if st.button("Salvar Servico",type="primary"):
        cur.execute("INSERT INTO servicos (cliente,telefone,descricao,valor,data_entrada,data_revisao,status) VALUES (?,?,?,?,?,?,?)",(nome,tel,desc,val,str(date.today()),str(dt),status));conn.commit();st.success("Servico salvo!");st.rerun()
    rows=cur.execute("SELECT * FROM servicos ORDER BY id DESC").fetchall()
    for r in rows:
        with st.expander(f"#{r[0]} {r[1]} - {r[7]} - R$ {float(r[4]):.2f}"):
            msg=f"Ola {r[1]}! Sua moto esta PRONTA! Servico: {r[3]} Valor: R$ {float(r[4]):.2f} Oficina Caruaru"
            st.link_button(f"📲 Enviar Zap para {r[1]}",f"https://wa.me/55{limpa(r[2])}?text={quote(msg)}",use_container_width=True)
            st.download_button("📄 Baixar Recibo PDF",pdf_recibo(r),f"recibo_{r[0]}.pdf",use_container_width=True,key=f"pdf{r[0]}")
            if st.button("🗑️ Deletar Servico",key=f"del{r[0]}"): cur.execute("DELETE FROM servicos WHERE id=?",(r[0],));conn.commit();st.rerun()
