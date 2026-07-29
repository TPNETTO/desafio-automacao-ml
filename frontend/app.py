"""Frontend Streamlit para configuracao de VLANs e hostname do switch Cisco."""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Automacao Switch Cisco", page_icon=":gear:")

st.title("Automacao de Switch Cisco")
st.caption("Configuracao de VLANs e hostname via Netmiko")

with st.form("formulario_configuracao"):
    st.subheader("Conexao com o switch")
    host = st.text_input("Host / IP", value=os.getenv("SWITCH_HOST", ""))
    usuario = st.text_input("Usuario", value=os.getenv("SWITCH_USER", ""))
    senha = st.text_input(
        "Senha", value=os.getenv("SWITCH_PASSWORD", ""), type="password"
    )

    st.subheader("Hostname")
    novo_hostname = st.text_input("Novo hostname", value="SWITCH_AUTOMATIZADO")

    st.subheader("VLANs")
    coluna_10, coluna_20, coluna_50 = st.columns(3)
    with coluna_10:
        nome_vlan_10 = st.text_input("VLAN 10", value="VLAN_DADOS")
    with coluna_20:
        nome_vlan_20 = st.text_input("VLAN 20", value="VLAN_VOZ")
    with coluna_50:
        nome_vlan_50 = st.text_input("VLAN 50", value="VLAN_SEGURANCA")

    enviado = st.form_submit_button("Aplicar configuracao")

if enviado:
    st.info(
        "Formulario recebido. A integracao com o backend (aplicar, salvar "
        "na NVRAM, gerar backup e validar) sera adicionada no proximo commit."
    )
