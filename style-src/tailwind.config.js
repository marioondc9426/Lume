/* Tailwind do "Visual novo" do Lume.
   As cores NAO sao fixas: apontam para as variaveis de cada tema (--bg-main, --accent...), entao os 7 temas e o editor de temas continuam funcionando.
   Como funciona o app: ele so carrega libs/lume-look.css (ja pronto, offline). Este config so e usado por quem quer REGERAR o CSS: `python build.py`. */
module.exports = {
  content: [],   // nenhuma classe solta e gerada: so o que esta em look.src.css (via @apply)
  corePlugins: { preflight: false },   // nao mexe no reset do app: so entram as regras de look.src.css
  theme: {
    extend: {
      colors: {
        main: 'var(--bg-main)', side: 'var(--bg-sidebar)', field: 'var(--bg-input)', ai: 'var(--bg-msg-ai)', mine: 'var(--bg-msg-user)',
        fg: 'var(--text-main)', mute: 'var(--text-muted)', line: 'var(--border-color)', accent: 'var(--accent)', danger: 'var(--danger)',
        pop: 'var(--lk-pop)', soft: 'var(--lk-soft)',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,.2)',
        lift: '0 12px 30px -12px rgba(0,0,0,.5)',
        pop: '0 24px 60px -14px rgba(0,0,0,.65)',
        glow: '0 6px 16px -8px color-mix(in srgb, var(--accent) 80%, transparent)',
      },
      keyframes: { rise: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'none' } } },
      animation: { rise: 'rise .35s cubic-bezier(.2,.8,.3,1) both' },
    },
  },
};
