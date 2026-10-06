import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io
from fpdf import FPDF

# ============ CONEXÃO TURSO ============
try:
    import libsql
    URL = str(st.secrets["TURSO_URL"]).strip().replace("\n","").replace("\r","").replace(" ","")
    RAW = str(st.secrets["TURSO_TOKEN"])
    TOKEN = "".join(RAW.split()).strip('"').strip("'")
    @st.cache_resource
    def get_conn():
        c = libsql.connect(database=URL, auth_token=TOKEN)
        c.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT, placa TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, status TEXT, placa TEXT)")
        try: c.execute("ALTER TABLE clientes ADD COLUMN placa TEXT")
        except: pass
        try: c.execute("ALTER TABLE servicos ADD COLUMN placa TEXT")
        except: pass
        c.commit()
        return c
    conn = get_conn()
    st.toast("✅ Turso Conectado", icon="✅")
except Exception as e:
    st.warning(f"⚠️ Temporário: {e}")
    import sqlite3
    conn = sqlite3.connect("oficina.db", check_same_thread=False)
    cur0 = conn.cursor()
    cur0.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT, placa TEXT)")
    cur0.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, status TEXT, placa TEXT)")
    try: cur0.execute("ALTER TABLE clientes ADD COLUMN placa TEXT")
    except: pass
    try: cur0.execute("ALTER TABLE servicos ADD COLUMN placa TEXT")
    except: pass
    conn.commit()

cur = conn.cursor()
def query_df(sql, params=()):
    try:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        return pd.DataFrame(cur.fetchall(), columns=cols)
    except:
        return pd.DataFrame()

# ============ PDF OS CLIENTE ============
def gerar_pdf_os(os_id, cliente, zap, placa, servico, valor, data_e, status):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "OFICINA CARUARU - ORDEM DE SERVICO", ln=True, align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)
    pdf.cell(0, 8, f"OS Nº: {os_id} | Data: {data_e} | Status: {status}", ln=True)
    pdf.cell(0, 8, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 8, f"WhatsApp: {zap} | Placa: {placa}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Descricao do Servico:", ln=True)
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 8, servico)
    pdf.ln(5)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"Valor: R$ {float(valor):.2f}", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, "Assinatura Cliente: ___________________________", ln=True)
    return pdf.output(dest='S').encode('latin-1')

st.set_page_config(page_title="Oficina Caruaru", layout="wide")
st.title("🏍️ Oficina Caruaru - OS")
if "edit_id" not in st.session_state: st.session_state.edit_id = None
menu = st.sidebar.radio("Menu", ["Dashboard", "Nova OS", "Pesquisar / Filtrar", "Clientes", "Backup"])

# ============ AÇÕES COM WHATSAPP E PDF ============
def acoes_completas(df_origem):
    st.divider()
    st.subheader("✏️ Ações - Editar / Deletar / WhatsApp / PDF")
    if df_origem.empty: return
    os_sel = st.selectbox("Selecione a OS", df_origem['OS'].tolist(), key=f"sel_{menu}")
    dados = query_df("SELECT * FROM servicos WHERE id=?", (int(os_sel),))
    if dados.empty: return
    d = dados.iloc[0]

    # WHATSAPP LINK
    zap_limpo = ''.join(filter(str.isdigit, str(d['telefone'])))
    msg = f"Ola {d['cliente']}! Sua OS #{d['id']} - Moto {d['placa']} - Status: {d['status']} - Valor: R$ {float(d['valor'] or 0):.2f}. Oficina Caruaru"
    link_zap = f"https://wa.me/55{zap_limpo}?text={msg.replace(' ', '%20')}"

    c1,c2,c3,c4 = st.columns(4)
    c1.link_button(f"📱 WhatsApp #{os_sel}", link_zap, use_container_width=True)

    # PDF
    pdf_bytes = gerar_pdf_os(d['id'], d['cliente'], d['telefone'], d['placa'], d['descricao'], d['valor'], d['data_entrada'], d['status'])
    c2.download_button(f"📄 PDF OS #{os_sel}", pdf_bytes, file_name=f"OS_{os_sel}_{d['cliente']}.pdf", mime="application/pdf", use_container_width=True)

    if c3.button(f"✏️ Editar #{os_sel}", use_container_width=True):
        st.session_state.edit_id = int(os_sel)
    if c4.button(f"🗑️ Deletar #{os_sel}", type="primary", use_container_width=True):
        cur.execute("DELETE FROM servicos WHERE id=?", (int(os_sel),))
        conn.commit()
        st.success("Deletada!"); st.rerun()

    if st.session_state.edit_id == int(os_sel):
        with st.form(f"edit_{os_sel}"):
            c1,c2 = st.columns(2)
            nome = c1.text_input("Cliente", value=d['cliente'])
            zap = c2.text_input("WhatsApp", value=d['telefone'])
            c3,c4 = st.columns(2)
            placa = c3.text_input("Placa", value=str(d['placa'] or ""))
            valor = c4.number_input("Valor", value=float(d['valor'] or 0))
            desc = st.text_area("Serviço", value=d['descricao'])
            c5,c6 = st.columns(2)
            data_e = c5.text_input("Data", value=d['data_entrada'])
            status = c6.selectbox("Status", ["Aberta","Em andamento","Pronta","Entregue","Cancelada"])
            if st.form_submit_button("💾 SALVAR"):
                cur.execute("UPDATE servicos SET cliente=?, telefone=?, descricao=?, valor=?, data_entrada=?, status=?, placa=? WHERE id=?",(nome, zap, desc, valor, data_e, status, placa, int(os_sel)))
                conn.commit()
                st.session_state.edit_id=None
                st.success("Atualizado!"); st.rerun()

