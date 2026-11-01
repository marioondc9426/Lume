chrome.runtime.sendMessage({ cmd: 'status' }, r => {
  r = r || {};
  document.getElementById('s').textContent = r.ok ? 'Conectado ao Lume' : 'Lume nao encontrado';
  document.getElementById('d').textContent = r.ok ? 'A IA pode usar as abas quando voce permitir no Lume.' : 'Abra o Lume neste PC (porta 8000 a 8010).';
});
