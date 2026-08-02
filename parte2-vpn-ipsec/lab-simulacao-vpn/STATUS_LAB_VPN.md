# Status do laboratório de simulação VPN IPSec (bônus, Parte 2)

**Item opcional da Parte 2** — demonstração de automação (scripts + evidências)
contra um laboratório real (EVE-NG). O túnel não fica operante (ver seção
abaixo), mas a automação de ambos os lados e a estratégia de validação/alerta
são demonstradas com evidência real, não simulada.

## Resumo em uma frase

Os dois lados (**Palo Alto PA-VM** e **Fortigate**) foram configurados com
sucesso via automação (API XML do PAN-OS + SSH/CLI via Netmiko) — interfaces,
zonas, Phase1, Phase2, interface de túnel e políticas de segurança estão
aplicados e commitados dos dois lados. **O túnel não sobe (SA down)** porque o
FortiGate-VM, sem licença paga (só licença de avaliação, mesmo a
permanente/gratuita), só suporta baixa criptografia (DES) — confirmado na
documentação oficial da Fortinet — e o PAN-OS recusa DES simples. Não é erro
de configuração; é limitação de licenciamento (ver "Causa raiz definitiva"
abaixo).

## Arquivos desta pasta

- `exemplo_paloalto_vpn_ipsec.py` — aplica a config do lado Palo Alto via API XML (executado)
- `exemplo_fortigate_vpn_ipsec.py` — aplica a config do lado Fortigate via SSH/CLI (executado)
- `teste_conectividade_vpn.py` — checa status do túnel nos dois lados e só tenta
  ping se ambos reportarem SA up (estratégia de validação da seção 5 do plano
  oficial). **Executado contra o lab real**: reporta corretamente `DOWN` nos
  dois lados e sai com `exit code 1` — comportamento correto de alerta, dado
  que o túnel não está operante
- `evidencias/` — prints do PA-VM, do Fortigate, o diagrama de topologia e a
  documentação oficial da Fortinet sobre a licença de avaliação

## Ambiente

- **Plataforma**: EVE-NG (após descartar uma tentativa anterior em ESXi, ver
  seção "Histórico" no fim deste arquivo)
- **Topologia**: Fortigate `port2` (WAN-VPN) ligado ponto a ponto ao PA-VM
  `ethernet1/1`, rede `10.0.0.0/30`. Ambos também têm uma interface de
  management na mesma rede compartilhada (`10.10.1.0/24`), usada para
  acesso via API/SSH. Sem segmentos de LAN atrás dos firewalls (escopo
  simplificado combinado: só precisamos de SA up, sem tráfego real).
  Ver `evidencias/topologia.png`.

## O que foi aplicado e confirmado (Palo Alto PA-VM, PAN-OS 11.2.5)

Via API XML do PAN-OS (`https://10.10.1.78/api/`), com commit confirmado
("Configuration committed successfully"):

| Item | Valor |
|---|---|
| Interface `ethernet1/1` | Layer3, IP `10.0.0.2/30`, zona `WAN` |
| Interface de túnel `tunnel.1` | IP `169.255.1.2/30`, zona `VPN` |
| IKE Crypto Profile `IKE-ML` | AES-256-CBC / SHA-256 / DH Group 14 |
| IPSec Crypto Profile `IPSEC-ML` | ESP AES-256-CBC / SHA-256 / PFS DH14 |
| IKE Gateway `IKE-GW-FGT` | IKEv2, local `10.0.0.2` (ethernet1/1), peer `10.0.0.1`, PSK |
| IPSec Tunnel `IPSEC-TUN-FGT` | liga `tunnel.1` ao IKE Gateway, usa `IPSEC-ML` |
| Política de segurança `ALLOW-VPN-LAB` | permite tráfego entre zonas `WAN` e `VPN` |

Essa configuração segue exatamente os parâmetros do documento oficial
(`plano_vpn_ipsec_fortigate_paloalto.md`, seção 1: IKEv2/AES-256/SHA-256/DH14).
**Não foi alterada** — é a config correta e recomendada, e não deve ser
rebaixada para bater com a limitação do Fortigate.

## O que foi aplicado e confirmado (Fortigate, FortiGate-VM64-KVM v7.6.5)

Via SSH/CLI (Netmiko), confirmado por `get vpn ipsec tunnel summary`:

