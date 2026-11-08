const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

const SIMBOLO = { Hearts: "♥", Diamonds: "♦", Spades: "♠", Trefoils: "♣" };
const VERMELHOS = new Set(["Hearts", "Diamonds"]);

let estado = null;
let posicaoEscolhida = null;
let etapaSelecionada = null;
let ocupado = false;
let cameraPronta = false;
let motivoCamera = "";

async function api(url, opcoes = {}) {
  const resp = await fetch(url, opcoes);
  let corpo;
  try { corpo = await resp.json(); } catch { corpo = { erro: `Resposta inválida (${resp.status})` }; }
  if (!resp.ok) throw new Error(corpo.erro || resp.statusText);
  return corpo;
}

const seg = (v) => (v == null ? "—" : `${Number(v).toFixed(2).replace(".", ",")} s`);
const esc = (t) => String(t ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function cartaHTML(rotulo) {
  if (!rotulo) return '<div class="carta vazia"></div>';
  const [valor, naipe] = rotulo.split(" ");
  const cor = VERMELHOS.has(naipe) ? " vermelha" : "";
  return `<div class="carta${cor}" title="${esc(rotulo)}">${esc(valor)}<span class="naipe">${SIMBOLO[naipe] || "?"}</span></div>`;
}

const curta = (rotulo) => {
  const [v, n] = rotulo.split(" ");
  return `${v}${SIMBOLO[n] || "?"}`;
};

function mensagens(alvo, itens) {
  $(alvo).innerHTML = itens.map(([tipo, texto]) => `<div class="msg ${tipo}">${esc(texto)}</div>`).join("");
}

function classeAcao(acao) {
  return String(acao || "indefinida").toLowerCase().replace(/[^a-z]/g, "");
}

let yoloPronto = false;
const uploadPronto = () => yoloPronto;

function atualizarBotaoCamera() {
  const ativa = Boolean(estado && estado.posicao);
  const podeCapturar = ativa && Boolean(etapaSelecionada) && !ocupado;
  $("#btn-camera").disabled = !podeCapturar || !cameraPronta;
  $("#btn-camera").title = cameraPronta ? "" : motivoCamera;
}

async function atualizarStatus() {
  try {
    const s = await api("/api/status");
    const chip = (nome, item, rotulo) =>
      `<span class="chip${item.ok ? " ok" : ""}" title="${esc(item.erro || "ok")}"><span class="ponto"></span>${esc(rotulo || nome)}</span>`;
    const llmRotulo = s.llm.simulacao ? "LLM (simulação)" : `${s.llm.modelo}${s.llm.ok && !s.llm.aquecido ? " (carregando)" : ""}`;
    const sis = s.sistema;
    const metricas = [
      sis.cpu_pct != null ? `CPU ${Math.round(sis.cpu_pct)}%` : null,
      sis.ram_pct != null ? `RAM ${Math.round(sis.ram_pct)}%` : null,
      sis.temp_c != null ? `${String(sis.temp_c).replace(".", ",")} °C` : null,
    ].filter(Boolean).map((m) => `<span class="chip metrica">${m}</span>`).join("");
    $("#status").innerHTML =
      chip("Câmera", s.camera) +
      chip("YOLO", s.yolo) +
      chip("Regras", s.regras) +
      chip("RAG", s.rag, s.rag.ok ? `RAG (${s.rag.trechos})` : "RAG") +
      chip("LLM", s.llm, llmRotulo) +
      metricas;
    cameraPronta = s.camera.ok && s.yolo.ok;
    yoloPronto = s.yolo.ok;
    $("label[for=arquivo]").title = s.yolo.ok ? "" : s.yolo.erro;
    motivoCamera = !s.camera.ok ? s.camera.erro : !s.yolo.ok ? s.yolo.erro : "";
    atualizarBotaoCamera();
  } catch (e) {
    $("#status").innerHTML = `<span class="chip">Servidor indisponível</span>`;
  }
}

function renderEstado() {
  if (!estado) return;
  const ativa = Boolean(estado.posicao);

  if (!etapaSelecionada || !ativa) etapaSelecionada = estado.proxima_etapa;
  $("#etapas").innerHTML = estado.etapas.map((e, i) => {
    const anteriorOk = i === 0 || estado.etapas[i - 1].completa;
    const cls = ["etapa", e.completa ? "completa" : "", e.chave === etapaSelecionada ? "selecionada" : ""].join(" ");
    return `<li><button type="button" class="${cls}" data-etapa="${e.chave}" ${!ativa || !anteriorOk ? "disabled" : ""}>
      <strong>${esc(e.nome)}</strong>${e.registradas}/${e.qtd}</button></li>`;
  }).join("");
  $$(".etapa").forEach((b) => b.addEventListener("click", () => {
    etapaSelecionada = b.dataset.etapa;
    renderEstado();
  }));

  const c = estado.cartas;
  const board = [...c.flop, ...c.turn, ...c.river];
  $("#board").innerHTML = Array.from({ length: 5 }, (_, i) => cartaHTML(board[i])).join("");
  $("#mao").innerHTML = [0, 1].map((i) => cartaHTML(c.mao[i])).join("");
  $("#info-pos").textContent = ativa
    ? `Posição: ${estado.posicao} — ${estado.posicao_descritiva}`
    : "Nenhuma mão em andamento.";

  const podeCapturar = ativa && Boolean(etapaSelecionada) && !ocupado;
  $("#form-manual button").disabled = !podeCapturar;
  $("#arquivo").disabled = !podeCapturar || !uploadPronto();
  $("label[for=arquivo]").classList.toggle("desativado", $("#arquivo").disabled);
  atualizarBotaoCamera();
  $("#btn-decidir").disabled = !ativa || !estado.ultima_etapa_completa || ocupado;
  if (estado.ultima_etapa_completa) {
    const nome = estado.etapas.find((e) => e.chave === estado.ultima_etapa_completa).nome;
    $("#btn-decidir").textContent = `Obter decisão (${nome === "Mão" ? "pré-flop" : nome.toLowerCase()})`;
  } else {
    $("#btn-decidir").textContent = "Obter decisão";
  }

  renderHistorico();
}

function renderHistorico() {
  const linhas = estado.decisoes || [];
  if (!linhas.length) {
    $("#historico").innerHTML = '<tr><td colspan="8" class="vazio">Nenhuma decisão ainda.</td></tr>';
    return;
  }
  $("#historico").innerHTML = linhas.map((d) => `
    <tr>
      <td>${esc(d.etapa_nome)}</td>
      <td><strong>${esc(d.acao)}</strong></td>
      <td><span class="tag">${esc(d.caminho)}</span></td>
      <td class="numero">${seg(d.tempos.deteccao_s)}</td>
      <td class="numero">${seg(d.tempos.retrieval_s)}</td>
      <td class="numero">${seg(d.tempos.geracao_s)}</td>
      <td class="numero">${seg(d.tempos.decisao_s)}</td>
      <td>${d.coerente ? "sim" : "<strong>não</strong>"}</td>
    </tr>`).join("");
}

async function carregarEstado() {
  estado = await api("/api/estado");
  if (estado.posicao) selecionarPosicao(estado.posicao);
  renderEstado();
}

function selecionarPosicao(sigla) {
  posicaoEscolhida = sigla;
  $$(".pos").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.pos === sigla)));
  $("#btn-nova-mao").disabled = false;
}

