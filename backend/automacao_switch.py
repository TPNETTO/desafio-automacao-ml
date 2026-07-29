"""Modulo de conexao SSH com o switch Cisco via Netmiko."""

import os
import re
from datetime import datetime

from dotenv import load_dotenv
from netmiko import ConnectHandler

load_dotenv()

PASTA_BACKUP = os.path.join(os.path.dirname(__file__), "backup")


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


def alterar_hostname(conexao, novo_hostname):
    """Altera o hostname do switch na mesma sessao Netmiko ja aberta.

    Atualiza o prompt base apos a mudanca, pois o Netmiko usa o hostname
    original para reconhecer o prompt e comandos seguintes travariam sem isso.

    Sem o parametro `pattern`, o Netmiko aceita o prompt assim que encontrar
    QUALQUER '#'/'>' no buffer, o que pode capturar um fragmento do prompt
    ainda incompleto (ex.: 'SWITCH_AUTOMATIZ' em vez de
    'SWITCH_AUTOMATIZADO') caso a leitura ocorra no meio da transmissao.
    Passar o hostname esperado como pattern forca a espera pelo texto
    completo antes de aceitar o prompt.
    """
    resultado = conexao.send_config_set([f"hostname {novo_hostname}"])
    conexao.set_base_prompt(pattern=re.escape(novo_hostname))
    return resultado


def salvar_configuracao(conexao):
    """Salva a configuracao atual na NVRAM (copy running-config startup-config).

    Usa o metodo nativo do Netmiko para cisco_ios, que ja trata a confirmacao
    de nome de arquivo pedida pelo switch nesse comando.
    """
    return conexao.save_config()


def fazer_backup(conexao, pasta_backup=PASTA_BACKUP):
    """Salva um backup local da configuracao atual do switch.

    O nome do arquivo usa o hostname atual do switch e a data/hora da
    execucao, ex.: SWITCH_AUTOMATIZADO_20260728_210500.txt
    """
    config_atual = conexao.send_command("show running-config")
    hostname = conexao.base_prompt
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    os.makedirs(pasta_backup, exist_ok=True)
    caminho_arquivo = os.path.join(pasta_backup, f"{hostname}_{timestamp}.txt")
    with open(caminho_arquivo, "w", encoding="utf-8") as arquivo:
        arquivo.write(config_atual)

    return caminho_arquivo


def validar_configuracao(conexao, hostname_esperado, vlans_esperadas=None):
    """Rele a configuracao do switch e compara com o esperado (hostname + VLANs).

    Retorna um dicionario {"ok": bool, "divergencias": list[str]} para o
    frontend/script exibir um alerta claro em caso de qualquer divergencia.
    """
    vlans_esperadas = vlans_esperadas or VLANS_PADRAO
    divergencias = []

    hostname_atual = conexao.base_prompt
    if hostname_atual != hostname_esperado:
        divergencias.append(
            f"Hostname divergente: esperado '{hostname_esperado}', "
            f"encontrado '{hostname_atual}'"
        )

    saida_vlans = conexao.send_command("show vlan brief")
    for vlan_id, nome_esperado in vlans_esperadas.items():
        padrao = rf"^{vlan_id}\s+{re.escape(nome_esperado)}\b"
        if not re.search(padrao, saida_vlans, re.MULTILINE):
            divergencias.append(
                f"VLAN {vlan_id} ('{nome_esperado}') nao encontrada ou "
                f"com nome divergente na saida de 'show vlan brief'"
            )

    return {"ok": not divergencias, "divergencias": divergencias}


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