| Item | Valor |
|---|---|
| Phase1 `VPN-PaloAlto` | interface `port2`, IKEv2, peer `10.0.0.2`, PSK |
| Phase2 `VPN-PaloAlto-p2` | PFS habilitado, DH Group 14 |
| Interface de túnel `VPN-PaloAlto` | IP `169.255.1.1/32`, remote-ip `169.255.1.2/32` |
| Políticas de firewall | `WAN-to-PaloAlto` e `PaloAlto-to-WAN` (porta `port2` ↔ túnel) |

**Ressalva sobre o proposal**: essa instância de Fortigate roda em licença de
avaliação (não paga) — por isso só aceita propostas `des-*` em Phase1 **e**
Phase2 (`des-md5/sha1/sha256/sha384/sha512`), ver "Causa raiz definitiva"
abaixo. Testado exaustivamente: `3des-sha256`, `3des-md5`, `aes128-sha256`,
`aes256-sha256` — todos rejeitados com `command parse error`. Por isso o
Phase1/Phase2 do Fortigate usa `des-sha256`, diferente do `aes256-sha256` do
PA-VM.

## Por que o túnel não sobe: incompatibilidade real de criptografia

- **Fortigate**: só aceita **DES** em qualquer instância testada.
- **PAN-OS 11.2.5**: **recusa DES simples** como algoritmo válido
  (`'des' is not an allowed keyword`) — bloqueio de segurança da própria
  versão, não relacionado a licença.
- **Não existe proposta em comum** entre os dois softwares. O IKE (Phase1)
  nunca fecha; sem Phase1 não há Phase2, não há SA, não há túnel.
- O Palo Alto está com a configuração **correta e recomendada**
  (AES-256/SHA-256) — não precisa (e não deve) ser alterada.

### Causa raiz definitiva: licença de avaliação do FortiGate-VM, não a build/versão

Inicialmente diagnosticamos isso como uma característica de uma build
específica ("LENC"/export-restricted). **Confirmado depois, com a
documentação oficial da Fortinet** (`evidencias/05-fortinet-doc-licenca-low-encryption.png`),
que a causa é mais ampla e definitiva: qualquer FortiGate-VM sem uma
**licença paga** — incluindo a licença de avaliação gratuita permanente
("permanent evaluation VM license") — tem, por definição, **"support for
low encryption operation only"** (DES), independente da versão do firmware.

Confirmamos isso na prática: trocamos a imagem do Fortigate no EVE-NG
diversas vezes (v6.0, v6.2.3, v6.4.6, v7.0.3, v7.6.7) tentando encontrar uma
versão sem essa restrição — sem sucesso (em algumas tentativas o EVE-NG nem
chegou a bootar a imagem nova de fato, mesmo firmware/serial do node
anterior; problema de infraestrutura do próprio EVE-NG, fora do alcance do
Claude Code). Mas o documento oficial da Fortinet deixa claro que **nenhuma
versão resolveria isso**: a restrição de baixa criptografia é inerente à
licença de avaliação, não à build. Só uma licença FortiCare **paga**
(produção) remove essa limitação — a licença de avaliação permanente
gratuita mantém a mesma restrição.

Isso é análogo, em espírito, ao bloqueio de licença que travou o PA-VM no
ESXi (`vm-license: none`) — os dois fabricantes, neste laboratório, esbarram
em restrições de licenciamento que só se resolvem com uma conta
paga/autorizada no portal do fabricante, fora do escopo razoável para um
item bônus.

## Evidências (`evidencias/palo-alto/`, `evidencias/fortigate/`, `evidencias/topologia.png`)

**PA-VM (`evidencias/palo-alto/`)** — todos conferidos, batem com a config aplicada:
- [x] `01-zonas.png` — zonas WAN (ethernet1/1) e VPN (tunnel.1)
- [x] `02-interface-ethernet1-1.png` — ethernet1/1, Layer3, `10.0.0.2/30`
- [x] `03-interface-tunnel1.png` — tunnel.1, `169.255.1.2/30`, zona VPN
- [x] `04-ike-crypto-profile.png` — IKE-ML: aes-256-cbc/sha256/group14
- [x] `05-ipsec-crypto-profile.png` — IPSEC-ML: aes-256-cbc/sha256/group14
- [x] `06-ike-gateway.png` — IKE-GW-FGT, peer 10.0.0.1, local ethernet1/1 (10.0.0.2/30), ikev2
- [x] `07-ipsec-tunnel-status-inativo.png` — IPSEC-TUN-FGT, **Status: vermelho (Tunnel Info e IKE Info inativos)**
- [x] `08-security-policy.png` — ALLOW-VPN-LAB (WAN↔VPN, universal)
- [x] `09-log-erro-negociacao-ike.png` — **prova direta do erro**, ver citação abaixo

