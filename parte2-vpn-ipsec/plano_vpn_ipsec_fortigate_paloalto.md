# Plano de Automação — VPN IPSec entre Fortigate e Palo Alto

## Objetivo

Documentar o planejamento técnico para automatizar, via script, a configuração de um
túnel VPN IPSec site-to-site entre um firewall **Fortigate** e um firewall **Palo Alto**,
dispositivos de fabricantes diferentes com modelos de configuração distintos.

Este documento cobre parâmetros, ferramentas, passos lógicos de automação, desafios de
um ambiente heterogêneo, e estratégia de validação/alertas. Não é esperada uma simulação
funcional (é bônus, conforme "Considerações Adicionais" do desafio).

---

## 1. Definição de Parâmetros

### Topologia de exemplo

```
[Rede Local A]                                              [Rede Local B]
192.168.10.0/24                                              192.168.20.0/24
      |                                                             |
  [Fortigate]  ---- Internet ----  túnel IPSec  ----  [Palo Alto]
  WAN: 203.0.113.10                                    WAN: 198.51.100.20
```

| Parâmetro | Fortigate | Palo Alto |
|---|---|---|
| IP WAN (peer público) | `203.0.113.10` | `198.51.100.20` |
| Rede local protegida | `192.168.10.0/24` | `192.168.20.0/24` |
| Rede de túnel (ponto a ponto) | `169.255.1.1/30` | `169.255.1.2/30` |

A rede de túnel `169.255.1.0/30` fornece apenas 2 endereços utilizáveis, um para cada
extremidade — adequada para uma interface de túnel roteada (VTI/tunnel interface), em vez
de VPN somente baseada em política.

### Propostas de Phase 1 (IKE) — devem ser idênticas nos dois lados

| Parâmetro | Valor proposto |
|---|---|
| Versão IKE | IKEv2 |
| Autenticação | Pre-shared key (PSK) |
| Criptografia | AES-256 |
| Hash | SHA-256 |
| Grupo Diffie-Hellman | Group 14 (2048-bit) |
| Lifetime | 28800 segundos (8h) |

### Propostas de Phase 2 (IPSec) — devem ser idênticas nos dois lados

| Parâmetro | Valor proposto |
|---|---|
| Protocolo | ESP |
| Criptografia | AES-256 |
| Hash (autenticação) | SHA-256 |
| PFS (Perfect Forward Secrecy) | Group 14 |
| Lifetime | 3600 segundos (1h) |

**Observação importante:** os algoritmos e grupos DH acima precisam ser suportados por
ambos os fabricantes com a mesma nomenclatura interna — ver seção "Considerações
Específicas" sobre diferenças de rotulagem entre Fortigate e Palo Alto.

---

## 2. Identificação de Ferramentas/APIs

| Dispositivo | Opção de automação | Observações |
|---|---|---|
| **Fortigate** | FortiOS REST API | API nativa, autenticação via token ou usuário/senha, payloads em JSON. Endpoint típico: `https://<ip>/api/v2/cmdb/...` |
| **Fortigate** | SSH + CLI script | Alternativa via Netmiko/Paramiko, útil se a API REST não estiver disponível na licença/versão. |
| **Palo Alto** | PAN-OS XML API | API nativa baseada em XML, autenticação via API key. Endpoint típico: `https://<ip>/api/?type=config&action=set&...` |
| **Palo Alto** | PAN-OS REST API | Disponível a partir de versões mais recentes do PAN-OS, alternativa mais moderna ao XML API. |
| **Gerenciamento centralizado** | FortiManager (Fortigate) / Panorama (Palo Alto) | Em ambientes com múltiplos dispositivos, a automação poderia mirar o gerenciador central em vez do firewall individualmente — fora do escopo deste desafio pontual, mas relevante para produção. |
| **Bibliotecas Python sugeridas** | `requests` (REST genérico), `pan-os-python` (SDK oficial da Palo Alto), `paramiko`/`netmiko` (SSH), `xml.etree.ElementTree` (montagem de payloads XML) | |

---

## 3. Passos de Automação (lógica do script)

### No Fortigate (via REST API)

1. Autenticar na API (obter token/sessão).
2. Criar objeto de endereço (address object) para a rede local remota (Palo Alto).
3. Criar a Phase 1 (`vpn.ipsec/phase1-interface`): peer IP, PSK, propostas IKE, interface
   WAN de saída.
