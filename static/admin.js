'use strict';
const $ = (selector) => document.querySelector(selector);
const csrf = $('meta[name="csrf-token"]').content;
const form = $('#system-form');
const money = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' });
let records = [];
let editingId = null;
let editingVersion = null;
let dirty = false;
let saving = false;

function notice(message, error = false) {
  $('#admin-notice').textContent = message;
  $('#admin-notice').classList.toggle('error', error);
  $('#admin-notice').hidden = false;
}

async function api(path, method = 'GET', body) {
  const response = await fetch(path, { method, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: body === undefined ? undefined : JSON.stringify(body) });
  let data;
  try { data = await response.json(); } catch { throw new Error('Sunucudan geçerli yanıt alınamadı.'); }
  if (!response.ok) throw new Error(data.message || 'İşlem tamamlanamadı.');
  return data;
}

function readParts() {
  if ($('#system-kind').value === 'ready') {
    return [{ category: 'system', name: $('#system-name').value, price: $('#ready-price').value || null, url: $('#ready-url').value }];
  }
  return [...document.querySelectorAll('.manual-part[data-category]')].map((row) => ({
    category: row.dataset.category, name: row.querySelector('.entry-name').value,
    price: row.querySelector('.entry-price').value || null, url: row.querySelector('.entry-url').value,
  }));
}

function preview() {
  const ready = $('#system-kind').value === 'ready';
  $('#parts-editor').hidden = ready;
  $('#ready-editor').hidden = !ready;
  // Disable hidden fields so browser URL validation applies to the chosen mode.
  $('#parts-editor').querySelectorAll('input').forEach((input) => { input.disabled = ready || saving; });
  $('#ready-editor').querySelectorAll('input').forEach((input) => { input.disabled = !ready || saving; });
  const total = readParts().reduce((sum, part) => sum + (Number(part.price) || 0), 0);
  $('#editor-total').textContent = money.format(total);
}

function setBudgetBound(selector, value) {
  const field = $(selector);
  field.querySelectorAll('[data-legacy]').forEach((option) => option.remove());
  const normalized = String(Number(value));
  if (![...field.options].some((option) => option.value === normalized)) {
    // Retain older saved ranges when editing; they cannot be newly selected.
    const legacy = document.createElement('option');
    legacy.value = normalized;
    legacy.textContent = `${money.format(value)} (önceki kayıt)`;
    legacy.disabled = true;
    legacy.dataset.legacy = 'true';
    field.prepend(legacy);
  }
  field.value = normalized;
}

function fill(record = null) {
  form.reset();
  editingId = record ? record.id : null;
  editingVersion = record ? record.version : null;
  setBudgetBound('#budget-min', record?.budget_min ?? 30000);
  setBudgetBound('#budget-max', record?.budget_max ?? 40000);
  if (record) {
    $('#system-name').value = record.name;
    $('#system-resolution').value = record.resolution;
    $('#system-priority').value = record.priority;
    $('#system-kind').value = record.kind;
    $('#system-notes').value = record.notes;
    $('#compatibility-confirmed').checked = record.compatibility_confirmed;
    if (record.kind === 'ready') {
      const part = record.parts[0];
      if (part) { $('#ready-price').value = part.price ?? ''; $('#ready-url').value = part.url; }
    } else {
      for (const part of record.parts) {
        const row = document.querySelector(`.manual-part[data-category="${part.category}"]`);
        if (row) { row.querySelector('.entry-name').value = part.name; row.querySelector('.entry-price').value = part.price ?? ''; row.querySelector('.entry-url').value = part.url; }
      }
    }
  }
  $('#editor-state').textContent = record ? 'KAYDI DÜZENLE' : 'YENİ SİSTEM';
  $('#editor-title').textContent = record ? record.name : 'Bir bütçeye, bir sistem.';
  $('#editor-status').textContent = record?.enabled ? 'Yayında' : 'Taslak';
  $('#editor-status').classList.toggle('draft', !record?.enabled);
  dirty = false;
  preview();
}

