"""
Exemplo de automacao (item OPCIONAL da Parte 2): aplica configuracao de VPN IPSec
no lado Fortigate via FortiOS REST API.

STATUS: script funcional, testado contra o Fortigate real do laboratorio.
A configuracao foi aplicada e validada (Phase1, Phase2, interface de tunel, rota
estatica e politicas de firewall) - ver README.md desta pasta para o status
completo do lab (o tunel NAO esta operante, pois falta a configuracao do lado
Palo Alto).

Credenciais/token de API NAO ficam neste arquivo - vem de variavel de ambiente.
"""
import json
import os
import ssl
import urllib.error
import urllib.request

FGT_HOST = os.environ.get("FGT_HOST", "192.168.1.1")
FGT_TOKEN = os.environ["FGT_API_TOKEN"]  # token de admin REST API (perfil super_admin, sem PKI Group)
PSK = os.environ["FGT_VPN_PSK"]  # pre-shared key da Phase 1

BASE_URL = f"https://{FGT_HOST}/api/v2/cmdb"

# Parametros da VPN (ver plano_vpn_ipsec_fortigate_paloalto.md secao 1)
WAN_INTERFACE = "port2"
LAN_INTERFACE = "port3"
REMOTE_GATEWAY = "192.0.2.2"  # WAN do Palo Alto
LAN_LOCAL = "192.168.10.0 255.255.255.0"
LAN_REMOTA = "192.168.20.0 255.255.255.0"
TUNNEL_LOCAL_IP = "169.255.1.1 255.255.255.255"
TUNNEL_REMOTE_IP = "169.255.1.2 255.255.255.255"
TUNNEL_NAME = "VPN-PaloAlto"

# NOTA: o plano oficial (secao 1) recomenda AES-256/SHA-256/DH14. Neste
# laboratorio especifico, o firmware do Fortigate (build "LENC" - Limited
# Encryption, por restricao de exportacao) so aceita propostas DES. Em um
# Fortigate com firmware completo (ENC), troque PROPOSAL abaixo por
# "aes256-sha256" para bater com o documentado no plano.
PROPOSAL = "des-sha256"
DHGRP = "14"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def call(method, path, body=None):
    """Executa uma chamada REST na API do FortiOS e reporta sucesso/erro."""
    url = f"{BASE_URL}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {FGT_TOKEN}")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            print(f"[OK] {method} {path} -> HTTP {resp.status}")
            return result
    except urllib.error.HTTPError as e:
        print(f"[ERRO] {method} {path} -> HTTP {e.code}\n{e.read().decode()}")
        return None


def aplicar_configuracao():
    # 1. Objetos de endereco
    call("POST", "firewall/address", {"name": "LAN-FORTIGATE", "subnet": LAN_LOCAL})
    call("POST", "firewall/address", {"name": "LAN-PALOALTO", "subnet": LAN_REMOTA})

    # 2. Phase 1 (IKE)
    call("POST", "vpn.ipsec/phase1-interface", {
        "name": TUNNEL_NAME,
        "interface": WAN_INTERFACE,
        "ike-version": "2",
        "remote-gw": REMOTE_GATEWAY,
        "psksecret": PSK,
        "proposal": PROPOSAL,
        "dhgrp": DHGRP,
        "nattraversal": "disable",
    })

    # 3. Phase 2 (IPSec)
    call("POST", "vpn.ipsec/phase2-interface", {
        "name": f"{TUNNEL_NAME}-p2",
        "phase1name": TUNNEL_NAME,
        "proposal": PROPOSAL,
        "pfs": "enable",
        "dhgrp": DHGRP,
        "src-subnet": LAN_LOCAL,
        "dst-subnet": LAN_REMOTA,
    })

    # 4. IP da interface de tunel (FortiOS exige mascara /32 + remote-ip separado)
    call("PUT", f"system/interface/{TUNNEL_NAME}", {
        "ip": TUNNEL_LOCAL_IP,
        "remote-ip": TUNNEL_REMOTE_IP,
    })

    # 5. Rota estatica
    call("POST", "router/static", {"dst": LAN_REMOTA, "device": TUNNEL_NAME})

    # 6. Politicas de firewall (as duas direcoes)
    call("POST", "firewall/policy", {
        "name": "LAN-to-PaloAlto",
        "srcintf": [{"name": LAN_INTERFACE}],
        "dstintf": [{"name": TUNNEL_NAME}],
        "srcaddr": [{"name": "LAN-FORTIGATE"}],
        "dstaddr": [{"name": "LAN-PALOALTO"}],
        "action": "accept",
        "schedule": "always",
        "service": [{"name": "ALL"}],
        "nat": "disable",
    })
    call("POST", "firewall/policy", {
        "name": "PaloAlto-to-LAN",
        "srcintf": [{"name": TUNNEL_NAME}],
        "dstintf": [{"name": LAN_INTERFACE}],
        "srcaddr": [{"name": "LAN-PALOALTO"}],
        "dstaddr": [{"name": "LAN-FORTIGATE"}],
        "action": "accept",
        "schedule": "always",
        "service": [{"name": "ALL"}],
        "nat": "disable",
    })


def validar_status_tunel():
    """Consulta o status do tunel apos a aplicacao (secao 5 do plano)."""
    url = f"https://{FGT_HOST}/api/v2/monitor/vpn/ipsec"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {FGT_TOKEN}")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            print(json.dumps(result, indent=2))
    except urllib.error.HTTPError as e:
        print(f"[ERRO] GET monitor/vpn/ipsec -> HTTP {e.code}\n{e.read().decode()}")


if __name__ == "__main__":
    aplicar_configuracao()
    validar_status_tunel()
