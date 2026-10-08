import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
app.use(express.json({ limit: '10mb' }));

// Serve static frontend
app.use(express.static(path.join(__dirname, 'app', 'frontend')));

// In-memory process store and webhook store (100% offline, zero-cost)
const processes = new Map();
const requestedProcesses = new Set();
const webhookStore = new Map();

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

processes.set(DEMO_CODE, defaultDemoProcess);
processes.set(DEMO_CLEAN_CODE, defaultDemoProcess);

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
  
  let proc = processes.get(rawCode) || processes.get(cleanCode);

  if (!proc) {
    if (cleanCode.length === 20) {
      if (!requestedProcesses.has(cleanCode)) {
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
            text: "Petição de manifestação juntada aos autos (simulação local offline)."
          },
          {
            occurred_at: new Date(Date.now() - 86400000 * 5).toISOString(),
            title: "Distribuição",
            text: "Distribuição de processo cível."
          }
        ],
        attachments: [
          { id: "att-req-1", name: "Petição_Inicial_Requisitada.pdf", size: "1.5 MB", status: "processed" }
        ],
        summary_status: "ready",
        summary: {
          markdown: `# Resumo do processo\n\nProcesso ${rawCode} consultado com sucesso (modo local offline).\n\n## Pontos de atenção\n- Autos ativos e regulares.\n- Aguardando manifestação das partes.`,
          created_at: new Date().toISOString(),
          model: "local-offline-demo"
        }
      };
      processes.set(rawCode, proc);
      processes.set(cleanCode, proc);
    } else {
      return res.status(404).json({ error: 'Invalid CNJ format' });
    }
  }
  res.json(proc);
});

app.post('/processes/:code/request', checkAuth, (req, res) => {
  const rawCode = req.params.code;
  const cleanCode = rawCode.replace(/\D/g, '');
  if (cleanCode.length === 20) {
    requestedProcesses.add(cleanCode);
    requestedProcesses.add(rawCode);
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
  console.log(`Rpy server running on http://0.0.0.0:${PORT} (Offline Zero-Cost Mode)`);
});
