# Status do laboratório de simulação VPN IPSec (bônus, Parte 2)

**Item opcional da Parte 2** — demonstração de automação (scripts + evidências)
contra equipamento real: um **FortiGate físico** (FortiWiFi-60C) e um **Palo
Alto PA-VM** (PAN-OS 11.2.5). O túnel IPSec foi **estabelecido com sucesso**
nos dois lados (IKE SA + IPsec SA `established`/`active`), com tráfego ESP
real confirmado.

## Resumo em uma frase

Os dois lados (**Palo Alto PA-VM** e **FortiGate físico**) foram configurados
via automação (API XML do PAN-OS + SSH/CLI via Netmiko) — interfaces, zonas,
Phase1, Phase2, interface de túnel e políticas de segurança — e o túnel
**subiu de verdade**: IKE SA e IPsec SA `established` nos dois lados, e ping
através do overlay do túnel (`169.255.1.1` ↔ `169.255.1.2`) com 0% de perda.
Isso confirma, na prática, que os parâmetros do documento oficial
(IKEv2/AES-256/SHA-256/DH14) funcionam de ponta a ponta entre um FortiGate e
um Palo Alto reais.

Uma tentativa anterior, com um FortiGate **virtual** (FortiGate-VM64-KVM)
sem licença paga, não conseguia estabelecer o túnel — ver seção "Histórico"
no fim deste arquivo. Trocar para hardware físico resolveu o problema,
confirmando que o bloqueio era da licença da VM, não do plano documentado.

## Arquivos desta pasta

- `exemplo_paloalto_vpn_ipsec.py` — aplica a config do lado Palo Alto via API XML (executado)
- `exemplo_fortigate_vpn_ipsec.py` — aplica a config do lado Fortigate via SSH/CLI (executado)
- `teste_conectividade_vpn.py` — checa status do túnel nos dois lados e só tenta
  ping se ambos reportarem SA up (estratégia de validação da seção 5 do plano
  oficial)
- `evidencias/` — prints do PA-VM, do FortiGate físico e o diagrama de
  topologia atual; a tentativa anterior (FortiGate virtual, sem licença) fica
  preservada em `evidencias/tentativa-anterior-fortigate-vm/`

## Ambiente

- **Palo Alto**: PA-VM (PAN-OS 11.2.5) rodando no EVE-NG, interface de dados
  `ethernet1/1` bridgeada via um nó Cloud do EVE-NG até a rede física real
  (a mesma usada pela interface de management) — `10.10.1.202/24`
- **FortiGate**: físico, modelo **FortiWiFi-60C** (serial `FWF60C3G13003764`,
  FortiOS v5.2.0), interface `wan1` — `10.10.90.7/24`
- **Roteamento**: as duas pontas ficam em sub-redes diferentes
  (`10.10.90.0/24` e `10.10.1.0/24`), conectadas pela rede/roteamento já
  existente no laboratório físico — não é um link ponto a ponto isolado como
  na tentativa anterior. Isso exigiu uma rota estática default explícita no
  roteador virtual do Palo Alto (ver "Detalhes técnicos" abaixo)
- **Túnel**: rede `169.255.1.0/30` — FortiGate `169.255.1.1/32` (com
  `remote-ip 169.255.1.2`) e Palo Alto `tunnel.1` — `169.255.1.2/30`
- Sem segmento de LAN atrás de nenhum dos dois firewalls (escopo
  simplificado: o objetivo era validar SA up e tráfego pelo túnel, não
  tráfego de uma rede de usuário real)

Ver `evidencias/topologia.png` (captura do canvas do EVE-NG mostrando o
Palo Alto comunicando com o FortiGate físico via o nó Cloud).

## O que foi aplicado e confirmado (Palo Alto PA-VM, PAN-OS 11.2.5)

Via API XML do PAN-OS (`https://10.10.1.201/api/`), com commit confirmado
("Configuration committed successfully"):

| Item | Valor |
|---|---|
| Interface `ethernet1/1` | Layer3, IP `10.10.1.202/24`, zona `WAN`, management profile `allow-ping` |
| Interface de túnel `tunnel.1` | IP `169.255.1.2/30`, zona `VPN`, management profile `allow-ping` |
| Roteador virtual `default` | rota estática `0.0.0.0/0` via `10.10.1.1` (interface `ethernet1/1`) |
| IKE Crypto Profile `IKE-ML` | AES-256-CBC / SHA-256 / DH Group 14 |
| IPSec Crypto Profile `IPSEC-ML` | ESP AES-256-CBC / SHA-256 / PFS DH14 |
| IKE Gateway `IKE-GW-FGT` | IKEv2, local `10.10.1.202` (ethernet1/1), peer `10.10.90.7`, PSK |
| IPSec Tunnel `IPSEC-TUN-FGT` | liga `tunnel.1` ao IKE Gateway, usa `IPSEC-ML` |
| Política de segurança `ALLOW-VPN-LAB` | permite tráfego entre zonas `WAN` e `VPN` (hit count real: 59) |

