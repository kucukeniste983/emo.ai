'use strict';

const $ = (selector) => document.querySelector(selector);
const budget = $('#budget');
const range = $('#budget-range');
const form = $('#build-form');
const button = $('#build-button');
const panel = $('#result-panel');
const money = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 2 });
const integer = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 0 });
const symbols = { cpu: 'CPU', gpu: 'GPU', motherboard: 'MB', ram: 'RAM', ssd: 'SSD', psu: 'PSU', case: 'PC' };
let currentBuild = null;
let running = false;
let copyTimer;

function readBudget() {
  const raw = budget.value.replace(/[.\s]/g, '');
  return /^\d{1,6}$/.test(raw) ? Number(raw) : NaN;
}

function syncBudget(value, format = true) {
  if (format) budget.value = integer.format(value);
  if (Number.isFinite(value)) range.value = Math.min(150000, Math.max(15000, value));
  document.querySelectorAll('[data-budget]').forEach((preset) => {
    const selected = Number(preset.dataset.budget) === value;
    preset.classList.toggle('selected', selected);
    preset.setAttribute('aria-pressed', String(selected));
  });
}

range.addEventListener('input', () => syncBudget(Number(range.value)));
budget.addEventListener('input', () => {
  syncBudget(readBudget(), false);
  $('#budget-error').hidden = true;
  budget.removeAttribute('aria-invalid');
});
budget.addEventListener('blur', () => { if (Number.isFinite(readBudget())) syncBudget(readBudget()); });
document.querySelectorAll('[data-budget]').forEach((preset) => {
  preset.addEventListener('click', () => {
    syncBudget(Number(preset.dataset.budget));
    $('#budget-error').hidden = true;
    budget.removeAttribute('aria-invalid');
  });
});
syncBudget(40000);

function state(name) {
  ['empty-state', 'loading-state', 'error-state', 'build-result'].forEach((id) => {
    $(`#${id}`).hidden = id !== name;
  });
}

function errorState(message, kind) {
  state('error-state');
  $('#error-title').textContent = kind === 'no_matching_build' ? 'Biraz farklı düşünelim.' : 'Fiyatları doğrulayamadık.';
  $('#error-message').textContent = message;
  $('#error-title').focus({ preventScroll: true });
}

function renderBuild(data) {
  currentBuild = data;
  const list = $('#parts-list');
  list.replaceChildren();
  data.parts.forEach((part) => {
    const row = $('#part-template').content.cloneNode(true);
    row.querySelector('.part-symbol').textContent = symbols[part.category] || 'PC';
    row.querySelector('.part-category').textContent = part.category_name.toLocaleUpperCase('tr-TR');
    row.querySelector('.part-name').textContent = part.name;
    row.querySelector('.part-price').textContent = money.format(part.price);
    const link = row.querySelector('.part-link');
    const url = new URL(part.url);
    if (url.protocol !== 'https:' || !['www.akakce.com', 'akakce.com'].includes(url.hostname) || url.username || url.password) {
      throw new Error('invalid_product_url');
    }
    link.href = url.href;
    link.setAttribute('aria-label', `${part.name} — Akakçe ürün sayfasını yeni sekmede aç`);
    list.append(row);
  });
  $('#total-price').textContent = money.format(data.total);
  $('#remaining-price').textContent = money.format(data.remaining);
  $('#result-resolution').textContent = data.resolution.toUpperCase();
  const used = Math.min(100, Math.round(data.total / data.budget * 100));
  $('#budget-fill').style.width = `${used}%`;
  $('.budget-meter').setAttribute('aria-valuenow', String(used));
  const checked = new Intl.DateTimeFormat('tr-TR', { timeZone: 'Europe/Istanbul', hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }).format(new Date(data.oldest_price_check));
  $('#price-time').textContent = `Fiyat kontrolü: ${checked}`;
  [['#compatibility-list', data.checks], ['#warning-list', data.warnings]].forEach(([selector, items]) => {
    $(selector).replaceChildren(...items.map((text) => {
      const li = document.createElement('li');
      li.textContent = text;
      return li;
    }));
  });
  state('build-result');
  $('#result-title').focus({ preventScroll: true });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (running) return;
  const value = readBudget();
  if (!Number.isFinite(value) || value < 15000 || value > 150000) {
    $('#budget-error').textContent = '15.000–150.000 TL arasında bir bütçe gir.';
    $('#budget-error').hidden = false;
    budget.setAttribute('aria-invalid', 'true');
    budget.focus();
    return;
  }
  running = true;
  currentBuild = null;
  button.disabled = true;
  form.querySelectorAll('input, button[type="button"]').forEach((control) => { control.disabled = true; });
  $('#copy-build').textContent = 'Listeyi kopyala';
  clearTimeout(copyTimer);
  button.querySelector('.button-label').textContent = 'Parçalar kontrol ediliyor';
  button.querySelector('.button-arrow').hidden = true;
  button.querySelector('.spinner').hidden = false;
  panel.setAttribute('aria-busy', 'true');
  state('loading-state');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 120000);
  if (window.matchMedia('(max-width: 600px)').matches) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  try {
    const response = await fetch('/api/build', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ budget: value, resolution: form.querySelector('input[name="resolution"]:checked').value }),
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      errorState(data.message || 'Şu anda sistem oluşturamıyoruz. Biraz sonra tekrar dene.', data.error);
    } else {
      renderBuild(data);
    }
  } catch (error) {
    currentBuild = null;
    errorState(error.name === 'AbortError' ? 'Fiyat kontrolü beklenenden uzun sürdü. Biraz sonra tekrar dene.' : 'Bağlantı kurulamadı. İnternet bağlantını kontrol edip tekrar dene.');
  } finally {
    clearTimeout(timer);
    running = false;
    button.disabled = false;
    form.querySelectorAll('input, button[type="button"]').forEach((control) => { control.disabled = false; });
    button.querySelector('.button-label').textContent = 'Sistemimi oluştur';
    button.querySelector('.button-arrow').hidden = false;
    button.querySelector('.spinner').hidden = true;
    panel.setAttribute('aria-busy', 'false');
  }
});

$('#retry-button').addEventListener('click', () => form.requestSubmit());
$('#copy-build').addEventListener('click', async () => {
  if (!currentBuild) return;
  const text = ['RIGLAB — Oyun sistemi', `Bütçe: ${money.format(currentBuild.budget)} / ${currentBuild.resolution}`, '',
    ...currentBuild.parts.map((part) => `${part.category_name}: ${part.name}\n${money.format(part.price)} — ${part.url}`),
    '', `Toplam: ${money.format(currentBuild.total)}`, `Fiyat kontrolü: ${currentBuild.oldest_price_check}`,
    'Fiyat ve stok değişebilir. Kargo, montaj, işletim sistemi ve çevre birimleri dahil değildir.'].join('\n');
  try {
    await navigator.clipboard.writeText(text);
    $('#copy-build').textContent = 'Liste kopyalandı ✓';
  } catch {
    $('#copy-build').textContent = 'Kopyalanamadı. Yeniden dene.';
  }
  copyTimer = setTimeout(() => { $('#copy-build').textContent = 'Listeyi kopyala'; }, 3000);
});
