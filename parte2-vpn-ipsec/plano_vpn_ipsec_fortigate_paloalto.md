# Plano de Automação — VPN IPSec entre Fortigate e Palo Alto

## Escopo deste documento

Este documento é o planejamento (Parte 2 do projeto) de como a criação de um túnel
IPSec site-to-site entre um firewall Fortigate e um firewall Palo Alto poderia ser
automatizada via API/script Python. Cobre parâmetros, ferramentas, passos lógicos,
diferenças entre os dois fabricantes e a estratégia de validação/alertas. Não exige uma
VPN funcional — IPs e nomes de objeto usados abaixo são exemplos ilustrativos (faixas
reservadas para documentação, RFC 5737) e não correspondem a nenhum ambiente real.

---

## 1. Definição de parâmetros

| Parâmetro | Fortigate (lado A) | Palo Alto (lado B) |
|---|---|---|
| IP WAN (extremidade do túnel) | `203.0.113.10` | `198.51.100.20` |
| Rede local (LAN) de exemplo | `192.168.10.0/24` | `192.168.20.0/24` |
| Interface de túnel | `vpn_to_paloalto` (route-based, tipo `tunnel`) | `tunnel.1` (VTI) |
| IP da interface de túnel | `169.255.1.1/30` | `169.255.1.2/30` |

A rede `169.255.1.0/30` é dedicada ao roteamento interno do IPSec (endereçamento ponto a
ponto entre as duas interfaces de túnel). O tráfego entre `192.168.10.0/24` e
`192.168.20.0/24` é roteado por cima do túnel via rota estática apontando para o IP da
outra ponta.

### Proposta de Phase 1 (IKE)

Combinação suportada nativamente pelos dois fabricantes, sem exigir licenças adicionais:

| Parâmetro | Valor |
|---|---|
| Versão IKE | IKEv2 |
| Autenticação | Pre-shared key (PSK) |
| Criptografia | AES-256 |
| Hash/Integridade | SHA-256 |
| Grupo Diffie-Hellman | Group 14 (2048-bit) |
| Lifetime | 28800 segundos (8h) |
| NAT-T | Habilitado (detecção automática) |
| DPD (Dead Peer Detection) | Habilitado, intervalo 10s |

### Proposta de Phase 2 (IPSec)

| Parâmetro | Valor |
|---|---|
| Protocolo | ESP |
| Criptografia | AES-256 |
| Hash/Integridade | SHA-256 |
| PFS (Perfect Forward Secrecy) | Habilitado, Group 14 |
| Lifetime | 3600 segundos (1h) |
| Modo | Tunnel mode |
| Seletores de tráfego (proxy-id) | `0.0.0.0/0 <-> 0.0.0.0/0` (route-based — o roteamento define o que passa pelo túnel, não o proxy-id) |

> Route-based (VTI) foi escolhido nos dois lados para evitar o modelo policy-based do
> Fortigate (proxy-id por par de sub-redes), que não existe no Palo Alto — ver seção 4.

---

## 2. Identificação de ferramentas/APIs

| Fabricante | API | Autenticação | Bibliotecas Python relevantes |
|---|---|---|---|
| Fortinet (Fortigate) | FortiOS REST API (`/api/v2/cmdb/...`) | Token Bearer (API user + token, IP de origem restrito) | `requests` (chamadas diretas), `fortiosapi` (wrapper), `netmiko` (fallback via CLI/SSH) |
| Palo Alto (PAN-OS) | PAN-OS XML API (`/api/`); versões 9.0+ também expõem REST API em JSON para parte dos objetos | API key gerada uma vez via `keygen` (usuário/senha → chave), reutilizada nas chamadas seguintes | `pan-os-python` (SDK oficial, recomendado — abstrai XML), `requests` (chamadas diretas à XML API), `netmiko` (fallback via CLI/SSH) |
| Ambos | — | — | `python-dotenv` (credenciais fora do código, mesmo padrão da Parte 1), `logging` (log estruturado) |
| Alternativa a script próprio | Ansible | Módulos `fortinet.fortios` e `paloaltonetworks.panos` | — |
| Gerenciamento centralizado (mencionado, fora do escopo mínimo) | FortiManager (Fortinet) / Panorama (Palo Alto) | Cada um com sua própria API | Reduz a automação a "um script por orquestrador" em vez de por dispositivo, mas exige que esses gerenciadores estejam implantados |