Config idêntica aos parâmetros do documento oficial
(`plano_vpn_ipsec_fortigate_paloalto.md`, seção 1: IKEv2/AES-256/SHA-256/DH14).

## O que foi aplicado e confirmado (FortiGate físico, FortiWiFi-60C, FortiOS v5.2.0)

Via SSH/CLI (Netmiko), confirmado por `get vpn ipsec tunnel details`:

| Item | Valor |
|---|---|
| Phase1 `VPN-PaloAlto` | interface `wan1`, IKEv2, `aes256-sha256`, DH grupo 14, peer `10.10.1.202`, PSK |
| Phase2 `VPN-PaloAlto-p2` | `aes256-sha256`, PFS habilitado, DH grupo 14 |
| Interface de túnel `VPN-PaloAlto` | IP `169.255.1.1/32`, `remote-ip 169.255.1.2` |
| Políticas de firewall | 2 regras (`wan1` ↔ `VPN-PaloAlto`), accept/all |
| Rota conectada | `169.255.1.1/32` e `169.255.1.2/32` via `VPN-PaloAlto` (criada automaticamente após o túnel subir) |

Diferente da tentativa anterior (FortiGate-VM sem licença), esse hardware
físico **aceitou `aes256-sha256`/DH14 sem nenhuma rejeição** — os mesmos
parâmetros recomendados no documento oficial, sem precisar de nenhum
algoritmo mais fraco.

## Resultado: túnel estabelecido com sucesso

- **FortiGate** — `IKE SA: created 1/1 established 1/1` e `IPsec SA:
  created 1/1 established 1/1`, proposal `aes256-sha256`; GUI mostra
  `VPN-PaloAlto` com status **Up** e contadores de tráfego reais (>0 bytes)
- **Palo Alto** — IKE SA `role Resp, algo PSK/DH14/AES256-CBC/SHA256`;
  IPsec SA `proto ESP, enc A256, hash SHA256, dh DH14`; `show vpn flow`
  reporta `state: active`; GUI mostra bolinha verde em `Tunnel Info` e
  `IKE Info` na lista de IPSec Tunnels
- **Tráfego real confirmado**: ping entre os IPs do túnel (`169.255.1.1`
  ↔ `169.255.1.2`) com **0% de perda**, e o contador `rx(pkt,err)` do
  FortiGate incrementando de fato — não é só SA up, é tráfego ESP
  criptografado passando pelo túnel
- **Log do Palo Alto** (`Monitor → System`) confirma a negociação:
  `IKEv2 IKE SA negotiation is succeeded as responder` seguido de
  `IKEv2 child SA negotiation is succeeded` — ver
  `evidencias/palo-alto/11-log-ike-sa-established.png`

### Detalhes técnicos descobertos durante a automação real

Três obstáculos reais (não relacionados ao plano documentado, mas ao
ambiente de laboratório) foram identificados e corrigidos durante a
automação:

1. **Interface de dados do PA-VM não aparecia** (`show interface hardware`
   vazio) até o node do PA-VM levar um **stop/start completo** no EVE-NG —
   um hot-add de vNIC sozinho não bastou.
2. **Roteador virtual "default" do PAN-OS sem rota** para a rede do
   FortiGate: o gateway de management do PAN-OS é uma tabela de rotas
   **completamente separada** da tabela de rotas do dataplane. Sem uma rota
   estática default explícita no roteador virtual `default`, o Palo Alto
   recebia o tráfego do FortiGate mas não conseguia responder — 100% de
   perda de pacote mesmo com L2/L3 e ARP corretos.
3. **Interfaces de dados do PAN-OS não respondem a ping por padrão** — foi
   necessário anexar um Interface Management Profile (`allow-ping`) tanto em
   `ethernet1/1` quanto em `tunnel.1` para permitir ICMP de diagnóstico
   (não é necessário para o túnel funcionar, só para testar com ping).

## Evidências