$$(".pos").forEach((b) => b.addEventListener("click", () => selecionarPosicao(b.dataset.pos)));

$("#btn-nova-mao").addEventListener("click", async () => {
  try {
    estado = await api("/api/nova-mao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ posicao: posicaoEscolhida }),
    });
    etapaSelecionada = estado.proxima_etapa;
    $("#resultado").hidden = true;
    $("#fig-deteccao").hidden = true;
    mensagens("#msg-cartas", [["info", "Mão iniciada. Capture ou digite as 2 cartas da sua mão."]]);
    mensagens("#msg-decisao", []);
    renderEstado();
  } catch (e) {
    mensagens("#msg-cartas", [["erro", e.message]]);
  }
});

async function enviarCartas(fonte, extra = {}) {
  if (!etapaSelecionada) return;
  const form = new FormData();
  form.append("etapa", etapaSelecionada);
  form.append("fonte", fonte);
  Object.entries(extra).forEach(([k, v]) => form.append(k, v));

  ocupado = true;
  renderEstado();
  mensagens("#msg-cartas", [["info", fonte === "camera" ? "Capturando e detectando…" : "Processando…"]]);
  try {
    const r = await api("/api/cartas", { method: "POST", body: form });
    estado = r.estado;
    etapaSelecionada = estado.proxima_etapa;

    const itens = [];
    if (r.aceitas.length) itens.push(["info", `Registradas: ${r.aceitas.map(curta).join("  ")}`]);
    r.avisos.forEach((a) => itens.push(["aviso", a]));
    mensagens("#msg-cartas", itens);

    if (r.imagem_b64) {
      $("#img-deteccao").src = `data:image/jpeg;base64,${r.imagem_b64}`;
      const det = r.detectadas.map((d) => `${curta(d.rotulo)} (${Math.round(d.confianca * 100)}%)`).join(", ") || "nenhuma carta";
      const t = r.tempos;
      $("#cap-deteccao").textContent =
        `Detectadas: ${det} · captura ${seg(t.captura_s)} · detecção ${seg(t.deteccao_s)}` +
        (t.yolo_ms ? ` (inferência ${t.yolo_ms.inference} ms)` : "");
      $("#fig-deteccao").hidden = false;
    } else {
      $("#fig-deteccao").hidden = true;
    }
    $("#texto-manual").value = "";
  } catch (e) {
    mensagens("#msg-cartas", [["erro", e.message]]);
  } finally {
    ocupado = false;
    renderEstado();
  }
}

