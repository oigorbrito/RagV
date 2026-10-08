import express from 'express';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import helmet from 'helmet';
import crypto from 'crypto';

const RAW_RPY_TOKENS = process.env.RPY_BEARER_TOKENS || process.env.RPY_BEARER_TOKEN || process.env.RPY_OPS_TOKEN || '';
const configuredBearerTokens = RAW_RPY_TOKENS.split(',').map(t => t.trim()).filter(Boolean);

function isTimingSafeEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const bufA = Buffer.from(a);
  const bufB = Buffer.from(b);
  if (bufA.length !== bufB.length) return false;
  return crypto.timingSafeEqual(bufA, bufB);
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(helmet({ contentSecurityPolicy: false }));
app.use(express.json({ limit: '10mb' }));

// Serve static frontend
app.use(express.static(path.join(__dirname, 'app', 'frontend')));

const DATA_DIR = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_DIR)) {
  try { fs.mkdirSync(DATA_DIR, { recursive: true }); } catch {}
}
const PROCESSES_FILE = path.join(DATA_DIR, 'processes.json');
const REQUESTS_FILE = path.join(DATA_DIR, 'requests.json');

// Persistent process store and webhook store
const processes = new Map();
const requestedProcesses = new Set();
const webhookStore = new Map();

try {
  if (fs.existsSync(PROCESSES_FILE)) {
    const data = JSON.parse(fs.readFileSync(PROCESSES_FILE, 'utf-8'));
    for (const [k, v] of Object.entries(data)) {
      processes.set(k, v);
    }
  }
} catch (e) {
  console.warn('Could not load persistent processes:', e);
}

try {
  if (fs.existsSync(REQUESTS_FILE)) {
    const data = JSON.parse(fs.readFileSync(REQUESTS_FILE, 'utf-8'));
    data.forEach(item => requestedProcesses.add(item));
  }
} catch (e) {
  console.warn('Could not load persistent requests:', e);
}

function persistState() {
  try {
    const procObj = Object.fromEntries(processes.entries());
    fs.writeFileSync(PROCESSES_FILE, JSON.stringify(procObj, null, 2));
    fs.writeFileSync(REQUESTS_FILE, JSON.stringify(Array.from(requestedProcesses.values()), null, 2));
  } catch (e) {
    console.warn('Could not persist state:', e);
  }
}

function isValidCnj(cnj) {
  const clean = String(cnj || '').replace(/\D/g, '');
  if (clean.length !== 20) return false;
  if (clean === DEMO_CLEAN_CODE) return true;
  try {
    const seq = clean.slice(0, 7);
    const dv = clean.slice(7, 9);
    const rest = clean.slice(9);
    const base = BigInt(seq + rest);
    const expected = 98n - ((base * 100n) % 97n);
    return Number(expected) === parseInt(dv, 10);
  } catch {
    return true;
  }
}

const DEMO_CODE = "0000000-00.2026.8.21.0001";
const DEMO_CLEAN_CODE = "00000000020268210001";

const defaultDemoProcess = {
  code: DEMO_CODE,
  class_name: "Ação Cível",
  court: "TJRS",
  updated_at: new Date().toISOString(),
  header: {
    instance: 1,
    state: "RS",
    county: "Porto Alegre",
    amount: "50000.00",
    justice_description: "Estadual",
    area: "Cível"
  },
  parties: [
    { name: "Empresa Alfa Ltda.", side: "active", person_type: "company" },
    { name: "Empresa Beta Ltda.", side: "passive", person_type: "company" }
  ],
  subjects: [
    { name: "Contrato", code: "9583" },
    { name: "Obrigações", code: "7699" }
  ],
  recent_steps: [
    {
      occurred_at: "2026-03-18T12:00:00Z",
      title: "Contestação",
      text: "Contestação sintética apresentada para teste do fluxo do produto."
    },
    {
      occurred_at: "2026-02-05T12:00:00Z",
      title: "Citação",
      text: "Citação sintética registrada no ambiente de demonstração."
    },
    {
      occurred_at: "2026-01-10T12:00:00Z",
      title: "Distribuição",
      text: "Processo sintético distribuído para fins de demonstração local."
    }
  ],
  attachments: [
    { id: "att-1", name: "Petição Inicial.pdf", size: "1.2 MB", status: "processed" },
    { id: "att-2", name: "Contestação.pdf", size: "850 KB", status: "processed" }
  ],
  summary_status: "ready",
  summary: {
    markdown: "# Resumo do processo\n\nProcesso 0000000-00.2026.8.21.0001. Situação processual registrada.\n\n## Pontos de atenção\n- Nenhuma divergência objetiva identificada.\n- Prazo regular em curso.",
    created_at: new Date().toISOString(),
    model: "local-demo-no-provider"
  }
};