**FortiGate físico (`evidencias/fortigate/`)**:
- `01-ipsec-tunnel-status-up.png` — VPN-PaloAlto, status **Up**, tráfego real (780/840 bytes)
- `02-phase1-phase2-config.png` — Phase1 (AES256-SHA256/DH14/IKEv2) e Phase2 Selectors
- `03-firewall-policies.png` — as 2 políticas `wan1` ↔ `VPN-PaloAlto`, accept
- `04-routing-table.png` — rotas conectadas `169.255.1.1/32` e `169.255.1.2/32` via `VPN-PaloAlto`

**Palo Alto (`evidencias/palo-alto/`)**:
- `01-interface-ethernet1-1.png` — ethernet1/1, Layer3, `10.10.1.202/24`, zona WAN
- `02-zonas-wan-vpn.png` — zonas WAN (ethernet1/1) e VPN (tunnel.1)
- `03-virtual-router-interfaces.png` — roteador virtual `default` com as 2 interfaces + 1 rota estática
- `04-ike-gateway-list.png` — IKE-GW-FGT, peer `10.10.90.7`, ikev2
- `05-ike-gateway-detail.png` — detalhe do gateway (PSK, local/peer address, crypto profile)
- `06-ike-crypto-profile.png` — IKE-ML: aes-256-cbc/sha256/group14
- `07-ipsec-crypto-profile.png` — IPSEC-ML: aes-256-cbc/sha256/group14
- `08-ipsec-tunnel-status-up.png` — IPSEC-TUN-FGT, **status verde (Tunnel Info e IKE Info up)**
- `09-virtual-router-route-table.png` — tabela de rotas real, incluindo a rota default `0.0.0.0/0 via 10.10.1.1` e a rota conectada `169.255.1.0/30 via tunnel.1`
- `10-security-policy-allow-vpn-lab.png` — ALLOW-VPN-LAB, hit count 59 (tráfego real)
- `11-log-ike-sa-established.png` — log de sistema confirmando IKE SA e child SA estabelecidos

**Topologia**: `evidencias/topologia.png` — captura do canvas do EVE-NG.

## Recomendação

Esse resultado demonstra o plano documentado funcionando de ponta a ponta em
equipamento real de dois fabricantes diferentes — não apenas a automação
isolada de cada lado (que já tinha sido demonstrada na tentativa anterior),
mas o túnel de fato operante, com tráfego passando. Reforça também, na
prática, o ponto da seção 4 do documento oficial sobre riscos de
compatibilidade multi-fabricante: o bloqueio real não era técnico
(algoritmos incompatíveis), mas comercial (licenciamento da VM) — uma vez
removida essa variável, o mesmo plano funcionou sem nenhum ajuste.

---

## Histórico (tentativas anteriores)

**ESXi (descartado)**: tentativa inicial rodou em ESXi (Host Client). O PA-VM
(PAN-OS 11.1.6-h7) nunca detectou interfaces de dataplane (`show interface
hardware` vazio) por causa de `vm-license: none` bloqueando o dataplane
inteiro nessa versão específica — sem contorno de configuração possível.
Migramos para EVE-NG, onde o PA-VM (PAN-OS 11.2.5) funciona normalmente
mesmo sem licença (bloqueio era específico da build 11.1.6-h7, não uma regra
geral do PAN-OS).

**FortiGate virtual no EVE-NG (descartado)**: com os dois lados configurados
e commitados, o túnel não subia (SA down) porque o FortiGate-VM, sem licença
paga (mesmo a licença de avaliação permanente/gratuita), só suporta baixa
criptografia (DES) — confirmado na documentação oficial da Fortinet
(preservada em `evidencias/tentativa-anterior-fortigate-vm/05-fortinet-doc-licenca-low-encryption.png`).
O PAN-OS recusa DES simples como algoritmo válido, então não havia proposta
em comum. Trocamos a imagem do Fortigate no EVE-NG várias vezes (v6.0,
v6.2.3, v6.4.6, v7.0.3, v7.6.7) tentando encontrar uma versão sem essa
restrição — sem sucesso (a documentação oficial confirma que a restrição é
da licença, não da build, então nenhuma imagem sem licença paga resolveria
isso). Evidência completa dessa tentativa (interfaces, crypto profiles,
logs de erro `no proposal chosen`) preservada em
`evidencias/tentativa-anterior-fortigate-vm/`.

**Resolução**: conectar um FortiGate **físico** (FortiWiFi-60C) à rede,
substituindo a VM, eliminou a restrição de licença — o mesmo plano
(AES-256/SHA-256/DH14) funcionou sem nenhuma alteração. Ver seções acima.
