import streamlit as st, pandas as pd, re, io, sqlite3
from urllib.parse import quote
from fpdf import FPDF
from datetime import date

st.set_page_config(page_title="Oficina Caruaru", layout="wide")
conn = sqlite3.connect("oficina.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT)")
cur.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, status TEXT)")
conn.commit()

def limpa(t):
    n=re.sub(r'\D','',str(t)); return n[2:] if n.startswith('55') and len(n)>11 else n

def pdf_relatorio(df):
    p=FPDF(); p.add_page(); p.set_fill_color(20,20,20); p.rect(0,0,210,30,'F')
    p.set_text_color(255,255,255); p.set_font("Arial","B",16); p.set_y(8); p.cell(0,10,"RELATORIO OFICINA CARUARU",align="C",ln=True)
    p.ln(18); p.set_text_color(0,0,0); p.set_font("Arial","B",11)
    p.cell(0,8,f"Data: {date.today()} | Fat: R$ {df['valor'].sum():.2f} | Ticket: R$ {df['valor'].mean():.2f}",ln=True)
    p.set_font("Arial","B",8); p.set_fill_color(230,230,230)
    p.cell(10,7,"ID",1,0,'C',True); p.cell(35,7,"CLIENTE",1,0,'C',True); p.cell(80,7,"DESCRICAO",1,0,'C',True); p.cell(20,7,"VALOR",1,0,'C',True); p.cell(30,7,"STATUS",1,1,'C',True)
    p.set_font("Arial","",7)
    for _,row in df.iterrows():
        p.cell(10,6,str(row['id']),1); p.cell(35,6,str(row['cliente'])[:18],1); p.cell(80,6,str(row['descricao'])[:42],1); p.cell(20,6,f"{float(row['valor']):.2f}",1); p.cell(30,6,str(row['status']),1,1)
    # CORRECAO FPDF2 NOVO
    return bytes(p.output())

st.title("🏍️ Oficina Caruaru")
menu=st.sidebar.selectbox("Menu",["Dashboard / Relatorio","Clientes","Novo Servico"])

if menu=="Dashboard / Relatorio":
    rows=cur.execute("SELECT * FROM servicos ORDER BY id DESC").fetchall()
    df=pd.DataFrame(rows,columns=["id","cliente","telefone","descricao","valor","data_entrada","status"]) if rows else pd.DataFrame()
    if df.empty:
        st.info("Nenhum servico ainda")
    else:
        c1,c2,c3=st.columns(3)
        c1.metric("💰 Faturamento",f"R$ {df['valor'].sum():.2f}")
        c2.metric("🎫 Ticket Medio",f"R$ {df['valor'].mean():.2f}")
        c3.metric("🔧 Qtd Servicos",len(df))
        st.dataframe(df,use_container_width=True)

        # EXCEL CORRIGIDO
        buf=io.BytesIO()
        df.to_excel(buf,index=False)
        buf.seek(0)

        b1,b2=st.columns(2)
        b1.download_button("📥 Baixar Excel Relatorio",buf.getvalue(),f"relatorio_{date.today()}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
        b2.download_button("📄 Baixar PDF Relatorio",pdf_relatorio(df),f"relatorio_{date.today()}.pdf",mime="application/pdf",use_container_width=True)

        st.divider()
        st.subheader("Histórico - Editar, Deletar e WhatsApp")
        for r in rows:
            with st.expander(f"#{r[0]} {r[1]} - {r[6]} - R$ {float(r[4]):.2f}"):
                msg=f"Ola {r[1]}! Oficina Caruaru: {r[3]} Valor R$ {float(r[4]):.2f} Status {r[6]}"
                st.link_button(f"📲 WhatsApp {r[1]}",f"https://wa.me/55{limpa(r[2])}?text={quote(msg)}",use_container_width=True)
                col1,col2=st.columns(2)
                if col1.button("🗑️ Deletar",key=f"del{r[0]}"):
                    cur.execute("DELETE FROM servicos WHERE id=?",(r[0],)); conn.commit(); st.rerun()
                if col2.button("✏️ Marcar Pronto",key=f"pr{r[0]}"):
                    cur.execute("UPDATE servicos SET status='Pronto' WHERE id=?",(r[0],)); conn.commit(); st.rerun()

elif menu=="Clientes":
    n=st.text_input("Nome"); t=st.text_input("WhatsApp"); m=st.text_input("Moto")
    if st.button("Salvar Cliente",type="primary"):
        cur.execute("INSERT INTO clientes (nome,telefone,moto) VALUES (?,?,?)",(n,limpa(t),m)); conn.commit(); st.success("Salvo!"); st.rerun()
    rows=cur.execute("SELECT * FROM clientes ORDER BY id DESC").fetchall()
    df=pd.DataFrame(rows,columns=["id","nome","telefone","moto"]) if rows else pd.DataFrame()
    st.dataframe(df,use_container_width=True)
    if not df.empty:
        buf=io.BytesIO(); df.to_excel(buf,index=False); buf.seek(0)
        st.download_button("📥 Baixar Excel Clientes",buf.getvalue(),"clientes.xlsx")
        sel=st.selectbox("ID para editar/deletar",df['id'].tolist())
        d=cur.execute("SELECT * FROM clientes WHERE id=?",(sel,)).fetchone()
        en=st.text_input("Editar Nome",d[1]); et=st.text_input("Editar WhatsApp",d[2]); em=st.text_input("Editar Moto",d[3])
        c1,c2=st.columns(2)
        if c1.button("✏️ Atualizar"): cur.execute("UPDATE clientes SET nome=?,telefone=?,moto=? WHERE id=?",(en,limpa(et),em,sel)); conn.commit(); st.rerun()
        if c2.button("🗑️ Deletar Cliente"): cur.execute("DELETE FROM clientes WHERE id=?",(sel,)); conn.commit(); st.rerun()
else:
    cli=cur.execute("SELECT nome,telefone FROM clientes").fetchall()
    df_cli=pd.DataFrame(cli,columns=["nome","telefone"]) if cli else pd.DataFrame()
    nome=st.selectbox("Cliente",df_cli['nome'].tolist() if not df_cli.empty else ["Cadastre cliente primeiro"])
    tel=df_cli[df_cli['nome']==nome]['telefone'].values[0] if not df_cli.empty and nome!="Cadastre cliente primeiro" else ""
    desc=st.text_area("Descricao / Relatorio"); val=st.number_input("Valor",0.0,step=10.0); status=st.selectbox("Status",["Em andamento","Pronto","Entregue"])
    if st.button("Salvar Servico",type="primary"):
        cur.execute("INSERT INTO servicos (cliente,telefone,descricao,valor,data_entrada,status) VALUES (?,?,?,?,?,?)",(nome,tel,desc,val,str(date.today()),status)); conn.commit(); st.success("Salvo!"); st.rerun()