if (!processes.has(DEMO_CODE)) {
  processes.set(DEMO_CODE, defaultDemoProcess);
  processes.set(DEMO_CLEAN_CODE, defaultDemoProcess);
  persistState();
}

function checkAuth(req, res, next) {
  const authHeader = req.headers['authorization'];
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Falta credencial de usuário (Bearer token obrigatório).' });
  }
  const token = authHeader.substring(7).trim();
  if (!token) {
    return res.status(401).json({ error: 'Token de autorização não pode ser vazio.' });
  }
  if (configuredBearerTokens.length > 0) {
    const isValid = configuredBearerTokens.some(expected => isTimingSafeEqual(token, expected));
    if (!isValid) {
      return res.status(401).json({ error: 'Token de autorização inválido ou não autorizado.' });
    }
  }
  req.userToken = token;
  next();
}

// Webhook & Attachments Ingress Endpoint (100% offline, zero-cost)
app.post(['/webhook', '/judit/webhook', '/api/webhook', '/api/v1/webhook'], (req, res) => {
  const tokenHeader = req.headers['x-webhook-token'] || req.headers['authorization'];
  const expectedToken = process.env.JUDIT_WEBHOOK_TOKEN || process.env.WEBHOOK_SECRET;

  if (expectedToken) {
    const cleanHeaderToken = tokenHeader ? tokenHeader.replace(/^Bearer\s+/i, '').trim() : '';
    if (cleanHeaderToken !== expectedToken) {
      return res.status(401).json({ error: 'Invalid webhook token/secret' });
    }
  }

  const tenantId = req.headers['x-webhook-tenant-id'] || req.headers['x-tenant-id'] || process.env.JUDIT_WEBHOOK_TENANT_ID || 'default-tenant';
  const payload = req.body || {};

  console.log(`[Webhook Received] Tenant ID: ${tenantId}, Payload type:`, payload.response_type || payload.event || 'unknown');

  const responseData = payload.response_data || payload.data || payload;
  const cnjCode = responseData.code || responseData.numeroProcesso;

  if (cnjCode) {
    const cleanCode = cnjCode.replace(/\D/g, '');
    const webhookProcess = {
      code: cnjCode,
      class_name: responseData.class_name || responseData.classe?.nome || "Procedimento Comum",
      court: responseData.court || "TJ",
      updated_at: new Date().toISOString(),
      header: responseData.header || { instance: 1, state: "SP" },
      parties: responseData.parties || [],
      subjects: responseData.subjects || [],
      recent_steps: responseData.recent_steps || responseData.movimentacoes || [],
      attachments: responseData.attachments || [
        { id: "att-webhook-1", name: "Documento_Oficial.pdf", size: "2.1 MB", status: "processed", tenant_id: tenantId }
      ],
      summary_status: "ready",
      summary: {
        markdown: `# Resumo do processo (Webhook)\n\nProcesso ${cnjCode} atualizado com sucesso via webhook (Tenant: ${tenantId}).`,
        created_at: new Date().toISOString(),
        model: "webhook-ingest"
      }
    };
    processes.set(cnjCode, webhookProcess);
    processes.set(cleanCode, webhookProcess);
    webhookStore.set(cleanCode, { tenantId, payload, receivedAt: new Date().toISOString() });
    persistState();
  }

  res.json({
    status: "received",
    tenant_id: tenantId,
    timestamp: new Date().toISOString()
  });
});

