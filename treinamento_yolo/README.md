# Treinamento e avaliação do detector

## Conteúdo

| Caminho | Conteúdo |
|---|---|
| `YOLO_Poker_Treino_Avaliacao_TCC.ipynb` | notebook do Google Colab com as saídas da execução |
| `pesos/yolov8n_cartas_embarcado.pt` | peso do modelo que roda na Raspberry Pi (YOLOv8n, 50 épocas) |
| `pesos/yolov8n_cartas_best.pt` | melhor peso (época 44) de um novo treinamento com a mesma configuração, feito para registrar o histórico por época |
| `avaliar_modelo_embarcado.py` | avalia um peso em treino, validação e teste e conta as cartas trocadas por outra classe |
| `resultados/metricas_modelo_embarcado.json` | métricas do modelo embarcado (usadas no TCC) |
| `resultados/metricas.json` | métricas do novo treinamento e a composição do conjunto |
| `resultados/args.yaml` | configuração do treinamento (Ultralytics 8.4, 640 px, lote 16, semente 0) |
| `resultados/results.csv` | histórico por época do novo treinamento (curvas de perda do TCC) |
| `resultados/tabelas/` | composição do conjunto, instâncias por classe, métricas por classe e por conjunto |
| `resultados/figuras/` | curvas PR e F1, matrizes de confusão normalizadas e exemplo de predições |

## Executar o notebook

1. Abra o notebook no Google Colab com GPU.
2. Em **Secrets** (ícone de chave), crie `ROBOFLOW_API_KEY` com a sua chave do Roboflow. Ela não fica escrita no notebook.
3. Ajuste `MODEL`, `EPOCHS` e `TREINAR` na célula de parâmetros e execute todas as células.

As saídas vão para `MyDrive/TCC_YOLO/<modelo>_<épocas>ep/` no Google Drive.

## Avaliar o modelo embarcado

Depois de baixar o conjunto no notebook, rode numa célula:

```bash
!python avaliar_modelo_embarcado.py --pesos pesos/yolov8n_cartas_embarcado.pt --dados <pasta do conjunto>/data.yaml
```

| Conjunto | P | R | mAP50 | mAP50-95 | Cartas trocadas |
|---|---:|---:|---:|---:|---:|
| Treino | 0,992 | 0,988 | 0,994 | 0,971 | – |
| Validação | 0,989 | 0,988 | 0,993 | 0,983 | – |
| Teste | 0,990 | 0,989 | 0,995 | 0,983 | 5 de 602 |

## Conjunto de dados

O conjunto está no Roboflow (projeto `cartas-poker-vks90`, versão 4) e tem 52 classes, no formato `<valor> <naipe>` (por exemplo, `10 Hearts`). São 2.551 fotos originais com 7.926 cartas anotadas, cerca de três por foto.

| Conjunto | Imagens | Fotos originais | Instâncias |
|---|---:|---:|---:|
| Treino | 6.285 (93,2%) | 2.095 (82,1%) | 19.182 (com aumento) |
| Validação | 283 (4,2%) | 283 (11,1%) | 930 |
| Teste | 173 (2,6%) | 173 (6,8%) | 602 |

O aumento de dados gerou três versões de cada foto de treino. A verificação de vazamento não encontrou fotos originais em comum entre os conjuntos.

**Atenção em `matriz_confusao_resumo.csv`:** a coluna de falsos positivos de fundo conta também predições de baixa confiança. Ela não foi usada no TCC. O indicador usado foi o de cartas trocadas por outra classe: 5 de 602 no teste com o modelo embarcado e 6 de 602 com o novo treinamento.

## Exportar para a Raspberry Pi

```bash
yolo export model=pesos/yolov8n_cartas_embarcado.pt format=ncnn imgsz=640
```
