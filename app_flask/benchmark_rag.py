import argparse
import csv
import math
import os
import random
import statistics
import sys
import time
from collections import Counter
from itertools import combinations

VALORES = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
NAIPES = ["Hearts", "Diamonds", "Spades", "Trefoils"]
PESO = {v: i + 2 for i, v in enumerate(VALORES)}
SIMB = {"Hearts": "♥", "Diamonds": "♦", "Spades": "♠", "Trefoils": "♣"}
BARALHO = [f"{v} {n}" for v in VALORES for n in NAIPES]
POSICOES = ["UTG", "MP", "CO", "BTN", "SB", "BB"]
RUAS = {"PRÉ-FLOP": 0, "FLOP": 3, "TURN": 4, "RIVER": 5}


def ler(c):
    v, n = c.split()
    return PESO[v], n


def curta(c):
    v, n = c.split()
    return v + SIMB[n]


def _seq(pesos):
    s = set(pesos)
    if 14 in s:
        s.add(1)
    for topo in range(14, 4, -1):
        if all(p in s for p in range(topo - 4, topo + 1)):
            return topo
    return None


def _p5(cs):
    pesos = sorted((p for p, _ in cs), reverse=True)
    cont = Counter(pesos)
    g = sorted(cont.items(), key=lambda x: (x[1], x[0]), reverse=True)
    flush = len({n for _, n in cs}) == 1
    seq = _seq(pesos) if len(cont) == 5 else None
    if flush and seq:
        return (8, seq)
    if g[0][1] == 4:
        return (7, g[0][0], g[1][0])
    if g[0][1] == 3 and g[1][1] == 2:
        return (6, g[0][0], g[1][0])
    if flush:
        return (5, *pesos)
    if seq:
        return (4, seq)
    if g[0][1] == 3:
        return (3, g[0][0], *[p for p, _ in g[1:]])
    if g[0][1] == 2 and g[1][1] == 2:
        return (2, g[0][0], g[1][0], g[2][0])
    if g[0][1] == 2:
        return (1, g[0][0], *[p for p, _ in g[1:]])
    return (0, *pesos)


def pontuar7(cs):
    return max(_p5(c) for c in combinations(cs, 5))


def equidade(mao, mesa, oponentes, n_sim, rng):
    usadas = set(mao) | set(mesa)
    resto = [c for c in BARALHO if c not in usadas]
    m = [ler(c) for c in mao]
    b0 = [ler(c) for c in mesa]
    faltam = 5 - len(mesa)
    total = 0.0
    for _ in range(n_sim):
        amostra = rng.sample(resto, faltam + 2 * oponentes)
        board = b0 + [ler(c) for c in amostra[:faltam]]
        minha = pontuar7(m + board)
        melhores, empates = True, 1
        for k in range(oponentes):
            op = [ler(c) for c in amostra[faltam + 2 * k: faltam + 2 * k + 2]]
            s = pontuar7(op + board)
            if s > minha:
                melhores = False
                break
            if s == minha:
                empates += 1
        if melhores:
            total += 1.0 / empates
    return total / n_sim


def acao_referencia(eq, oponentes, lim_raise, lim_fold):
    justa = 1.0 / (oponentes + 1)
    if eq >= lim_raise * justa:
        return "Raise"
    if eq < lim_fold * justa:
        return "Fold"
    return "Call/Check"


def normalizar_acao(a):
    a = (a or "").strip().lower()
    if a in ("raise", "bet"):
        return "Raise"
    if a in ("call", "check", "check/call"):
        return "Call/Check"
    if a in ("fold", "check/fold"):
        return "Fold"
    return "Indefinida"


def sortear_situacoes(n, seed):
    rng = random.Random(seed)
    ruas = list(RUAS)
    sits = []
    for i in range(n):
        rua = ruas[i % 4]
        cartas = rng.sample(BARALHO, 2 + RUAS[rua])
        sits.append({"id": i + 1, "rua": rua, "posicao": rng.choice(POSICOES),
                     "mao": cartas[:2], "mesa": cartas[2:]})
    return sits


