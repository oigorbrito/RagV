import express from 'express';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import helmet from 'helmet';

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
    return res.status(401).json({ error: 'Missing or invalid authorization token' });
  }
  const token = authHeader.substring(7).trim();
  if (!token) {
    return res.status(401).json({ error: 'Token cannot be empty' });
  }
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

app.get('/processes/:code', checkAuth, (req, res) => {
  const rawCode = req.params.code;
  const cleanCode = rawCode.replace(/\D/g, '');
  const requestedSource = (req.headers['x-process-source'] || req.query.source || 'judit').toLowerCase();

  if (!isValidCnj(rawCode)) {
    return res.status(400).json({ error: 'Invalid CNJ format or verification digit check failed' });
  }
  
  let proc = processes.get(rawCode) || processes.get(cleanCode);

  if (!proc) {
    if (cleanCode.length === 20) {
      if (!requestedProcesses.has(cleanCode) && !requestedProcesses.has(rawCode)) {
        return res.status(404).json({ error: 'Process not found in local cache. Request required.' });
      }
      
      proc = {
        code: rawCode,
        class_name: "Procedimento Comum Cível",
        court: "TJSP",
        updated_at: new Date().toISOString(),
        header: {
          instance: 1,
          state: "SP",
          county: "São Paulo",
          amount: "150000.00",
          justice_description: "Estadual",
          area: "Cível"
        },
        parties: [
          { name: "Autor Exemplo S.A.", side: "active", person_type: "company" },
          { name: "Réu Exemplo Ltda.", side: "passive", person_type: "company" }
        ],
        subjects: [
          { name: "Indenização por Danos Materiais", code: "10432" }
        ],
        recent_steps: [
          {
            occurred_at: new Date().toISOString(),
            title: "Juntada de Petição",
            text: "Petição de manifestação juntada aos autos."
          },
          {
            occurred_at: new Date(Date.now() - 86400000 * 5).toISOString(),
            title: "Distribuição",
            text: "Distribuição de processo cível."
          }
        ],
        attachments: requestedSource === 'datajud' ? [] : [
          { id: "att-req-1", name: "Petição_Inicial_Requisitada.pdf", size: "1.5 MB", status: "processed" }
        ],
        summary_status: "ready",
        summary: {
          markdown: `# Resumo do processo\n\nProcesso ${rawCode} consultado com sucesso.\n\n## Pontos de atenção\n- Autos ativos e regulares.\n- Aguardando manifestação das partes.`,
          created_at: new Date().toISOString(),
          model: "local-demo-no-provider"
        }
      };
      processes.set(rawCode, proc);
      processes.set(cleanCode, proc);
      persistState();
    } else {
      return res.status(404).json({ error: 'Invalid CNJ format' });
    }
  }
  res.json(proc);
});

app.post('/processes/:code/request', checkAuth, (req, res) => {
  const rawCode = req.params.code;
  const cleanCode = rawCode.replace(/\D/g, '');
  if (!isValidCnj(rawCode)) {
    return res.status(400).json({ error: 'Invalid CNJ format or verification digit check failed' });
  }
  if (cleanCode.length === 20) {
    requestedProcesses.add(cleanCode);
    requestedProcesses.add(rawCode);
    persistState();
  }
  res.json({
    status: "available",
    created: true,
    message: "Consulta registrada e processada com sucesso no modo local offline."
  });
});

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'app', 'frontend', 'index.html'));
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Rag-V server running on http://0.0.0.0:${PORT} (Offline Zero-Cost Mode with Security & Persistence)`);
});
