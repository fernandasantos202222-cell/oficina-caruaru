import streamlit as st, pandas as pd, re, requests, io
from urllib.parse import quote
from fpdf import FPDF
from datetime import date

st.set_page_config(page_title="Oficina Caruaru - Relatorio", layout="wide")

# --- CONEXAO TURSO (não apaga mais) ---
URL = st.secrets["TURSO_URL"].replace("libsql://", "https://")
TOKEN = st.secrets["TURSO_TOKEN"]

def q(sql):
    try:
        r = requests.post(f"{URL}/v2/pipeline", headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}, json={"requests": [{"type": "execute", "stmt": {"sql": sql}}, {"type": "close"}]})
        j = r.json()
        rows = j["results"][0]["response"]["result"]["rows"]
        return [[c["value"] if "value" in c else list(c.values())[0] if isinstance(c, dict) else c for c in row] for row in rows]
    except: return []

def exec_sql(sql):
    try:
        requests.post(f"{URL}/v2/pipeline", headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}, json={"requests": [{"type": "execute", "stmt": {"sql": sql}}, {"type": "close"}]})
    except: pass

# cria tabelas
for s in [
    "CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT)",
    "CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, status TEXT)"
]: exec_sql(s)

def limpa(t):
    n=re.sub(r'\D','',str(t)); return n[2:] if n.startswith('55') and len(n)>11 else n

def pdf_relatorio(df, periodo="Geral"):
    p=FPDF(); p.add_page()
    p.set_fill_color(20,20,20); p.rect(0,0,210,30,'F')
    p.set_text_color(255,255,255); p.set_font("Arial","B",18); p.set_y(8); p.cell(0,10,"OFICINA CARUARU",align="C",ln=True)
    p.set_font("Arial","",10); p.cell(0,5,f"RELATORIO DE SERVICOS - {periodo}",align="C",ln=True)
    p.ln(20); p.set_text_color(0,0,0)
    p.set_font("Arial","B",10); p.cell(0,7,f"Gerado em: {date.today()} | Total: {len(df)} servicos",ln=True)
    p.set_font("Arial","B",9); p.set_fill_color(240,240,240)
    # cabecalho tabela
    p.cell(10,7,"ID",1,0,'C',True); p.cell(45,7,"CLIENTE",1,0,'C',True); p.cell(70,7,"SERVICO",1,0,'C',True); p.cell(25,7,"VALOR",1,0,'C',True); p.cell(40,7,"STATUS",1,1,'C',True)
    p.set_font("Arial","",8)
    for _, r in df.iterrows():
        p.cell(10,7,str(r['id']),1); p.cell(45,7,str(r['cliente'])[:22],1); p.cell(70,7,str(r['descricao'])[:35],1); p.cell(25,7,f"R$ {float(r['valor']):.2f}",1); p.cell(40,7,str(r['status']),1,1)
    p.ln(5); p.set_font("Arial","B",12); p.cell(0,10,f"FATURAMENTO TOTAL: R$ {df['valor'].sum():.2f}",ln=True)
    p.cell(0,7,f"TICKET MEDIO: R$ {df['valor'].mean():.2f} | TOTAL SERVICOS: {len(df)}",ln=True)
    return p.output(dest='S').encode('latin1')

st.title("🏍️ Oficina Caruaru")
menu=st.sidebar.selectbox("Menu",["Dashboard / Relatorio","Clientes","Novo Servico"])

