# Treinamento e avaliação do detector

## Conteúdo

| Caminho | Conteúdo |
|---|---|
| `YOLO_Poker_Treino_Avaliacao_TCC.ipynb` | notebook do Google Colab com as saídas da execução |
| `pesos/yolov8n_cartas_best.pt` | melhor peso do YOLOv8n após 50 épocas (época 44) |
| `resultados/metricas.json` | métricas de treino, validação e teste e a composição do conjunto |
| `resultados/args.yaml` | configuração do treinamento (Ultralytics 8.4, 640 px, lote 16, semente 0) |
| `resultados/results.csv` | histórico por época |
| `resultados/tabelas/` | composição do conjunto, instâncias por classe, métricas por classe e por conjunto |
| `resultados/figuras/` | curvas PR e F1, matrizes de confusão normalizadas e exemplo de predições |

## Executar o notebook

1. Abra o notebook no Google Colab com GPU.
2. Em **Secrets** (ícone de chave), crie `ROBOFLOW_API_KEY` com a sua chave do Roboflow. Ela não fica escrita no notebook.
3. Ajuste `MODEL`, `EPOCHS` e `TREINAR` na célula de parâmetros e execute todas as células.

As saídas vão para `MyDrive/TCC_YOLO/<modelo>_<épocas>ep/` no Google Drive.

## Conjunto de dados

O conjunto está no Roboflow (projeto `cartas-poker-vks90`, versão 4) e tem 52 classes, no formato `<valor> <naipe>` (por exemplo, `10 Hearts`).

| Conjunto | Imagens | Fotos originais | Instâncias |
|---|---:|---:|---:|
| Treino | 6.285 (93,2%) | 2.095 (82,1%) | 19.182 |
| Validação | 283 (4,2%) | 283 (11,1%) | 930 |
| Teste | 173 (2,6%) | 173 (6,8%) | 602 |

O aumento de dados gerou três versões de cada foto de treino. A verificação de vazamento não encontrou fotos originais em comum entre os conjuntos.

**Atenção em `matriz_confusao_resumo.csv`:** a coluna de falsos positivos de fundo conta também predições de baixa confiança. Ela não foi usada no TCC. O indicador usado foi o de cartas trocadas por outra classe (6 de 602 no teste).

## Exportar para a Raspberry Pi

```bash
yolo export model=pesos/yolov8n_cartas_best.pt format=ncnn imgsz=640
```
