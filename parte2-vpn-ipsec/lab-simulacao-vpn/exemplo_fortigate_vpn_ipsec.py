"""
Exemplo de automacao (item OPCIONAL da Parte 2): configuracao de VPN IPSec no
lado Fortigate.

STATUS: script EXECUTADO com sucesso contra um FortiGate FISICO (FortiWiFi-60C,
FortiOS v5.2.0). Phase1, Phase2, interface de tunel e politicas de firewall
foram aplicados e o tunel ficou operante (IKE SA + IPsec SA established nos
dois lados, trafego real confirmado) - ver STATUS_LAB_VPN.md para o resultado
completo, incluindo a tentativa anterior com um Fortigate virtual sem licenca
(que so aceitava propostas DES e nunca conseguia negociar com o Palo Alto).

NOTAS sobre particularidades desta versao de firmware (FortiOS v5.2.0, de
2014), descobertas durante a automacao real - nao sao erros do plano, sao
diferencas de sintaxe entre versoes do FortiOS:
- `set net-device disable` nao existe nesta versao (comando adicionado em
  releases mais recentes do FortiOS) - omitido abaixo.
- `set remote-ip` na interface de tunel so aceita o IP, sem mascara, nesta
  versao (`set remote-ip 255.255.255.255` da erro de sintaxe).
- `set name` no firewall policy nao existe nesta versao - as politicas ficam
  sem nome de exibicao, mas funcionam normalmente.
Numa versao mais recente do FortiOS, esses comandos podem ser incluidos
normalmente.

Usa Netmiko (SSH/CLI) em vez da REST API porque a API HTTPS deste FortiOS nao
completou o handshake TLS pelo curl/schannel do Windows neste ambiente (SSH
funcionou normalmente). Credenciais/PSK NAO ficam neste arquivo - vem de
variavel de ambiente.
"""
import os

from netmiko import ConnectHandler

FGT_HOST = os.environ.get("FGT_HOST", "10.10.90.7")
FGT_USER = os.environ.get("FGT_USER", "admin")
FGT_PASSWORD = os.environ["FGT_PASSWORD"]
PSK = os.environ["FGT_VPN_PSK"]  # pre-shared key da Phase 1 (mesma do lado Palo Alto)

# Parametros da VPN (sem LAN atras dos firewalls - escopo simplificado para
# validar o tunel; ver topologia.png e STATUS_LAB_VPN.md)
WAN_INTERFACE = "wan1"           # WAN fisica do Fortigate
REMOTE_GATEWAY = "10.10.1.202"   # ethernet1/1 do Palo Alto
TUNNEL_LOCAL_IP = "169.255.1.1 255.255.255.255"
TUNNEL_REMOTE_IP = "169.255.1.2"  # sem mascara - ver nota sobre esta versao de firmware
TUNNEL_NAME = "VPN-PaloAlto"
PROPOSAL = "aes256-sha256"       # mesma proposta recomendada no plano oficial (secao 1)
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
