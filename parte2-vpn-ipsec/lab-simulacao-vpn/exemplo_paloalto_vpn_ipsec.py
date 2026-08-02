"""
Exemplo de automacao (item OPCIONAL da Parte 2): configuracao de VPN IPSec no
lado Palo Alto via PAN-OS XML API.

STATUS: script EXECUTADO com sucesso contra um Palo Alto PA-VM (PAN-OS 11.2.5)
comunicando com um FortiGate FISICO real. Interfaces, zonas, Phase1, Phase2,
interface de tunel, rota e politica foram aplicados e commitados (commit job
OK), e o tunel ficou operante (IKE SA + IPsec SA established, trafego real
confirmado) - ver STATUS_LAB_VPN.md para o resultado completo, incluindo a
tentativa anterior com um Fortigate virtual sem licenca (que nunca conseguia
negociar por so aceitar propostas DES).

NOTA sobre a rota estatica (passo 5 abaixo): o roteador virtual do PAN-OS
(dataplane) usa uma tabela de rotas completamente separada da tabela de rotas
da interface de management. Mesmo que a gerencia already alcance a rede do
Fortigate, o dataplane precisa de uma rota propria - sem ela, o Palo Alto
recebe os pacotes do Fortigate mas nao consegue responder (comportamento
descoberto durante a automacao real, nao documentado no plano original).

NOTA sobre os management profiles (passo 6): interfaces de dados do PAN-OS
nao respondem a ping por padrao. Os profiles abaixo sao so para permitir
diagnostico com ping durante os testes - nao sao necessarios para o tunel
IPSec funcionar.
"""
import os
import urllib.parse
import urllib.request
import ssl

PA_HOST = os.environ.get("PA_HOST", "10.10.1.201")
PA_API_KEY = os.environ["PA_API_KEY"]  # gerado via keygen (usuario/senha) antes de rodar este script

BASE_URL = f"https://{PA_HOST}/api/"

# Parametros da VPN (sem LAN atras dos firewalls - escopo simplificado para
# validar o tunel; ver topologia.png e STATUS_LAB_VPN.md)
WAN_INTERFACE = "ethernet1/1"
WAN_LOCAL_IP = "10.10.1.202/24"
WAN_GATEWAY = "10.10.1.1"       # gateway da rede do WAN_INTERFACE (nao o peer da VPN)
REMOTE_GATEWAY = "10.10.90.7"   # wan1 do Fortigate fisico
TUNNEL_IP = "169.255.1.2/30"
PSK = os.environ["PA_VPN_PSK"]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def api_set(xpath, element):
    """Monta uma chamada type=config&action=set contra a API XML do PAN-OS."""
    params = {
        "type": "config",
        "action": "set",
        "key": PA_API_KEY,
        "xpath": xpath,
        "element": element,
    }
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return resp.read().decode()


def api_commit():
    params = {"type": "commit", "key": PA_API_KEY, "cmd": "<commit></commit>"}
    url = BASE_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return resp.read().decode()


