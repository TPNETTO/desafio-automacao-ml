# Scripts de exemplo — automação da VPN IPSec (item opcional da Parte 2)

Esta pasta contém o item **opcional** descrito no desafio: scripts de exemplo
(conceituais ou parciais) para automatizar a VPN IPSec entre Fortigate e Palo
Alto, seguindo a lógica descrita em
[`../plano_vpn_ipsec_fortigate_paloalto.md`](../plano_vpn_ipsec_fortigate_paloalto.md).

## Resumo em uma frase

O lado **Fortigate** foi configurado e validado com sucesso via automação real
(script + REST API, contra um dispositivo físico). O lado **Palo Alto** não
pôde ser configurado devido a um bloqueio de detecção de hardware em um
laboratório de simulação (ESXi). **O túnel não chegou a ficar operante** — os
dois scripts aqui documentam o que foi de fato testado e o que ficou apenas no
nível conceitual.

## `exemplo_fortigate_vpn_ipsec.py` — funcional, testado

Aplicado com sucesso via FortiOS REST API contra um Fortigate real:

- Phase 1 (IKEv2, PSK, DH Group 14) e Phase 2 (PFS DH14)
- Interface de túnel (`169.255.1.1/32`, `remote-ip 169.255.1.2/32`)
- Rota estática para a rede remota
- Políticas de firewall nas duas direções

Confirmado por duas fontes independentes (resposta da API e `show system
interface` via CLI).

**Nota sobre o proposal de criptografia**: o firmware do Fortigate usado no
laboratório é uma build "LENC" (Limited Encryption, restrição de exportação de
criptografia) que só aceita propostas `des-*` — não tem AES/3DES/GCM
disponível. Por isso o script usa `des-sha256` como exemplo funcional, em vez
do `aes256-sha256` recomendado no plano oficial (seção 1). Em um Fortigate com
firmware completo, basta trocar a constante `PROPOSAL` no script.

Credenciais (token de API e pre-shared key) não ficam no código — vêm de
variáveis de ambiente (`FGT_API_TOKEN`, `FGT_VPN_PSK`).

## `exemplo_paloalto_vpn_ipsec.py` — conceitual, não executado

Segue a mesma lógica lógica do plano oficial (seção 3, "No Palo Alto via
XML/REST API"): interfaces, zonas, IKE Crypto Profile, IKE Gateway, IPSec
Crypto Profile, IPSec Tunnel, rota estática, política de segurança e commit.

**Por que não foi executado**: no laboratório de simulação (PA-VM em ESXi),
`show interface hardware` sempre retornou 0 interfaces de dataplane
detectadas, mesmo após:

- Confirmar que os adapters de rede no ESXi estavam corretos (VMXNET3,
  conectados, portgroups certos)
- Configurar reserva de CPU e memória na VM (exigência documentada da Palo
  Alto para VM-Series em ESXi)
- Múltiplos power cycles completos

O dataplane confirmadamente sobe (`show chassis-ready` retorna `yes`), mas não
enxerga as placas de rede adicionais — só a interface de management. A VM
também não tinha nenhuma licença/auth-code aplicado (`vm-license: none`), o
que pode ou não ser a causa raiz (não foi possível confirmar com certeza dentro
do tempo disponível para este item bônus).

O script tem um guard (`raise SystemExit`) no final para deixar explícito que
não deve ser executado sem antes resolver esse bloqueio.

## `teste_conectividade_vpn.py` — parcialmente funcional, testado

Script de teste de conectividade (item opcional), seguindo a "Estratégia de
validação proposta" da seção 5 do plano: consulta o status do túnel (IKE/IPSec
SA) em cada fabricante via API e só tenta um `ping` pelo túnel se os dois
lados reportarem SA estabelecida — evitando testar tráfego num túnel que nem
terminou de negociar.

- **Checagem do Fortigate**: funcional e testada de verdade contra a API REST
  — retornou corretamente o status real do túnel (`down`, com o `proxyid`
  mostrando as redes `192.168.10.0/24` ↔ `192.168.20.0/24` configuradas).
- **Checagem do Palo Alto**: conceitual (usa `show vpn ike-sa` via API XML),
  pulada automaticamente se `PA_API_KEY` não estiver definida — mesmo bloqueio
  de hardware do `exemplo_paloalto_vpn_ipsec.py`.
- **Ping pelo túnel**: só é tentado se as duas checagens acima retornarem "up".
  Neste laboratório isso nunca acontece, então o script sempre reporta a
  divergência corretamente (`exit code 1`) em vez de travar ou dar falso
  positivo — esse é o comportamento esperado e correto dado o estado real do
  ambiente, não uma falha do script.

## Por que incluir isso, mesmo incompleto

O desafio explicitamente trata a simulação funcional da VPN como bônus, não
como entregável obrigatório ("não é esperada uma simulação funcional da VPN,
caso seja realizada é um bônus"). Documentar o que foi testado de verdade
(Fortigate) e o que ficou conceitual (Palo Alto), incluindo o diagnóstico do
bloqueio, demonstra o processo real de automação e troubleshooting em um
ambiente heterogêneo — que é justamente um dos pontos avaliados na Parte 2.
