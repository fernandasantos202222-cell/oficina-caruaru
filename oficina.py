import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io

# ============ CONEXÃO + ATUALIZAÇÃO AUTOMÁTICA ============
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
        # TENTA ADICIONAR COLUNA SE NÃO EXISTIR
        try: c.execute("ALTER TABLE clientes ADD COLUMN placa TEXT")
        except: pass
        try: c.execute("ALTER TABLE servicos ADD COLUMN placa TEXT")
        except: pass
        c.commit()
        return c
    conn = get_conn()
except Exception as e:
    st.warning(f"⚠️ Turso temporário: {e}")
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
    except Exception as ex:
        # Se der erro de coluna, retorna vazio mas não quebra o app
        if "no such column: placa" in str(ex).lower():
            sql2 = sql.replace(", placa", "").replace("placa,", "").replace("placa", "'' as placa")
            try:
                cur.execute(sql2, params)
                cols = [d[0] for d in cur.description] if cur.description else []
                return pd.DataFrame(cur.fetchall(), columns=cols)
            except:
                return pd.DataFrame()
        return pd.DataFrame()

st.set_page_config(page_title="Oficina Caruaru", layout="wide")
st.title("🏍️ Oficina Caruaru - OS")
if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

menu = st.sidebar.radio("Menu", ["Dashboard", "Nova OS", "Pesquisar / Filtrar", "Clientes", "Backup"])

def acoes_os(df_origem):
    st.divider()
    st.subheader("✏️ Editar / Deletar")
    col_id = 'OS' if 'OS' in df_origem.columns else 'id'
    if col_id not in df_origem.columns or df_origem.empty:
        return
    os_lista = df_origem[col_id].tolist()
    os_sel = st.selectbox("Selecione a OS", os_lista)
    dados = query_df("SELECT * FROM servicos WHERE id=?", (int(os_sel),))
    if dados.empty: return
    d = dados.iloc[0]
    c1, c2 = st.columns(2)
    if c1.button(f"✏️ Editar #{os_sel}", use_container_width=True):
        st.session_state.edit_id = int(os_sel)
    if c2.button(f"🗑️ DELETAR #{os_sel}", type="primary", use_container_width=True):
        cur.execute("DELETE FROM servicos WHERE id=?", (int(os_sel),))
        conn.commit()
        st.success(f"OS #{os_sel} deletada!")
        st.rerun()
    if st.session_state.edit_id == int(os_sel):
        with st.form(f"edit_{os_sel}"):
            c1, c2 = st.columns(2)
            nome = c1.text_input("Cliente", value=d['cliente'])
            zap = c2.text_input("WhatsApp", value=d['telefone'])
            c3, c4 = st.columns(2)
            placa = c3.text_input("Placa", value=str(d['placa']) if 'placa' in d and pd.notna(d['placa']) else "")
            valor = c4.number_input("Valor", value=float(d['valor'] or 0))
            desc = st.text_area("Serviço", value=d['descricao'])
            c5, c6 = st.columns(2)
            data_e = c5.text_input("Data", value=d['data_entrada'])
            status = c6.selectbox("Status", ["Aberta", "Em andamento", "Pronta", "Entregue", "Cancelada"])
            if st.form_submit_button("💾 SALVAR"):
                cur.execute("UPDATE servicos SET cliente=?, telefone=?, descricao=?, valor=?, data_entrada=?, status=?, placa=? WHERE id=?",
                            (nome, zap, desc, valor, data_e, status, placa, int(os_sel)))
                conn.commit()
                st.session_state.edit_id = None
                st.success("Atualizado!")
                st.rerun()

if menu == "Dashboard":
    df = query_df("SELECT id as OS, data_entrada as Data, cliente as Cliente, telefone as WhatsApp, placa as Placa, descricao as Servico, valor as Valor, status as Status FROM servicos")
    if df.empty:
        st.info("Nenhum serviço ainda. Vai em Nova OS")
    else:
        df['Valor'] = pd.to_numeric(df['Valor'], errors='coerce').fillna(0)
        c1,c2,c3 = st.columns(3)
        c1.metric("💰 Faturamento", f"R$ {df['Valor'].sum():.2f}")
        c2.metric("🎫 Ticket Médio", f"R$ {df['Valor'].mean():.2f}")
        c3.metric("🔧 Qtd", len(df))
        st.dataframe(df.sort_values('OS', ascending=False), use_container_width=True)
        acoes_os(df)

elif menu == "Nova OS":
    with st.form("os"):
        c1,c2 = st.columns(2)
        nome = c1.text_input("Cliente*")
        zap = c2.text_input("WhatsApp*")
        c3,c4 = st.columns(2)
        moto = c3.text_input("Moto")
        placa = c4.text_input("Placa")
        desc = st.text_area("Serviço*")
        c5,c6,c7 = st.columns(3)
        valor = c5.number_input("Valor R$", min_value=0.0, step=10.0)
        data_os = c6.date_input("Data", value=date.today())
        status = c7.selectbox("Status", ["Aberta", "Em andamento", "Pronta", "Entregue", "Cancelada"])
        if st.form_submit_button("💾 Salvar OS"):
            cur.execute("INSERT INTO servicos (cliente, telefone, descricao, valor, data_entrada, status, placa) VALUES (?,?,?,?,?,?,?)",(nome, zap, desc, valor, str(data_os), status, placa))
            cur.execute("INSERT INTO clientes (nome, telefone, moto, placa) VALUES (?,?,?,?)",(nome, zap, moto, placa))
            conn.commit()
            st.success(f"OS #{cur.lastrowid} criada!")

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
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        st.download_button("📥 Excel Filtrado", buf.getvalue(), "os_filtradas.xlsx")
        acoes_os(df)

elif menu == "Clientes":
    df_serv = query_df("SELECT cliente as Cliente, telefone as WhatsApp, SUM(valor) as total_gasto, COUNT(*) as qtd FROM servicos GROUP BY cliente, telefone")
    if not df_serv.empty:
        st.subheader("Clientes com Valores")
        st.dataframe(df_serv.sort_values('total_gasto', ascending=False), use_container_width=True)
        buf = io.BytesIO()
        df_serv.to_excel(buf, index=False)
        st.download_button("📥 Excel CLIENTES com Valores", buf.getvalue(), "clientes_com_valores.xlsx")
    df_s = query_df("SELECT * FROM servicos")
    if not df_s.empty:
        buf2 = io.BytesIO()
        df_s.to_excel(buf2, index=False)
        st.download_button("📥 Excel SERVIÇOS Feitos", buf2.getvalue(), "servicos.xlsx")

elif menu == "Backup":
    df1 = query_df("SELECT * FROM clientes")
    df2 = query_df("SELECT * FROM servicos")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df1.to_excel(w, sheet_name="clientes", index=False)
        df2.to_excel(w, sheet_name="servicos", index=False)
    st.download_button("⬇️ BACKUP COMPLETO", buf.getvalue(), f"backup_{date.today()}.xlsx", type="primary")
