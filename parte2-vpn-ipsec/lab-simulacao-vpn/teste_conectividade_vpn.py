"""
Script de teste de conectividade pelo tunel IPSec (item OPCIONAL da Parte 2).

Segue a "Estrategia de validacao proposta" descrita na secao 5 do plano
(../plano_vpn_ipsec_fortigate_paloalto.md): consulta o status do tunel
(IKE/IPSec SA) em cada fabricante, e so tenta um ping pelo tunel se os dois
lados reportarem SA estabelecida.

STATUS: EXECUTADO com sucesso contra o laboratorio real - FortiGate fisico
(FortiWiFi-60C) + Palo Alto PA-VM (PAN-OS 11.2.5). As duas checagens
(Fortigate via SSH/CLI, Palo Alto via API XML) sao funcionais, e o tunel
esta de fato up: o script reporta UP nos dois lados e confirma o ping pelo
overlay do tunel (ver STATUS_LAB_VPN.md para o resultado completo e a
tentativa anterior, com um FortiGate virtual sem licenca, onde o script
reportava corretamente a divergencia).
"""
import os
import re
import ssl
import subprocess
import urllib.parse
import urllib.request

from netmiko import ConnectHandler

FGT_HOST = os.environ.get("FGT_HOST", "10.10.90.7")
FGT_USER = os.environ.get("FGT_USER", "admin")
FGT_PASSWORD = os.environ["FGT_PASSWORD"]
FGT_TUNNEL_NAME = "VPN-PaloAlto"

PA_HOST = os.environ.get("PA_HOST", "10.10.1.201")
PA_API_KEY = os.environ["PA_API_KEY"]  # gerado via keygen antes de rodar este script
PA_TUNNEL_NAME = "IPSEC-TUN-FGT"

REMOTE_TUNNEL_IP = "169.255.1.2"  # IP da interface de tunel do lado Palo Alto

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def checar_fortigate():
    """Consulta o status real do tunel no Fortigate via SSH/CLI (Netmiko).

    A REST API HTTPS deste FortiOS nao completou o handshake TLS pelo
    curl/schannel do Windows neste ambiente (ver STATUS_LAB_VPN.md) - por
    isso a checagem usa CLI, igual ao script de aplicacao de config.
    """
    conn = ConnectHandler(
        device_type="fortinet",
        host=FGT_HOST,
        username=FGT_USER,
        password=FGT_PASSWORD,
    )
    saida = conn.send_command("get vpn ipsec tunnel summary")
    conn.disconnect()

    # Formato: 'VPN-PaloAlto' 10.0.0.2:0  selectors(total,up): 1/0  ...
    match = re.search(r"selectors\(total,up\):\s*(\d+)/(\d+)", saida)
    up = bool(match) and int(match.group(2)) > 0
    return {"up": up, "detalhe": saida.strip()}


def checar_palo_alto():
    """Consulta o status do tunel no Palo Alto via API XML (show vpn ike-sa).

    Uma IKE SA estabelecida aparece como <entry> com um <gwid> - tanto para
    IKEv1 (que tambem expoe <state>Mature</state>/<state>I2</state>) quanto
    para IKEv2 (que nao usa essa tag de state, so role/mode/algo). Checar a
    presenca de <gwid> cobre os dois casos; sem SA, a API retorna <result/>
    vazio.
    """
    params = {
        "type": "op",
        "key": PA_API_KEY,
        "cmd": "<show><vpn><ike-sa></ike-sa></vpn></show>",
    }
    url = f"https://{PA_HOST}/api/?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        corpo = resp.read().decode()

    up = "<gwid>" in corpo
    return {"up": up, "detalhe": corpo[:400]}


def testar_ping_pelo_tunel(destino=REMOTE_TUNNEL_IP, tentativas=3):
    """Tenta pingar o IP de tunel do lado remoto. So faz sentido se as duas
    pontas reportarem SA up - caso contrario o pacote nao tem pra onde ir."""
    resultado = subprocess.run(
        ["ping", "-n", str(tentativas), destino],
        capture_output=True,
        text=True,
        timeout=15,
    )
    sucesso = "TTL=" in resultado.stdout
    return {"sucesso": sucesso, "saida": resultado.stdout}


def main():
    print("=== Teste de conectividade pelo tunel IPSec ===\n")

    print("1. Consultando status do tunel no Fortigate (SSH/CLI)...")
    status_fgt = checar_fortigate()
    print(f"   Fortigate: {'UP' if status_fgt['up'] else 'DOWN'}\n{status_fgt['detalhe']}\n")

    print("2. Consultando status do tunel no Palo Alto (API XML)...")
    status_pa = checar_palo_alto()
    print(f"   Palo Alto: {'UP' if status_pa['up'] else 'DOWN'}\n")

    if not (status_fgt["up"] and status_pa["up"]):
        print("[ALERTA] Tunel nao esta up nos dois lados - conectividade nao sera testada.")
        print("Divergencias encontradas:")
        if not status_fgt["up"]:
            print(f"  - Fortigate: SA nao estabelecida ({FGT_TUNNEL_NAME})")
        if not status_pa["up"]:
            print(f"  - Palo Alto: SA nao estabelecida ({PA_TUNNEL_NAME})")
        raise SystemExit(1)

    print(f"3. Ambos os lados up - testando ping para {REMOTE_TUNNEL_IP}...")
    ping = testar_ping_pelo_tunel()
    if ping["sucesso"]:
        print("[OK] Conectividade pelo tunel confirmada.")
    else:
        print("[ALERTA] Tunel reportado como up, mas ping falhou - possivel problema de rota ou politica.")
        print(ping["saida"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