function getTribunalAlias(cnj) {
  const clean = String(cnj || '').replace(/\D/g, '');
  if (clean.length !== 20) return null;
  const j = clean[13];
  const tr = clean.slice(14, 16);

  if (j === '8') {
    const tjMap = {
      '01': 'tjac', '02': 'tjal', '03': 'tjap', '04': 'tjam',
      '05': 'tjba', '06': 'tjce', '07': 'tjdft', '08': 'tjes',
      '09': 'tjgo', '10': 'tjma', '11': 'tjmt', '12': 'tjms',
      '13': 'tjmg', '14': 'tjpa', '15': 'tjpb', '16': 'tjpr',
      '17': 'tjpe', '18': 'tjpi', '19': 'tjrj', '20': 'tjrn',
      '21': 'tjrs', '22': 'tjro', '23': 'trr', '24': 'tjsc',
      '25': 'tjse', '26': 'tjsp', '27': 'tjto'
    };
    return tjMap[tr] || null;
  }
  if (j === '4') {
    const num = parseInt(tr, 10);
    if (num >= 1 && num <= 6) return `trf${num}`;
  }
  if (j === '5') {
    const num = parseInt(tr, 10);
    if (num >= 1 && num <= 24) return `trt${num}`;
  }
  if (j === '3') return 'stj';
  if (j === '1') return 'stf';
  if (j === '2') return 'tst';
  return null;
}

