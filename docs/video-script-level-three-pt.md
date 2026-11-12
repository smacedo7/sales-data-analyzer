# Roteiro de vídeo — nível 3 (banco SQLite e menu no terminal) — até 3 minutos

Duração planejada: 2min50s; reserve 10 segundos de margem. Antes da gravação, abra
a UML do nível 3 (`docs/diagrams/level-three.svg`), o `docs/database.md` e o
terminal na raiz do projeto. Use `--database data/demo.sqlite3` para que o banco
fique dentro do projeto e possa ser aberto por uma extensão de SQLite no VS Code.
Aumente a fonte. Não leia toda a saída do menu.

| Tempo | Mostrar | Fala sugerida |
| --- | --- | --- |
| 0:00–0:15 | README, seção "Level 3" | "No nível 2, os dados ficavam só na memória. No nível 3, o sistema grava tudo num banco SQLite local. Cada confirmação é salva na hora, então sair do programa não perde nada." |
| 0:15–0:40 | UML `level-three.svg` | "A interface de terminal continua falando só com a camada de aplicação. Quem decide como os dados são guardados é o repositório: a aplicação depende de uma interface, e a implementação SQLite fica na camada de persistência. Por isso o mesmo código de regra de negócio roda com outro banco, se for preciso." |
| 0:40–1:05 | `docs/database.md`, seção do esquema | "O esquema tem quatro tabelas: company, product, sale e sale_item. As chaves estrangeiras compostas garantem que um item só pode apontar para uma venda e um produto da mesma empresa. Os valores monetários são guardados como texto decimal, para não perder centavos com ponto flutuante." |
| 1:05–1:25 | `persistence/sqlite.py`, função que abre a conexão | "Cada conexão liga as chaves estrangeiras, e o arquivo se identifica pelo application_id e pela versão do esquema. Arquivos de outro programa ou de versão mais nova são recusados. As escritas usam BEGIN IMMEDIATE, então uma importação que falha no meio é desfeita por completo." |
| 1:25–2:20 | Executar o menu com `--database data/demo.sqlite3`: opções 1, 7, 10, sair (`0`), abrir de novo, opção 16 | "Crio a empresa, importo o CSV e vejo a receita. Agora saio do programa e abro de novo. Ao listar as vendas com a opção 16, os mesmos dados aparecem, porque foram gravados no arquivo." |
| 2:20–2:40 | Abrir o `data/demo.sqlite3` na extensão de SQLite do VS Code, mostrar as tabelas `company` e `sale` | "Aqui está o arquivo que o menu acabou de gravar. A linha da empresa e as vendas estão nas tabelas, com as mesmas chaves que vimos no esquema." |
| 2:40–2:50 | Executar os testes de persistência | "Os testes de persistência cobrem o round trip, a recusa de arquivos inválidos e de versões mais novas, e a remoção de vendas e produtos. A integração contínua roda em Linux, macOS e Windows." |

Comandos preparados:

```sh
uv sync --locked
uv run sales-data-analyzer --database data/demo.sqlite3
uv run python -m unittest discover -s tests
```

Consultas para mostrar o banco (num segundo terminal, ou pelo VS Code):

```sh
sqlite3 data/demo.sqlite3 ".tables"
sqlite3 -header -column data/demo.sqlite3 "SELECT * FROM company;"
sqlite3 -header -column data/demo.sqlite3 "SELECT * FROM sale LIMIT 5;"
```

Entradas da demonstração (digite uma por vez):

| Opção | Entradas | Saída esperada |
| --- | --- | --- |
| `1` | `Coffee Shop`, `Retail` | empresa criada e selecionada |
| `7` | `tests/fixtures/valid_sales.csv` | `Imported 2 sales, 3 items.` |
| `10` | — | `Revenue 45.40`, `Gross profit 27.20` |
| `0` | — | sai do programa |
| `--database` | `data/demo.sqlite3` na nova execução | a empresa Coffee Shop ainda está lá |
| `16` | — | as duas vendas aparecem |
| `0` | — | sai do programa |

Se o arquivo `data/demo.sqlite3` não existir, a primeira execução com esse caminho
cria o banco vazio. Nesse caso, repita a sequência de entradas acima.

Antes de gravar, confira a duração final, a legibilidade da fonte do terminal e
o caminho do banco exibido nas linhas de inicialização. Este arquivo é apenas
roteiro: gravação, publicação e submissão são responsabilidade do aluno.
