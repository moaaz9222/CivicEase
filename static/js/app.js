const state = {
  messages: [],
  busy: false,
};

const els = {
  form: document.querySelector('#chatForm'),
  input: document.querySelector('#messageInput'),
  submit: document.querySelector('#submitBtn'),
  reset: document.querySelector('#resetBtn'),
  chatLog: document.querySelector('#chatLog'),
  status: document.querySelector('#systemStatus'),
  loadingPanel: document.querySelector('#loadingPanel'),
  loadingText: document.querySelector('#loadingText'),
  alertPanel: document.querySelector('#alertPanel'),
  emptyState: document.querySelector('#emptyState'),
  dashboard: document.querySelector('#dashboardContent'),
  nextBestAction: document.querySelector('#nextBestAction'),
  urgencySection: document.querySelector('#urgencySection'),
  urgencyList: document.querySelector('#urgencyList'),
  benefitsGrid: document.querySelector('#benefitsGrid'),
  checklistBlocks: document.querySelector('#checklistBlocks'),
  supportContacts: document.querySelector('#supportContacts'),
  metricPrograms: document.querySelector('#metricPrograms'),
  metricSteps: document.querySelector('#metricSteps'),
  metricConfidence: document.querySelector('#metricConfidence'),
};

function el(tag, className = '', text = '') {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null && text !== '') node.textContent = String(text);
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function icon(className, label = '') {
  const node = el('i', className);
  node.setAttribute('aria-hidden', label ? 'false' : 'true');
  if (label) node.setAttribute('aria-label', label);
  return node;
}

function hostLabel(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch (_) {
    return 'Source link';
  }
}

function checklistIcon(index, step = {}) {
  // تم تعديل السطر بالأسفل ليقرأ step.task أيضاً لضمان مطابقة الكلمات دلالياً وتغيير الأيقونة
  const text = `${step.category || ''} ${step.title || step.task || ''}`.toLowerCase();
  
  if (index === 0 || text.includes('review') || text.includes('policy')) return 'fa-solid fa-book-open';
  if (index === 1 || text.includes('document') || text.includes('identity') || text.includes('proof')) return 'fa-solid fa-folder-open';
  if (index === 2 || text.includes('submit') || text.includes('apply') || text.includes('application')) return 'fa-solid fa-paper-plane';
  if (text.includes('appointment')) return 'fa-solid fa-calendar-check';
  if (text.includes('link') || text.includes('online')) return 'fa-solid fa-arrow-up-right-from-square';
  return 'fa-solid fa-circle-check';
}

function sanitizeUrl(value) {
  if (!value || typeof value !== 'string') return null;
  try {
    const url = new URL(value, window.location.origin);
    if (url.protocol === 'http:' || url.protocol === 'https:') return url.href;
  } catch (_) {
    return null;
  }
  return null;
}

function setBusy(isBusy, text = 'Agents are working...') {
  state.busy = isBusy;
  els.submit.disabled = isBusy;
  els.input.disabled = isBusy;
  els.loadingText.textContent = text;
  els.loadingPanel.classList.toggle('hidden', !isBusy);
  els.status.className = isBusy
    ? 'rounded-full border border-cyan/25 bg-cyan/10 px-3 py-2 text-cyan'
    : 'rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-2 text-emerald-200';
  els.status.textContent = isBusy ? 'Working' : 'Ready';
}

function avatarFor(role) {
  const avatar = el('div', role === 'user' ? 'avatar-user' : 'avatar-ai');
  const badge = el(
    'div',
    role === 'user'
      ? 'avatar-badge flex items-center justify-center bg-slate-800 border border-slate-700 rounded-full w-full h-full'
      : 'avatar-badge flex items-center justify-center bg-slate-800 border border-cyan-500/30 rounded-full w-full h-full'
  );
  badge.appendChild(
    icon(role === 'user' ? 'fas fa-user text-slate-300 text-sm' : 'fas fa-robot text-cyan-400 text-sm')
  );
  avatar.appendChild(badge);
  return avatar;
}

function appendMessage(role, content) {
  const wrapper = el('div', role === 'user' ? 'message-user reveal' : 'message-ai reveal');
  const bubble = el('div', role === 'user' ? 'bubble-user' : 'bubble-ai');
  bubble.appendChild(el('p', '', content));

  if (role === 'user') {
    wrapper.append(bubble, avatarFor('user'));
  } else {
    wrapper.append(avatarFor('assistant'), bubble);
  }

  els.chatLog.appendChild(wrapper);
  els.chatLog.scrollTop = els.chatLog.scrollHeight;
}

