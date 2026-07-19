#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "🟣 Installing NYXOR v1.0.0..."

pkg install python git -y
python -m pip install --upgrade pip
python -m pip install -r requirements-termux.txt

mkdir -p data logs runtime locales "$PREFIX/bin"
touch data/.gitkeep logs/.gitkeep runtime/.gitkeep

if [ ! -f nyxor_settings.json ]; then
    cp nyxor_settings.example.json nyxor_settings.json
fi

cat > "$PREFIX/bin/nyxor" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
cd "$PROJECT_DIR" || exit 1
unset NYXOR_LANG
exec python "$PROJECT_DIR/nyxor_app.py" "\$@"
EOF
chmod +x "$PREFIX/bin/nyxor"
chmod +x install.sh uninstall.sh

find "$PROJECT_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} +

python -m json.tool locales/uk.json >/dev/null
python -m json.tool locales/en.json >/dev/null
python -m json.tool nyxor_settings.example.json >/dev/null

mapfile -t PYTHON_FILES < <(find "$PROJECT_DIR" -type f -name '*.py' \
    -not -path '*/__pycache__/*' | sort)
python -m py_compile "${PYTHON_FILES[@]}"

echo
echo "✅ NYXOR v1.0.0 installed"
echo
echo "First authentication:"
echo "  cd $PROJECT_DIR"
echo "  python nyxor_auth.py"
echo
echo "Start:"
echo "  nyxor"
