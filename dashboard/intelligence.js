// Direct access (evolve.justaskevolveiq.com/dashboard/intelligence.html) has no prefix,
// so API_BASE is "". Viewed through the admin launcher's proxy
// (team.justaskevolveiq.com/proxy/{port}/dashboard/intelligence.html), it's
// "/proxy/{port}" — without this, fetch("/api/...") would hit the launcher's own
// domain root instead of staying inside the proxy prefix. Same fix as dashboard/app.js.
const API_BASE = window.location.pathname.replace(/\/dashboard(\/.*)?$/, "");

const $ = (id) => document.getElementById(id);
const splitList = (value) => value.split(/[,\n]/).map(v => v.trim()).filter(Boolean);
const show = (message) => { $('status').textContent = message; setTimeout(() => $('status').textContent = '', 2500); };

async function api(path, options={}) {
  const res = await fetch(API_BASE + path, {headers:{'Content-Type':'application/json'}, ...options});
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function loadSettings(){
  const s = await api('/api/intelligence/settings');
  $('enabled').checked = !!s.enabled;
  $('vertical').value = s.vertical || '';
  $('primary_jurisdiction').value = s.primary_jurisdiction || '';
  $('additional_jurisdictions').value = (s.additional_jurisdictions || []).join(', ');
  $('jurisdiction_mode').value = s.jurisdiction_mode || 'single_state';
  $('approved_boundary_text').value = s.approved_boundary_text || '';
  $('accepted_types').value = (s.accepted_types || []).join(', ');
  $('excluded_types').value = (s.excluded_types || []).join(', ');
  $('existing_representation_policy').value = s.existing_representation_policy || '';
  $('out_of_area_policy').value = s.out_of_area_policy || '';
  $('property_damage_only_policy').value = s.property_damage_only_policy || '';
  $('urgent_handoff_webhook_url').value = s.urgent_handoff_webhook_url || '';
  $('urgent_handoff_email').value = s.urgent_handoff_email || '';
  $('standard_handoff_webhook_url').value = s.standard_handoff_webhook_url || '';
  $('standard_handoff_email').value = s.standard_handoff_email || '';
  $('after_hours_behavior').value = s.after_hours_behavior || 'capture_and_notify';
  const languages = s.languages || [];
  $('lang_english').checked = languages.includes('English');
  $('lang_spanish').checked = languages.includes('Spanish');
  $('languages_other').value = languages.filter(l => l !== 'English' && l !== 'Spanish').join(', ');
  $('never_say_text').value = s.never_say_text || '';
  $('scoring_rules').value = JSON.stringify(s.scoring_rules || {}, null, 2);
  $('priority_thresholds').value = JSON.stringify(s.priority_thresholds || {}, null, 2);
}

async function saveSettings(){
  let scoring, thresholds;
  try {
    scoring = JSON.parse($('scoring_rules').value || '{}');
    thresholds = JSON.parse($('priority_thresholds').value || '{}');
  } catch (e) {
    alert('Scoring rules and thresholds must be valid JSON.');
    return;
  }
  const languages = [
    ...($('lang_english').checked ? ['English'] : []),
    ...($('lang_spanish').checked ? ['Spanish'] : []),
    ...splitList($('languages_other').value),
  ];
  const payload = {
    enabled: $('enabled').checked,
    vertical: $('vertical').value.trim(),
    primary_jurisdiction: $('primary_jurisdiction').value.trim(),
    additional_jurisdictions: splitList($('additional_jurisdictions').value),
    jurisdiction_mode: $('jurisdiction_mode').value,
    approved_boundary_text: $('approved_boundary_text').value.trim(),
    accepted_types: splitList($('accepted_types').value),
    excluded_types: splitList($('excluded_types').value),
    existing_representation_policy: $('existing_representation_policy').value.trim(),
    out_of_area_policy: $('out_of_area_policy').value.trim(),
    property_damage_only_policy: $('property_damage_only_policy').value.trim(),
    urgent_handoff_webhook_url: $('urgent_handoff_webhook_url').value.trim(),
    urgent_handoff_email: $('urgent_handoff_email').value.trim(),
    standard_handoff_webhook_url: $('standard_handoff_webhook_url').value.trim(),
    standard_handoff_email: $('standard_handoff_email').value.trim(),
    after_hours_behavior: $('after_hours_behavior').value,
    languages,
    never_say_text: $('never_say_text').value.trim(),
    scoring_rules: scoring,
    priority_thresholds: thresholds,
  };
  await api('/api/intelligence/settings', {method:'PUT', body:JSON.stringify(payload)});
  show('Saved');
}

async function loadRules(){
  const rules = await api('/api/intelligence/routing-rules');
  const root = $('rules');
  root.innerHTML = '';
  if (!rules.length) root.innerHTML = '<p class="muted">No routing rules yet. P1 uses urgent routing; other priorities use standard routing.</p>';
  rules.forEach(rule => {
    const div = document.createElement('div');
    div.className = 'rule';
    div.innerHTML = `<strong>${escapeHtml(rule.label)}</strong> <span class="badge">${escapeHtml(rule.priority_override || 'score')}</span><br>
      <span class="muted">${escapeHtml(JSON.stringify(rule.condition))} → ${escapeHtml(rule.destination_label || 'configured destination')}</span>
      <div class="actions"><button data-delete="${rule.id}">Delete</button></div>`;
    root.appendChild(div);
  });
  root.querySelectorAll('[data-delete]').forEach(btn => btn.onclick = async () => {
    await api(`/api/intelligence/routing-rules/${btn.dataset.delete}`, {method:'DELETE'});
    loadRules();
  });
}

async function addRule(){
  let condition;
  try { condition = JSON.parse($('rule_condition').value || '{}'); }
  catch(e){ alert('Condition must be valid JSON.'); return; }
  await api('/api/intelligence/routing-rules', {method:'POST', body:JSON.stringify({
    label: $('rule_label').value.trim() || 'Routing rule',
    condition,
    priority_override: $('rule_priority').value || null,
    destination_label: $('rule_destination').value.trim(),
    handoff_webhook_url: $('rule_webhook').value.trim(),
    handoff_email: $('rule_email').value.trim(),
    position: Number($('rule_position').value || 0),
    active: true
  })});
  $('rule_label').value=''; $('rule_destination').value=''; $('rule_webhook').value=''; $('rule_email').value='';
  await loadRules();
}

function escapeHtml(value){
  return String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
}

$('save').onclick = saveSettings;
$('addRule').onclick = addRule;
Promise.all([loadSettings(), loadRules()]).catch(err => { console.error(err); alert('Could not load intelligence configuration.'); });