function showAlert(message, tone = 'warning') {
  clear(els.alertPanel);
  const row = el('div', 'flex items-start gap-3');
  row.appendChild(el('i', tone === 'error' ? 'fa-solid fa-circle-exclamation mt-1 text-rose-300' : 'fa-solid fa-triangle-exclamation mt-1 text-amber-200'));
  const copy = el('p', 'text-sm leading-6', message);
  row.appendChild(copy);
  els.alertPanel.appendChild(row);
  els.alertPanel.classList.remove('hidden');
}

function hideAlert() {
  els.alertPanel.classList.add('hidden');
  clear(els.alertPanel);
}

function likelihoodClasses(value) {
  const normalized = String(value || 'LOW').toUpperCase();
  if (normalized === 'HIGH') return 'border-emerald-300/25 bg-emerald-300/10 text-emerald-200';
  if (normalized === 'MEDIUM') return 'border-cyan/25 bg-cyan/10 text-cyan';
  if (normalized === 'UNLIKELY') return 'border-rose-300/25 bg-rose-300/10 text-rose-200';
  return 'border-amber-300/25 bg-amber-300/10 text-amber-100';
}

function renderBenefits(benefits = []) {
  clear(els.benefitsGrid);
  if (!benefits.length) {
    const empty = el('div', 'rounded-3xl border border-line bg-white/[0.035] p-5 text-sm leading-6 text-slate-400 xl:col-span-2', 'No specific benefit cards are available yet. The starter checklist is still safe to use.');
    els.benefitsGrid.appendChild(empty);
    return;
  }

  benefits.forEach((benefit) => {
    const card = el('article', 'reveal rounded-3xl border border-line bg-white/[0.045] p-5 transition hover:-translate-y-1 hover:border-cyan/35 hover:bg-white/[0.065]');
    const top = el('div', 'mb-4 flex items-start justify-between gap-3');
    const titleWrap = el('div');
    titleWrap.appendChild(el('h4', 'font-bold text-white', benefit.benefit_name || 'Benefit Program'));
    titleWrap.appendChild(el('p', 'mt-1 text-xs text-slate-500', benefit.agency || 'Agency varies'));
    const score = Number(benefit.confidence_score || 0);
    const calculatedLikelihood = score >= 0.8 ? 'HIGH' : (score >= 0.6 ? 'MEDIUM' : 'LOW');

    const badge = el('span', `rounded-full border px-3 py-1 text-xs font-bold ${likelihoodClasses(calculatedLikelihood)}`, calculatedLikelihood);
    top.append(titleWrap, badge);

    const confidence = Number(benefit.confidence_score || 0);
    const pct = Math.max(0, Math.min(100, Math.round(confidence * 100)));
    const meter = el('div', 'mb-4');
    const meterHead = el('div', 'mb-2 flex justify-between text-xs text-slate-400');
    meterHead.append(el('span', '', 'Confidence'), el('span', 'font-semibold text-slate-200', `${pct}%`));
    const track = el('div', 'h-2 rounded-full bg-slate-800');
    const fill = el('div', 'h-2 rounded-full bg-gradient-to-r from-cyan to-blueglow');
    fill.style.width = `${pct}%`;
    track.appendChild(fill);
    meter.append(meterHead, track);

    card.append(top, meter, el('p', 'text-sm leading-6 text-slate-300', benefit.plain_language_summary || 'Review this program with the listed agency.'));

    if (benefit.monthly_benefit_estimate) {
      const estimate = el('div', 'mt-4 rounded-2xl border border-cyan/20 bg-cyan/[0.06] px-4 py-3 text-sm text-cyan');
      estimate.append(el('i', 'fa-solid fa-coins mr-2'), document.createTextNode(`Est. benefit: ${benefit.monthly_benefit_estimate}`));
      card.appendChild(estimate);
    }

    const citations = Array.isArray(benefit.source_citations) ? benefit.source_citations : [];
    if (citations.length) {
      const details = el('details', 'citation-accordion mt-4 rounded-2xl border border-line bg-[#0D1524] p-4');
      const summary = el('summary', 'flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-cyan');
      const summaryLabel = el('span', 'inline-flex items-center gap-2');
      summaryLabel.append(icon('fa-solid fa-file-circle-check text-cyan/90'), document.createTextNode('Source citations'));
      summary.append(summaryLabel, icon('fa-solid fa-chevron-down citation-chevron text-xs text-slate-500'));
      details.appendChild(summary);
      const list = el('div', 'mt-4 space-y-3');
      citations.forEach((citation) => {
        const item = el('div', 'rounded-2xl border border-line bg-white/[0.035] p-3 text-xs leading-5 text-slate-400');
        const titleRow = el('div', 'flex items-start gap-2');
        titleRow.append(icon('fa-solid fa-scroll mt-0.5 text-cyan/80'), el('p', 'font-semibold text-slate-200', citation.document_title || 'Policy document'));
        item.appendChild(titleRow);
        item.appendChild(el('p', 'mt-2', citation.excerpt_summary || 'Retrieved policy excerpt'));
        const safe = sanitizeUrl(citation.url);
        if (safe) {
          const link = el('a', 'citation-pill mt-3 inline-flex items-center gap-2 rounded-full border border-cyan/25 bg-cyan/[0.08] px-3 py-1.5 font-semibold text-cyan transition hover:-translate-y-0.5 hover:border-cyan/60 hover:bg-cyan/[0.14] hover:text-white', hostLabel(safe));
          link.href = safe;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.appendChild(icon('fa-solid fa-external-link-alt text-[10px]'));
          item.appendChild(link);
        }
        list.appendChild(item);
      });
      details.appendChild(list);
      card.appendChild(details);
    }

    els.benefitsGrid.appendChild(card);
  });
}

