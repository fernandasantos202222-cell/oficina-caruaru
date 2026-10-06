import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io
from fpdf import FPDF

# ============ CONEXÃO ============
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
except Exception as e:
    st.warning(f"Temporário: {e}")
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

def gerar_pdf_os(os_id, cliente, zap, placa, servico, valor, data_e, status):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "OFICINA CARUARU - ORDEM DE SERVICO", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Arial", "", 12)
    pdf.ln(10)
    pdf.cell(0, 8, f"OS N: {os_id} | Data: {data_e} | Status: {status}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"Cliente: {cliente}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, f"WhatsApp: {zap} | Placa: {placa}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Descricao:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 12)
    pdf.multi_cell(0, 8, str(servico))
    pdf.ln(5)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, f"Valor: R$ {float(valor):.2f}", new_x="LMARGIN", new_y="NEXT")
    out = pdf.output()
    return bytes(out) if not isinstance(out, str) else out.encode('latin-1')

st.set_page_config(page_title="Oficina Caruaru", layout="wide")
st.title("🏍️ Oficina Caruaru - OS")
if "edit_id" not in st.session_state: st.session_state.edit_id = None
if "ultima_os" not in st.session_state: st.session_state.ultima_os = None

menu = st.sidebar.radio("Menu", ["Dashboard", "Nova OS", "Pesquisar / Filtrar", "Clientes", "Backup"])

# ============ DASHBOARD COM FATURAMENTO E TICKET MEDIO ============
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

