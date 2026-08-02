"""
Exemplo de automacao (item OPCIONAL da Parte 2): configuracao de VPN IPSec no
lado Fortigate.

STATUS: script EXECUTADO com sucesso neste laboratorio (EVE-NG, FortiGate-VM64-
KVM v7.6.5). Phase1, Phase2, interface de tunel e politicas de firewall foram
aplicados e confirmados via CLI. O tunel nao sobe (SA down) por
incompatibilidade real de algoritmos com o Palo Alto - ver STATUS_LAB_VPN.md.

NOTA IMPORTANTE sobre o proposal: esta build de Fortigate e "LENC" (Limited
Encryption, restricao de exportacao) - so aceita propostas DES em Phase1 e
Phase2 (testado exaustivamente: 3des-sha256, 3des-md5, aes128-sha256,
aes256-sha256 - todos rejeitados). O plano oficial (secao 1) recomenda
AES-256/SHA-256; num Fortigate com firmware completo, troque PROPOSAL abaixo
por "aes256-sha256" para bater com o documentado no plano.

Usa Netmiko (SSH/CLI) em vez da REST API porque a API HTTPS deste FortiOS nao
completou o handshake TLS pelo curl/schannel do Windows neste ambiente (SSH
funcionou normalmente). Credenciais/PSK NAO ficam neste arquivo - vem de
variavel de ambiente.
"""
import os

from netmiko import ConnectHandler

FGT_HOST = os.environ.get("FGT_HOST", "10.10.1.200")
FGT_USER = os.environ.get("FGT_USER", "admin")
FGT_PASSWORD = os.environ["FGT_PASSWORD"]
PSK = os.environ["FGT_VPN_PSK"]  # pre-shared key da Phase 1 (mesma do lado Palo Alto)

# Parametros da VPN (topologia ponto a ponto simplificada deste lab, sem LAN
# atras dos firewalls - ver topologia.png e STATUS_LAB_VPN.md)
WAN_INTERFACE = "port2"          # WAN-VPN, ligado direto ao ethernet1/1 do PA-VM
REMOTE_GATEWAY = "10.0.0.2"      # ethernet1/1 do Palo Alto
TUNNEL_LOCAL_IP = "169.255.1.1 255.255.255.255"
TUNNEL_REMOTE_IP = "169.255.1.2 255.255.255.255"
TUNNEL_NAME = "VPN-PaloAlto"
PROPOSAL = "des-sha256"  # ver nota sobre build LENC no topo do arquivo
DHGRP = "14"


def aplicar_configuracao():
    conn = ConnectHandler(
        device_type="fortinet",
        host=FGT_HOST,
        username=FGT_USER,
        password=FGT_PASSWORD,
    )

    config_commands = [
        "config vpn ipsec phase1-interface",
        f'edit "{TUNNEL_NAME}"',
        f'set interface "{WAN_INTERFACE}"',
        "set ike-version 2",
        "set peertype any",
        "set net-device disable",
        f"set proposal {PROPOSAL}",
        f"set dhgrp {DHGRP}",
        f"set remote-gw {REMOTE_GATEWAY}",
        f"set psksecret {PSK}",
        "next",
        "end",

        "config vpn ipsec phase2-interface",
        f'edit "{TUNNEL_NAME}-p2"',
        f'set phase1name "{TUNNEL_NAME}"',
        f"set proposal {PROPOSAL}",
        "set pfs enable",
        f"set dhgrp {DHGRP}",
        "next",
        "end",

        "config system interface",
        f'edit "{TUNNEL_NAME}"',
        f"set ip {TUNNEL_LOCAL_IP}",
        f"set remote-ip {TUNNEL_REMOTE_IP}",
        "set allowaccess ping",
        "next",
        "end",

        "config firewall policy",
        "edit 0",
        'set name "WAN-to-PaloAlto"',
        f'set srcintf "{WAN_INTERFACE}"',
        f'set dstintf "{TUNNEL_NAME}"',
        'set srcaddr "all"',
        'set dstaddr "all"',
        "set action accept",
        'set schedule "always"',
        'set service "ALL"',
        "next",
        "end",

        "config firewall policy",
        "edit 0",
        'set name "PaloAlto-to-WAN"',
        f'set srcintf "{TUNNEL_NAME}"',
        f'set dstintf "{WAN_INTERFACE}"',
        'set srcaddr "all"',
        'set dstaddr "all"',
        "set action accept",
        'set schedule "always"',
        'set service "ALL"',
        "next",
        "end",
    ]

    print(conn.send_config_set(config_commands))
    conn.disconnect()


def validar_status_tunel():
    """Consulta o status do tunel apos a aplicacao (secao 5 do plano)."""
    conn = ConnectHandler(
        device_type="fortinet",
        host=FGT_HOST,
        username=FGT_USER,
        password=FGT_PASSWORD,
    )
    print(conn.send_command("get vpn ipsec tunnel summary"))
    conn.disconnect()


if __name__ == "__main__":
    aplicar_configuracao()
    validar_status_tunel()