function renderChecklist(blocks = []) {
  clear(els.checklistBlocks);
  if (!blocks.length) {
    els.checklistBlocks.appendChild(el('div', 'rounded-3xl border border-line bg-white/[0.035] p-5 text-sm leading-6 text-slate-400', 'Gather proof of identity, residence, household members, income, and any notices related to your situation.'));
    return;
  }

  blocks.forEach((block) => {
    const card = el('article', 'rounded-3xl border border-line bg-white/[0.045] p-5 transition hover:border-cyan/30 hover:bg-white/[0.055]');
    const head = el('div', 'mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between');
    const title = el('div', 'flex items-center gap-3');
    const titleIcon = el('div', 'grid h-9 w-9 place-items-center rounded-xl border border-cyan/20 bg-cyan/10 text-cyan');
    titleIcon.appendChild(icon('fa-solid fa-clipboard-list'));
    title.append(titleIcon, el('h4', 'font-bold text-white', block.benefit_name || 'Benefit'));
    head.appendChild(title);
    head.appendChild(el('span', 'rounded-full border border-line bg-white/[0.04] px-3 py-1 text-xs text-slate-300', block.estimated_processing_time || 'Timeline varies'));
    card.appendChild(head);

    if (block.deadline_warning) {
      card.appendChild(el('div', 'mb-4 rounded-2xl border border-amber-300/25 bg-amber-300/[0.08] p-3 text-sm text-amber-100', block.deadline_warning));
    }

    const list = el('div', 'space-y-3');
    (block.checklist || []).forEach((step, index) => {
      const row = el('div', 'group flex gap-3 rounded-2xl border border-line bg-[#0D1524] p-4 transition hover:-translate-y-0.5 hover:border-cyan/30 hover:bg-white/[0.045]');
      const marker = el('div', 'phase-icon grid h-11 w-11 shrink-0 place-items-center rounded-2xl border border-cyan/20 bg-cyan/10 text-cyan transition group-hover:scale-105 group-hover:border-cyan/50 group-hover:bg-cyan/15');
      marker.appendChild(icon(checklistIcon(index, step)));
      const body = el('div', 'min-w-0 flex-1');
      // قراءة عنوان الخطوة سواء رجعت باسم task أو title
      const stepTitle = step.title || step.task || 'Checklist step';

      // قراءة الوصف، ولو مش مبعوت وصريح من الـ الـ Backend حط جملة مناسبة ديناميكية بديلة
      const stepDesc = step.description || (step.task ? 'Please fulfill this requirement for the program.' : 'Complete this step when ready.');

      body.appendChild(el('p', 'font-semibold text-slate-100', stepTitle));
      body.appendChild(el('p', 'mt-1 text-sm leading-6 text-slate-400', stepDesc));
      const safe = sanitizeUrl(step.resource_url);
      if (safe) {
        const link = el('a', 'mt-2 inline-flex items-center gap-2 text-sm font-semibold text-cyan transition hover:text-blueglow', 'Open resource');
        link.href = safe;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.appendChild(icon('fa-solid fa-external-link-alt text-xs'));
        body.appendChild(link);
      }
      row.append(marker, body);
      list.appendChild(row);
    });
    card.appendChild(list);

    if (block.pro_tip) {
      const tip = el('div', 'pro-tip mt-4 flex items-start gap-3 rounded-2xl border border-amber-300/25 bg-amber-300/[0.08] p-3 text-sm leading-6 text-amber-50');
      const tipIcon = el('div', 'grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-amber-300/15 text-amber-200');
      tipIcon.appendChild(icon('fa-solid fa-lightbulb'));
      tip.append(tipIcon, el('p', '', `Pro tip: ${block.pro_tip}`));
      card.appendChild(tip);
    }

    els.checklistBlocks.appendChild(card);
  });
}

