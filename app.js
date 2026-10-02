const list = document.querySelector('#list');
const setup = document.querySelector('#setup');
const chat = document.querySelector('#chat');
const chooseArchive = document.querySelector('#choose-archive');
const setupStatus = document.querySelector('#setup-status');
const search = document.querySelector('#search');
const status = document.querySelector('#status');
const frame = document.querySelector('#frame');
const empty = document.querySelector('#empty');
const shell = document.querySelector('.shell');
let chats = [], selected = '', timer;

const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const initials = name => name.split(/[\s,]+/).filter(Boolean).slice(0,2).map(x=>x[0]).join('').toUpperCase() || '?';
const shortDate = value => (value.match(/^[A-Z][a-z]{2} \d{1,2}, \d{4}/)||[''])[0];

function renderChats() {
  status.textContent = `${chats.length} conversations`;
  list.innerHTML = chats.map(c => `<div class="row ${selected===c.file?'active':''}" role="option" data-file="${esc(c.file)}"><div class="avatar">${esc(initials(c.name))}</div><div class="meta"><div class="top"><span class="name">${esc(c.name)}</span><span class="date">${esc(shortDate(c.last))}</span></div><div class="preview">${esc(c.preview)}</div></div></div>`).join('');
}
function openChat(file, message) {
  selected = file;
  frame.src = `/chat?file=${encodeURIComponent(file)}${message == null ? '' : `&message=${message}`}`;
  frame.hidden = false; empty.hidden = true; shell.classList.add('chat-open');
  if (!search.value) renderChats();
}
async function loadChats() {
  const data = await fetch('/api/chats').then(r=>r.json());
  if (!data.ready) return setTimeout(loadChats, 350);
  chats = data.chats; renderChats();
}

function showChat(archive) {
  setup.hidden = true;
  chat.hidden = false;
  document.title = archive ? `${archive} — Chat View` : 'Chat View';
  status.textContent = 'Indexing your archive…';
  loadChats();
}

async function initialize() {
  try {
    const state = await fetch('/api/state').then(r => r.json());
    if (state.selected) showChat(state.archive);
  } catch {
    setupStatus.textContent = 'Could not connect to Chat View. Please reopen the app.';
  }
}

chooseArchive.addEventListener('click', async () => {
  chooseArchive.disabled = true;
  setupStatus.textContent = 'Waiting for your folder selection…';
  try {
    const response = await fetch('/api/select-archive', {method: 'POST'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'The archive could not be opened.');
    if (data.cancelled) {
      setupStatus.textContent = 'No folder selected.';
    } else {
      showChat(data.archive);
    }
  } catch (error) {
    setupStatus.textContent = error.message;
  } finally {
    chooseArchive.disabled = false;
  }
});
async function runSearch() {
  const q = search.value.trim();
  if (!q) return renderChats();
  status.textContent = 'Searching…';
  const data = await fetch(`/api/search?q=${encodeURIComponent(q)}`).then(r=>r.json());
  if (!data.ready) return setTimeout(runSearch, 350);
  status.textContent = `${data.results.length}${data.results.length===150?'+' : ''} results`;
  list.innerHTML = data.results.map(r=>`<div class="result" data-file="${esc(r.file)}" data-message="${r.index}"><span class="result-chat">${esc(r.chat)}</span><span class="result-date">${esc(shortDate(r.timestamp))}</span><div class="result-text">${esc(r.text)}</div></div>`).join('') || '<div class="status">No messages found</div>';
}
list.addEventListener('click', e => { const row=e.target.closest('[data-file]'); if(row) openChat(row.dataset.file, row.dataset.message); });
search.addEventListener('input', () => { clearTimeout(timer); timer=setTimeout(runSearch, 180); });
document.addEventListener('keydown', e => { if((e.metaKey||e.ctrlKey)&&e.key.toLowerCase()==='k'){e.preventDefault();search.focus();} if(e.key==='Escape'){search.value='';search.blur();renderChats();} });
document.querySelector('#theme').onclick=()=>document.body.classList.toggle('dark');
document.querySelector('.viewer').addEventListener('click', e=>{if(innerWidth<=680 && e.clientY<65) shell.classList.remove('chat-open')});
initialize();