NOMES = {"sem": "sem RAG", "livro": "RAG livro", "curada": "RAG curado"}
NIVEIS = (("llm", "LLM"), ("corr", "com correção"), ("sis", "sistema híbrido"))
CAMPOS = ["id", "rua", "posicao", "mao", "mesa", "equidade", "ref_acao", "config", "situacao",
          "acao_llm", "acao_corrigida", "acao_sistema", "caminho_sistema", "corrigida",
          "concorda_llm", "erro_grave_llm", "concorda_corr", "erro_grave_corr",
          "concorda_sis", "erro_grave_sis", "coerente", "formato_valido",
          "t_retrieval_s", "t_geracao_s", "t_decisao_s", "tokens_prompt", "tokens_gerados",
          "tokens_por_s", "trechos_recuperados", "trechos_usados", "score_max", "ficha",
          "categoria", "alerta", "motivo", "cpu_pct", "ram_pct", "temp_c"]


def media(vals):
    vals = [float(v) for v in vals if v not in (None, "", "None")]
    return statistics.mean(vals) if vals else None


def pct(linhas, campo):
    return 100.0 * sum(1 for l in linhas if str(l[campo]) == "True") / len(linhas) if linhas else None


def mcnemar_exato(b, c):
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(min(b, c) + 1)) / 2 ** n)


def resumir(linhas, configs):
    resumo = []
    for cfg in configs:
        L = [l for l in linhas if l["config"] == cfg]
        if not L:
            continue
        r = {"Configuração": NOMES.get(cfg, cfg), "N": len(L)}
        for chave, rotulo in NIVEIS:
            r[f"Concordância {rotulo} (%)"] = pct(L, f"concorda_{chave}")
            r[f"Erro grave {rotulo} (%)"] = pct(L, f"erro_grave_{chave}")
        r.update({
            "Coerentes LLM (%)": pct(L, "coerente"),
            "Corrigidas (%)": pct(L, "corrigida"),
            "Formato válido (%)": pct(L, "formato_valido"),
            "Tempo médio LLM (s)": media(l["t_decisao_s"] for l in L),
            "Tempo mínimo LLM (s)": min(float(l["t_decisao_s"]) for l in L),
            "Tempo máximo LLM (s)": max(float(l["t_decisao_s"]) for l in L),
            "Tokens de prompt (média)": media(l["tokens_prompt"] for l in L),
            "Escore máximo médio": media(l["score_max"] for l in L) if cfg != "sem" else None,
            "Temperatura máxima (°C)": max((float(l["temp_c"]) for l in L if l["temp_c"] not in ("", "None")), default=None),
        })
        resumo.append(r)
    return resumo


def imprimir(resumo, linhas, configs):
    def f(v, nd=1):
        return "—" if v is None else (f"{v:.{nd}f}".replace(".", ","))
    print("\n" + "=" * 78)
    print("RESUMO (vai para a Tabela da Seção 4.5)")
    print("=" * 78)
    for r in resumo:
        print(f"\n{r['Configuração']}  (N = {r['N']})")
        for k in list(r)[2:]:
            print(f"  {k:<36} {f(r[k], 3 if 'Escore' in k else 1)}")

    por_id = {}
    for l in linhas:
        por_id.setdefault(l["id"], {})[l["config"]] = l
    if "sem" in configs:
        for cfg in configs:
            if cfg == "sem":
                continue
            pares = [v for v in por_id.values() if "sem" in v and cfg in v]
            if not pares:
                continue
            print(f"\nComparação pareada: {NOMES[cfg]} x sem RAG ({len(pares)} situações)")
            for chave, rotulo in NIVEIS:
                k = f"concorda_{chave}"
                b = sum(1 for v in pares if v[cfg][k] == "True" and v["sem"][k] != "True")
                c = sum(1 for v in pares if v["sem"][k] == "True" and v[cfg][k] != "True")
                print(f"  {rotulo:<16} só {NOMES[cfg]} acertou: {b:>2} | só sem RAG acertou: {c:>2} | "
                      f"McNemar exato p = {mcnemar_exato(b, c):.3f}")

    print("\nConcordância do LLM por rua:")
    print("  " + " " * 10 + " / ".join(NOMES[c] for c in configs))
    for rua in RUAS:
        vals = [pct([l for l in linhas if l["rua"] == rua and l["config"] == c], "concorda_llm") for c in configs]
        print(f"  {rua:<9} " + " / ".join(f"{f(v)}%" for v in vals))
    uma = [l for l in linhas if l["config"] == configs[0]]
    print("\nDistribuição das ações de referência:", dict(Counter(l["ref_acao"] for l in uma)))
    print("Decisões do sistema pelo caminho rápido:",
          sum(1 for l in uma if l["caminho_sistema"] == "fast-path"), "de", len(uma))