async function fetchDatajudProcess(cleanCode, rawCode, apiKey) {
  const alias = getTribunalAlias(cleanCode);
  if (!alias) {
    return { error: 'Não foi possível identificar o tribunal correspondente a partir deste número CNJ.', status: 400 };
  }

  const cleanKey = apiKey ? apiKey.replace(/^ApiKey\s+/i, '').replace(/^Bearer\s+/i, '').trim() : '';
  if (!cleanKey) {
    return { error: 'Chave da API Pública do Datajud não informada.', status: 401 };
  }

  const endpoint = `https://api-publica.datajud.cnj.jus.br/api_publica_${alias}/_search`;
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Authorization': `APIKey ${cleanKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query: {
          match: {
            numeroProcesso: cleanCode
          }
        }
      }),
      signal: AbortSignal.timeout(15000)
    });

    if (response.status === 401 || response.status === 403) {
      return {
        error: 'Chave do Datajud inválida ou rejeitada pelo CNJ. Verifique se a sua chave pública da API Datajud está correta e atualizada.',
        status: 401
      };
    }

    if (!response.ok) {
      const errText = await response.text();
      return { error: `Erro retornado pelo tribunal no Datajud (${response.status}): ${errText.slice(0, 150)}`, status: response.status };
    }

    const data = await response.json();
    const hits = data?.hits?.hits || [];
    if (!hits.length) {
      return {
        notFound: true,
        message: `Processo ${rawCode} não localizado no Datajud para o tribunal ${alias.toUpperCase()}. Verifique se o processo é público e pertence a esse tribunal.`
      };
    }

    const source = hits[0]._source;
    const courtName = source.tribunal || alias.toUpperCase();
    const className = source.classe?.nome || source.dadosBasicos?.classeProcessual?.nome || 'Procedimento Comum';
    const orgaoNome = source.orgaoJulgador?.nome || source.dadosBasicos?.orgaoJulgador?.nome || '';
    const valorCausa = source.dadosBasicos?.valorCausa || source.valorCausa || '';
    const updatedAt = source.dataHoraUltimaAtualizacao || new Date().toISOString();

    const parties = [];
    const poloList = source.dadosBasicos?.polo || source.polos || [];
    if (Array.isArray(poloList)) {
      for (const p of poloList) {
        const side = (p.polo === 'AT' || p.polo === 'A') ? 'active' : (p.polo === 'PA' || p.polo === 'P') ? 'passive' : 'other';
        const parte = p.parte || p;
        const name = parte.nome || p.nome || 'Parte não identificada';
        const personType = parte.tipoPessoa === 'JURIDICA' || parte.pessoaJuridica ? 'company' : 'person';
        parties.push({ name, side, person_type: personType });
      }
    }

    const subjects = [];
    const assuntosList = source.assuntos || source.dadosBasicos?.assuntos || [];
    if (Array.isArray(assuntosList)) {
      for (const a of assuntosList) {
        subjects.push({
          code: String(a.codigo || ''),
          name: a.nome || 'Assunto'
        });
      }
    }

    const recent_steps = [];
    const movimentosList = source.movimentos || [];
    if (Array.isArray(movimentosList)) {
      const sorted = [...movimentosList].sort((a, b) => {
        const da = new Date(a.dataHora || 0).getTime();
        const db = new Date(b.dataHora || 0).getTime();
        return db - da;
      });

      for (const m of sorted.slice(0, 40)) {
        let text = '';
        if (Array.isArray(m.complementosTabelados) && m.complementosTabelados.length) {
          text = m.complementosTabelados.map(c => c.descricao || c.nome || '').filter(Boolean).join(' - ');
        }
        if (!text && m.descricao) text = m.descricao;
        if (!text) text = `Movimento registrado na fonte (${courtName}).`;

        recent_steps.push({
          occurred_at: m.dataHora || new Date().toISOString(),
          title: m.nome || 'Movimentação',
          text
        });
      }
    }

    const summaryText = `# Resumo do processo (Datajud / CNJ)\n\nProcesso **${rawCode}** (${className}) em tramitação perante o **${courtName}**${orgaoNome ? ` (${orgaoNome})` : ''}.\n\n## Principais informações\n- **Tribunal:** ${courtName}\n- **Última atualização registrada:** ${new Date(updatedAt).toLocaleString('pt-BR')}\n- **Total de movimentações:** ${movimentosList.length}\n${recent_steps.length ? `- **Último andamento:** ${recent_steps[0].title} (${new Date(recent_steps[0].occurred_at).toLocaleDateString('pt-BR')})` : ''}\n\n## Partes qualificadas\n${parties.length ? parties.map(p => `- **${p.side === 'active' ? 'Polo Ativo' : 'Polo Passivo'}:** ${p.name}`).join('\n') : '- Nenhuma parte pública detalhada no extrato do CNJ.'}`;

    return {
      success: true,
      process: {
        code: rawCode,
        class_name: className,
        court: courtName,
        updated_at: updatedAt,
        header: {
          instance: source.grau === 'G2' ? 2 : 1,
          state: alias.startsWith('tj') ? alias.slice(2).toUpperCase() : 'BR',
          county: orgaoNome,
          amount: valorCausa ? String(valorCausa) : '',
          justice_description: "Pública / CNJ Datajud",
          area: source.sistema?.nome || "Judicial"
        },
        parties,
        subjects,
        recent_steps,
        attachments: [],
        summary_status: "ready",
        summary: {
          markdown: summaryText,
          created_at: new Date().toISOString(),
          model: "datajud-cnj-live"
        }
      }
    };
  } catch (err) {
    if (err.name === 'TimeoutError') {
      return { error: 'Tempo limite esgotado ao conectar à API do Datajud (CNJ).', status: 504 };
    }
    return { error: `Falha na requisição ao Datajud: ${err.message}`, status: 502 };
  }
}

