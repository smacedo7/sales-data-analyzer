# Roteiro de vídeo — nível 4 (janela desktop PySide6) — até 3 minutos

Duração planejada: 2min50s; reserve 10 segundos de margem. Antes da gravação, abra
a UML do nível 4 (`docs/diagrams/level-four.svg`), o README na seção "Running the
Desktop Window" e o terminal na raiz do projeto. Aumente a fonte e use o banco
`data/demo.sqlite3`, para que os dados de demonstração e a importação do CSV
fiquem no mesmo arquivo que o menu do nível 3 usa.

| Tempo | Mostrar | Fala sugerida |
| --- | --- | --- |
| 0:00–0:15 | README, seção do nível 4 | "No nível 3, o programa era um menu de terminal com banco SQLite. No nível 4, as mesmas regras e o mesmo banco ganharam uma janela desktop em português, feita com PySide6. A janela não duplica nenhuma regra: ela chama os mesmos serviços de aplicação." |
| 0:15–0:40 | UML `level-four.svg` | "A camada gui é a única que importa PySide6. As páginas, como vendas, produtos, previsões e gráficos, só mostram resultados e chamam a SalesSession. A persistência e as análises continuam nas camadas de níveis anteriores, então o domínio não muda." |
| 0:40–1:00 | `gui/pages/home.py`, método do botão de demonstração | "A tela inicial oferece dados de demonstração. Eles são gerados em um CSV temporário e importados pelo mesmo caminho de uma importação real, com validação e transação única. Assim, a demonstração testa o caminho de produção." |
| 1:00–1:45 | Executar `uv run sales-data-analyzer-desktop --database data/demo.sqlite3`: botão de demonstração, Visão geral, Previsões | "Abro a janela. Ao carregar os dados de demonstração, a visão geral mostra os indicadores do período. Na página de previsões, a comparação de métodos aparece com erro médio e RMSE. Os números são os mesmos do terminal, porque vêm do mesmo serviço." |
| 1:45–2:15 | Página de gráficos (zoom, deslocar, passar o mouse) e a página de relatório PDF | "Os gráficos são interativos: dá para dar zoom, deslocar e ver o valor ao passar o mouse. O relatório PDF é gerado pelo próprio Qt, sem dependência extra, e só substitui o arquivo de destino quando termina por completo." |
| 2:15–2:35 | Página de vendas, importar `/caminho/para/vendas_demonstracao.csv`, e depois fechar a janela | "Importo um CSV pela janela. A regra de tudo ou nada vale aqui também. Ao fechar, nada se perde, porque cada confirmação já foi gravada no banco." |
| 2:35–2:50 | Terminal: `sqlite3 -header -column data/demo.sqlite3 "SELECT COUNT(*) AS vendas FROM sale;"` e os testes | "O mesmo banco mostra as vendas gravadas pela janela. Os testes de interface rodam sem tela, com o modo offscreen do Qt, e cobrem as páginas, os textos em português e o relatório PDF." |

Comandos preparados (a partir da raiz do projeto, `sales-data-analyzer`):

```sh
uv sync --locked
uv run sales-data-analyzer-desktop --database data/demo.sqlite3
uv run python -m unittest discover -s tests
```

Antes de gravar, confirme que o terminal está dentro da pasta do projeto: o
comando de testes só encontra `tests` a partir dela.

Confirmações da demonstração:

| Passo | O que deve aparecer |
| --- | --- |
| Início com `data/demo.sqlite3` | a janela abre com a tela inicial |
| Dados de demonstração | empresa "Café Aurora (demo)" com 42 dias de vendas |
| Previsões | tabela de comparação de métodos, com erro médio e RMSE |
| Gráficos | zoom, deslocamento e valores ao passar o mouse |
| Relatório PDF | visualização e exportação de um PDF A4 |
| Importação do CSV | mensagem de importação com a quantidade de vendas |

Este arquivo é apenas roteiro: gravação, publicação e submissão são responsabilidade
do aluno.