4. Criar a Phase 2 (`vpn.ipsec/phase2-interface`): vincular à Phase 1, definir proposals,
   PFS, redes de interesse (proxy-id ou modo de rota).
5. Criar/associar interface de túnel com IP da rede `169.255.1.0/30`.
6. Criar rota estática apontando a rede remota (`192.168.20.0/24`) via interface de
   túnel.
7. Criar política de firewall permitindo tráfego entre as redes locais e remotas através
   da interface de túnel (nos dois sentidos, se necessário).
8. Salvar/aplicar (commit implícito na maioria das chamadas REST do FortiOS).

### No Palo Alto (via XML/REST API)

1. Autenticar (obter API key).
2. Criar objeto de endereço para a rede local remota (Fortigate).
3. Criar o IKE Crypto Profile (Phase 1: criptografia, hash, DH group, lifetime).
4. Criar o IPSec Crypto Profile (Phase 2: criptografia, hash, PFS, lifetime).
5. Criar o IKE Gateway: peer IP, PSK, interface local, crypto profile referenciado.
6. Criar a interface de túnel lógica (`tunnel.X`) com o IP da rede `169.255.1.0/30`.
7. Criar o IPSec Tunnel: vincular IKE Gateway, interface de túnel, IPSec crypto profile.
8. Criar rota estática apontando a rede remota via a interface de túnel.
9. Criar política de segurança (Security Policy) permitindo o tráfego entre as zonas
   envolvidas.
10. Commit da configuração (etapa explícita e obrigatória no PAN-OS, diferente do
    FortiOS).

### Orquestração pelo script

O script de automação deveria rodar essas duas sequências (Fortigate e Palo Alto) de
forma coordenada — idealmente com validação de que a Phase 1/Phase 2 de um lado é
espelho compatível do outro **antes** de aplicar em ambos, evitando um túnel
parcialmente configurado.

---

## 4. Considerações Específicas (ambiente heterogêneo)

- **Terminologia divergente**: o que o Fortigate chama de "Phase 1/Phase 2" e "proxy-id",
  o Palo Alto separa em "IKE Gateway" + "IKE Crypto Profile" e "IPSec Tunnel" + "IPSec
  Crypto Profile". O script precisa de um mapeamento explícito entre os conceitos.
- **Formato de payload diferente**: FortiOS REST usa JSON; PAN-OS API tradicional usa
  XML (a REST API mais nova do PAN-OS também aceita JSON, mas nem toda operação está
  coberta). O script precisaria de duas camadas de serialização distintas.
- **Autenticação diferente**: Fortigate tipicamente usa usuário/senha ou token de API
  fixo; Palo Alto usa uma API key gerada a partir de usuário/senha, que pode expirar e
  precisar ser renovada.
- **Compatibilidade de algoritmos**: embora ambos suportem AES-256/SHA-256/DH Group 14,
  é preciso confirmar a licença e a versão de software de cada dispositivo — nem toda
  combinação de proposta está disponível em todas as versões.
- **Commit explícito no Palo Alto**: diferente do Fortigate (onde a alteração normalmente
  já é aplicada na chamada REST), o PAN-OS exige uma chamada de commit separada — o
  script precisa tratar isso como uma etapa distinta e verificar o status do commit
  (que é assíncrono).
- **Modo de política vs. modo de rota**: Fortigate suporta VPN baseada em política
  (policy-based) ou em rota (route-based); Palo Alto trabalha nativamente em modo de
  rota via interface de túnel. Para evitar incompatibilidade, o planejamento aqui já
  assume **modo de rota (route-based)** dos dois lados, com a rede `169.255.1.0/30`
  fazendo esse papel.

---

## 5. Validação de Configuração e Alertas

### Como verificar se a VPN subiu corretamente

**No Fortigate:**
- API REST: `GET /api/v2/monitor/vpn/ipsec` retorna o status de cada túnel (up/down),
  contadores de pacotes.
- CLI equivalente: `get vpn ipsec tunnel summary` / `diagnose vpn tunnel list`.

