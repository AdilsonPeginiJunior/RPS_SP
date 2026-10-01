# RPS SP - Importador de Recibos e Gerador de Lote RPS

Aplicação Python que cadastra recibos (manualmente ou a partir de um TXT), cria uma planilha intermediária e gera arquivo de texto (`.txt`) no Layout de Lote de RPS da Prefeitura de São Paulo.

## O que este repositório faz

- Gera arquivo posicional (`.txt`) seguindo o layout oficial para envio de RPS em lote.
- Oferece uma GUI em CustomTkinter (`gui_ctk.py`) para cadastrar recibos manualmente, com cálculo automático da descrição do serviço a partir das datas de sessão selecionadas.
- Aplica automaticamente o modelo de histórico (`HistoricoPacienteFem.txt` / `HistoricoPacienteMasc.txt`) conforme o sexo do paciente cadastrado.
- Inclui tela de **Cadastro de Clientes**, com CRUD sobre `clientes.json` (dados do responsável, paciente e endereço).
- Também importa arquivos `.txt` de recibos (modo CLI) e converte os registros para o modelo de RPS.
- Gera uma planilha `.xlsx` intermediária para conferência antes do envio.
- Normaliza campos (datas, CPF/CNPJ), converte valores para centavos e substitui quebras de linha na descrição por `|`.
- Oferece modo CLI e GUI (CustomTkinter, com fallback para Tkinter caso o pacote não esteja instalado).

## Instalação

Recomenda-se usar um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

O Tkinter é usado pela interface gráfica e normalmente já acompanha a instalação do Python no Windows.

## Como usar

Modo CLI (exemplo):

```powershell
python main.py caminho\para\RPS_SP.xlsx 12345678
```

Fluxo integrado a partir do TXT de recibos:

```powershell
python main.py --txt-path caminho\para\recibos.txt --municipal-registration 12345678
```

Esse comando extrai os recibos, cria `recibos_rps.xlsx` e gera `recibos.rps.txt` no mesmo diretório. O código de serviço usado na conversão é `5118`; revise a planilha intermediária antes do envio se esse código, a série ou os dados do tomador variarem.

Na conversão, o número do RPS é criado sequencialmente, a série padrão é `E`, o tipo é `RPS`, o status é `T` e o CPF/CNPJ é obtido preferencialmente do pagador. Registros com dados fiscais incompletos devem ser corrigidos na planilha antes da geração final.

Modo GUI (CustomTkinter):

```powershell
python main.py
# ou diretamente: python gui_ctk.py
```

Na tela **Gerador de Arquivos RPS - São Paulo**:

1. Preencha a data do recebimento, o valor, o **CPF Pagador** e o **CPF do Beneficiário** (ambos selecionados a partir do cadastro de clientes).
2. Clique em **Selecionar Datas das Sessões** para gerar a descrição automaticamente.
3. Clique em **Salvar Recibo** — o recibo entra na lista **Recibos Salvos**, onde pode ser editado ou removido antes da geração final.
4. Informe a inscrição municipal e o primeiro número de RPS, e clique em **Gerar XLSX e TXT RPS**.

O botão **Cadastro de Clientes** abre a tela de CRUD sobre `clientes.json`, usada para popular os combos de pagador/beneficiário e os dados de endereço/e-mail do recibo.

Se o pacote `customtkinter` não estiver instalado, `python main.py` sem argumentos cai automaticamente para a GUI Tkinter legada, que ainda suporta a importação de um TXT de recibos.

As configurações locais são salvas em `.rps_sp_settings.json`. O campo `last_rps_number` guarda o último RPS utilizado (inicializado em `144`), e o próximo lote automático começa no número `145`. A inscrição municipal informada também é reutilizada na próxima inicialização.

Para gerar o TXT de lote RPS a partir de um XLSX já existente, use o modo CLI:

```powershell
python main.py caminho\para\RPS_SP.xlsx 12345678
```

Ao executar, o script gera um arquivo com o mesmo nome base do Excel e extensão `.txt` (ex.: `RPS_SP.txt`).

## Estrutura principal

- `main.py`: validação, conversão e geração dos arquivos de RPS; também expõe as funções reaproveitadas pela GUI.
- `gui_ctk.py`: GUI CustomTkinter (cadastro manual de recibos e cadastro de clientes).
- `clientes_storage.py`: CRUD sobre `clientes.json` usado pela tela de Cadastro de Clientes.
- `ui_widgets.py`: widgets reutilizáveis (seletor de data única e seletor de múltiplas datas de sessão).
- `tests/`: testes automatizados.

## Dados sensíveis (não versionados)

Os arquivos abaixo contêm dados reais de clientes/pacientes ou configurações locais e **nunca devem ser commitados** (já estão listados no `.gitignore`):

- `clientes.json`, `.rps_sp_settings.json`
- `cliente_novo*.txt`, `MCSP*.txt`
- `HistoricoPacienteFem.txt`, `HistoricoPacienteMasc.txt` (contêm dados bancários do prestador)

Cada máquina/ambiente precisa criar esses arquivos localmente antes de usar o sistema.

## Validação e importação

- Alguns erros retornados pelo portal (ex.: código `1604`) são regras de negócio (reemissão, RPS já convertido) e não problemas de formato; nesses casos é preciso usar a funcionalidade apropriada do sistema da Prefeitura.

Para executar os testes:

```powershell
python -m unittest discover -s tests -v
```