def aplicar_configuracao():
    vsys_xpath = "/config/devices/entry/vsys/entry"

    # 1. Interface WAN (dataplane)
    api_set(
        f"/config/devices/entry/network/interface/ethernet/entry[@name='{WAN_INTERFACE}']",
        f"<layer3><ip><entry name='{WAN_LOCAL_IP}'/></ip></layer3>",
    )

    # 2. Zona WAN
    api_set(f"{vsys_xpath}/zone/entry[@name='WAN']", f"<network><layer3><member>{WAN_INTERFACE}</member></layer3></network>")

    # 3. Interface de tunel logica + zona VPN
    api_set(
        "/config/devices/entry/network/interface/tunnel/units/entry[@name='tunnel.1']",
        f"<ip><entry name='{TUNNEL_IP}'/></ip>",
    )
    api_set(f"{vsys_xpath}/zone/entry[@name='VPN']", "<network><layer3><member>tunnel.1</member></layer3></network>")

    # 4. Adicionar interfaces ao virtual router default
    api_set(
        "/config/devices/entry/network/virtual-router/entry[@name='default']/interface",
        f"<member>{WAN_INTERFACE}</member><member>tunnel.1</member>",
    )

    # 5. Rota estatica default no virtual router (dataplane) - ver nota no topo do arquivo
    api_set(
        "/config/devices/entry/network/virtual-router/entry[@name='default']/routing-table/ip/static-route/entry[@name='default']",
        f"<destination>0.0.0.0/0</destination><interface>{WAN_INTERFACE}</interface>"
        f"<nexthop><ip-address>{WAN_GATEWAY}</ip-address></nexthop>",
    )

    # 6. Management profile com ping (so para diagnostico - ver nota no topo do arquivo)
    api_set(
        "/config/devices/entry/network/profiles/interface-management-profile/entry[@name='allow-ping']",
        "<ping>yes</ping>",
    )
    api_set(
        f"/config/devices/entry/network/interface/ethernet/entry[@name='{WAN_INTERFACE}']/layer3",
        "<interface-management-profile>allow-ping</interface-management-profile>",
    )
    api_set(
        "/config/devices/entry/network/interface/tunnel/units/entry[@name='tunnel.1']",
        "<interface-management-profile>allow-ping</interface-management-profile>",
    )

    # 7. IKE Crypto Profile (Phase 1) - AES-256/SHA-256/DH14, conforme o plano oficial
    api_set(
        "/config/devices/entry/network/ike/crypto-profiles/ike-crypto-profiles/entry[@name='IKE-ML']",
        "<hash><member>sha256</member></hash>"
        "<encryption><member>aes-256-cbc</member></encryption>"
        "<dh-group><member>group14</member></dh-group>"
        "<lifetime><hours>8</hours></lifetime>",
    )

    # 8. IKE Gateway
    api_set(
        "/config/devices/entry/network/ike/gateway/entry[@name='IKE-GW-FGT']",
        f"<authentication><pre-shared-key><key>{PSK}</key></pre-shared-key></authentication>"
        f"<protocol><ikev2><ike-crypto-profile>IKE-ML</ike-crypto-profile></ikev2><version>ikev2</version></protocol>"
        f"<local-address><interface>{WAN_INTERFACE}</interface><ip>{WAN_LOCAL_IP}</ip></local-address>"
        f"<peer-address><ip>{REMOTE_GATEWAY}</ip></peer-address>",
    )

    # 9. IPSec Crypto Profile (Phase 2)
    api_set(
        "/config/devices/entry/network/ike/crypto-profiles/ipsec-crypto-profiles/entry[@name='IPSEC-ML']",
        "<esp><encryption><member>aes-256-cbc</member></encryption>"
        "<authentication><member>sha256</member></authentication></esp>"
        "<dh-group>group14</dh-group>"
        "<lifetime><hours>1</hours></lifetime>",
    )

    # 10. IPSec Tunnel
    api_set(
        "/config/devices/entry/network/tunnel/ipsec/entry[@name='IPSEC-TUN-FGT']",
        "<tunnel-interface>tunnel.1</tunnel-interface>"
        "<auto-key><ike-gateway><entry name='IKE-GW-FGT'/></ike-gateway>"
        "<ipsec-crypto-profile>IPSEC-ML</ipsec-crypto-profile></auto-key>",
    )

    # 11. Politica de seguranca (sem LAN neste lab - so a interface de tunel)
    api_set(
        f"{vsys_xpath}/rulebase/security/rules/entry[@name='ALLOW-VPN-LAB']",
        "<from><member>WAN</member><member>VPN</member></from><to><member>WAN</member><member>VPN</member></to>"
        "<source><member>any</member></source><destination><member>any</member></destination>"
        "<application><member>any</member></application><service><member>any</member></service>"
        "<action>allow</action>",
    )

    # 12. Commit (etapa obrigatoria e explicita no PAN-OS)
    api_commit()


if __name__ == "__main__":
    aplicar_configuracao()
