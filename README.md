# RPS SP - Importador de Recibos e Gerador de Lote RPS

Aplicação Python que importa recibos em texto, cria uma planilha intermediária e gera arquivo de texto (`.txt`) no Layout de Lote de RPS da Prefeitura de São Paulo.

## O que este repositório faz

- Gera arquivo posicional (`.txt`) seguindo o layout oficial para envio de RPS em lote.
- Importa arquivos `.txt` de recibos e converte os registros para o modelo de RPS.
- Gera uma planilha `.xlsx` intermediária para conferência antes do envio.
- Normaliza campos (datas, CPF/CNPJ), converte valores para centavos e substitui quebras de linha na descrição por `|`.
- Oferece modo CLI e formulário gráfico com Tkinter.

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

Modo GUI (seleção interativa):

```powershell
python main.py
# abre a interface para importar o TXT e gerar o XLSX e o TXT de lote RPS
```

Na interface gráfica:

1. Clique em **Importar arquivo TXT** e selecione o arquivo de recibos.
2. Informe a inscrição municipal do prestador.
3. Confira a quantidade de recibos importados.
4. Clique em **Gerar XLSX e TXT RPS** e escolha onde salvar a planilha.

A interface salva o arquivo TXT de lote RPS automaticamente na mesma pasta e com o mesmo nome-base do XLSX.

As configurações locais são salvas em `.rps_sp_settings.json`. O campo `last_rps_number` guarda o último RPS utilizado (inicializado em `144`), e o próximo lote automático começa no número `145`. A inscrição municipal informada também é reutilizada na próxima inicialização.

Para gerar o TXT de lote RPS a partir de um XLSX já existente, use o modo CLI:

```powershell
python main.py caminho\para\RPS_SP.xlsx 12345678
```

Ao executar, o script gera um arquivo com o mesmo nome base do Excel e extensão `.txt` (ex.: `RPS_SP.txt`).

## Estrutura principal

- `main.py`: importação, validação e geração dos arquivos.
- `tests/`: testes automatizados.
- `Descarte/_MCSP_Import_Txt/`: projeto original arquivado, usado apenas como referência histórica.
- `Descarte/`: artefatos auxiliares e caches que não participam da execução.
- `NFe_Layout_RPS.pdf` e `NFe_Layout_RPS.docx`: referências do layout fiscal.

## Validação e importação

- O layout segue as especificações encontradas no manual oficial (versões V.001 / V.002) — consulte `NFe_Layout_RPS.pdf` para regras detalhadas.
- Alguns erros retornados pelo portal (ex.: código `1604`) são regras de negócio (reemissão, RPS já convertido) e não problemas de formato; nesses casos é preciso usar a funcionalidade apropriada do sistema da Prefeitura.

Para executar os testes:

```powershell
python -m unittest discover -s tests -v
```