function renderRecords() {
  $('#system-list').replaceChildren();
  $('#system-count').textContent = records.length;
  $('#catalog-empty').hidden = records.length !== 0;
  for (const record of records) {
    const fragment = $('#system-card').content.cloneNode(true);
    const card = fragment.querySelector('article');
    card.querySelector('.card-name').textContent = record.name;
    card.querySelector('.status-badge').textContent = record.enabled ? 'YAYINDA' : 'TASLAK';
    card.querySelector('.status-badge').classList.toggle('draft', !record.enabled);
    card.querySelector('.card-resolution').textContent = record.resolution === 'any' ? 'Tüm çözünürlükler' : record.resolution.toUpperCase();
    card.querySelector('.card-range').textContent = `${money.format(record.budget_min)} – ${money.format(record.budget_max)}`;
    card.querySelector('.card-total').textContent = `Toplam: ${money.format(record.total)}`;
    card.querySelector('[data-action="edit"]').addEventListener('click', () => {
      if (dirty && !confirm('Kaydedilmemiş değişiklikleri bırakıp bu kaydı açmak istiyor musun?')) return;
      fill(record);
      $('#editor-title').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    const toggle = card.querySelector('[data-action="toggle"]');
    toggle.textContent = record.enabled ? 'Yayından kaldır' : 'Yayınla';
    toggle.addEventListener('click', async () => {
      toggle.disabled = true;
      try {
        const data = await api(`/api/admin/systems/${record.id}`, 'PUT', { ...record, enabled: !record.enabled });
        if (editingId === record.id && !dirty) fill(data.system);
        await refresh();
        notice(data.system.enabled ? 'Sistem yayına alındı.' : 'Sistem yayından kaldırıldı. Kayıt taslak olarak saklanıyor.');
      } catch (error) { notice(error.message, true); } finally { toggle.disabled = false; }
    });
    card.querySelector('[data-action="delete"]').addEventListener('click', async () => {
      if (!confirm(`“${record.name}” kalıcı olarak silinsin mi?`)) return;
      try {
        await api(`/api/admin/systems/${record.id}`, 'DELETE', { version: record.version });
        if (editingId === record.id) fill();
        await refresh();
        notice('Sistem silindi.');
      } catch (error) { notice(error.message, true); }
    });
    $('#system-list').append(fragment);
  }
}

async function refresh() {
  const data = await api('/api/admin/systems');
  records = data.systems;
  renderRecords();
}

form.addEventListener('input', () => { dirty = true; preview(); });
form.addEventListener('change', () => { dirty = true; preview(); });
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (saving) return;
  const payload = {
    name: $('#system-name').value, budget_min: $('#budget-min').value, budget_max: $('#budget-max').value,
    resolution: $('#system-resolution').value, priority: Number($('#system-priority').value), kind: $('#system-kind').value,
    notes: $('#system-notes').value, compatibility_confirmed: $('#compatibility-confirmed').checked,
    enabled: event.submitter?.dataset.action === 'publish', parts: readParts(), version: editingVersion,
  };
  saving = true;
  form.querySelectorAll('button[type="submit"]').forEach((button) => { button.disabled = true; });
  try {
    const path = editingId ? `/api/admin/systems/${editingId}` : '/api/admin/systems';
    const data = await api(path, editingId ? 'PUT' : 'POST', payload);
    fill(data.system);
    await refresh();
    notice(data.system.enabled ? 'Sistem kaydedildi ve yayınlandı. Siteyi açıp bütçe girerek görebilirsin.' : 'Taslak kaydedildi. Eksik alanları daha sonra tamamlayabilirsin.');
  } catch (error) { notice(error.message, true); }
  finally { saving = false; form.querySelectorAll('button[type="submit"]').forEach((button) => { button.disabled = false; }); preview(); }
});

$('#new-system').addEventListener('click', () => {
  if (dirty && !confirm('Kaydedilmemiş değişiklikleri bırakmak istiyor musun?')) return;
  fill();
  $('#system-name').focus();
});
$('#import-button').addEventListener('click', () => $('#import-file').click());
$('#import-file').addEventListener('change', async () => {
  const file = $('#import-file').files[0];
  if (!file) return;
  try {
    if (file.size > 2 * 1024 * 1024) throw new Error('Yedek dosyası 2 MB sınırını aşamaz.');
    const data = JSON.parse(await file.text());
    if (!Array.isArray(data.systems)) throw new Error('Geçerli bir RIGLAB yedeği seç.');
    if (!confirm(`${data.systems.length} sistem yüklenecek. Aynı kimliğe sahip kayıtlar güncellenir. Kaydedilmemiş form değişiklikleri bırakılır. Devam edilsin mi?`)) return;
    const result = await api('/api/admin/import', 'POST', data);
    fill();
    await refresh();
    notice(`${result.imported} sistem yüklendi.`);
  } catch (error) { notice(error.message, true); } finally { $('#import-file').value = ''; }
});
$('#logout')?.addEventListener('click', async () => {
  if (dirty && !confirm('Kaydedilmemiş değişiklikleri bırakıp çıkmak istiyor musun?')) return;
  try { await api('/api/admin/logout', 'POST', {}); dirty = false; location.assign('/admin'); }
  catch (error) { notice(error.message, true); }
});
window.addEventListener('beforeunload', (event) => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
fill();
refresh().catch((error) => notice(error.message, true));
