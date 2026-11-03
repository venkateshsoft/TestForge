let currentId = null;
const $ = (id) => document.getElementById(id);
const toast = (message) => { const el = $('toast'); el.textContent = message; el.classList.add('show'); setTimeout(() => el.classList.remove('show'), 3200); };
const esc = (value) => String(value).replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[char]));

$('generation-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = $('generate'); button.disabled = true; button.textContent = 'Generating…';
  try {
    const response = await fetch('/api/v1/generations', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:$('title').value,description:$('description').value,domain:$('domain').value,language:'Python',framework:$('framework').value,environment:$('environment').value,authentication:$('authentication').value,generation_mode:'Generate a complete automation framework'})});
    if (!response.ok) throw new Error((await response.json()).detail || 'Generation failed');
    render(await response.json()); toast('Automation blueprint generated');
  } catch (error) { toast(error.message); } finally { button.disabled = false; button.innerHTML = 'Generate automation solution <span>→</span>'; }
});

function render(data) {
  currentId = data.id; $('result').classList.remove('hidden'); $('result-title').textContent = data.request.title; $('download').href = `/api/v1/projects/${data.id}/download`; $('case-count').textContent = `${data.coverage_summary.total_scenarios} scenarios`;
  const i = data.interpretation;
  $('interpretation-content').innerHTML = `<div class="info-block"><h3>Objective</h3><p>${esc(i.objective)}</p></div><div class="info-block"><h3>System under test</h3><p>${esc(i.system_under_test)}</p></div><div class="info-block"><h3>Extracted requirements</h3><ul>${i.requirements.map(item=>`<li><strong>${esc(item.id)} · ${esc(item.title)}</strong><br>${esc(item.statement)}</li>`).join('')}</ul></div><div class="info-block"><h3>Assumptions & clarification needed</h3><ul>${[...i.assumptions,...i.open_questions].map(item=>`<li>${esc(item)}</li>`).join('')}</ul></div>`;
  const summary = data.coverage_summary;
  $('coverage-content').innerHTML = `<div class="coverage-card"><strong>${summary.total_scenarios}</strong><span>Total scenarios</span></div><div class="coverage-card"><strong>${Object.keys(summary.by_category).length}</strong><span>Categories</span></div><div class="coverage-card wide"><strong>By category</strong><span>${Object.entries(summary.by_category).map(([key,value])=>`${esc(key)} (${value})`).join(' · ')}</span></div><div class="coverage-card wide"><strong>Gaps</strong><span>${summary.coverage_gaps.length ? summary.coverage_gaps.map(esc).join(' · ') : 'No explicit gaps identified'}</span></div>`;
  $('cases-body').innerHTML = data.test_cases.map(c=>`<tr><td>${esc(c.id)}</td><td>${esc(c.title)}</td><td>${esc(c.requirement)}</td><td>${esc(c.category)}</td><td>${esc(c.priority)}</td><td>${esc(c.automation_feasibility)}</td><td>${esc(c.expected)}</td></tr>`).join('');
  $('files-body').innerHTML = data.files.map(f=>`<div class="file-item">${esc(f.path)}</div>`).join('');
  $('validation-content').innerHTML = '<p class="empty">Static validation has not run for this generation.</p>'; document.querySelector('.result-section').scrollIntoView({behavior:'smooth'});
}

$('validate').addEventListener('click', async () => { if (!currentId) return; const button = $('validate'); button.disabled = true; button.textContent = 'Validating…'; try { const response = await fetch(`/api/v1/projects/${currentId}/validate`, {method:'POST'}); if (!response.ok) throw new Error('Validation failed'); const data = await response.json(); $('validation-content').innerHTML = `<div class="check"><span class="check-mark">${data.validation.status === 'passed' ? '✓' : '!'}</span><strong>${data.validation.status === 'passed' ? 'Validation passed' : 'Validation needs attention'}</strong></div>` + data.validation.checks.map(c=>`<div class="check ${c.status === 'failed' ? 'failed':''}"><span class="check-mark">${c.status === 'passed'?'✓':'!'}</span><div><strong>${esc(c.name)}</strong><br><span class="empty">${esc(c.message)}</span></div></div>`).join(''); toast(`Validation ${data.validation.status}`); } catch (error) { toast(error.message); } finally { button.disabled = false; button.textContent = 'Run static validation'; } });
