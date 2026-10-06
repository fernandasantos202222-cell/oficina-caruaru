import streamlit as st, pandas as pd, re, requests, json
from urllib.parse import quote
from fpdf import FPDF
from datetime import date, timedelta

st.set_page_config(page_title="Oficina Caruaru", layout="wide")

URL = st.secrets["TURSO_URL"].replace("libsql://", "https://")
TOKEN = st.secrets["TURSO_TOKEN"]

def turso(sql, params=[]):
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    payload = {"statements": [f"{sql}"]}
    # converte? para execução
    # execução simples via hrana
    r = requests.post(f"{URL}/v2/pipeline", headers=headers, json={"requests": [{"type": "execute", "stmt": {"sql": sql, "args": [{"type": "text", "value": str(p)} if not isinstance(p, (int,float)) else {"type": "float" if isinstance(p,float) else "integer", "value": p} for p in params]}}, {"type": "close"}]})
    if r.status_code!= 200:
        # fallback cria tabela se não existir
        return []
    try:
        data = r.json()
        res = data["results"][0]["response"]["result"]
        if "rows" in res: return res["rows"]
        return []
    except: return []

def exec_turso(sql, params=[]):
    headers = {"Authorization": f"Bearer {TOKEN}"}
    # usa libsql via requests simples
    import urllib.request
    try:
        # método mais simples
        turso(sql, params)
    except: pass

# Inicializa
try:
    # cria tabelas usando fetch direto
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    for s in [
        "CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT)",
        "CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, data_revisao TEXT, status TEXT)"
    ]:
        requests.post(f"{URL}/v2/pipeline", headers=headers, json={"requests": [{"type": "execute", "stmt": {"sql": s}}, {"type": "close"}]})
except: pass

def q(sql):
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        r = requests.post(f"{URL}/v2/pipeline", headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}, json={"requests": [{"type": "execute", "stmt": {"sql": sql}}, {"type": "close"}]})
        j = r.json()
        rows = j["results"][0]["response"]["result"]["rows"]
        return [[c["value"] if "value" in c else list(c.values())[0] for c in row] for row in rows]
    except: return []

def exec_sql(sql, params=()):
    # formata params direto na query pra evitar lib
    for p in params:
        v = f"'{p}'" if isinstance(p, str) else str(p)
        sql = sql.replace("?", v, 1)
    q(sql)

def limpa(t):
    n=re.sub(r'\D','',str(t)); return n[2:] if n.startswith('55') and len(n)>11 else n

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
    rows=q("SELECT * FROM servicos")
    df=pd.DataFrame(rows,columns=["id","cliente","telefone","descricao","valor","data_entrada","data_revisao","status"]) if rows else pd.DataFrame()
    c1,c2,c3=st.columns(3)
    c1.metric("Faturamento Total",f"R$ {df['valor'].sum():.2f}" if not df.empty else "R$ 0,00")
    c2.metric("Ticket Medio",f"R$ {df['valor'].mean():.2f}" if not df.empty else "R$ 0,00")
    c3.metric("Total Servicos",len(df))
    if not df.empty:
        st.dataframe(df,use_container_width=True)
        st.bar_chart(df.groupby("status")["valor"].sum())
    else:
        st.info("Sem servicos ainda - mas agora nao apaga mais!")

elif menu=="Clientes":
    st.subheader("Novo Cliente")
    n=st.text_input("Nome"); t=st.text_input("WhatsApp"); m=st.text_input("Moto")
    if st.button("Salvar Cliente",type="primary"):
        exec_sql("INSERT INTO clientes (nome,telefone,moto) VALUES (?,?,?)",(n,limpa(t),m));st.success("Salvo!");st.rerun()
    df=pd.DataFrame(q("SELECT * FROM clientes ORDER BY id DESC"),columns=["id","nome","telefone","moto"]) if q("SELECT * FROM clientes") else pd.DataFrame()
    st.dataframe(df,use_container_width=True)

else:
    cli=q("SELECT nome,telefone FROM clientes")
    df_cli=pd.DataFrame(cli,columns=["nome","telefone"]) if cli else pd.DataFrame()
    nome=st.selectbox("Cliente",[""]+(df_cli['nome'].tolist() if not df_cli.empty else []))
    tel=df_cli[df_cli['nome']==nome]['telefone'].values[0] if nome and not df_cli.empty and nome in df_cli['nome'].values else ""
    desc=st.text_area("O que foi feito?"); val=st.number_input("Valor R$",0.0,step=10.0); dt=st.date_input("Data Revisao",date.today()+timedelta(days=90)); status=st.selectbox("Status",["Em andamento","Pronto","Entregue"])
    if st.button("Salvar Servico",type="primary"):
        exec_sql("INSERT INTO servicos (cliente,telefone,descricao,valor,data_entrada,data_revisao,status) VALUES (?,?,?,?,?,?,?)",(nome,tel,desc,val,str(date.today()),str(dt),status));st.success("Servico salvo!");st.rerun()
    rows=q("SELECT * FROM servicos ORDER BY id DESC")
    for r in rows:
        with st.expander(f"#{r[0]} {r[1]} - {r[7]} - R$ {float(r[4]):.2f}"):
            msg=f"Ola {r[1]}! Sua moto esta PRONTA! Servico: {r[3]} Valor: R$ {float(r[4]):.2f} Oficina Caruaru"
            st.link_button(f"📲 Enviar Zap para {r[1]}",f"https://wa.me/55{limpa(r[2])}?text={quote(msg)}",use_container_width=True)
            st.download_button("📄 Baixar Recibo PDF",pdf_recibo(r),f"recibo_{r[0]}.pdf",use_container_width=True,key=f"pdf{r[0]}")
            if st.button("🗑️ Deletar Servico",key=f"del{r[0]}"): exec_sql(f"DELETE FROM servicos WHERE id={r[0]}");st.rerun()
