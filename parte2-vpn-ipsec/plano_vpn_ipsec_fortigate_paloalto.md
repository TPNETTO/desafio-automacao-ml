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

## 7. Referência de Aplicação — GUI, CLI e Script/API

Tabela de consulta rápida: para cada parâmetro do túnel, como aplicá-lo pela GUI,
pela CLI, e o campo/endpoint equivalente usado nos scripts de automação (ver
[`scripts-exemplo/`](scripts-exemplo/)).

**Nota sobre as colunas:** as colunas do **Fortigate** foram testadas e validadas
no laboratório (ver [`scripts-exemplo/README.md`](scripts-exemplo/README.md)). As
colunas do **Palo Alto** seguem a sintaxe oficial do PAN-OS, mas não puderam ser
executadas neste laboratório (interfaces de dataplane não detectadas) — são
conceituais.

### 7.1 Phase 1 (IKE)

| Parâmetro | Valor | Fortigate — GUI | Fortigate — CLI/Script | Palo Alto — GUI | Palo Alto — CLI/Script |
|---|---|---|---|---|---|
| Versão IKE | IKEv2 | VPN → IPsec Tunnels → Create New → Authentication → IKE Version | `set ike-version 2` | Network → IKE Gateways → General → Version | `set network ike gateway <nome> protocol ikev2 ike-crypto-profile <perfil>` |
| Autenticação | Pre-shared key | VPN → IPsec Tunnels → Authentication → Pre-shared Key | `set psksecret <chave>` | Network → IKE Gateways → General → Pre-shared Key | `set network ike gateway <nome> authentication pre-shared-key key <chave>` |
| Gateway remoto | IP estático do peer | VPN → IPsec Tunnels → Network → Remote Gateway | `set remote-gw <ip>` | Network → IKE Gateways → General → Peer Address | `set network ike gateway <nome> peer-address ip <ip>` |
| Interface local | Interface WAN | VPN → IPsec Tunnels → Network → Interface | `set interface "<porta>"` | Network → IKE Gateways → General → Interface | `set network ike gateway <nome> local-address interface <interface>` |
| Criptografia | AES-256¹ | VPN → IPsec Tunnels → Phase 1 Proposal → Encryption | `set proposal aes256-sha256` | Network → IKE Crypto Profiles → Encryption | `set network ike crypto-profiles ike-crypto-profiles <perfil> encryption aes-256-cbc` |
| Hash | SHA-256 | (mesmo campo do proposal, combinado) | (mesmo campo) | Network → IKE Crypto Profiles → Authentication | `set network ike crypto-profiles ike-crypto-profiles <perfil> hash sha256` |
| Grupo DH | Group 14 | VPN → IPsec Tunnels → Phase 1 Proposal → DH Group | `set dhgrp 14` | Network → IKE Crypto Profiles → DH Group | `set network ike crypto-profiles ike-crypto-profiles <perfil> dh-group group14` |
| Lifetime | 28800s (8h) | VPN → IPsec Tunnels → Phase 1 Proposal → Key Lifetime | `set keylife 28800` | Network → IKE Crypto Profiles → Key Lifetime | `set network ike crypto-profiles ike-crypto-profiles <perfil> lifetime hours 8` |

¹ No laboratório, o firmware do Fortigate (build LENC/exportação restrita) só
aceita propostas `des-*` — foi usado `des-sha256` como exemplo funcional. Ver
nota em [`scripts-exemplo/README.md`](scripts-exemplo/README.md).

### 7.2 Phase 2 (IPSec)

| Parâmetro | Valor | Fortigate — GUI | Fortigate — CLI/Script | Palo Alto — GUI | Palo Alto — CLI/Script |
|---|---|---|---|---|---|
| Protocolo | ESP | (implícito no IPsec Tunnel) | (implícito) | Network → IPSec Crypto Profiles → ESP | `set network ike crypto-profiles ipsec-crypto-profiles <perfil> esp encryption aes-256-cbc` |
| Criptografia | AES-256¹ | VPN → IPsec Tunnels → Phase 2 Selectors → Encryption | `set proposal aes256-sha256` | Network → IPSec Crypto Profiles → ESP → Encryption | `set network ike crypto-profiles ipsec-crypto-profiles <perfil> esp encryption aes-256-cbc` |
| Hash (autenticação) | SHA-256 | (mesmo campo do proposal) | (mesmo campo) | Network → IPSec Crypto Profiles → ESP → Authentication | `set network ike crypto-profiles ipsec-crypto-profiles <perfil> esp authentication sha256` |
| PFS | Group 14 | VPN → IPsec Tunnels → Phase 2 Selectors → Enable PFS / DH Group | `set pfs enable` + `set dhgrp 14` | Network → IPSec Crypto Profiles → DH Group | `set network ike crypto-profiles ipsec-crypto-profiles <perfil> dh-group group14` |
| Lifetime | 3600s (1h) | VPN → IPsec Tunnels → Phase 2 Selectors → Auto-negotiate → Key Lifetime | `set keylifeseconds 3600` | Network → IPSec Crypto Profiles → Lifetime | `set network ike crypto-profiles ipsec-crypto-profiles <perfil> lifetime hours 1` |
| Redes de interesse | LAN local ↔ LAN remota | VPN → IPsec Tunnels → Phase 2 Selectors → Local/Remote Address | `set src-subnet <rede> ` + `set dst-subnet <rede>` | (definido via política de segurança + roteamento) | — |

### 7.3 Demais itens (interface de túnel, rota, política)

| Item | Fortigate — GUI | Fortigate — CLI/Script | Palo Alto — GUI | Palo Alto — CLI/Script |
|---|---|---|---|---|
| Interface de túnel | Network → Interfaces → (interface criada com o nome da Phase1) → IP/Netmask² | `config system interface` → `edit "<nome>"` → `set ip <ip> 255.255.255.255` → `set remote-ip <ip_remoto> 255.255.255.255` | Network → Interfaces → Tunnel → Add tunnel.X → IPv4 | `set network interface tunnel units tunnel.1 ip <ip>/30` |
| Zona (Palo Alto) | — (não aplicável no Fortigate) | — | Network → Zones → Add | `set zone vpn network layer3 tunnel.1` |
| Rota estática | Network → Static Routes → Create New | `config router static` → `edit 0` → `set dst <rede>` → `set device "<interface_tunel>"` | Network → Virtual Routers → Static Routes → Add | `set network virtual-router default routing-table ip static-route <nome> destination <rede> interface tunnel.1` |
| Política de firewall/segurança | Policy & Objects → Firewall Policy → Create New | `config firewall policy` → `edit 0` → `set srcintf/dstintf/srcaddr/dstaddr/action` | Policies → Security → Add | `set rulebase security rules <nome> from <zona_origem> to <zona_destino> action allow` |
| Commit | (implícito a cada alteração) | (implícito) | Commit (canto superior direito) | `commit` |

² O Fortigate exige máscara `/32` na interface de túnel, com o IP da outra
ponta em um campo `remote-ip` separado — diferente da notação `/30` usada como
simplificação na seção 1. Detalhe descoberto durante a automação real no
laboratório (ver `scripts-exemplo/exemplo_fortigate_vpn_ipsec.py`).