# ============ DASHBOARD COM FATURAMENTO E TICKET ============
if menu == "Dashboard":
    df = query_df("SELECT id as OS, data_entrada as Data, cliente as Cliente, telefone as WhatsApp, placa as Placa, descricao as Servico, valor as Valor, status as Status FROM servicos")
    if df.empty:
        st.info("Nenhum serviço ainda.")
    else:
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
        c1,c2,c3 = st.columns(3)
        c1.metric("💰 Faturamento Total", f"R$ {df['Valor'].sum():.2f}")
        c2.metric("🎫 Ticket Médio", f"R$ {df['Valor'].mean():.2f}")
        c3.metric("🔧 Qtd Serviços", len(df))
        st.dataframe(df.sort_values('OS', ascending=False), use_container_width=True)
        acoes_completas(df)

elif menu == "Nova OS":
    with st.form("os"):
        c1,c2 = st.columns(2)
        nome = c1.text_input("Cliente*")
        zap = c2.text_input("WhatsApp* (só números)")
        c3,c4 = st.columns(2)
        moto = c3.text_input("Moto")
        placa = c4.text_input("Placa")
        desc = st.text_area("Serviço*")
        c5,c6,c7 = st.columns(3)
        valor = c5.number_input("Valor R$", min_value=0.0, step=10.0)
        data_os = c6.date_input("Data", value=date.today())
        status = c7.selectbox("Status", ["Aberta","Em andamento","Pronta","Entregue","Cancelada"])
        if st.form_submit_button("💾 Salvar OS"):
            cur.execute("INSERT INTO servicos (cliente, telefone, descricao, valor, data_entrada, status, placa) VALUES (?,?,?,?,?,?,?)",(nome, zap, desc, valor, str(data_os), status, placa))
            cur.execute("INSERT INTO clientes (nome, telefone, moto, placa) VALUES (?,?,?,?)",(nome, zap, moto, placa))
            conn.commit()
            new_id = cur.lastrowid
            st.success(f"OS #{new_id} criada!")
            # Já gera whatsapp e pdf na hora
            zap_limpo = ''.join(filter(str.isdigit, zap))
            msg = f"Ola {nome}! Sua OS #{new_id} foi aberta - Moto {placa} - Valor R$ {valor:.2f}. Oficina Caruaru"
            link_zap = f"https://wa.me/55{zap_limpo}?text={msg.replace(' ', '%20')}"
            st.link_button("📱 Enviar WhatsApp pro Cliente", link_zap)
            pdf_bytes = gerar_pdf_os(new_id, nome, zap, placa, desc, valor, str(data_os), status)
            st.download_button("📄 Baixar PDF da OS pro Cliente", pdf_bytes, file_name=f"OS_{new_id}.pdf", mime="application/pdf")

elif menu == "Pesquisar / Filtrar":
    df = query_df("SELECT id as OS, data_entrada as Data, cliente as Cliente, telefone as WhatsApp, placa as Placa, descricao as Servico, valor as Valor, status as Status FROM servicos")
    if df.empty:
        st.info("Sem OS")
    else:
        c1,c2,c3,c4 = st.columns(4)
        periodo = c1.date_input("Período", value=(date.today()-timedelta(days=30), date.today()))
        f_cli = c2.text_input("Cliente")
        f_placa = c3.text_input("Placa")
        f_st = c4.multiselect("Status", ["Aberta","Em andamento","Pronta","Entregue","Cancelada"])
        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        if len(periodo)==2:
            df = df[(df['Data'].dt.date >= periodo[0]) & (df['Data'].dt.date <= periodo[1])]
        if f_cli: df = df[df['Cliente'].str.contains(f_cli, case=False, na=False)]
        if f_placa: df = df[df['Placa'].astype(str).str.contains(f_placa, case=False, na=False)]
        if f_st: df = df[df['Status'].isin(f_st)]
        st.dataframe(df.sort_values('OS', ascending=False), use_container_width=True)
        st.caption(f"{len(df)} OS | Faturamento filtrado: R$ {df['Valor'].sum():.2f} | Ticket Médio filtrado: R$ {df['Valor'].mean():.2f}")
        buf = io.BytesIO(); df.to_excel(buf, index=False)
        st.download_button("📥 Excel Filtrado", buf.getvalue(), "os_filtradas.xlsx")
        acoes_completas(df)

elif menu == "Clientes":
    df_serv = query_df("SELECT cliente as Cliente, telefone as WhatsApp, SUM(valor) as total_gasto, COUNT(*) as qtd, AVG(valor) as ticket_medio FROM servicos GROUP BY cliente, telefone")
    if not df_serv.empty:
        st.subheader("Clientes com Valores (Total Gasto + Ticket Médio)")
        st.dataframe(df_serv.sort_values('total_gasto', ascending=False), use_container_width=True)
        buf = io.BytesIO(); df_serv.to_excel(buf, index=False)
        st.download_button("📥 Excel CLIENTES com Valores", buf.getvalue(), "clientes_com_valores.xlsx")
    df_s = query_df("SELECT * FROM servicos")
    if not df_s.empty:
        buf2 = io.BytesIO(); df_s.to_excel(buf2, index=False)
        st.download_button("📥 Excel SERVIÇOS Feitos", buf2.getvalue(), "servicos.xlsx")

elif menu == "Backup":
    df1 = query_df("SELECT * FROM clientes")
    df2 = query_df("SELECT * FROM servicos")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df1.to_excel(w, sheet_name="clientes", index=False)
        df2.to_excel(w, sheet_name="servicos", index=False)
    st.download_button("⬇️ BACKUP COMPLETO", buf.getvalue(), f"backup_{date.today()}.xlsx", type="primary")
