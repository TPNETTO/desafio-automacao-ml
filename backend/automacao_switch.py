"""Modulo de conexao SSH com o switch Cisco via Netmiko."""

import os

from dotenv import load_dotenv
from netmiko import ConnectHandler

load_dotenv()


def obter_credenciais_padrao():
    """Le host/usuario/senha padrao do switch a partir do arquivo .env."""
    return {
        "host": os.getenv("SWITCH_HOST", ""),
        "usuario": os.getenv("SWITCH_USER", ""),
        "senha": os.getenv("SWITCH_PASSWORD", ""),
    }


def conectar_switch(host, usuario, senha, device_type="cisco_ios"):
    """Abre uma conexao SSH com o switch e retorna a conexao Netmiko."""
    dispositivo = {
        "device_type": device_type,
        "host": host,
        "username": usuario,
        "password": senha,
    }
    return ConnectHandler(**dispositivo)


VLANS_PADRAO = {
    10: "VLAN_DADOS",
    20: "VLAN_VOZ",
    50: "VLAN_SEGURANCA",
}


def configurar_vlans(conexao, vlans=None):
    """Cria/configura VLANs no switch a partir de um dicionario {id_vlan: nome}.

    Usa uma conexao Netmiko ja aberta (ver conectar_switch), permitindo
    encadear outras alteracoes (ex.: hostname) na mesma sessao.
    """
    vlans = vlans or VLANS_PADRAO
    comandos = []
    for vlan_id, nome in vlans.items():
        comandos.append(f"vlan {vlan_id}")
        comandos.append(f"name {nome}")
    return conexao.send_config_set(comandos)


def testar_conexao(host, usuario, senha):
    """Testa a conexao com o switch via 'show version', sem alterar nada.

    Util como primeiro teste antes de aplicar qualquer configuracao real.
    """
    conexao = conectar_switch(host, usuario, senha)
    try:
        saida = conexao.send_command("show version")
    finally:
        conexao.disconnect()
    return saida


if __name__ == "__main__":
    credenciais = obter_credenciais_padrao()
    print(testar_conexao(**credenciais))
