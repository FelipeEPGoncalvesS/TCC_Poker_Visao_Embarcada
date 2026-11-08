# Aplicação embarcada (Flask)

Esta pasta é a aplicação que roda na Raspberry Pi 5. O fluxo de uma decisão é este:

1. captura a imagem;
2. detecta as cartas com o YOLO em NCNN;
3. avalia a mão;
4. decide pelo caminho rápido ou pelo RAG com o modelo de linguagem;
5. verifica a coerência da resposta;
6. registra tudo em CSV.

## Módulos

| Arquivo | Função |
|---|---|
| `app.py` | servidor Flask: interface web e API (`/api/status`, `/api/nova-mao`, `/api/cartas`, `/api/decidir`, `/api/benchmark.csv`) |
| `config.py` | parâmetros ajustáveis por variável de ambiente |
| `templates/`, `static/` | página da interface (HTML, CSS e JavaScript sem framework) |
| `poker/camera.py` | Picamera2 aberta uma única vez, em 640 × 480 |
| `poker/detector.py` | YOLO em NCNN; mantém só a detecção de maior confiança de cada carta |
| `poker/cartas.py` | leitura das cartas e avaliador determinístico (melhor jogo de 5 entre 7 cartas, projetos, força só na mesa) |
| `poker/estrategia.py` | regras pré-flop, caminho rápido, situação estratégica, verificação e correção de coerência, *prompts* |
| `poker/rag.py` | recuperação: trechos do livro (`BaseConhecimento`), base curada (`BaseCurada`) ou nenhuma (`SemRAG`) |
| `poker/llm.py` | chamada ao Ollama (Gemma 3 1B), aquecimento e métricas de *tokens* |
| `poker/pipeline.py` | orquestra todas as etapas de uma decisão |
| `poker/partida.py` | estado da mão na interface (posição, cartas por fase da mão) |
| `poker/benchmark.py` | log CSV com tempos, *tokens*, CPU, RAM e temperatura |
| `benchmark_rag.py` | benchmark em lote contra a referência de equidade |
| `criar_base_curada.py` | cria o índice Chroma da base curada a partir de `base_estrategia.json` |

## Principais parâmetros (`config.py`)

| Variável | Padrão | Efeito |
|---|---|---|
| `RAG_FONTE` | `livro` | `livro` usa trechos de 300 caracteres; `curada` usa as fichas por fase da mão e situação |
| `USAR_FAST_PATH` | `1` | decide sem o modelo de linguagem nos casos conclusivos |
| `CORRIGIR_INCOERENCIA` | `1` | troca a ação incoerente pela ação segura da regra violada |
| `BB_CHECK_GRATIS` | `1` | caminho rápido indica Check, em vez de Fold, para mão fraca no Big Blind |
| `NUM_PREDICT` / `TEMPERATURE` | `60` / `0.2` | limite e variação da resposta do modelo |
| `K_RETRIEVAL` / `SCORE_THRESHOLD` | `2` / `0.35` | trechos recuperados do livro e relevância mínima |
| `USAR_CAMERA` / `LLM_MOCK` | `1` / `0` | permitem testar num PC sem câmera e sem Ollama |

## Verificação de coerência

Quando `CORRIGIR_INCOERENCIA=1`, a ação do modelo é substituída nos casos abaixo:

| Situação | Resposta do modelo | Ação aplicada |
|---|---|---|
| Pré-flop com mão "lixo_marginal" | Raise/Bet | Fold (Check no Big Blind) |
| Dois pares ou melhor, usando a mão | Fold | Call |
| Jogo inteiro na mesa | Raise/Bet | Check/Fold |
| Carta alta sem projeto | Raise/Bet | Check/Fold |
| Turn com carta alta e só sequência interna (4 outs) | Raise/Bet | Check/Fold |

## Base curada (`base_estrategia.json`)

São 43 fichas, uma por fase da mão e situação. No pré-flop, a situação é a categoria da mão combinada com o grupo de posição. No pós-flop, é algo como *top pair*, par médio, projeto forte ou jogo só na mesa.

Cada ficha resume a recomendação de "O livro verde do pôquer" e informa as páginas do PDF que a fundamentam. A recuperação filtra a ficha pelos metadados (fase da mão e situação) calculados pelo avaliador e coloca uma única ficha no *prompt*.

Depois de editar o JSON, recrie o índice:

```bash
python criar_base_curada.py
```

## Arquivos gerados localmente (não versionados)

`Models/` (modelo NCNN), `chroma_db_poker/` e `chroma_db_curada/` (índices), `logs/` (CSVs) e `Images/` (capturas).