**No Palo Alto:**
- API XML: operação `<show><vpn><ike-sa></ike-sa></vpn></show>` e
  `<show><vpn><ipsec-sa></ipsec-sa></vpn></show>` retornam o status das SAs (security
  associations) ativas.
- CLI equivalente: `show vpn ike-sa` / `show vpn ipsec-sa`.

### Estratégia de validação proposta

1. Após aplicar a configuração em ambos os firewalls, aguardar um intervalo curto
   (ex: 10-15s) para a negociação IKE ocorrer.
2. Consultar o status do túnel em cada dispositivo via API/CLI.
3. Comparar o resultado esperado (túnel "up", SA estabelecida) com o resultado real.
4. Se o túnel não subir em um lado, ou os parâmetros da Phase 1/Phase 2 não baterem
   entre os dois fabricantes (ex: mismatch de proposta), reportar isso como divergência.

### Estratégia de alertas

- **Alerta de configuração**: se a chamada de API para criar objetos/políticas falhar
  (erro HTTP diferente de 200, ou corpo de resposta com campo de erro), o script deve
  interromper a sequência e reportar em qual etapa falhou (ex: "Falha ao criar IKE
  Gateway no Palo Alto: erro X").
- **Alerta de divergência pós-aplicação**: se a configuração foi aceita por ambos os
  dispositivos mas o túnel não sobe (SA não estabelecida), o script deve reportar isso
  separadamente — indica problema de compatibilidade de parâmetros ou de conectividade
  de rede (não é erro de sintaxe da automação).
- **Canal do alerta**: no contexto deste desafio, o alerta seria exibido na saída do
  script (log estruturado); em um cenário de produção, poderia ser estendido para
  webhook (Slack/Teams) ou sistema de monitoramento (ex: enviar métrica para um SIEM).

---

## 6. Resumo do fluxo completo

```
1. Validar parâmetros de entrada (IPs, PSK, redes)
        |
2. Aplicar configuração no Fortigate (objetos, Phase1, Phase2, política, rota)
        |
3. Aplicar configuração no Palo Alto (objetos, IKE Gateway, IPSec Tunnel, política, rota, commit)
        |
4. Aguardar negociação IKE
        |
5. Consultar status do túnel em ambos os lados (API)
        |
6. Comparar resultado esperado x real
        |
7. Reportar sucesso ou alerta de divergência
```

---

## 7. Referência de Aplicação — Automação (CLI/Script) e Verificação Manual (GUI)

O entregável deste desafio é a **automação** (script/API) — é isso que está
implementado em [`scripts-exemplo/`](scripts-exemplo/) e é o que as colunas
**CLI/Script** abaixo documentam campo a campo. As colunas **GUI** aparecem
**apenas como referência de verificação manual** (útil para conferir na tela o
que a automação aplicou, ou para troubleshooting) — não são um caminho de
entrega alternativo ao script.

**Nota sobre a validação:** as colunas do **Fortigate** foram testadas e
validadas no laboratório (ver [`scripts-exemplo/README.md`](scripts-exemplo/README.md)).
As colunas do **Palo Alto** seguem a sintaxe oficial do PAN-OS, mas não puderam
ser executadas neste laboratório (interfaces de dataplane não detectadas) —
são conceituais. Os valores abaixo são os mesmos da topologia de exemplo da
seção 1 e dos nomes de objeto usados em `scripts-exemplo/`, já preenchidos como
se fossem aplicados de fato.

### 7.1 Phase 1 (IKE)

| Parâmetro | Valor | Fortigate — CLI/Script (automação) | Palo Alto — CLI/Script (automação) | Fortigate — GUI (verificação) | Palo Alto — GUI (verificação) |
|---|---|---|---|---|---|
| Nome do túnel/gateway | `VPN-PaloAlto` (Fortigate) / `IKE-GW-FORTIGATE` (Palo Alto) | `edit "VPN-PaloAlto"` | `set network ike gateway IKE-GW-FORTIGATE` | VPN → IPsec Tunnels → Create New → Name: `VPN-PaloAlto` | Network → IKE Gateways → Add → Name: `IKE-GW-FORTIGATE` |
| Versão IKE | IKEv2 | `set ike-version 2` | `set network ike gateway IKE-GW-FORTIGATE protocol ikev2 ike-crypto-profile IKE-FORTIGATE` | Authentication → IKE Version: `2` | General → Version: `IKEv2 only mode` |
| Autenticação | Pre-shared key | `set psksecret TrocarPorChaveSegura123!` | `set network ike gateway IKE-GW-FORTIGATE authentication pre-shared-key key TrocarPorChaveSegura123!` | Authentication → Pre-shared Key: `TrocarPorChaveSegura123!` | General → Pre-shared Key: `TrocarPorChaveSegura123!` |
| Gateway remoto (peer) | `198.51.100.20` | `set remote-gw 198.51.100.20` | `set network ike gateway IKE-GW-FORTIGATE peer-address ip 203.0.113.10` | Network → Remote Gateway: Static IP Address `198.51.100.20` | General → Peer Address: `203.0.113.10`¹ |
| Interface local | `port2` (Fortigate) / `ethernet1/1` (Palo Alto) | `set interface "port2"` | `set network ike gateway IKE-GW-FORTIGATE local-address interface ethernet1/1` | Network → Interface: `port2` | General → Interface: `ethernet1/1` |
| Criptografia | AES-256 | `set proposal aes256-sha256` | `set network ike crypto-profiles ike-crypto-profiles IKE-FORTIGATE encryption aes-256-cbc` | Phase 1 Proposal → Encryption: `AES256` | IKE Crypto Profiles → Encryption: `aes-256-cbc` |
| Hash | SHA-256 | (mesmo campo do proposal acima) | `set network ike crypto-profiles ike-crypto-profiles IKE-FORTIGATE hash sha256` | Phase 1 Proposal → Authentication: `SHA256` | IKE Crypto Profiles → Authentication: `sha256` |
| Grupo DH | Group 14 | `set dhgrp 14` | `set network ike crypto-profiles ike-crypto-profiles IKE-FORTIGATE dh-group group14` | Phase 1 Proposal → DH Group: `14` | IKE Crypto Profiles → DH Group: `group14` |
| Lifetime | 28800s (8h) | `set keylife 28800` | `set network ike crypto-profiles ike-crypto-profiles IKE-FORTIGATE lifetime hours 8` | Phase 1 Proposal → Key Lifetime: `28800` | IKE Crypto Profiles → Key Lifetime: `8 hours` |

¹ Do ponto de vista do Palo Alto, o peer é o Fortigate — por isso o IP aqui é o
WAN do Fortigate (`203.0.113.10`), o inverso da linha do Fortigate (que aponta
para o WAN do Palo Alto, `198.51.100.20`).

### 7.2 Phase 2 (IPSec)

| Parâmetro | Valor | Fortigate — CLI/Script (automação) | Palo Alto — CLI/Script (automação) | Fortigate — GUI (verificação) | Palo Alto — GUI (verificação) |
|---|---|---|---|---|---|
| Nome | `VPN-PaloAlto-p2` (Fortigate) / `TUNNEL-FORTIGATE` (Palo Alto) | `edit "VPN-PaloAlto-p2"` | `set network tunnel ipsec TUNNEL-FORTIGATE` | Phase 2 Selectors → Add: `VPN-PaloAlto-p2` | Network → IPSec Tunnels → Add: `TUNNEL-FORTIGATE` |
| Protocolo | ESP | (implícito) | `set network ike crypto-profiles ipsec-crypto-profiles IPSEC-FORTIGATE esp encryption aes-256-cbc` | (implícito no IPsec Tunnel) | IPSec Crypto Profiles → ESP |
| Criptografia | AES-256 | `set proposal aes256-sha256` | `set network ike crypto-profiles ipsec-crypto-profiles IPSEC-FORTIGATE esp encryption aes-256-cbc` | Phase 2 → Encryption: `AES256` | IPSec Crypto Profiles → ESP → Encryption: `aes-256-cbc` |
| Hash (autenticação) | SHA-256 | (mesmo campo do proposal) | `set network ike crypto-profiles ipsec-crypto-profiles IPSEC-FORTIGATE esp authentication sha256` | Phase 2 → Authentication: `SHA256` | IPSec Crypto Profiles → ESP → Authentication: `sha256` |
| PFS | Group 14 | `set pfs enable` + `set dhgrp 14` | `set network ike crypto-profiles ipsec-crypto-profiles IPSEC-FORTIGATE dh-group group14` | Phase 2 → Enable PFS: `on`, DH Group: `14` | IPSec Crypto Profiles → DH Group: `group14` |
| Lifetime | 3600s (1h) | `set keylifeseconds 3600` | `set network ike crypto-profiles ipsec-crypto-profiles IPSEC-FORTIGATE lifetime hours 1` | Phase 2 → Key Lifetime: `3600` | IPSec Crypto Profiles → Lifetime: `1 hour` |
| Rede local | `192.168.10.0/24` | `set src-subnet 192.168.10.0 255.255.255.0` | `set network interface ethernet ethernet1/2 layer3 ip 192.168.10.1/24`² | Phase 2 → Local Address: `192.168.10.0/255.255.255.0` | (definida via zona `trust` + roteamento) |
| Rede remota | `192.168.20.0/24` | `set dst-subnet 192.168.20.0 255.255.255.0` | — | Phase 2 → Remote Address: `192.168.20.0/255.255.255.0` | (definida via zona `vpn` + roteamento) |

² Do lado Palo Alto, `192.168.10.0/24` é a rede **remota** (atrás do Fortigate);
o exemplo de IP de interface local do Palo Alto é `192.168.20.1/24` em
`ethernet1/2`.

### 7.3 Demais itens (interface de túnel, rota, política)

| Item | Valor | Fortigate — CLI/Script (automação) | Palo Alto — CLI/Script (automação) | Fortigate — GUI (verificação) | Palo Alto — GUI (verificação) |
|---|---|---|---|---|---|
| Interface de túnel (local) | Fortigate: `169.255.1.1/32`³ · Palo Alto: `169.255.1.2/30` | `config system interface` → `edit "VPN-PaloAlto"` → `set ip 169.255.1.1 255.255.255.255` → `set remote-ip 169.255.1.2 255.255.255.255` | `set network interface tunnel units tunnel.1 ip 169.255.1.2/30` | Network → Interfaces → `VPN-PaloAlto` → IP/Netmask: `169.255.1.1/255.255.255.255` | Network → Interfaces → Tunnel → Add `tunnel.1` → IPv4: `169.255.1.2/30` |
| Zona (Palo Alto) | `untrust` / `trust` / `vpn` | — | `set zone vpn network layer3 tunnel.1` | — (não aplicável no Fortigate) | Network → Zones → Add `untrust`/`trust`/`vpn` |
| Rota estática | Fortigate: destino `192.168.20.0/24` via `VPN-PaloAlto` · Palo Alto: destino `192.168.10.0/24` via `tunnel.1` | `config router static` → `edit 0` → `set dst 192.168.20.0 255.255.255.0` → `set device "VPN-PaloAlto"` | `set network virtual-router default routing-table ip static-route to-fortigate-lan destination 192.168.10.0/24 interface tunnel.1` | Network → Static Routes → Destination: `192.168.20.0/24`, Interface: `VPN-PaloAlto` | Network → Virtual Routers → `default` → Static Routes → Add `to-fortigate-lan` |
| Política de firewall/segurança | Fortigate: `LAN-to-PaloAlto` / `PaloAlto-to-LAN` · Palo Alto: `LAN-VPN` | `config firewall policy` → `edit 0` → `set srcintf "port3"` → `set dstintf "VPN-PaloAlto"` → `set srcaddr "LAN-FORTIGATE"` → `set dstaddr "LAN-PALOALTO"` → `set action accept` | `set rulebase security rules LAN-VPN from trust to vpn source any destination any application any service any action allow` | Policy & Objects → Firewall Policy → Create New: `LAN-to-PaloAlto` (port3 → VPN-PaloAlto) | Policies → Security → Add `LAN-VPN` (from `trust` to `vpn`) |
| Commit | — | (implícito) | `commit` | (implícito a cada alteração) | Commit (canto superior direito) |

³ O Fortigate exige máscara `/32` na interface de túnel, com o IP da outra
ponta em um campo `remote-ip` separado — diferente da notação `/30` usada como
simplificação na seção 1. Detalhe descoberto durante a automação real no
laboratório (ver `scripts-exemplo/exemplo_fortigate_vpn_ipsec.py`). O Palo Alto
aceita a notação `/30` normalmente na interface de túnel.