if menu=="Dashboard / Relatorio":
    st.subheader("📊 Relatorio Geral")
    rows=q("SELECT * FROM servicos ORDER BY id DESC")
    df=pd.DataFrame(rows,columns=["id","cliente","telefone","descricao","valor","data_entrada","status"]) if rows else pd.DataFrame()
    if df.empty:
        st.info("Nenhum servico ainda.")
    else:
        c1,c2,c3=st.columns(3)
        c1.metric("Faturamento Total",f"R$ {df['valor'].sum():.2f}")
        c2.metric("Ticket Medio",f"R$ {df['valor'].mean():.2f}")
        c3.metric("Qtd Servicos",len(df))

        # filtros do relatorio
        colf1,colf2=st.columns(2)
        f_cliente=colf1.selectbox("Filtrar por cliente",["Todos"]+df['cliente'].unique().tolist())
        f_status=colf2.selectbox("Filtrar por status",["Todos","Em andamento","Pronto","Entregue"])
        df_f=df.copy()
        if f_cliente!="Todos": df_f=df_f[df_f['cliente']==f_cliente]
        if f_status!="Todos": df_f=df_f[df_f['status']==f_status]

        st.dataframe(df_f,use_container_width=True)

        # downloads
        b1,b2=st.columns(2)
        buf=io.BytesIO(); df_f.to_excel(buf,index=False)
        b1.download_button("📥 Baixar Excel (Relatorio)",buf.getvalue(),f"relatorio_oficina_{date.today()}.xlsx",use_container_width=True)
        b2.download_button("📄 Baixar PDF (Relatorio)",pdf_relatorio(df_f, f"{f_cliente} - {f_status}"),f"relatorio_oficina_{date.today()}.pdf",use_container_width=True)

        st.divider()
        st.subheader("Servicos - Acoes Rapidas")
        for r in q("SELECT * FROM servicos ORDER BY id DESC")[:20]:
            with st.expander(f"#{r[0]} {r[1]} - {r[6]} - R$ {float(r[4]):.2f}"):
                msg=f"Ola {r[1]}! Aqui e da Oficina Caruaru. Seu servico: {r[3]} ficou R$ {float(r[4]):.2f} - Status: {r[6]}. Obrigado!"
                st.link_button(f"📲 WhatsApp {r[1]}",f"https://wa.me/55{limpa(r[2])}?text={quote(msg)}",use_container_width=True)
                if st.button("🗑️ Deletar",key=f"del{r[0]}"): exec_sql(f"DELETE FROM servicos WHERE id={r[0]}"); st.rerun()

elif menu=="Clientes":
    st.subheader("Clientes")
    n=st.text_input("Nome"); t=st.text_input("WhatsApp"); m=st.text_input("Moto / Modelo")
    if st.button("Salvar Cliente",type="primary"):
        exec_sql(f"INSERT INTO clientes (nome,telefone,moto) VALUES ('{n}','{limpa(t)}','{m}')"); st.success("Salvo!"); st.rerun()
    rows=q("SELECT * FROM clientes ORDER BY id DESC")
    df=pd.DataFrame(rows,columns=["id","nome","telefone","moto"]) if rows else pd.DataFrame()
    st.dataframe(df,use_container_width=True)
    if not df.empty:
        buf=io.BytesIO(); df.to_excel(buf,index=False)
        st.download_button("📥 Baixar Excel Clientes",buf.getvalue(),"clientes.xlsx")

else: # Novo Servico
    st.subheader("Novo Servico (sem data de revisao)")
    cli=q("SELECT nome,telefone FROM clientes")
    df_cli=pd.DataFrame(cli,columns=["nome","telefone"]) if cli else pd.DataFrame()
    nome=st.selectbox("Cliente",df_cli['nome'].tolist() if not df_cli.empty else [])
    tel=df_cli[df_cli['nome']==nome]['telefone'].values[0] if not df_cli.empty and nome else ""
    desc=st.text_area("Descricao do Servico / Relatorio"); val=st.number_input("Valor R$",0.0,step=10.0); status=st.selectbox("Status",["Em andamento","Pronto","Entregue"])
    if st.button("Salvar Servico",type="primary"):
        exec_sql(f"INSERT INTO servicos (cliente,telefone,descricao,valor,data_entrada,status) VALUES ('{nome}','{tel}','{desc}',{val},'{str(date.today())}','{status}')")
        st.success("Servico salvo no relatorio!"); st.rerun()