$("#btn-camera").addEventListener("click", () => enviarCartas("camera"));
$("#arquivo").addEventListener("change", (ev) => {
  const arquivo = ev.target.files[0];
  if (arquivo) enviarCartas("upload", { imagem: arquivo });
  ev.target.value = "";
});
$("#form-manual").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const texto = $("#texto-manual").value.trim();
  if (texto) enviarCartas("manual", { texto });
});

function renderDecisao(d) {
  const t = d.tempos;
  const linhasTempo = [
    ["Captura da imagem", t.captura_s],
    ["Detecção (YOLO)", t.deteccao_s],
    ["Busca no livro (RAG)", t.retrieval_s],
    ["Geração (LLM)", t.geracao_s],
  ].map(([n, v]) => `<tr><td>${n}</td><td>${seg(v)}</td></tr>`).join("");
  const total = (t.captura_s || 0) + (t.deteccao_s || 0) + (t.decisao_s || 0);

  const tokens = d.tokens_gerados != null
    ? `<tr><td>Tokens gerados / velocidade</td><td>${d.tokens_gerados} · ${String(d.tokens_por_s).replace(".", ",")} tok/s</td></tr>`
    : "";

  const trechos = (d.trechos || []).map((tr) => `
    <div class="trecho${tr.usado ? "" : " descartado"}">
      <div class="cab">score ${String(tr.score).replace(".", ",")} · ${tr.usado ? "usado no prompt" : "descartado (abaixo do limiar)"}${tr.pagina != null && tr.pagina !== "" ? ` · pág. ${typeof tr.pagina === "number" ? tr.pagina + 1 : tr.pagina}` : ""}</div>
      ${esc(tr.texto)}
    </div>`).join("");

  $("#resultado").innerHTML = `
    <div class="decisao-topo">
      <span class="acao ${classeAcao(d.acao)}">${esc(d.acao)}</span>
      <div>
        <div class="meta-decisao">${esc(d.fase)} · ${esc(d.posicao_descritiva)}</div>
        <span class="tag">${esc(d.caminho)}</span>
        ${d.formato_valido ? "" : '<span class="tag">resposta fora do formato</span>'}
      </div>
    </div>
    <p class="motivo">${esc(d.motivo)}</p>
    ${d.alerta ? `<div class="msg aviso">Possível incoerência: ${esc(d.alerta)}</div>` : ""}
    <p class="avaliacao"><strong>Avaliação determinística:</strong> ${esc(d.avaliacao.descricao)}</p>
    <table class="tempos">
      ${linhasTempo}
      ${tokens}
      <tr class="total"><td>Total (visão + decisão)</td><td>${seg(total)}</td></tr>
    </table>
    ${d.consulta_rag ? `<details><summary>Consulta ao livro e trechos (${(d.trechos || []).length})</summary>
      <pre>${esc(d.consulta_rag)}</pre>${trechos || '<p class="dica">Nenhum trecho retornado.</p>'}</details>` : ""}
    ${d.prompt ? `<details><summary>Prompt enviado ao modelo</summary><pre>${esc(d.prompt)}</pre></details>` : ""}
    ${d.resposta_bruta ? `<details><summary>Resposta bruta do modelo</summary><pre>${esc(d.resposta_bruta)}</pre></details>` : ""}
  `;
  $("#resultado").hidden = false;
}

$("#btn-decidir").addEventListener("click", async () => {
  ocupado = true;
  renderEstado();
  mensagens("#msg-decisao", []);
  $("#resultado").hidden = true;
  $("#carregando").hidden = false;
  const inicio = performance.now();
  const relogio = setInterval(() => {
    $("#cronometro").textContent = `${((performance.now() - inicio) / 1000).toFixed(1).replace(".", ",")} s`;
  }, 100);

  try {
    const d = await api("/api/decidir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ forcar_llm: $("#forcar-llm").checked }),
    });
    renderDecisao(d);
    estado = await api("/api/estado");
  } catch (e) {
    mensagens("#msg-decisao", [["erro", e.message]]);
  } finally {
    clearInterval(relogio);
    $("#carregando").hidden = true;
    ocupado = false;
    renderEstado();
  }
});

atualizarStatus();
carregarEstado();
setInterval(atualizarStatus, 3000);
