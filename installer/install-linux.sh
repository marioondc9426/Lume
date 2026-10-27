#!/bin/sh
# Instala o Lume no Linux, so para o seu usuario (sem sudo): copia o programa, cria o atalho no menu e o comando "lume".
#   ./install-linux.sh                      baixa o AppImage da ultima versao do GitHub e instala
#   ./install-linux.sh caminho/Lume-linux   instala o arquivo que voce ja tem (AppImage ou binario, inclusive o Lume-linux-owner)
#   ./install-linux.sh --uninstall          remove (suas conversas em ~/.local/share/Lume ficam)
set -eu
DIR="$HOME/.local/opt/lume"; BIN="$HOME/.local/bin"; APPS="$HOME/.local/share/applications"; ICONS="$HOME/.local/share/icons"
REPO="marioondc9426/Lume"

if [ "${1:-}" = "--uninstall" ]; then
  rm -rf "$DIR" "$BIN/lume" "$APPS/lume.desktop" "$ICONS/lume.png"
  echo "Lume removido. Suas conversas e chaves continuam em ~/.local/share/Lume."; exit 0
fi

mkdir -p "$DIR" "$BIN" "$APPS" "$ICONS"
if [ -n "${1:-}" ]; then
  [ -f "$1" ] || { echo "Arquivo nao encontrado: $1"; exit 1; }
  cp "$1" "$DIR/Lume"
else
  echo "Procurando a ultima versao..."
  URL=$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" | grep -o '"browser_download_url": *"[^"]*AppImage"' | head -1 | sed 's/.*"\(http[^"]*\)"/\1/')
  [ -n "$URL" ] || { echo "Nao achei o AppImage na ultima versao. Baixe a mao em https://github.com/$REPO/releases e rode: $0 arquivo"; exit 1; }
  echo "Baixando $URL"; curl -fL --progress-bar -o "$DIR/Lume" "$URL"
fi
chmod +x "$DIR/Lume"

# icone: o que vem ao lado do script (repositorio) ou o do GitHub
if [ -f "$(dirname "$0")/../icons/lume.png" ]; then cp "$(dirname "$0")/../icons/lume.png" "$ICONS/lume.png"
else curl -fsSL -o "$ICONS/lume.png" "https://raw.githubusercontent.com/$REPO/main/icons/lume.png" || true; fi

ln -sf "$DIR/Lume" "$BIN/lume"
cat > "$APPS/lume.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=Lume
Comment=Chat de IA local
Exec=$DIR/Lume
Icon=$ICONS/lume.png
Terminal=false
Categories=Utility;Network;
DESK
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1 || true
echo "Pronto! Abra o Lume pelo menu de aplicativos ou rode: lume"
case ":$PATH:" in *":$BIN:"*) ;; *) echo "(se o comando 'lume' nao for achado, ponha $BIN no seu PATH)";; esac