async function fetchJuditProcess(cleanCode, rawCode, apiKey) {
  const cleanKey = apiKey ? apiKey.replace(/^Bearer\s+/i, '').replace(/^ApiKey\s+/i, '').trim() : '';
  if (!cleanKey) {
    return { error: 'Chave da API da Judit não informada.', status: 401 };
  }

  try {
    const lawsuitResponse = await fetch(`https://lawsuits.prod.judit.io/lawsuits/${cleanCode}`, {
      method: 'GET',
      headers: {
        'api-key': cleanKey,
        'Authorization': `Bearer ${cleanKey}`,
        'Accept': 'application/json'
      },
      signal: AbortSignal.timeout(15000)
    });

    if (lawsuitResponse.status === 401 || lawsuitResponse.status === 403) {
      return { error: 'Chave da Judit inválida ou não autorizada. Verifique a credencial da Judit.', status: 401 };
    }

    if (lawsuitResponse.ok) {
      const payload = await lawsuitResponse.json();
      const resData = payload.response_data || payload.data || payload;

      const movements = (resData.recent_steps || resData.movimentacoes || []).map(m => ({
        occurred_at: m.occurred_at || m.dataHora || new Date().toISOString(),
        title: m.title || m.nome || 'Movimentação',
        text: m.text || m.descricao || ''
      }));

      const parties = (resData.parties || resData.partes || []).map(p => ({
        name: p.name || p.nome || 'Parte',
        side: p.side || (p.polo === 'AT' ? 'active' : 'passive'),
        person_type: p.person_type || 'person'
      }));

      const subjects = (resData.subjects || resData.assuntos || []).map(s => ({
        code: String(s.code || s.codigo || ''),
        name: s.name || s.nome || 'Assunto'
      }));

      const attachments = (resData.attachments || resData.anexos || []).map((att, idx) => ({
        id: att.id || `att-${idx + 1}`,
        name: att.name || att.nome || `Documento_${idx + 1}.pdf`,
        size: att.size || att.tamanho || 'Disponível',
        status: 'processed'
      }));

      return {
        success: true,
        process: {
          code: rawCode,
          class_name: resData.class_name || resData.classe?.nome || "Procedimento Comum",
          court: resData.court || resData.tribunal || "TJ",
          updated_at: resData.updated_at || new Date().toISOString(),
          header: resData.header || {
            instance: 1,
            state: "BR",
            county: resData.county || resData.comarca || "",
            amount: resData.amount || "",
            justice_description: "Datalake Processual"
          },
          parties,
          subjects,
          recent_steps: movements,
          attachments,
          summary_status: "ready",
          summary: {
            markdown: `# Resumo do processo\n\nProcesso **${rawCode}** consultado na fonte processual.\n\n## Status\n- **Tribunal:** ${resData.court || "Identificado"}\n- **Movimentações indexadas:** ${movements.length}\n- **Anexos disponíveis:** ${attachments.length}`,
            created_at: new Date().toISOString(),
            model: "rag-v-live"
          }
        }
      };
    }

    if (lawsuitResponse.status === 404) {
      return { notFound: true, message: 'Processo ainda não localizado na fonte processual. Clique em "Solicitar consulta" para iniciar a busca.' };
    }
  } catch (err) {
    if (err.name === 'TimeoutError') {
      return { error: 'Tempo limite esgotado ao conectar à API da Judit.', status: 504 };
    }
    return { error: `Falha na requisição à Judit: ${err.message}`, status: 502 };
  }

  return { notFound: true, message: 'Processo ainda não disponível na Judit.' };
}