Motivo da escolha do `pan-os-python` no lado Palo Alto: evita montar XML manualmente
(propenso a erro), expõe objetos como classes Python (`AddressObject`, `IkeGateway`,
`IpsecTunnel`, etc.) e trata comparação/aplicação de configuração.

---

## 3. Passos de automação

A ordem abaixo é a mesma nos dois fabricantes, adaptada à terminologia de cada um (ver
seção 4):

1. **Criação de objetos de endereço**
   - Objeto para a rede local (`LAN_LOCAL`, ex. `192.168.10.0/24`)
   - Objeto para a rede remota (`LAN_REMOTA`, ex. `192.168.20.0/24`)
2. **Configuração de zonas** (quando aplicável)
   - Fortigate: a interface de túnel é referenciada diretamente nas políticas de
     firewall — zona é opcional
   - Palo Alto: criar (ou reaproveitar) uma zone `VPN` e associar a interface
     `tunnel.1` a ela — no PAN-OS toda política de segurança depende de zona
3. **Phase 1 (IKE gateway)**: peer IP, PSK, proposta de criptografia/hash/DH, versão IKE
4. **Phase 2 (IPSec tunnel)**: vinculado à Phase 1, proposta de criptografia/hash/PFS,
   associado à interface de túnel
5. **Interface de túnel e roteamento**: atribuir IP da rede `169.255.1.0/30` em cada
   lado e criar rota estática (rede remota → next-hop = IP de túnel da outra ponta)
6. **Políticas de firewall**
   - Fortigate: política `LAN → VPN` e `VPN → LAN` permitindo o tráfego entre
     `LAN_LOCAL` e `LAN_REMOTA` (NAT desabilitado nessas políticas)
   - Palo Alto: security policy `LAN → VPN` e `VPN → LAN` equivalente, nas zonas
     correspondentes
7. **Estabelecimento do túnel**: route-based sobe automaticamente quando há tráfego
   roteado para a rede remota (ou pode-se forçar com um "ping" de gatilho)
8. **Validação pós-configuração** — ver seção 5

Cada passo corresponderia a uma função Python isolada — mesmo padrão usado em
`backend/automacao_switch.py` na Parte 1 (uma função por responsabilidade, reaproveitando
uma sessão/conexão já autenticada) — permitindo repetir a lógica de forma simétrica para
os dois fabricantes por trás de uma interface comum (`FortigateClient` /
`PaloAltoClient`).

---

## 4. Considerações específicas (Fortinet × Palo Alto)

- **Terminologia e modelo de VPN**: o Fortigate permite VPN **policy-based** (proxy-id
  por par de sub-redes) ou **route-based** (interface de túnel + rota). O Palo Alto
  **só** trabalha route-based — toda VPN IPSec usa uma tunnel interface. Por isso o
  plano assume route-based nos dois lados, evitando ter que traduzir proxy-id do
  Fortigate para um conceito que não existe no PAN-OS.
- **Modelo de objetos**: no PAN-OS, praticamente tudo depende de **zona** (interface →
  zona → política de segurança referenciando zonas). No FortiOS, a política de firewall
  referencia interfaces diretamente; zonas existem mas são opcionais. A automação do
  lado Palo Alto precisa garantir que a zona exista *antes* de associar a interface de
  túnel a ela.
- **Autenticação de API**: Fortigate usa token Bearer (gerado uma vez no equipamento e
  associado a um IP de origem confiável). Palo Alto usa uma API key derivada de
  usuário/senha via chamada `keygen`, reutilizada depois — mais parecido com "login que
  gera token", mas via parâmetro de URL/header em vez de Bearer. As duas exigem HTTPS
  (geralmente com certificado autoassinado em laboratório).
