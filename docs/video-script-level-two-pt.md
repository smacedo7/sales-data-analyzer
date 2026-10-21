# Roteiro de vídeo — nível 2 (menu no terminal) — até 3 minutos

Duração planejada: 2min45s; reserve 15 segundos de margem. Abra antes da gravação
a UML do nível 2 (`docs/diagrams/level-two.svg`), os arquivos citados e o terminal
na raiz do projeto. Aumente a fonte e use os dados sintéticos de `tests/fixtures`.
Não leia toda a saída do menu nem dos testes.

| Tempo | Mostrar | Fala sugerida |
| --- | --- | --- |
| 0:00–0:15 | README, seção do nível 2 | “No nível 1, o Sales Data Analyzer importava CSV, validava e analisava vendas pelo código Python. No nível 2, tudo isso ganhou um menu interativo no terminal, sem mudar o domínio. Os dados ficam só na memória; banco de dados é o próximo nível.” |
| 0:15–0:50 | UML `level-two.svg` | “Organizei o sistema em camadas. TerminalMenu só lê e mostra texto e chama SalesSession. A sessão guarda as empresas, a empresa atual e o período selecionado, representado pela classe Selection. Cada empresa tem um CompanyWorkspace com seu catálogo de produtos e suas vendas. Por baixo, as mesmas classes do nível 1: Company, Product, Sale, SalesDataset, as análises e o RevenueForecaster.” |
| 0:50–1:15 | `application/workspace.py`, método `import_sales` | “O CompanyWorkspace aplica a regra do tudo ou nada: valida, monta coleções candidatas e só troca os dados no final. Se um ID de venda já existe ou um produto conflita com o catálogo, nada é importado. Ele aceita qualquer DataImporter, então o CSVImporter entra por polimorfismo.” |
| 1:15–1:30 | `application/errors.py` | “Os erros de regra de negócio herdam de ApplicationError, como DuplicateSaleError, CatalogConflictError e InsufficientHistoryError. O menu captura essa hierarquia e mostra uma mensagem clara, sem quebrar o programa.” |
| 1:30–2:10 | Executar o menu: opções 1, 7, 10, 11, 7 de novo, 8 | “Crio a empresa Coffee Shop e importo o CSV: duas vendas, três itens. A análise financeira mostra receita de 45,40 e lucro bruto de 27,20; a de produtos ranqueia o café em primeiro. Se importo o mesmo arquivo de novo, a importação é recusada e nada muda. Agora escolho só o dia 2 de janeiro: a receita cai para 5,00.” |
| 2:10–2:30 | Executar o menu: opções 1, 7 (`forecast_14_days.csv`), 12 | “Numa segunda empresa, importo 14 dias de vendas e peço a previsão. O menu mostra os dias de treino e teste, compara o modelo com um baseline e lista os próximos sete dias, sempre com as limitações da previsão.” |
| 2:30–2:45 | Executar os testes | “São 147 testes: parsing de entradas, formatação, sessão, workspace, menu com entradas roteirizadas e uma sessão ponta a ponta executando o programa de verdade. A integração contínua roda em Linux, macOS e Windows, com Ruff.” |

Comandos preparados:

```sh
uv run sales-data-analyzer
uv run python -m unittest discover -s tests
```

Entradas da demonstração (digite uma por vez):

| Opção | Entradas | Saída esperada |
| --- | --- | --- |
| `1` | `Coffee Shop`, `Retail` | `Company created and selected: Coffee Shop` |
| `7` | `tests/fixtures/valid_sales.csv` | `Imported 2 sales, 3 items. Products: 2 new, 0 reused.` |
| `10` | — | `Revenue 45.40`, `Gross profit 27.20` |
| `11` | — | `007 Coffee, premium` em primeiro |
| `7` | `tests/fixtures/valid_sales.csv` | `Import refused: 2 sale ID(s) already exist ... Nothing was imported.` |
| `8` | `2026-01-02`, `2026-01-02` | `Selection: 2026-01-02 to 2026-01-02 (1 sale)` |
| `10` | — | `Revenue 5.00` |
| `1` | `Forecast Shop`, `Retail` | nova empresa selecionada |
| `7` | `tests/fixtures/forecast_14_days.csv` | `Imported 14 sales, 14 items.` |
| `12` | Enter, Enter | `Training days: 12 \| Test days: 2` e 7 dias previstos |
| `0` | `y` | sai do programa |

Depois, confira a duração final e publique no YouTube com acesso pelo link.
Envie os links exigidos pela disciplina. Este arquivo é apenas roteiro: gravação,
publicação e submissão são responsabilidade do aluno.
