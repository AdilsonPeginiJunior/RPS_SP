# RPS SP - Gerador de Layout de Lote de RPS

Script Python para gerar arquivo de texto (`.txt`) no Layout de Lote de RPS da Prefeitura de São Paulo a partir de uma planilha Excel (`.xlsx`).

## O que este repositório faz

- Gera arquivo posicional (`.txt`) seguindo o layout oficial para envio de RPS em lote.
- Normaliza campos (datas, CPF/CNPJ), converte valores para centavos e substitui quebras de linha na descrição por `|`.
- Fornece um pequeno formulário GUI (Tkinter) ou modo CLI para gerar o `.txt`.

## Instalação

Instale as dependências no ambiente (ex.: venv):

```powershell
python -m pip install -r requirements.txt
```

## Como usar

Modo CLI (exemplo):

```powershell
python main.py caminho\para\RPS_SP.xlsx 12345678
```

Modo GUI (seleção interativa):

```powershell
python main.py
# abre um formulário para selecionar o Excel e informar a inscrição municipal
```

Ao executar, o script gera um arquivo com o mesmo nome base do Excel e extensão `.txt` (ex.: `RPS_SP.txt`).

## Arquivos auxiliares e descarte

- A pasta `descartar/` foi criada para agrupar arquivos auxiliares e artefatos que não fazem parte do fluxo de execução (ex.: imagens de erro, extração de PDF). Se precisar recuperar algum arquivo, verifique essa pasta.

Atualmente, esta pasta contém arquivos movidos durante a análise: `ERRO_RPS_SP.jpg`, `pdf_layout_text.txt` e `__pycache__/`.

Se preferir que eu compacte ou remova esses arquivos, posso fazer isso mediante confirmação.

## Notas sobre validação e importação

- O layout segue as especificações encontradas no manual oficial (versões V.001 / V.002) — consulte `NFe_Layout_RPS.pdf` para regras detalhadas.
- Alguns erros retornados pelo portal (ex.: código `1604`) são regras de negócio (reemissão, RPS já convertido) e não problemas de formato; nesses casos é preciso usar a funcionalidade apropriada do sistema da Prefeitura.

## Contribuição e commit automático

Este repositório permite edição local; após atualizar arquivos execute:

```powershell
git add README.md
git commit -m "Atualiza README: instruções e pasta descartar"
```

Se quiser, posso executar o commit automaticamente (já será tentado pelo script quando solicitado).

## Dependências

- `pandas`
- `openpyxl`

---
Arquivo gerado/atualizado automaticamente pelo assistente.
