# Roteiro de vídeo — até 3 minutos

Duração planejada: 2min45s; reserve 15 segundos de margem. Abra antes da gravação
a UML, os arquivos citados e o terminal na raiz do projeto. Aumente a fonte e
use dados sintéticos. Não explique cada classe ou leia toda a saída dos testes.

| Tempo | Mostrar | Fala sugerida |
| --- | --- | --- |
| 0:00–0:20 | README e repositório | “Este é o Sales Data Analyzer, um projeto Python não web. Neste nível, ele importa vendas de CSV, valida os dados e calcula indicadores financeiros e rankings de produtos. O repositório é público.” |
| 0:20–0:55 | UML, páginas Domain e Import | “Cada empresa está associada aos seus produtos e vendas. Uma venda cria e possui seus itens: essa é a composição. Cada item referencia um produto, e o dataset reúne vendas por associação. CSVImporter herda o contrato abstrato DataImporter e depende do SalesValidator.” |
| 0:55–1:20 | UML Analysis e Forecast | “FinancialAnalysis e ProductAnalysis herdam Analysis. As duas implementam run e retornam AnalysisResult com métricas tipadas. A previsão está separada em RevenueForecaster, com resultados e erros próprios. A UML mostra o que está implementado; interface e banco são etapas futuras.” |
| 1:20–1:50 | Sale.add_item e examples/import_and_analyze.py | “Sale.add_item constrói os itens, demonstrando composição no código. Neste exemplo, uso a interface DataImporter e percorro análises pelo mesmo método run, demonstrando polimorfismo. O domínio é independente do CSV.” |
| 1:50–2:15 | Executar demo CSV | “Cada linha é um item; sale_id agrupa a compra, inclusive em linhas separadas. IDs preservam zeros à esquerda, valores usam Decimal e itens repetidos não são descartados. Aqui temos duas vendas, três itens, receita de 45,40 e lucro de 27,20.” |
| 2:15–2:40 | Executar testes | “Os testes verificam domínio, importação, análises e previsão. Há casos de CSV inválido, datas e fusos, metadados inconsistentes e integração. Uma falha na importação não entrega um dataset parcial. A suíte passou com 42 testes.” |
| 2:40–2:45 | README/checklist | “Os contratos, diagramas editáveis e instruções de execução estão documentados no repositório.” |

Comandos preparados:

```sh
PYTHONPATH=src uv run python examples/import_and_analyze.py
PYTHONPATH=src uv run python -m unittest discover -s tests -v
```

Depois, confira a duração final e publique no YouTube com acesso pelo link.
Envie os links exigidos pela disciplina. Este arquivo é apenas roteiro: gravação,
publicação e submissão são responsabilidade do aluno.
