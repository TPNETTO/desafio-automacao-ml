"""
Script de teste de conectividade pelo tunel IPSec (item OPCIONAL da Parte 2).

Segue a "Estrategia de validacao proposta" descrita na secao 5 do plano
(plano_vpn_ipsec_fortigate_paloalto.md): consulta o status do tunel (IKE/IPSec
SA) em cada fabricante via API, e so tenta um ping pelo tunel se os dois
lados reportarem SA estabelecida.

STATUS:
- Checagem do Fortigate: FUNCIONAL, roda de verdade contra a API REST.
- Checagem do Palo Alto: CONCEITUAL - ver exemplo_paloalto_vpn_ipsec.py e
  README.md desta pasta (PA-VM sem interfaces de dataplane detectadas).
- Ping pelo tunel: so e tentado se ambos os lados reportarem "up". Neste
  laboratorio isso nunca ocorre (Palo Alto nunca fica up), entao o script
  sempre reporta divergencia nesse ponto - o que e o comportamento correto
  e esperado dado o estado do ambiente.
"""
import json
import os
import ssl
import subprocess
import urllib.error
import urllib.request

FGT_HOST = os.environ.get("FGT_HOST", "192.168.1.1")
FGT_TOKEN = os.environ["FGT_API_TOKEN"]

PA_HOST = os.environ.get("PA_HOST", "192.168.1.22")
PA_API_KEY = os.environ.get("PA_API_KEY")  # opcional: sem key, a checagem do Palo Alto e pulada

TUNNEL_NAME = "VPN-PaloAlto"
REMOTE_TUNNEL_IP = "169.255.1.2"  # IP da interface de tunel do lado Palo Alto

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def checar_fortigate():
    """Consulta o status real do tunel no Fortigate via REST API."""
    url = f"https://{FGT_HOST}/api/v2/monitor/vpn/ipsec"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {FGT_TOKEN}")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            dados = json.loads(resp.read().decode())
    except urllib.error.HTTPError as erro:
        return {"up": False, "detalhe": f"erro HTTP {erro.code} ao consultar API"}

    for tunel in dados.get("results", []):
        if tunel.get("name") == TUNNEL_NAME:
            proxyid_ativo = any(
                p.get("status") == "up" for p in tunel.get("proxyid", [])
            )
            return {"up": proxyid_ativo, "detalhe": tunel}

    return {"up": False, "detalhe": f"tunel '{TUNNEL_NAME}' nao encontrado na resposta da API"}


def checar_palo_alto():
    """Consulta o status do tunel no Palo Alto via API XML (show vpn ike-sa)."""
    if not PA_API_KEY:
        return {"up": False, "detalhe": "PA_API_KEY nao definida - checagem pulada (ver README.md)"}

    url = (
        f"https://{PA_HOST}/api/?type=op&key={PA_API_KEY}"
        "&cmd=<show><vpn><ike-sa></ike-sa></vpn></show>"
    )
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            corpo = resp.read().decode()
    except urllib.error.HTTPError as erro:
        return {"up": False, "detalhe": f"erro HTTP {erro.code} ao consultar API"}

    # resposta XML simplificada: presenca de "<state>Mature</state>" indica SA ativa
    up = "<state>Mature</state>" in corpo
    return {"up": up, "detalhe": corpo[:300]}


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

    print("1. Consultando status do tunel no Fortigate...")
    status_fgt = checar_fortigate()
    print(f"   Fortigate: {'UP' if status_fgt['up'] else 'DOWN'}")

    print("2. Consultando status do tunel no Palo Alto...")
    status_pa = checar_palo_alto()
    print(f"   Palo Alto: {'UP' if status_pa['up'] else 'DOWN'} ({status_pa['detalhe']})\n")

    if not (status_fgt["up"] and status_pa["up"]):
        print("[ALERTA] Tunel nao esta up nos dois lados - conectividade nao sera testada.")
        print("Divergencias encontradas:")
        if not status_fgt["up"]:
            print(f"  - Fortigate: {status_fgt['detalhe']}")
        if not status_pa["up"]:
            print(f"  - Palo Alto: {status_pa['detalhe']}")
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
