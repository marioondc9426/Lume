chrome.runtime.sendMessage({ cmd: 'status' }, r => {
  r = r || {};
  document.getElementById('s').textContent = r.ok ? 'Conectado ao Lume' : 'Lume nao encontrado';
  document.getElementById('d').textContent = r.ok ? 'A IA pode usar as abas quando voce permitir no Lume.' : 'Abra o Lume neste PC (porta 8000 a 8010).';
  const btn = document.getElementById('dbg'), note = document.getElementById('n');
  if (!(chrome.debugger && chrome.permissions && chrome.permissions.request)) return;   // Firefox: sem PDF nem pagina inteira
  if (r.debugger) { note.textContent = 'PDF e foto da pagina inteira: liberados.'; return; }
  btn.hidden = false;
  btn.onclick = () => chrome.permissions.request({ permissions: ['debugger'] }, ok => { if (ok) { btn.hidden = true; note.textContent = 'Liberado. O navegador mostra um aviso amarelo "depurando" por alguns segundos quando a IA pede PDF ou a pagina inteira.'; } else note.textContent = 'Nao foi liberado.'; });
});