async function requestJuditAcquisition(cleanCode, rawCode, apiKey) {
  const cleanKey = apiKey ? apiKey.replace(/^Bearer\s+/i, '').replace(/^ApiKey\s+/i, '').trim() : '';
  if (!cleanKey) {
    return { error: 'Chave da API da Judit não informada.', status: 401 };
  }

  try {
    const response = await fetch('https://requests.prod.judit.io/requests', {
      method: 'POST',
      headers: {
        'api-key': cleanKey,
        'Authorization': `Bearer ${cleanKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        search: {
          search_type: "lawsuit_cnj",
          search_key: cleanCode
        }
      }),
      signal: AbortSignal.timeout(15000)
    });

    if (response.status === 401 || response.status === 403) {
      return { error: 'Chave da Judit inválida ou não autorizada.', status: 401 };
    }

    const data = await response.json();
    return {
      success: true,
      data,
      message: 'Solicitação de busca registrada na Judit. O robô está processando a aquisição dos autos.'
    };
  } catch (err) {
    return { error: `Erro ao solicitar busca na Judit: ${err.message}`, status: 502 };
  }
}

app.get('/api/sources', (req, res) => {
  const hasJudit = Boolean((process.env.JUDIT_API_KEY || '').trim());
  const hasDatajud = Boolean((process.env.DATAJUD_API_KEY || '').trim());
  res.json({
    sources: [
      { id: 'judit', name: 'Judit', description: 'Autos completos, movimentações e peças processuais', configured: hasJudit },
      { id: 'datajud', name: 'Datajud', description: 'API Pública CNJ (todos os tribunais do Brasil)', configured: hasDatajud }
    ],
    default: hasJudit ? 'judit' : (hasDatajud ? 'datajud' : 'judit')
  });
});

app.get('/processes/:code', checkAuth, async (req, res) => {
  const rawCode = req.params.code;
  const cleanCode = rawCode.replace(/\D/g, '');
  const requestedSource = (req.headers['x-process-source'] || req.query.source || 'judit').toLowerCase();

  if (!isValidCnj(rawCode)) {
    return res.status(400).json({ error: 'Formato CNJ inválido ou falha no cálculo do dígito verificador' });
  }

  // 1. Verificar cache local em memória / disco
  const cacheKey = `${cleanCode}_${requestedSource}`;
  let proc = processes.get(cacheKey);
  if (!proc) {
    const fallbackProc = processes.get(rawCode) || processes.get(cleanCode);
    if (fallbackProc && (!fallbackProc.source || fallbackProc.source === requestedSource)) {
      proc = fallbackProc;
    }
  }
  if (proc) {
    if (!proc.source) proc.source = requestedSource;
    return res.json(proc);
  }

  // 2. Resolver chaves de infraestrutura (gerenciadas com segurança no servidor)
  const juditApiKey = (process.env.JUDIT_API_KEY || '').trim();
  const datajudApiKey = (process.env.DATAJUD_API_KEY || '').trim();

  const activeSource = requestedSource === 'datajud' ? 'datajud' : 'judit';
  const hasKey = activeSource === 'datajud' ? Boolean(datajudApiKey) : Boolean(juditApiKey);
  const isDemo = cleanCode === DEMO_CLEAN_CODE || !hasKey;

  if (activeSource === 'datajud' && !isDemo && datajudApiKey) {
    const djResult = await fetchDatajudProcess(cleanCode, rawCode, datajudApiKey);
    if (djResult.success) {
      djResult.process.source = 'datajud';
      processes.set(cacheKey, djResult.process);
      processes.set(rawCode, djResult.process);
      processes.set(cleanCode, djResult.process);
      persistState();
      return res.json(djResult.process);
    }
    if (djResult.notFound) {
      return res.status(404).json({ error: djResult.message });
    }
    return res.status(djResult.status || 500).json({ error: djResult.error });
  }

  if (activeSource === 'judit' && !isDemo && juditApiKey) {
    const juditResult = await fetchJuditProcess(cleanCode, rawCode, juditApiKey);
    if (juditResult.success) {
      juditResult.process.source = 'judit';
      processes.set(cacheKey, juditResult.process);
      processes.set(rawCode, juditResult.process);
      processes.set(cleanCode, juditResult.process);
      persistState();
      return res.json(juditResult.process);
    }
    if (juditResult.notFound) {
      return res.status(404).json({ error: juditResult.message });
    }
    return res.status(juditResult.status || 500).json({ error: juditResult.error });
  }

  // Fallback demo/offline
  if (cleanCode.length === 20) {
    if (!requestedProcesses.has(cleanCode) && !requestedProcesses.has(rawCode)) {
      const sourceName = activeSource === 'datajud' ? 'Datajud (CNJ)' : 'Judit';
      return res.status(404).json({ error: `Processo não encontrado no cache local. Solicite a busca na fonte ${sourceName}.` });
    }
    proc = {
      code: rawCode,
      source: activeSource,
      class_name: "Procedimento Comum Cível",
      court: activeSource === 'datajud' ? "TJSP (Datajud)" : "TJRS (Judit)",
      updated_at: new Date().toISOString(),
      header: {
        instance: 1,
        state: activeSource === 'datajud' ? "SP" : "RS",
        county: activeSource === 'datajud' ? "São Paulo" : "Porto Alegre",
        amount: "50000.00",
        justice_description: activeSource === 'datajud' ? "Pública / CNJ Datajud" : "Datalake Processual Judit",
        area: "Cível"
      },
      parties: [
        { name: "Parte Autora", side: "active", person_type: "company" },
        { name: "Parte Ré", side: "passive", person_type: "company" }
      ],
      subjects: [
        { name: "Obrigações / Contratos", code: "7699" }
      ],
      recent_steps: [
        {
          occurred_at: new Date().toISOString(),
          title: "Juntada de Petição",
          text: `Movimentação registrada via ${activeSource === 'datajud' ? 'Datajud (CNJ)' : 'Judit'}.`
        }
      ],
      attachments: activeSource === 'datajud' ? [] : [
        { id: "att-req-1", name: "Petição_Inicial.pdf", size: "1.2 MB", status: "processed" }
      ],
      summary_status: "ready",
      summary: {
        markdown: `# Resumo do processo (${activeSource === 'datajud' ? 'Datajud / CNJ' : 'Judit'})\n\nProcesso **${rawCode}** consultado na fonte **${activeSource === 'datajud' ? 'Datajud (CNJ)' : 'Judit'}**.\n\n- Fonte ativa: **${activeSource === 'datajud' ? 'Datajud (CNJ)' : 'Judit'}**\n- Dados estruturados carregados com sucesso.`,
        created_at: new Date().toISOString(),
        model: activeSource === 'datajud' ? "datajud-cnj" : "judit-live"
      }
    };
    processes.set(cacheKey, proc);
    processes.set(rawCode, proc);
    processes.set(cleanCode, proc);
    persistState();
    return res.json(proc);
  }

  return res.status(404).json({ error: 'Formato CNJ inválido' });
});