function renderUrgency(actions = []) {
  clear(els.urgencyList);
  els.urgencySection.classList.toggle('hidden', !actions.length);
  actions.forEach((action) => {
    const row = el('div', 'rounded-2xl border border-amber-300/20 bg-amber-300/[0.07] p-3 text-sm leading-6 text-amber-50', action);
    els.urgencyList.appendChild(row);
  });
}

function renderSupport(contacts = []) {
  clear(els.supportContacts);
  if (!contacts.length) contacts = [{ name: '2-1-1', number: '2-1-1', available: '24/7' }];
  contacts.forEach((contact) => {
    const card = el('div', 'rounded-3xl border border-line bg-white/[0.045] p-4');
    card.appendChild(el('p', 'font-bold text-white', contact.name || 'Support'));
    card.appendChild(el('p', 'mt-1 text-lg font800 text-cyan', contact.number || ''));
    card.appendChild(el('p', 'mt-1 text-xs text-slate-500', contact.available || 'Availability varies'));
    els.supportContacts.appendChild(card);
  });
}

function updateMetrics(benefits = [], actionPlan = {}) {
  const blocks = Array.isArray(actionPlan.benefit_action_blocks) ? actionPlan.benefit_action_blocks : [];
  const steps = blocks.reduce((count, block) => count + (Array.isArray(block.checklist) ? block.checklist.length : 0), 0);
  const scores = benefits.map((b) => Number(b.confidence_score)).filter((n) => Number.isFinite(n));
  const avg = scores.length ? `${Math.round((scores.reduce((a, b) => a + b, 0) / scores.length) * 100)}%` : '--';
  els.metricPrograms.textContent = String(benefits.length || 0);
  els.metricSteps.textContent = String(steps);
  els.metricConfidence.textContent = avg;
}

function renderDashboard(data) {
  const actionPlan = data.action_plan || {};
  const benefits = Array.isArray(data.benefits) ? data.benefits : [];
  els.emptyState.classList.add('hidden');
  els.dashboard.classList.remove('hidden');
  els.nextBestAction.textContent = actionPlan.next_best_action || 'Gather documents and contact 2-1-1 for local benefits support.';
  renderUrgency(Array.isArray(actionPlan.urgency_actions) ? actionPlan.urgency_actions : []);
  renderBenefits(benefits);
  renderChecklist(Array.isArray(actionPlan.benefit_action_blocks) ? actionPlan.benefit_action_blocks : []);
  renderSupport(Array.isArray(actionPlan.support_contacts) ? actionPlan.support_contacts : []);
  updateMetrics(benefits, actionPlan);
}

async function processChat() {
  setBusy(true, 'Extracting intake details...');
  hideAlert();
  try {
    const response = await fetch('/api/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: state.messages }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.status === 'error') {
      throw new Error(data.assistant_message || 'The analysis could not be completed.');
    }
    appendMessage('assistant', data.assistant_message || 'I updated your dashboard.');
    state.messages.push({ role: 'assistant', content: data.assistant_message || 'I updated your dashboard.' });
    if (data.status === 'needs_clarification') {
      showAlert('A little more information is needed before a full policy match can be prepared.');
    }
    renderDashboard(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Something went wrong. Please try again.';
    appendMessage('assistant', message);
    showAlert(message, 'error');
  } finally {
    setBusy(false);
    els.input.focus();
  }
}

els.form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (state.busy) return;
  const content = els.input.value.trim();
  if (!content) return;
  state.messages.push({ role: 'user', content });
  appendMessage('user', content);
  els.input.value = '';
  await processChat();
});

els.reset.addEventListener('click', () => {
  state.messages = [];
  hideAlert();
  clear(els.chatLog);
  appendMessage('assistant', 'Hello. Tell me what is happening in your own words, and I will organize the details into a benefits-ready action plan.');
  els.emptyState.classList.remove('hidden');
  els.dashboard.classList.add('hidden');
  els.loadingPanel.classList.add('hidden');
  updateMetrics([], {});
  els.input.value = '';
  els.input.focus();
});