# ============ NOVA OS - CORRIGIDO FORA DO FORM ============
elif menu == "Nova OS":
    with st.form("os_form", clear_on_submit=True):
        c1,c2 = st.columns(2)
        nome = c1.text_input("Cliente*")
        zap = c2.text_input("WhatsApp* só números")
        c3,c4 = st.columns(2)
        moto = c3.text_input("Moto")
        placa = c4.text_input("Placa")
        desc = st.text_area("Serviço*")
        c5,c6,c7 = st.columns(3)
        valor = c5.number_input("Valor R$", min_value=0.0, step=10.0)
        data_os = c6.date_input("Data", value=date.today())
        status = c7.selectbox("Status", ["Aberta","Em andamento","Pronta","Entregue","Cancelada"])
        salvar = st.form_submit_button("💾 Salvar OS")
        if salvar and nome and desc:
            cur.execute("INSERT INTO servicos (cliente, telefone, descricao, valor, data_entrada, status, placa) VALUES (?,?,?,?,?,?,?)",(nome, zap, desc, valor, str(data_os), status, placa))
            cur.execute("INSERT INTO clientes (nome, telefone, moto, placa) VALUES (?,?,?,?)",(nome, zap, moto, placa))
            conn.commit()
            st.session_state.ultima_os = {
                "id": cur.lastrowid, "cliente": nome, "zap": zap, "placa": placa,
                "desc": desc, "valor": valor, "data": str(data_os), "status": status
            }
            st.success(f"OS #{cur.lastrowid} criada!")

    # AQUI FORA DO FORM - AGORA FUNCIONA
    if st.session_state.ultima_os:
        o = st.session_state.ultima_os
        st.divider()
        st.subheader(f"Ações da OS #{o['id']}")
        zap_limpo = ''.join(filter(str.isdigit, o['zap']))
        msg = f"Ola {o['cliente']}! Sua OS #{o['id']} Moto {o['placa']} Status {o['status']} Valor R$ {o['valor']:.2f} - Oficina Caruaru"
        link_zap = f"https://wa.me/55{zap_limpo}?text={msg.replace(' ', '%20')}"
        c1,c2 = st.columns(2)
        c1.link_button("📱 Enviar WhatsApp pro Cliente", link_zap, use_container_width=True)
        pdf_bytes = gerar_pdf_os(o['id'], o['cliente'], o['zap'], o['placa'], o['desc'], o['valor'], o['data'], o['status'])
        c2.download_button("📄 Baixar PDF da OS pro Cliente", pdf_bytes, file_name=f"OS_{o['id']}_{o['cliente']}.pdf", mime="application/pdf", use_container_width=True)

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
        st.caption(f"{len(df)} OS | Faturamento: R$ {df['Valor'].sum():.2f} | Ticket Médio: R$ {df['Valor'].mean():.2f}")

        # AÇÕES COM WHATSAPP E PDF + EDITAR/DELETAR
        st.divider()
        os_sel = st.selectbox("Selecione OS para ações", df['OS'].tolist())
        dados = query_df("SELECT * FROM servicos WHERE id=?", (int(os_sel),))
        if not dados.empty:
            d = dados.iloc[0]
            zap_limpo = ''.join(filter(str.isdigit, str(d['telefone'])))
            msg = f"Ola {d['cliente']}! OS #{d['id']} {d['placa']} Status {d['status']} R$ {float(d['valor'] or 0):.2f}"
            link_zap = f"https://wa.me/55{zap_limpo}?text={msg.replace(' ', '%20')}"
            c1,c2,c3,c4 = st.columns(4)
            c1.link_button("📱 WhatsApp", link_zap, use_container_width=True)
            pdf_b = gerar_pdf_os(d['id'], d['cliente'], d['telefone'], d['placa'], d['descricao'], d['valor'], d['data_entrada'], d['status'])
            c2.download_button("📄 PDF", pdf_b, file_name=f"OS_{d['id']}.pdf", mime="application/pdf", use_container_width=True)
            if c3.button(f"✏️ Editar #{os_sel}", use_container_width=True):
                st.session_state.edit_id = int(os_sel)
            if c4.button(f"🗑️ Deletar #{os_sel}", type="primary", use_container_width=True):
                cur.execute("DELETE FROM servicos WHERE id=?", (int(os_sel),))
                conn.commit()
                st.success("Deletada!"); st.rerun()
            if st.session_state.edit_id == int(os_sel):
                with st.form(f"edit_{os_sel}"):
                    nome = st.text_input("Cliente", value=d['cliente'])
                    zap = st.text_input("WhatsApp", value=d['telefone'])
                    placa = st.text_input("Placa", value=str(d['placa'] or ""))
                    valor = st.number_input("Valor", value=float(d['valor'] or 0))
                    desc = st.text_area("Serviço", value=d['descricao'])
                    status = st.selectbox("Status", ["Aberta","Em andamento","Pronta","Entregue","Cancelada"])
                    if st.form_submit_button("💾 SALVAR"):
                        cur.execute("UPDATE servicos SET cliente=?, telefone=?, descricao=?, valor=?, status=?, placa=? WHERE id=?",(nome, zap, desc, valor, status, placa, int(os_sel)))
                        conn.commit()
                        st.session_state.edit_id=None
                        st.rerun()

elif menu == "Clientes":
    df_serv = query_df("SELECT cliente as Cliente, telefone as WhatsApp, SUM(valor) as total_gasto, COUNT(*) as qtd, AVG(valor) as ticket_medio FROM servicos GROUP BY cliente, telefone")
    if not df_serv.empty:
        st.subheader("Clientes com Valores")
        st.dataframe(df_serv.sort_values('total_gasto', ascending=False), use_container_width=True)
        buf = io.BytesIO(); df_serv.to_excel(buf, index=False)
        st.download_button("📥 Excel CLIENTES com Valores", buf.getvalue(), "clientes_com_valores.xlsx")

elif menu == "Backup":
    df1 = query_df("SELECT * FROM clientes")
    df2 = query_df("SELECT * FROM servicos")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df1.to_excel(w, sheet_name="clientes", index=False)
        df2.to_excel(w, sheet_name="servicos", index=False)
    st.download_button("⬇️ BACKUP COMPLETO", buf.getvalue(), f"backup_{date.today()}.xlsx", type="primary")
