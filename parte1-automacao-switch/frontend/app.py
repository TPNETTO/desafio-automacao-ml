"""Frontend Streamlit para configuracao de VLANs e hostname do switch Cisco."""

import os
import sys

import streamlit as st
from dotenv import load_dotenv
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

# Permite importar o backend (pasta irma de frontend/) sem instalar como pacote.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from backend import automacao_switch as backend_switch

load_dotenv()

CAMINHO_LOGO = os.path.join(os.path.dirname(__file__), "assets", "logo_mercado_livre.png")

st.set_page_config(
    page_title="Automacao Switch Cisco",
    page_icon=":gear:",
    layout="centered",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        max-width: 780px;
    }
    div[data-testid="stForm"] {
        border: 1px solid rgba(0, 0, 0, 0.08);
        border-radius: 14px;
        padding: 1.75rem 2rem 1.25rem;
    }
    div[data-testid="stForm"] h3 {
        margin-top: 0;
        margin-bottom: 0.75rem;
    }
    .st-key-banner_ml {
        background: #FFE600;
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.75rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def banner_titulo():
    """Banner de topo no amarelo do Mercado Livre, com logo (se disponivel)."""
    with st.container(key="banner_ml"):
        coluna_logo, coluna_texto = st.columns([1, 4])
        with coluna_logo:
            if os.path.exists(CAMINHO_LOGO):
                st.image(CAMINHO_LOGO, width=90)
            else:
                st.markdown("### :gear:")
        with coluna_texto:
            st.markdown(
                """
                <h1 style="color:#2D3277; margin:0; font-size:1.7rem;">
                    Automação de Switch Cisco
                </h1>
                <p style="color:#2D3277; margin:0.25rem 0 0; opacity:0.85;">
                    Configuração de VLANs e hostname via Netmiko — Desafio Mercado Livre
                </p>
                """,
                unsafe_allow_html=True,
            )


def selo_secao(cor_fundo, cor_texto, texto):
    """Selo colorido usado para identificar visualmente cada secao do formulario."""
    st.markdown(
        f"""
        <span style="
            background:{cor_fundo};
            color:{cor_texto};
            padding:0.2rem 0.7rem;
            border-radius:999px;
            font-size:0.75rem;
            font-weight:700;
            letter-spacing:0.03em;
        ">{texto}</span>
        """,
        unsafe_allow_html=True,
    )


banner_titulo()

with st.form("formulario_configuracao"):
    selo_secao("#3483FA", "#FFFFFF", "CONEXÃO")
    st.subheader(":link: Conexão com o switch")
    coluna_host, coluna_usuario, coluna_senha = st.columns(3)
    with coluna_host:
        host = st.text_input("Host / IP", value=os.getenv("SWITCH_HOST", ""))
    with coluna_usuario:
        usuario = st.text_input("Usuário", value=os.getenv("SWITCH_USER", ""))
    with coluna_senha:
        senha = st.text_input(
            "Senha", value=os.getenv("SWITCH_PASSWORD", ""), type="password"
        )

    st.divider()

    selo_secao("#2D3277", "#FFFFFF", "HOSTNAME")
    st.subheader(":label: Hostname")
    novo_hostname = st.text_input(
        "Novo hostname", value="SWITCH_AUTOMATIZADO", label_visibility="collapsed"
    )

    st.divider()

    selo_secao("#FFE600", "#2D3277", "VLANS")
    st.subheader(":globe_with_meridians: VLANs")
    coluna_10, coluna_20, coluna_50 = st.columns(3)
    with coluna_10:
        selo_secao("#3483FA", "#FFFFFF", "DADOS")
        id_vlan_10 = st.number_input(
            "ID", min_value=1, max_value=4094, value=10, step=1, key="id_vlan_1"
        )
        nome_vlan_10 = st.text_input("Nome", value="VLAN_DADOS", key="nome_vlan_1")
    with coluna_20:
        selo_secao("#00A650", "#FFFFFF", "VOZ")
        id_vlan_20 = st.number_input(
            "ID", min_value=1, max_value=4094, value=20, step=1, key="id_vlan_2"
        )
        nome_vlan_20 = st.text_input("Nome", value="VLAN_VOZ", key="nome_vlan_2")
    with coluna_50:
        selo_secao("#E63C3C", "#FFFFFF", "SEGURANÇA")
        id_vlan_50 = st.number_input(
            "ID", min_value=1, max_value=4094, value=50, step=1, key="id_vlan_3"
        )
        nome_vlan_50 = st.text_input("Nome", value="VLAN_SEGURANCA", key="nome_vlan_3")

    st.write("")
    enviado = st.form_submit_button(
        ":rocket: Aplicar configuração", use_container_width=True, type="primary"
    )


def aplicar_configuracao_no_switch(host, usuario, senha, novo_hostname, vlans, avisar_etapa):
    """Executa o fluxo completo de automacao contra o switch fisico.

    Conecta via SSH, aplica VLANs e hostname, salva na NVRAM, gera o backup
    local e por fim rele a config para validar. Chama `avisar_etapa(texto)`
    apos cada etapa concluida, para o frontend mostrar progresso em tempo
    real (util para saber o que ja foi aplicado no switch caso uma etapa
    posterior falhe). Retorna um dicionario com o backup gerado e a
    validacao final.
    """
    resultado = {"backup": None, "validacao": None}

    conexao = backend_switch.conectar_switch(host, usuario, senha)
    try:
        backend_switch.configurar_vlans(conexao, vlans)
        avisar_etapa("VLANs 10/20/50 aplicadas")

        backend_switch.alterar_hostname(conexao, novo_hostname)
        avisar_etapa(f"Hostname alterado para '{novo_hostname}'")

        backend_switch.salvar_configuracao(conexao)
        avisar_etapa("Configuração salva na NVRAM")

        resultado["backup"] = backend_switch.fazer_backup(conexao)
        avisar_etapa(f"Backup gerado em '{resultado['backup']}'")

        resultado["validacao"] = backend_switch.validar_configuracao(conexao)
    finally:
        conexao.disconnect()

    return resultado


if enviado:
    novo_hostname = novo_hostname.strip()
    ids_vlans = [int(id_vlan_10), int(id_vlan_20), int(id_vlan_50)]
    if len(set(ids_vlans)) != len(ids_vlans):
        st.error("As três VLANs precisam ter IDs diferentes entre si.")
        st.stop()

    vlans_formulario = dict(zip(ids_vlans, [nome_vlan_10, nome_vlan_20, nome_vlan_50]))

    with st.status("Aplicando configuração no switch...", expanded=True) as status:
        try:
            st.write("Conectando via SSH...")
            resultado = aplicar_configuracao_no_switch(
                host,
                usuario,
                senha,
                novo_hostname,
                vlans_formulario,
                avisar_etapa=lambda texto: st.write(f":white_check_mark: {texto}"),
            )

            validacao = resultado["validacao"]
            if validacao["ok"]:
                status.update(
                    label="Configuração aplicada e validada com sucesso!",
                    state="complete",
                )
                st.success("Validação: hostname e VLANs conferem com o esperado.")
            else:
                status.update(
                    label="Configuração aplicada, mas com divergências na validação",
                    state="error",
                )
                st.warning("Divergências encontradas na validação pós-configuração:")
                for divergencia in validacao["divergencias"]:
                    st.write(f":warning: {divergencia}")

            with open(resultado["backup"], "rb") as arquivo_backup:
                st.download_button(
                    "Baixar backup gerado",
                    data=arquivo_backup.read(),
                    file_name=os.path.basename(resultado["backup"]),
                )

        except NetmikoAuthenticationException:
            status.update(label="Falha de autenticação no switch", state="error")
            st.error("Usuário ou senha incorretos para o switch informado.")
        except NetmikoTimeoutException:
            status.update(label="Timeout ao conectar no switch", state="error")
            st.error(
                "Não foi possível conectar ao switch (timeout). Verifique o IP, "
                "a rede e se o SSH está habilitado."
            )
        except Exception as erro:  # pylint: disable=broad-except
            status.update(label="Erro ao aplicar configuração", state="error")
            st.error(f"Erro inesperado ao aplicar a configuração: {erro}")