- **Formato de payload**: FortiOS REST API usa **JSON** nativamente. PAN-OS API usa
  **XML** como formato principal para VPN/IPSec (a REST API mais nova do PAN-OS cobre
  parte dos objetos em JSON, mas não tudo). Um script que automatiza os dois lados
  precisa lidar com dois formatos de serialização diferentes — daí a recomendação de
  usar o SDK oficial (`pan-os-python`) do lado Palo Alto em vez de montar XML na mão.
- **Compatibilidade de algoritmos**: os nomes dos algoritmos nem sempre coincidem
  caractere a caractere entre as duas interfaces de configuração (ex.: `aes256` vs
  `AES-256`, `sha256` vs `SHA256`), mesmo quando o algoritmo negociado no protocolo
  IKE/ESP é o mesmo. A automação deve manter uma tabela de mapeamento
  (`algoritmo_padrao → nome_no_fortios → nome_no_panos`) em vez de assumir que o mesmo
  literal funciona nas duas APIs.
- **Ordem de aplicação**: como as duas pontas precisam concordar em PSK, IPs de peer e
  propostas antes do túnel subir, a automação deve aplicar a configuração dos dois lados
  antes de tentar validar — não há "meio-termo" funcional com só um lado configurado.

---

## 5. Validação de configuração e alertas

### Verificação de status do túnel

| Fabricante | Via CLI/SSH | Via API |
|---|---|---|
| Fortigate | `get vpn ipsec tunnel summary` / `diagnose vpn ike gateway list` / `diagnose vpn tunnel list` | `GET /api/v2/monitor/vpn/ipsec` (status `up`/`down` de cada túnel, SAs ativas) |
| Palo Alto | `show vpn ike-sa` / `show vpn ipsec-sa tunnel <nome>` | Comando operacional via XML API: `<show><vpn><ipsec-sa></ipsec-sa></vpn></show>` (ou método equivalente do `pan-os-python`) |

### Lógica de validação (mesmo padrão da Parte 1)

Seguindo a mesma abordagem usada em `validar_configuracao()` no switch (reler o estado
real e comparar com o esperado, retornando uma lista de divergências), a automação da
VPN deveria:

1. Consultar o status do túnel nos dois lados após a criação (com retry/wait, já que a
   negociação IKE/IPSec route-based só ocorre quando há tráfego ou um "trigger" ativo).
2. Verificar, em cada lado:
   - Fase 1 (IKE SA) estabelecida
   - Fase 2 (IPSec SA) estabelecida
   - Interface de túnel com o IP esperado e `up`
   - Rota para a rede remota presente na tabela de roteamento
3. Se qualquer item divergir do esperado (túnel `down`, SA ausente, interface sem IP),
   registrar a divergência no mesmo formato usado na Parte 1:
   `{"ok": bool, "divergencias": [...]}`.

### Como os alertas seriam gerados

- **Curto prazo (mesmo padrão da Parte 1)**: exibir a divergência na saída do
  script/log, com severidade clara (ex.: `[ALERTA] Fase 2 não estabelecida no lado
  Fortigate`).
- **Teste de conectividade fim a fim** (complementar à checagem de SA): um ping/teste a
  partir de um host em `192.168.10.0/24` para um host em `192.168.20.0/24` confirma que
  o tráfego realmente passa pelo túnel — SAs "up" não garantem roteamento correto de
  ponta a ponta.
- **Monitoramento contínuo** (evolução natural, fora do escopo mínimo): repetir a
  checagem de status em intervalo (cron/scheduler) e, em caso de falha, notificar por
  e-mail ou webhook (Slack/Teams), reaproveitando a mesma função de validação — só
  trocando o destino do alerta de "print no terminal" para "chamada de webhook".

---

## Itens opcionais

- Scripts/configs de exemplo para Fortigate e Palo Alto: possível próximo passo se
  avançarmos para uma simulação em laboratório.
- Script de teste de conectividade pelo túnel: idem — depende de um ambiente de
  laboratório disponível.

## Resumo de rastreabilidade

| Requisito do desafio | Seção |
|---|---|
| Definição de Parâmetros | Seção 1 |
| Identificação de Ferramentas/APIs | Seção 2 |
| Passos de Automação | Seção 3 |
| Considerações Específicas | Seção 4 |
| Validação de Configuração e Alertas | Seção 5 |
