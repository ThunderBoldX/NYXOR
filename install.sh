#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$PROJECT_DIR"

echo "🟣 Installing NYXOR..."

pkg install python git -y

if [ -f requirements-termux.txt ]; then
    python -m pip install -r requirements-termux.txt
elif [ -f requirements.txt ]; then
    python -m pip install -r requirements.txt
else
    python -m pip install aiohttp rich textual
fi

mkdir -p data logs runtime locales "$PREFIX/bin"

touch data/.gitkeep logs/.gitkeep runtime/.gitkeep

if [ ! -f nyxor_settings.json ] && [ -f nyxor_settings.example.json ]; then
    cp nyxor_settings.example.json nyxor_settings.json
fi

cat > "$PREFIX/bin/nyxor" <<EOF
#!/data/data/com.termux/files/usr/bin/sh
cd "$PROJECT_DIR" || exit 1
unset NYXOR_LANG
exec python "$PROJECT_DIR/nyxor_app.py" "\$@"
EOF

chmod +x "$PREFIX/bin/nyxor"

find "$PROJECT_DIR" \
    -type d \
    -name '__pycache__' \
    -prune \
    -exec rm -rf {} +

python -m py_compile \
    nyxor_app.py \
    nyxor_worker.py \
    nyxor_core.py \
    $(find nyxor -type f -name '*.py' | sort)

echo
echo "✅ NYXOR installed"
echo
echo "First authentication:"
echo "  cd $PROJECT_DIR"
echo "  python nyxor_auth.py"
echo
echo "Start:"
echo "  nyxor"
