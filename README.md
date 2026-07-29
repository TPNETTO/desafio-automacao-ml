# Desafio de Automação  

Projeto desenvolvido para o desafio técnico de automação de redes.

O projeto é dividido em duas partes:

- **Parte 1**: automação de configuração de um switch Cisco (VLANs + hostname) via
  Netmiko, com frontend em Streamlit, backup automático e validação pós-configuração.
- **Parte 2**: planejamento (documentação) da automação de uma VPN IPSec entre um
  Fortigate e um Palo Alto, sem exigir implementação funcional.

## Estrutura do projeto

```
├── backend/
│   ├── automacao_switch.py   # Conexão SSH e automação via Netmiko
│   └── backup/                # Backups de configuração gerados em tempo de execução
├── frontend/
│   └── app.py                 # Interface Streamlit
├── docs/
│   └── plano_vpn_ipsec_fortigate_paloalto.md   # Documento da Parte 2
├── evidencias/
│   ├── frontend/               # Screenshots do frontend
│   └── switch_cli/             # Screenshots da CLI do switch
├── requirements.txt
├── .env                        # Credenciais reais (NUNCA vai para o Git)
└── .gitignore
```

## Pré-requisitos

- Python 3.10 ou superior
- Acesso de rede ao switch Cisco (SSH habilitado)
- Credenciais válidas de um usuário com privilégio 15 no switch

## Instalação

1. Clone o repositório e entre na pasta do projeto:
   ```bash
   git clone https://github.com/TPNETTO/desafio-automacao-ml.git
   cd desafio-automacao-ml
   ```

2. Crie e ative um ambiente virtual:
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # Linux/Mac
   ```

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Crie um arquivo `.env` na raiz do projeto com as credenciais do switch (esse
   arquivo já está no `.gitignore` e nunca deve ser commitado):
   ```
   SWITCH_HOST=10.10.90.6
   SWITCH_USER=admin
   SWITCH_PASSWORD=sua_senha_aqui
   ```

## Como usar o frontend

Com o ambiente virtual ativo, execute:

```bash
streamlit run frontend/app.py
```

O Streamlit abre uma página no navegador onde é possível:

- Informar/editar o IP e as credenciais de conexão com o switch (pré-preenchidos a
  partir do `.env`, mas editáveis na tela)
- Definir o novo hostname do switch
- Configurar as VLANs 10 (`VLAN_DADOS`), 20 (`VLAN_VOZ`) e 50 (`VLAN_SEGURANÇA`)
- Aplicar a configuração, gerar backup local e visualizar o resultado da validação
  pós-configuração (alertas em caso de divergência)

## Notas de implementação

- A automação usa [Netmiko](https://github.com/ktbyers/netmiko) (`device_type
  cisco_ios`) para conexão SSH com o switch.
- Após aplicar a configuração, ela é salva na NVRAM (`copy running-config
  startup-config`) e um backup local é gerado com o nome do host + data/hora.
- A validação relê a configuração do switch após a aplicação e compara com o
  esperado (VLANs e hostname), sinalizando qualquer divergência.
- Credenciais nunca ficam hardcoded no código — são lidas do `.env` via
  `python-dotenv`.

## Status

Consulte a Parte 2 (planejamento de VPN IPSec) em `docs/plano_vpn_ipsec_fortigate_paloalto.md`.
