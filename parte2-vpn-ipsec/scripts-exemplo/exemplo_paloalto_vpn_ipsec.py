"""
Exemplo de automacao (item OPCIONAL da Parte 2): configuracao de VPN IPSec no
lado Palo Alto via PAN-OS XML API.

STATUS: script CONCEITUAL, NAO EXECUTADO. Neste laboratorio, o PA-VM nao
detectou nenhuma interface de dataplane (ethernet1/1, ethernet1/2) mesmo apos
reconfiguracao de adapters e reserva de CPU/memoria no ESXi - ver README.md
desta pasta para o diagnostico completo. Sem interfaces, nenhum dos comandos
abaixo pode ser aplicado de fato neste ambiente.

O script segue a mesma logica descrita no plano (secao 3, "No Palo Alto via
XML/REST API") e serve como referencia de como a automacao seria feita caso
o ambiente estivesse funcional.
"""
import os
import urllib.parse
import urllib.request
import ssl

PA_HOST = os.environ.get("PA_HOST", "192.168.1.22")
PA_API_KEY = os.environ["PA_API_KEY"]  # gerado via keygen (usuario/senha) antes de rodar este script

BASE_URL = f"https://{PA_HOST}/api/"

# Parametros da VPN (ver plano_vpn_ipsec_fortigate_paloalto.md secao 1)
WAN_INTERFACE = "ethernet1/1"
LAN_INTERFACE = "ethernet1/2"
LAN_LOCAL_IP = "192.168.20.1/24"
WAN_LOCAL_IP = "192.0.2.2/29"
REMOTE_GATEWAY = "192.0.2.1"  # WAN do Fortigate
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
    vsys_xpath = "/config/devices/entry/vsys/entry[@name='vsys1']"

    # 1. Interfaces (dataplane) - BLOQUEADO neste lab (0 interfaces detectadas)
    api_set(
        f"{vsys_xpath}/import/network/interface",
        f"<member>{WAN_INTERFACE}</member><member>{LAN_INTERFACE}</member>",
    )
    api_set(
        f"/config/devices/entry/network/interface/ethernet/entry[@name='{WAN_INTERFACE}']",
        f"<layer3><ip><entry name='{WAN_LOCAL_IP}'/></ip></layer3>",
    )
    api_set(
        f"/config/devices/entry/network/interface/ethernet/entry[@name='{LAN_INTERFACE}']",
        f"<layer3><ip><entry name='{LAN_LOCAL_IP}'/></ip></layer3>",
    )

    # 2. Zonas
    api_set(f"{vsys_xpath}/zone/entry[@name='untrust']", f"<network><layer3><member>{WAN_INTERFACE}</member></layer3></network>")
    api_set(f"{vsys_xpath}/zone/entry[@name='trust']", f"<network><layer3><member>{LAN_INTERFACE}</member></layer3></network>")

    # 3. Interface de tunel logica
    api_set(
        "/config/devices/entry/network/interface/tunnel/units/entry[@name='tunnel.1']",
        f"<layer3><ip><entry name='{TUNNEL_IP}'/></ip></layer3>",
    )
    api_set(f"{vsys_xpath}/zone/entry[@name='vpn']", "<network><layer3><member>tunnel.1</member></layer3></network>")

    # 4. IKE Crypto Profile (Phase 1)
    api_set(
        "/config/devices/entry/network/ike/crypto-profiles/ike-crypto-profiles/entry[@name='IKE-FORTIGATE']",
        "<encryption><member>aes-256-cbc</member></encryption>"
        "<hash><member>sha256</member></hash>"
        "<dh-group><member>group14</member></dh-group>"
        "<lifetime><hours>8</hours></lifetime>",
    )

    # 5. IKE Gateway
    api_set(
        f"{vsys_xpath}/network/ike/gateway/entry[@name='IKE-GW-FORTIGATE']",
        f"<authentication><pre-shared-key><key>{PSK}</key></pre-shared-key></authentication>"
        f"<protocol><ikev2><ike-crypto-profile>IKE-FORTIGATE</ike-crypto-profile></ikev2></protocol>"
        f"<local-address><interface>{WAN_INTERFACE}</interface></local-address>"
        f"<peer-address><ip>{REMOTE_GATEWAY}</ip></peer-address>",
    )

    # 6. IPSec Crypto Profile (Phase 2)
    api_set(
        "/config/devices/entry/network/ike/crypto-profiles/ipsec-crypto-profiles/entry[@name='IPSEC-FORTIGATE']",
        "<esp><encryption><member>aes-256-cbc</member></encryption>"
        "<authentication><member>sha256</member></authentication></esp>"
        "<dh-group>group14</dh-group>"
        "<lifetime><hours>1</hours></lifetime>",
    )

    # 7. IPSec Tunnel
    api_set(
        f"{vsys_xpath}/network/tunnel/ipsec/entry[@name='TUNNEL-FORTIGATE']",
        "<auto-key><ike-gateway><entry name='IKE-GW-FORTIGATE'/></ike-gateway>"
        "<ipsec-crypto-profile>IPSEC-FORTIGATE</ipsec-crypto-profile></auto-key>"
        "<tunnel-interface>tunnel.1</tunnel-interface>",
    )

    # 8. Rota estatica
    api_set(
        f"{vsys_xpath}/network/virtual-router/entry[@name='default']/routing-table/ip/static-route/entry[@name='to-fortigate-lan']",
        "<destination>192.168.10.0/24</destination><interface>tunnel.1</interface>",
    )

    # 9. Politica de seguranca
    api_set(
        f"{vsys_xpath}/rulebase/security/rules/entry[@name='LAN-VPN']",
        "<from><member>trust</member></from><to><member>vpn</member></to>"
        "<source><member>any</member></source><destination><member>any</member></destination>"
        "<application><member>any</member></application><service><member>any</member></service>"
        "<action>allow</action>",
    )

    # 10. Commit (etapa obrigatoria e explicita no PAN-OS)
    api_commit()


if __name__ == "__main__":
    raise SystemExit(
        "Script conceitual - nao executar sem interfaces de dataplane detectadas "
        "(ver STATUS_LAB_VPN.md). Remova este guard apos resolver o bloqueio de "
        "hardware/licenca do PA-VM."
    )