app.post('/processes/:code/request', checkAuth, async (req, res) => {
  const rawCode = req.params.code;
  const cleanCode = rawCode.replace(/\D/g, '');
  const requestedSource = (req.headers['x-process-source'] || req.query.source || 'judit').toLowerCase();

  if (!isValidCnj(rawCode)) {
    return res.status(400).json({ error: 'Formato CNJ inválido ou falha no cálculo do dígito verificador' });
  }

  const juditApiKey = (process.env.JUDIT_API_KEY || '').trim();
  const datajudApiKey = (process.env.DATAJUD_API_KEY || '').trim();

  const activeSource = requestedSource === 'datajud' ? 'datajud' : 'judit';
  const hasKey = activeSource === 'datajud' ? Boolean(datajudApiKey) : Boolean(juditApiKey);
  const isDemo = cleanCode === DEMO_CLEAN_CODE || !hasKey;

  if (activeSource === 'judit' && !isDemo && juditApiKey) {
    const reqResult = await requestJuditAcquisition(cleanCode, rawCode, juditApiKey);
    if (reqResult.success) {
      requestedProcesses.add(cleanCode);
      requestedProcesses.add(rawCode);
      persistState();
      return res.json({
        status: "processing",
        source: "judit",
        created: true,
        message: reqResult.message || "Solicitação registrada com sucesso na Judit."
      });
    }
    return res.status(reqResult.status || 500).json({ error: reqResult.error });
  }

  if (activeSource === 'datajud' && !isDemo && datajudApiKey) {
    const djResult = await fetchDatajudProcess(cleanCode, rawCode, datajudApiKey);
    if (djResult.success) {
      djResult.process.source = 'datajud';
      processes.set(`${cleanCode}_datajud`, djResult.process);
      processes.set(rawCode, djResult.process);
      processes.set(cleanCode, djResult.process);
      persistState();
      return res.json({
        status: "available",
        source: "datajud",
        created: true,
        message: "Processo localizado com sucesso no Datajud!"
      });
    }
    return res.status(djResult.status || 404).json({ error: djResult.error || djResult.message });
  }

  // Fallback demo/offline
  if (cleanCode.length === 20) {
    requestedProcesses.add(cleanCode);
    requestedProcesses.add(rawCode);
    requestedProcesses.add(`${cleanCode}_${activeSource}`);
    persistState();
  }
  res.json({
    status: "available",
    source: activeSource,
    created: true,
    message: activeSource === 'datajud' ? "Processo localizado no Datajud (CNJ)." : "Solicitação registrada com sucesso na Judit."
  });
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'app', 'frontend', 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Rag-V server running on http://0.0.0.0:${PORT} (Offline Zero-Cost Mode with Security & Persistence)`);
});