def avaliar(acao, ref):
    return acao == ref, {acao, ref} == {"Raise", "Fold"}


def main():
    ap = argparse.ArgumentParser(description="Benchmark em lote: sem RAG x RAG livro x RAG curado")
    ap.add_argument("--situacoes", type=int, default=40, help="número de situações (múltiplo de 4)")
    ap.add_argument("--seed", type=int, default=2027,
                    help="2027 = situações novas (validação das regras); 2026 = as da Tabela 6")
    ap.add_argument("--configs", default="sem,livro,curada", help="lista separada por vírgulas: sem,livro,curada")
    ap.add_argument("--oponentes", type=int, default=2, help="oponentes aleatórios na equidade")
    ap.add_argument("--simulacoes", type=int, default=3000, help="simulações de Monte Carlo por situação")
    ap.add_argument("--lim-raise", type=float, default=1.5, help="Raise se equidade >= lim × parte justa")
    ap.add_argument("--lim-fold", type=float, default=0.75, help="Fold se equidade < lim × parte justa")
    ap.add_argument("--saida", default=os.path.join("logs", "benchmark_rag_v2_lote.csv"))
    ap.add_argument("--continuar", action="store_true", help="pula decisões já gravadas no CSV")
    ap.add_argument("--apenas-resumo", action="store_true", help="só recalcula o resumo do CSV existente")
    args = ap.parse_args()
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    invalidas = [c for c in configs if c not in NOMES]
    if invalidas:
        sys.exit(f"Configurações inválidas: {invalidas}. Use: sem, livro, curada.")
    os.makedirs(os.path.dirname(args.saida) or ".", exist_ok=True)
    arq_resumo = args.saida.replace("_lote.csv", "_resumo.csv")
    if arq_resumo == args.saida:
        arq_resumo = os.path.splitext(args.saida)[0] + "_resumo.csv"

    def ler_csv():
        if not os.path.exists(args.saida):
            return []
        with open(args.saida, encoding="utf-8") as fh:
            return list(csv.DictReader(fh, delimiter=";"))

    def gravar_resumo(linhas):
        resumo = resumir(linhas, configs)
        if not resumo:
            print("Nenhuma linha no CSV.")
            return
        with open(arq_resumo, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(resumo[0]), delimiter=";")
            w.writeheader()
            for r in resumo:
                w.writerow({k: ("" if v is None else (f"{v:.3f}".replace(".", ",") if isinstance(v, float) else v))
                            for k, v in r.items()})
        imprimir(resumo, linhas, configs)
        print(f"\nArquivos: {args.saida} e {arq_resumo}")

    if args.apenas_resumo:
        gravar_resumo(ler_csv())
        return

    import config
    config.USAR_CAMERA = False
    config.BENCHMARK_CSV = os.path.join("logs", "benchmark_lote_pipeline.csv")
    from poker.estrategia import fast_path_pos_flop, fast_path_pre_flop
    from poker.pipeline import Assistente

    sits = sortear_situacoes(args.situacoes, args.seed)
    feitas = {(l["id"], l["config"]) for l in ler_csv()} if args.continuar else set()
    if not args.continuar and os.path.exists(args.saida):
        os.remove(args.saida)

    assistente = Assistente(usar_camera=False)
    if not assistente.llm.disponivel:
        sys.exit(f"LLM indisponível: {assistente.llm.erro}")
    for cfg in configs:
        b = assistente.bases[cfg]
        if cfg != "sem" and not b.disponivel:
            sys.exit(f"Fonte '{cfg}' indisponível ({b.erro}).")
    print(f"Configurações: {', '.join(NOMES[c] for c in configs)} | semente {args.seed} | "
          f"correção de coerência: {'ligada' if config.CORRIGIR_INCOERENCIA else 'desligada'}")
    print("Aguardando o modelo carregar na memória...", end="", flush=True)
    for _ in range(180):
        if assistente.llm.aquecido:
            break
        time.sleep(1)
    print(" ok")

    rng_eq = random.Random(args.seed + 1)
    total = len(configs) * len(sits)
    n = len(feitas)
    t_ini = time.time()
    base_original = assistente.base
    novo = not os.path.exists(args.saida)
    with open(args.saida, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAMPOS, delimiter=";")
        if novo:
            w.writeheader()
        for s in sits:
            eq = equidade(s["mao"], s["mesa"], args.oponentes, args.simulacoes, rng_eq)
            ref = acao_referencia(eq, args.oponentes, args.lim_raise, args.lim_fold)
            k = s["id"] % len(configs)
            ordem = configs[k:] + configs[:k]
            for cfg in ordem:
                if (str(s["id"]), cfg) in feitas:
                    continue
                assistente.base = assistente.bases[cfg]
                try:
                    d = assistente.decidir(s["posicao"], s["mao"], s["mesa"], forcar_llm=True)
                finally:
                    assistente.base = base_original
                if d["fase"] == "PRÉ-FLOP":
                    fp = fast_path_pre_flop(d["regra_pre_flop"]["categoria"], s["posicao"])
                else:
                    fp = fast_path_pos_flop(d["avaliacao"])
                a_llm = normalizar_acao(d["acao_llm"])
                a_corr = normalizar_acao(d["acao"])
                a_sis = normalizar_acao(fp) if fp else a_corr
                trechos = d.get("trechos") or []
                linha = {
                    "id": s["id"], "rua": s["rua"], "posicao": s["posicao"],
                    "mao": " ".join(curta(c) for c in s["mao"]),
                    "mesa": " ".join(curta(c) for c in s["mesa"]),
                    "equidade": round(eq, 4), "ref_acao": ref, "config": cfg,
                    "situacao": d.get("situacao"),
                    "acao_llm": d["acao_llm"], "acao_corrigida": d["acao"],
                    "acao_sistema": fp or d["acao"], "caminho_sistema": "fast-path" if fp else "llm",
                    "corrigida": d.get("corrigida", False),
                    "coerente": d["coerente"], "formato_valido": d["formato_valido"],
                    "t_retrieval_s": d["tempos"]["retrieval_s"], "t_geracao_s": d["tempos"]["geracao_s"],
                    "t_decisao_s": d["tempos"]["decisao_s"],
                    "tokens_prompt": d.get("tokens_prompt"), "tokens_gerados": d.get("tokens_gerados"),
                    "tokens_por_s": d.get("tokens_por_s"),
                    "trechos_recuperados": len(trechos), "trechos_usados": sum(1 for t in trechos if t["usado"]),
                    "score_max": max((t["score"] for t in trechos), default=""),
                    "ficha": ",".join(str(t.get("ficha")) for t in trechos if t.get("ficha")),
                    "categoria": d["avaliacao"].get("categoria_regra") or d["avaliacao"]["categoria"],
                    "alerta": d.get("alerta") or "", "motivo": (d.get("motivo") or "").replace("\n", " ")[:300],
                    "cpu_pct": d["sistema"].get("cpu_pct"), "ram_pct": d["sistema"].get("ram_pct"),
                    "temp_c": d["sistema"].get("temp_c"),
                }
                for chave, acao in (("llm", a_llm), ("corr", a_corr), ("sis", a_sis)):
                    linha[f"concorda_{chave}"], linha[f"erro_grave_{chave}"] = avaliar(acao, ref)
                w.writerow(linha)
                fh.flush()
                n += 1
                passou = time.time() - t_ini
                resta = passou / max(1, n - len(feitas)) * (total - n)
                print(f"[{n:>3}/{total}] #{s['id']:<3} {s['rua']:<8} {NOMES[cfg]:<10} "
                      f"{linha['mao']:<7} | {linha['mesa']:<14} eq {eq:5.1%} ref {ref:<10} "
                      f"LLM {a_llm:<10}{'✓' if linha['concorda_llm'] else '✗'} "
                      f"sist {a_sis:<10}{'✓' if linha['concorda_sis'] else '✗'} {linha['t_decisao_s']:.1f}s"
                      f"  (faltam ~{resta/60:.0f} min)")
    assistente.encerrar()
    gravar_resumo(ler_csv())


if __name__ == "__main__":
    main()