**Fortigate (`evidencias/fortigate/`)** — todos conferidos:
- [x] `01-ipsec-tunnel-status-down.png` — VPN-PaloAlto com ícone vermelho, Remote Gateway 10.0.0.2
- [x] `02-firewall-policy.png` — as duas regras (WAN-to-PaloAlto, PaloAlto-to-WAN), enabled
- [x] `03-ipsec-monitor-inactive.png` — Status: **Inactive**
- [x] `04-log-erro-negociacao.png` — ciclo repetido de `negotiate_error` / `IPsec phase 1 error`

**Documentação oficial**:
- [x] `05-fortinet-doc-licenca-low-encryption.png` — trecho da documentação
  oficial da Fortinet confirmando a causa raiz definitiva

### Citação direta do log (PA-VM, Monitor → System, 2026-08-01 18:49:39)

```
Event: ikev2-nego-enc-mismatch
[IKE-GW-FGT]: Configured encryption algorithm 'AES256-CBC' was not presented
in the IKE proposal. Please ensure that matching proposals are configured on
both sides.

Event: ikev2-nego-ike-start
IKEv2 IKE SA negotiation is started as responder, non-rekey. Initiated SA:
10.0.0.2[500]-10.0.0.1[500] SPI:07f21c0fd2236540:ac9d9ee491cd49d9.

Event: ike-generic-event
no proposal chosen.
```

Essa sequência se repete a cada ~30s (retry automático do Fortigate) nos dois
lados — confirmação direta e definitiva, nos logs de ambos os fabricantes, do
diagnóstico de incompatibilidade de algoritmos.

Bônus: o próprio Fortigate sinaliza no GUI (VPN → IPsec Tunnels → "Security
Rating Insights") os avisos **"Phase1 Interface Diffie Hellman Group"** e
**"Phase1 Interface Proposal"**, recomendando algoritmos mais fortes — ironia
útil de documentar: o fabricante que só permite DES (por licença) é o mesmo
que alerta que DES é fraco.

## Recomendação

Documentar isso como o resultado real do item bônus: a automação e a
configuração de ambos os lados funcionaram (ver tabelas acima), mas o
túnel não fica operante devido a uma **limitação de licenciamento**, não de
configuração — achado que reforça, na prática, o que a seção 4 do documento
oficial já previa como risco ("necessidade de mapear compatibilidade de
algoritmos entre os dois fabricantes"), mostrando que na prática esse risco
pode vir tanto de diferenças técnicas reais quanto de restrições comerciais
de licenciamento dos fabricantes. Isso é uma demonstração honesta e completa
da automação, não uma VPN operante — alinhado com o que o próprio enunciado
permite ("mesmo que de forma conceitual ou parcial"). Resolver de vez exigiria
uma licença FortiCare paga (Fortigate) e um auth-code de avaliação (Palo
Alto) — ambos fora do escopo razoável para um item bônus.

---

## Histórico (tentativas anteriores)

**ESXi (descartado)**: tentativa inicial rodou em ESXi (Host Client). O PA-VM
(PAN-OS 11.1.6-h7) nunca detectou interfaces de dataplane (`show interface
hardware` vazio) por causa de `vm-license: none` bloqueando o dataplane
inteiro nessa versão específica — sem contorno de configuração possível.
Migramos para EVE-NG, onde o PA-VM (PAN-OS 11.2.5) funciona normalmente
mesmo sem licença (bloqueio era específico da build 11.1.6-h7, não uma regra
geral do PAN-OS).

**Troca de imagem do Fortigate no EVE-NG (descartado)**: com a
incompatibilidade DES/AES identificada, tentamos trocar a imagem do
Fortigate por versões diferentes (v6.0, v6.2.3, v6.4.6, v7.0.3, v7.6.7) na
esperança de encontrar uma sem a restrição. Em várias tentativas o EVE-NG
sequer bootou a imagem nova de fato (mesmo firmware/serial do node
anterior — problema de infraestrutura do EVE-NG, fora do alcance do Claude
Code). Mas mesmo isso resolvido, **não haveria solução**: confirmado via
documentação oficial da Fortinet que a restrição de baixa criptografia é da
licença de avaliação, não da versão — nenhuma imagem sem licença paga teria
suporte a AES/3DES.
