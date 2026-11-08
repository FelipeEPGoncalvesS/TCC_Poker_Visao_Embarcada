# Benchmark da camada de decisão

Os CSVs foram gerados por `app_flask/benchmark_rag.py` na Raspberry Pi 5. Cada situação sorteada (dez por rua) é decidida pelo Gemma 3 1B com o caminho rápido desligado. Só muda o conteúdo recuperado:

- **sem RAG:** nenhum trecho;
- **livro:** dois trechos do livro;
- **curada:** uma ficha da base curada.

## Referência

A referência é a equidade da mão contra dois oponentes com cartas aleatórias, estimada por Monte Carlo com 3.000 simulações. Ela vira uma ação por limiares em relação à fatia justa de 1/3:

- **Raise:** equidade igual ou maior que 1,5 × 1/3;
- **Fold:** equidade menor que 0,75 × 1/3;
- **Call/Check:** entre esses limites.

Um **erro grave** é Raise quando a referência é Fold, ou o contrário. Check/Fold conta como Fold.

A referência é uma aproximação: ignora pote, apostas, histórico da mão e o estilo dos adversários.

## Pastas

| Pasta | Conteúdo |
|---|---|
| `rodada1_semente2026/` | 40 situações × 2 configurações (sem RAG e livro), primeira versão do script |
| `rodada2_semente2027/` | 40 situações novas × 3 configurações (sem RAG, livro, curada), com a ação do modelo, a ação corrigida e a ação do sistema híbrido |
| `testes_interface/` | log das decisões feitas pela interface Flask (mãos A, B e C do TCC e testes avulsos) |

## Principais colunas (rodada 2)

| Coluna | Significado |
|---|---|
| `equidade`, `ref_acao` | equidade estimada e ação de referência |
| `config` | `sem`, `livro` ou `curada` |
| `situacao`, `ficha` | situação calculada pelo avaliador e ficha recuperada |
| `acao_llm` | ação devolvida pelo modelo |
| `acao_corrigida` | ação após a verificação de coerência |
| `acao_sistema`, `caminho_sistema` | ação que o sistema real tomaria (caminho rápido quando aplicável) |
| `concorda_*`, `erro_grave_*` | avaliação em cada nível (`llm`, `corr`, `sis`) |
| `t_retrieval_s`, `t_geracao_s`, `t_decisao_s` | tempos de recuperação, geração e decisão |
| `tokens_prompt`, `tokens_gerados`, `tokens_por_s` | métricas do Ollama |
| `cpu_pct`, `ram_pct`, `temp_c` | estado da Raspberry Pi em cada decisão |

## Opções do script

| Opção | Padrão | Efeito |
|---|---|---|
| `--situacoes` | `40` | número de situações (múltiplo de 4) |
| `--seed` | `2027` | semente do sorteio (`2026` repete as situações da rodada 1) |
| `--configs` | `sem,livro,curada` | fontes avaliadas |
| `--oponentes` / `--simulacoes` | `2` / `3000` | parâmetros da equidade por Monte Carlo |
| `--lim-raise` / `--lim-fold` | `1.5` / `0.75` | limiares da ação de referência |
| `--saida` | `logs/benchmark_rag_v2_lote.csv` | CSV de saída (o resumo é gravado ao lado) |
| `--continuar` | – | retoma uma execução interrompida |
| `--apenas-resumo` | – | só recalcula o resumo a partir do CSV |

## Recalcular o resumo da rodada 2

Funciona em qualquer PC, sem a Raspberry Pi:

```bash
cd app_flask
python benchmark_rag.py --apenas-resumo --saida ../benchmark/rodada2_semente2027/benchmark_rag_v2_lote.csv
```

O comando imprime a comparação pareada com o teste exato de McNemar e a concordância por rua.
