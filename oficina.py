import streamlit as st
import pandas as pd
from datetime import date, timedelta
import io

# ============ CONEXÃO TURSO COM LIMPEZA ============
try:
    import libsql
    URL = str(st.secrets["TURSO_URL"]).strip().replace("\n","").replace("\r","").replace(" ","")
    RAW = str(st.secrets["TURSO_TOKEN"])
    TOKEN = "".join(RAW.split()).strip('"').strip("'")

    @st.cache_resource
    def get_conn():
        c = libsql.connect(database=URL, auth_token=TOKEN)
        c.execute("""CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT, placa TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT,
            valor REAL, data_entrada TEXT, status TEXT, placa TEXT)""")
        c.commit()
        return c
    conn = get_conn()
    st.success(f"✅ Turso Conectado | Token: {len(TOKEN)} chars")
except Exception as e:
    st.warning(f"⚠️ Erro Turso: {e} - Usando temporário (vai apagar)")
    import sqlite3
    conn = sqlite3.connect("oficina.db", check_same_thread=False)
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, moto TEXT, placa TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, descricao TEXT, valor REAL, data_entrada TEXT, status TEXT, placa TEXT)")
    conn.commit()

cur = conn.cursor()
def query_df(sql, params=()):
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return pd.DataFrame(cur.fetchall(), columns=cols)

# ============ MENU ============
st.set_page_config(page_title="Oficina Caruaru", layout="wide")
st.title("🏍️ Oficina Caruaru - OS")
menu = st.sidebar.radio("Menu", ["Dashboard", "Nova OS", "Pesquisar / Filtrar", "Clientes", "Backup"])

# ============ DASHBOARD ============
if menu == "Dashboard":
    df = query_df("SELECT * FROM servicos")
    if df.empty:
        st.info("Nenhum serviço ainda.")
    else:
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 Faturamento Total", f"R$ {df['valor'].sum():.2f}")
        col2.metric("🎫 Ticket Médio", f"R$ {df['valor'].mean():.2f}")
        col3.metric("🔧 Qtd Serviços", len(df))

        st.dataframe(df.sort_values('id', ascending=False), use_container_width=True)

# ============ NOVA OS ============
elif menu == "Nova OS":
    with st.form("os"):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Cliente*")
        zap = c2.text_input("WhatsApp* (ex: 81999999999)")
        c3, c4 = st.columns(2)
        moto = c3.text_input("Moto / Modelo")
        placa = c4.text_input("Placa")
        desc = st.text_area("Serviço / Defeito*")
        c5, c6, c7 = st.columns(3)
        valor = c5.number_input("Valor R$", min_value=0.0, step=10.0)
        data_os = c6.date_input("Data", value=date.today())
        status = c7.selectbox("Status", ["Aberta", "Em andamento", "Pronta", "Entregue", "Cancelada"])
        if st.form_submit_button("💾 Salvar OS"):
            cur.execute("INSERT INTO servicos (cliente, telefone, descricao, valor, data_entrada, status, placa) VALUES (?,?,?,?,?,?,?)",
                        (nome, zap, desc, valor, str(data_os), status, placa))
            cur.execute("INSERT OR IGNORE INTO clientes (nome, telefone, moto, placa) VALUES (?,?,?,?)", (nome, zap, moto, placa))
            conn.commit()
            st.success(f"OS #{cur.lastrowid} criada!")
            # link whatsapp
            if zap:
                link = f"https://wa.me/55{zap.replace(' ','').replace('-','')}?text=Olá {nome}, sua OS #{cur.lastrowid} da moto {placa} está {status}!"
                st.link_button("📱 Enviar WhatsApp", link)

# ============ PESQUISAR / FILTRAR - O QUE VOCÊ PEDIU ============
elif menu == "Pesquisar / Filtrar":
    st.subheader("🔍 Filtrar Ordens de Serviço")
    df = query_df("SELECT id as OS, data_entrada as Data, cliente as Cliente, telefone as WhatsApp, placa as Placa, descricao as Servico, valor as Valor, status as Status FROM servicos")
    if df.empty:
        st.info("Sem OS")
    else:
        c1, c2, c3, c4 = st.columns(4)
        periodo = c1.date_input("Período", value=(date.today()-timedelta(days=30), date.today()))
        f_cliente = c2.text_input("Filtrar Cliente")
        f_moto = c3.text_input("Filtrar Placa/Moto")
        f_status = c4.multiselect("Filtrar Status", ["Aberta", "Em andamento", "Pronta", "Entregue", "Cancelada"])

        df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
        if len(periodo)==2:
            df = df[(df['Data'].dt.date >= periodo[0]) & (df['Data'].dt.date <= periodo[1])]
        if f_cliente:
            df = df[df['Cliente'].str.contains(f_cliente, case=False, na=False)]
        if f_moto:
            df = df[df['Placa'].str.contains(f_moto, case=False, na=False)]
        if f_status:
            df = df[df['Status'].isin(f_status)]

        st.dataframe(df.sort_values('OS', ascending=False), use_container_width=True)
        st.write(f"**{len(df)} OS encontradas | Total: R$ {df['Valor'].sum():.2f}**")

        # baixar filtrado
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False)
        st.download_button("📥 Baixar Excel FILTRADO", buffer.getvalue(), file_name="os_filtradas.xlsx")

# ============ CLIENTES COM VALORES ============
elif menu == "Clientes":
    df_cli = query_df("SELECT * FROM clientes")
    df_serv = query_df("SELECT cliente, SUM(valor) as total_gasto, COUNT(*) as qtd FROM servicos GROUP BY cliente")
    if not df_cli.empty:
        df_final = pd.merge(df_cli, df_serv, left_on="nome", right_on="cliente", how="left").fillna(0)
        st.dataframe(df_final, use_container_width=True)
        buf = io.BytesIO()
        df_final.to_excel(buf, index=False)
        st.download_button("📥 Excel CLIENTES com Valores", buf.getvalue(), "clientes_com_valores.xlsx")
    # Excel servicos
    df_s = query_df("SELECT id as OS, data_entrada, cliente, telefone, placa, descricao, valor, status FROM servicos")
    if not df_s.empty:
        buf2 = io.BytesIO()
        df_s.to_excel(buf2, index=False)
        st.download_button("📥 Excel SERVIÇOS Feitos", buf2.getvalue(), "servicos_feitos.xlsx")

# ============ BACKUP ============
elif menu == "Backup":
    st.subheader("💾 Backup para segurança")
    st.write("Baixe tudo. Se o Turso der erro, você não perde nada.")
    df1 = query_df("SELECT * FROM clientes")
    df2 = query_df("SELECT * FROM servicos")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df1.to_excel(w, sheet_name="clientes", index=False)
        df2.to_excel(w, sheet_name="servicos", index=False)
    st.download_button("⬇️ BAIXAR BACKUP COMPLETO (Excel com 2 abas)", buf.getvalue(), f"backup_oficina_{date.today()}.xlsx")
